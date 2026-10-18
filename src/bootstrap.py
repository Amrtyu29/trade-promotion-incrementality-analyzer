"""Bootstrap confidence intervals, resampling at the promotion-EVENT level.

Store-weeks inside an event (and the pre/post weeks around it) are serially correlated, so
resampling rows would give intervals that are far too narrow. Each bootstrap draw resamples
whole events with replacement and recomputes the statistic.
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def boot_ci(values: np.ndarray, stat=np.mean, n_boot: int = 1000, seed: int = 0, alpha: float = 0.05):
    """CI for a statistic of a 1-D array of event-level values."""
    v = np.asarray(values, dtype=float)
    v = v[~np.isnan(v)]
    if len(v) == 0:
        return np.nan, np.nan, np.nan, 0
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, len(v), size=(n_boot, len(v)))
    draws = stat(v[idx], axis=1)
    return float(stat(v)), float(np.percentile(draws, 100 * alpha / 2)), float(np.percentile(draws, 100 * (1 - alpha / 2))), len(v)


def boot_ratio_ci(num: np.ndarray, den: np.ndarray, n_boot: int = 1000, seed: int = 0, alpha: float = 0.05):
    """CI for sum(num)/sum(den) over events (e.g. lift% = sum incremental / sum baseline)."""
    num = np.asarray(num, float); den = np.asarray(den, float)
    m = ~(np.isnan(num) | np.isnan(den))
    num, den = num[m], den[m]
    if len(num) == 0:
        return np.nan, np.nan, np.nan, 0
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, len(num), size=(n_boot, len(num)))
    draws = num[idx].sum(axis=1) / den[idx].sum(axis=1)
    return float(num.sum() / den.sum()), float(np.percentile(draws, 100 * alpha / 2)), float(np.percentile(draws, 100 * (1 - alpha / 2))), len(num)


def summarise(ev: pd.DataFrame, incr_col: str, base_col: str, by: list[str] | None = None,
              n_boot: int = 1000, seed: int = 0) -> pd.DataFrame:
    """Mean incremental units per event (with CI) and lift % = sum incr / sum baseline (with CI)."""
    groups = [("ALL", ev)] if not by else list(ev.groupby(by, observed=True))
    rows = []
    for key, g in groups:
        m, lo, hi, n = boot_ci(g[incr_col].to_numpy(), n_boot=n_boot, seed=seed)
        r, rlo, rhi, _ = boot_ratio_ci(g[incr_col].to_numpy(), g[base_col].to_numpy(), n_boot=n_boot, seed=seed)
        d = {"n_events": n, "mean_incr_units": m, "incr_lo": lo, "incr_hi": hi,
             "lift_pct": r, "lift_lo": rlo, "lift_hi": rhi}
        if by:
            key = key if isinstance(key, tuple) else (key,)
            d = {**dict(zip(by, key)), **d}
        else:
            d = {"group": "ALL", **d}
        rows.append(d)
    return pd.DataFrame(rows)
