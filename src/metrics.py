"""Phase 2 metrics: pull-forward, event study, promo-type tests, penetration/volume decomposition."""
from __future__ import annotations

from itertools import combinations

import numpy as np
import pandas as pd
from scipy import stats
from statsmodels.stats.multitest import multipletests

from .panel import Panel

POST_WEEKS = 4
PRE_WEEKS = 4


def post_and_pre_windows(pan: Panel, ev: pd.DataFrame) -> pd.DataFrame:
    """Per event: incremental units (actual - Method A prediction) for the 4 weeks after the run and the
    4 weeks before it. A post-week is usable only if it is observed and NOT promoted; the post window is
    TRUNCATED at the first promoted or unobserved week (weeks after a new promotion are contaminated by it).
    Pre-weeks that are promoted are set to NaN (they belong to an earlier event)."""
    rows = []
    for r in ev[["event_id", "store_num", "upc", "t0", "t1"]].itertuples(index=False):
        s, p = pan.sidx(r.store_num), pan.pidx(r.upc)
        t0, t1 = r.t0 - 1, r.t1 - 1
        d = {"event_id": r.event_id}
        # post window
        n_clean = 0; post_sum = 0.0; post_base = 0.0
        for k in range(1, POST_WEEKS + 1):
            w = t1 + k
            if w >= pan.n_weeks or not pan.observed[s, p, w] or pan.promo[s, p, w]:
                break
            inc = pan.units[s, p, w] - pan.pred_units[s, p, w]
            d[f"post_{k}"] = inc
            post_sum += inc; post_base += pan.pred_units[s, p, w]; n_clean += 1
        d["n_post_clean"] = n_clean
        d["post_incr"] = post_sum if n_clean > 0 else np.nan
        d["post_baseline"] = post_base if n_clean > 0 else np.nan
        # pre window (for the event-study picture only)
        for k in range(1, PRE_WEEKS + 1):
            w = t0 - k
            if w < 0 or not pan.observed[s, p, w] or pan.promo[s, p, w]:
                continue
            d[f"pre_{k}"] = pan.units[s, p, w] - pan.pred_units[s, p, w]
        rows.append(d)
    out = pd.DataFrame(rows)
    for k in range(1, POST_WEEKS + 1):
        out[f"post_{k}"] = out.get(f"post_{k}", np.nan)
    for k in range(1, PRE_WEEKS + 1):
        out[f"pre_{k}"] = out.get(f"pre_{k}", np.nan)
    return out


def pullforward_summary(ev: pd.DataFrame, n_boot: int = 1000, seed: int = 0) -> dict:
    """Headline numbers on events with a full clean 4-week post window.
    pullforward_ratio = 1 - net / in_week, computed on sums over events, bootstrapped at event level."""
    g = ev[ev["n_post_clean"] == POST_WEEKS]
    inw = g["incr_A"].to_numpy(); post = g["post_incr"].to_numpy(); base = g["baseline_units"].to_numpy()
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, len(g), size=(n_boot, len(g)))
    net_draw = (inw[idx] + post[idx]).sum(axis=1)
    inw_draw = inw[idx].sum(axis=1)
    ratio_draw = 1 - net_draw / inw_draw
    lift_in_draw = inw_draw / base[idx].sum(axis=1)
    lift_net_draw = net_draw / base[idx].sum(axis=1)
    return {
        "n_events": int(len(g)),
        "in_week_incr_mean": float(inw.mean()), "post_incr_mean": float(post.mean()),
        "net_incr_mean": float((inw + post).mean()),
        "in_week_lift_pct": float(inw.sum() / base.sum()),
        "in_week_lift_lo": float(np.percentile(lift_in_draw, 2.5)), "in_week_lift_hi": float(np.percentile(lift_in_draw, 97.5)),
        "net_lift_pct": float((inw + post).sum() / base.sum()),
        "net_lift_lo": float(np.percentile(lift_net_draw, 2.5)), "net_lift_hi": float(np.percentile(lift_net_draw, 97.5)),
        "pullforward_ratio": float(1 - (inw + post).sum() / inw.sum()),
        "pullforward_lo": float(np.percentile(ratio_draw, 2.5)), "pullforward_hi": float(np.percentile(ratio_draw, 97.5)),
    }


def event_study(ev: pd.DataFrame, n_boot: int = 500, seed: int = 0) -> pd.DataFrame:
    """Mean incremental units per relative week with bootstrap CI. 'run' = per-week average inside the run."""
    cols = [(f"pre_{k}", -k) for k in range(PRE_WEEKS, 0, -1)] + [("incr_A_per_week", 0)] + [(f"post_{k}", k) for k in range(1, POST_WEEKS + 1)]
    rng = np.random.default_rng(seed)
    rows = []
    for col, rel in cols:
        v = ev[col].dropna().to_numpy()
        if len(v) == 0:
            continue
        idx = rng.integers(0, len(v), size=(n_boot, len(v)))
        draws = v[idx].mean(axis=1)
        rows.append({"rel_week": rel, "mean_incr": v.mean(), "lo": np.percentile(draws, 2.5), "hi": np.percentile(draws, 97.5),
                     "median_incr": np.median(v), "n": len(v)})
    return pd.DataFrame(rows)


def promo_type_tests(ev: pd.DataFrame, value_col: str = "lift_A_pct", min_n: int = 100) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Per-type summary and all pairwise Welch t-tests with Benjamini-Hochberg correction."""
    types = [t for t, g in ev.groupby("promo_type") if len(g) >= min_n]
    summ = ev[ev.promo_type.isin(types)].groupby("promo_type")[value_col].agg(["count", "mean", "std", "median"]).reset_index()
    rows = []
    for a, b in combinations(types, 2):
        x = ev.loc[ev.promo_type == a, value_col].dropna(); y = ev.loc[ev.promo_type == b, value_col].dropna()
        t, pval = stats.ttest_ind(x, y, equal_var=False)
        rows.append({"type_a": a, "type_b": b, "mean_a": x.mean(), "mean_b": y.mean(), "diff": x.mean() - y.mean(),
                     "t_welch": t, "p_raw": pval})
    pw = pd.DataFrame(rows)
    pw["p_bh"] = multipletests(pw["p_raw"], method="fdr_bh")[1]
    pw["significant_bh_05"] = pw["p_bh"] < 0.05
    return summ, pw.sort_values("p_bh")


def decomposition(ev: pd.DataFrame, min_log_lift: float = 0.10) -> pd.DataFrame:
    """ln(actual/baseline) for units = households component + units-per-household component.
    Classify events with meaningful lift (log lift > min_log_lift) as penetration- or volume-driven."""
    out = ev.copy()
    out["dln_units"] = np.log(out["actual_units"] / out["baseline_units"])
    out["dln_hhs"] = np.log(out["actual_hhs"] / out["baseline_hhs"])
    out["dln_uph"] = out["dln_units"] - out["dln_hhs"]
    out["pen_share"] = out["dln_hhs"] / out["dln_units"]
    out["driver"] = np.where(out["dln_units"] <= min_log_lift, "no_lift",
                             np.where(out["pen_share"] >= 0.5, "penetration", "volume"))
    return out


def compare_pullforward(ev: pd.DataFrame, group_col: str, groups: list[str], n_boot: int = 1000, seed: int = 0) -> pd.DataFrame:
    """Pull-forward ratio per group (events with full clean post window) with bootstrap CI,
    plus a bootstrap CI on the difference between the first two groups."""
    g = ev[ev["n_post_clean"] == POST_WEEKS]
    rng = np.random.default_rng(seed)
    rows, draws = [], {}
    for name in groups:
        s = g[g[group_col] == name]
        if len(s) == 0:
            continue
        inw = s["incr_A"].to_numpy(); post = s["post_incr"].to_numpy()
        idx = rng.integers(0, len(s), size=(n_boot, len(s)))
        d = 1 - (inw[idx] + post[idx]).sum(axis=1) / inw[idx].sum(axis=1)
        draws[name] = d
        rows.append({group_col: name, "n_events": len(s), "in_week_incr_mean": inw.mean(), "post_incr_mean": post.mean(),
                     "pullforward_ratio": 1 - (inw + post).sum() / inw.sum(),
                     "lo": np.percentile(d, 2.5), "hi": np.percentile(d, 97.5)})
    res = pd.DataFrame(rows)
    if len(groups) >= 2 and all(x in draws for x in groups[:2]):
        diff = draws[groups[0]] - draws[groups[1]]
        res.attrs["diff"] = {"a": groups[0], "b": groups[1], "diff": float(res.pullforward_ratio.iloc[0] - res.pullforward_ratio.iloc[1]),
                             "lo": float(np.percentile(diff, 2.5)), "hi": float(np.percentile(diff, 97.5)),
                             "p_boot": float(2 * min((diff <= 0).mean(), (diff >= 0).mean()))}
    return res
