"""Method A: ML counterfactual baseline trained on non-promotion weeks.

Two targets are modelled with the same design: `units` and `hhs` (purchasing households).
The second one exists so that Phase 2c can decompose log lift into a households component
and a units-per-household component against the SAME counterfactual.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.model_selection import train_test_split

CAT_FEATURES = ["store_num", "upc", "category", "store_segment"]
NUM_FEATURES = ["week_index", "woy_sin", "woy_cos", "base_price", "sp_median", "sp_median_q",
                "store_sqft", "avg_weekly_baskets"]
FEATURES = CAT_FEATURES + NUM_FEATURES


def training_mask(df: pd.DataFrame, clean_gap: int = 4) -> pd.Series:
    """Non-promo weeks that are also at least `clean_gap` weeks after the last promotion.

    Why: weeks just after a promotion carry the pantry-loading dip that Phase 2 wants to measure.
    If they are in the training set the model learns a slightly depressed baseline and the
    measured dip shrinks toward zero. Excluding them keeps the baseline a true 'undisturbed' week.
    weeks_since_promo is NaN before the first promotion of a series -> treated as clean.
    """
    since = df["weeks_since_promo"]
    return (~df["is_promo"]) & (since.isna() | (since > clean_gap))


def add_features(df: pd.DataFrame, train_mask: pd.Series) -> pd.DataFrame:
    """Add model features. Store-product medians are computed from training rows only."""
    out = df.copy()
    ang = 2 * np.pi * out["week_of_year"] / 52.18
    out["woy_sin"], out["woy_cos"] = np.sin(ang), np.cos(ang)
    out["quarter"] = ((out["week_of_year"] - 1) // 13).clip(0, 3)
    tr = out[train_mask]
    med = tr.groupby(["store_num", "upc"])["units"].median().rename("sp_median")
    medq = tr.groupby(["store_num", "upc", "quarter"])["units"].median().rename("sp_median_q")
    out = out.merge(med, on=["store_num", "upc"], how="left")
    out = out.merge(medq, on=["store_num", "upc", "quarter"], how="left")
    out["sp_median_q"] = out["sp_median_q"].fillna(out["sp_median"])
    out["sp_median"] = out["sp_median"].fillna(out.groupby("upc")["sp_median"].transform("median"))
    out["sp_median_q"] = out["sp_median_q"].fillna(out["sp_median"])
    for c in CAT_FEATURES:
        out[c] = out[c].astype("category")
    return out


def _model(seed: int) -> HistGradientBoostingRegressor:
    return HistGradientBoostingRegressor(
        loss="poisson", max_iter=600, learning_rate=0.05, max_leaf_nodes=63,
        min_samples_leaf=40, l2_regularization=1.0, categorical_features="from_dtype",
        random_state=seed, early_stopping=True, validation_fraction=0.1, n_iter_no_change=30)


@dataclass
class Validation:
    target: str
    n_train: int
    n_holdout: int
    rmse_model: float
    mape_model: float
    rmse_naive: float
    mape_naive: float
    rmse_naive_sp: float
    mape_naive_sp: float
    calibration: float  # sum(actual)/sum(predicted) on the holdout; 1.0 = unbiased in aggregate

    def as_dict(self):
        return self.__dict__.copy()


def _mape(y, yhat):
    m = y > 0
    return float(np.mean(np.abs(y[m] - yhat[m]) / y[m]))


def _rmse(y, yhat):
    return float(np.sqrt(np.mean((y - yhat) ** 2)))


def naive_prediction(train: pd.DataFrame, test: pd.DataFrame, target: str) -> tuple[np.ndarray, np.ndarray]:
    """Naive benchmark 1: store-product-week_of_year median from the training rows.
    Naive benchmark 2: store-product median (no seasonality)."""
    m1 = train.groupby(["store_num", "upc", "week_of_year"], observed=True)[target].median().rename("n1")
    m2 = train.groupby(["store_num", "upc"], observed=True)[target].median().rename("n2")
    t = test[["store_num", "upc", "week_of_year"]].merge(m1, how="left", left_on=["store_num", "upc", "week_of_year"], right_index=True)
    t = t.merge(m2, how="left", left_on=["store_num", "upc"], right_index=True)
    n2 = t["n2"].fillna(train[target].median()).to_numpy(dtype=float)
    n1 = t["n1"].to_numpy(dtype=float)
    n1 = np.where(np.isnan(n1), n2, n1)
    return n1, n2


def fit_and_validate(feat: pd.DataFrame, train_mask: pd.Series, target: str, seed: int = 42):
    """Hold out 20% of clean non-promo rows, report RMSE/MAPE for model and two naive benchmarks,
    then refit on all clean rows and return (model, Validation)."""
    tr_all = feat[train_mask]
    tr, ho = train_test_split(tr_all, test_size=0.2, random_state=seed)
    mdl = _model(seed).fit(tr[FEATURES], tr[target])
    yhat = mdl.predict(ho[FEATURES])
    n1, n2 = naive_prediction(tr, ho, target)
    y = ho[target].to_numpy(dtype=float)
    val = Validation(target, len(tr), len(ho), _rmse(y, yhat), _mape(y, yhat),
                     _rmse(y, n1), _mape(y, n1), _rmse(y, n2), _mape(y, n2), float(y.sum() / yhat.sum()))
    full = _model(seed).fit(tr_all[FEATURES], tr_all[target])
    return full, val


def predict_all(feat: pd.DataFrame, models: dict) -> pd.DataFrame:
    """Counterfactual predictions for every row (promo and non-promo)."""
    out = feat[["store_num", "upc", "week_index"]].copy()
    for target, mdl in models.items():
        out[f"pred_{target}"] = np.clip(mdl.predict(feat[FEATURES]), 1e-6, None)
    out["store_num"] = out["store_num"].astype("int64")
    out["upc"] = out["upc"].astype("int64")
    return out
