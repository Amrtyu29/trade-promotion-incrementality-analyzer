"""Dense store x product x week panel arrays. Missing cells are NaN (product not sold that week).

Used by did.py and metrics.py so that pre-windows, post-windows and control lookups are
plain numpy slices on the calendar (week_index), not row offsets.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass
class Panel:
    stores: np.ndarray          # sorted unique store_num
    upcs: np.ndarray            # sorted unique upc
    n_weeks: int
    units: np.ndarray           # [S, P, W] float, NaN where unobserved
    hhs: np.ndarray
    promo: np.ndarray           # [S, P, W] bool (False where unobserved)
    observed: np.ndarray        # [S, P, W] bool
    pred_units: np.ndarray | None = None
    pred_hhs: np.ndarray | None = None

    def sidx(self, store):
        return int(np.searchsorted(self.stores, store))

    def pidx(self, upc):
        return int(np.searchsorted(self.upcs, upc))


def build_panel(df: pd.DataFrame, preds: pd.DataFrame | None = None) -> Panel:
    stores = np.sort(df["store_num"].unique())
    upcs = np.sort(df["upc"].unique())
    W = int(df["week_index"].max())
    S, P = len(stores), len(upcs)
    si = np.searchsorted(stores, df["store_num"].to_numpy())
    pi = np.searchsorted(upcs, df["upc"].to_numpy())
    wi = df["week_index"].to_numpy() - 1

    def arr(col, fill=np.nan, dtype=float):
        a = np.full((S, P, W), fill, dtype=dtype)
        a[si, pi, wi] = df[col].to_numpy()
        return a

    pan = Panel(stores, upcs, W, arr("units"), arr("hhs"), arr("is_promo", False, bool), arr("is_promo", False, bool))
    pan.observed[si, pi, wi] = True
    if preds is not None:
        m = df[["store_num", "upc", "week_index"]].merge(preds, on=["store_num", "upc", "week_index"], how="left")
        pu = np.full((S, P, W), np.nan); pu[si, pi, wi] = m["pred_units"].to_numpy()
        ph = np.full((S, P, W), np.nan); ph[si, pi, wi] = m["pred_hhs"].to_numpy()
        pan.pred_units, pan.pred_hhs = pu, ph
    return pan


def clean_pre_stats(pan: Panel, window: int = 8) -> tuple[np.ndarray, np.ndarray]:
    """For every cell (s,p,t): mean and count of NON-promo observed units in weeks t-window..t-1."""
    clean = np.where(pan.observed & ~pan.promo, pan.units, np.nan)
    vals = np.nan_to_num(clean, nan=0.0)
    cnt = (~np.isnan(clean)).astype(float)
    cs_v = np.concatenate([np.zeros(vals.shape[:2] + (1,)), np.cumsum(vals, axis=2)], axis=2)
    cs_c = np.concatenate([np.zeros(cnt.shape[:2] + (1,)), np.cumsum(cnt, axis=2)], axis=2)
    W = pan.n_weeks
    t = np.arange(W)
    lo = np.clip(t - window, 0, W)
    hi = t  # exclusive of t
    sum_v = cs_v[:, :, hi] - cs_v[:, :, lo]
    n = cs_c[:, :, hi] - cs_c[:, :, lo]
    with np.errstate(invalid="ignore", divide="ignore"):
        mean = np.where(n > 0, sum_v / n, np.nan)
    return mean, n


def events_table(df: pd.DataFrame) -> pd.DataFrame:
    """One row per promotion run (consecutive promoted weeks for a store-product)."""
    p = df[df["is_promo"]].sort_values(["store_num", "upc", "week_index"])
    g = p.groupby("promo_run_id", sort=False)
    ev = g.agg(store_num=("store_num", "first"), upc=("upc", "first"), category=("category", "first"),
               description=("description", "first"), t0=("week_index", "min"), t1=("week_index", "max"),
               run_length=("week_index", "size"), promo_type=("promo_type", "first"),
               n_types=("promo_type", "nunique"), discount_depth=("discount_depth", "mean"),
               feature_any=("feature", "max"), display_any=("display", "max"), price_any=("price_cut", "max"),
               actual_units=("units", "sum"), actual_hhs=("hhs", "sum"), actual_visits=("visits", "sum"),
               store_segment=("store_segment", "first"), state=("state", "first"),
               year=("year", "first"), week_of_year=("week_of_year", "first")).reset_index()
    ev = ev.rename(columns={"promo_run_id": "event_id"})
    ev["event_id"] = ev["event_id"].astype("int64")
    ev["promo_type_mixed"] = ev["n_types"] > 1
    return ev
