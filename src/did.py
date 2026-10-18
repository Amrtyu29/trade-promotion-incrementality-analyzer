"""Method B: difference-in-differences per promotion event against same-product control stores.

For event (store s, product p, run t0..t1):
  treated pre-mean   = mean of s's NON-promo observed units in t0-8..t0-1   (need >= MIN_PRE clean weeks)
  controls           = stores c != s with p observed and NOT promoted in every week t0..t1,
                       and with >= MIN_PRE clean pre-weeks in the same pre-window
  DiD per run week w = (units[s,w] - pre_s) - mean_c(units[c,w] - pre_c)
  event estimate     = sum over run weeks
The counterfactual for lift_pct is pre_s + mean_c(units[c,w] - pre_c).

Placebo: identical computation pretending the run started at t0-3 and lasted one week; treated
must be non-promo at that week. Expected ~0 if controls are valid.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .panel import Panel, clean_pre_stats

PRE_WINDOW = 8
MIN_PRE = 4
MIN_CONTROLS = 3


def _did_one(pan, pre_mean, pre_n, s, p, t0, t1):
    """Returns dict or None. t0, t1 are 0-based week indices (inclusive)."""
    if pre_n[s, p, t0] < MIN_PRE:
        return None
    pre_s = pre_mean[s, p, t0]
    weeks = slice(t0, t1 + 1)
    obs = pan.observed[:, p, weeks].all(axis=1)
    nop = ~pan.promo[:, p, weeks].any(axis=1)
    ok = obs & nop & (pre_n[:, p, t0] >= MIN_PRE)
    ok[s] = False
    nc = int(ok.sum())
    if nc < MIN_CONTROLS:
        return {"n_controls": nc}
    ctrl_change = pan.units[ok, p, weeks] - pre_mean[ok, p, t0][:, None]   # [C, L]
    ctrl_mean_change = ctrl_change.mean(axis=0)                              # [L]
    treated = pan.units[s, p, weeks]
    cf = pre_s + ctrl_mean_change
    did = (treated - pre_s) - ctrl_mean_change
    return {"n_controls": nc, "pre_treated": pre_s, "pre_control": float(pre_mean[ok, p, t0].mean()),
            "did_incr": float(did.sum()), "did_counterfactual": float(cf.sum()),
            "ctrl_change_sum": float(ctrl_mean_change.sum())}


def run_did(pan: Panel, ev: pd.DataFrame) -> pd.DataFrame:
    pre_mean, pre_n = clean_pre_stats(pan, PRE_WINDOW)
    rows = []
    for r in ev[["event_id", "store_num", "upc", "t0", "t1"]].itertuples(index=False):
        s, p = pan.sidx(r.store_num), pan.pidx(r.upc)
        t0, t1 = r.t0 - 1, r.t1 - 1
        res = _did_one(pan, pre_mean, pre_n, s, p, t0, t1)
        d = {"event_id": r.event_id, "pre_n": int(pre_n[s, p, t0]), "n_controls": 0}
        if res:
            d.update(res)
        # placebo at t0-3 (one week), treated must be non-promo and observed there
        tp = t0 - 3
        if tp >= PRE_WINDOW and pan.observed[s, p, tp] and not pan.promo[s, p, tp]:
            pr = _did_one(pan, pre_mean, pre_n, s, p, tp, tp)
            if pr and "did_incr" in pr:
                d["placebo_did"] = pr["did_incr"]
                d["placebo_cf"] = pr["did_counterfactual"]
                d["placebo_n_controls"] = pr["n_controls"]
        rows.append(d)
    out = pd.DataFrame(rows)
    out["has_controls"] = out["n_controls"] >= MIN_CONTROLS
    return out


def parallel_trends(pan: Panel, ev: pd.DataFrame, did: pd.DataFrame, max_events: int = 20000, seed: int = 0):
    """Average treated vs control units over the pre-window (t0-8..t0-1), each series normalised by its
    own clean pre-window mean, averaged over events with controls. Returns DataFrame indexed by rel_week."""
    pre_mean, pre_n = clean_pre_stats(pan, PRE_WINDOW)
    use = ev.merge(did[did["has_controls"]][["event_id"]], on="event_id")
    if len(use) > max_events:
        use = use.sample(max_events, random_state=seed)
    rel = np.arange(-PRE_WINDOW, 0)
    T = []; C = []
    for r in use[["store_num", "upc", "t0", "t1"]].itertuples(index=False):
        s, p = pan.sidx(r.store_num), pan.pidx(r.upc)
        t0, t1 = r.t0 - 1, r.t1 - 1
        lo = t0 - PRE_WINDOW
        if lo < 0:
            continue
        weeks = slice(t0, t1 + 1)
        ok = pan.observed[:, p, weeks].all(axis=1) & ~pan.promo[:, p, weeks].any(axis=1) & (pre_n[:, p, t0] >= MIN_PRE)
        ok[s] = False
        tr = np.where(pan.promo[s, p, lo:t0], np.nan, pan.units[s, p, lo:t0]) / pre_mean[s, p, t0]
        cu = np.where(pan.promo[ok, p, lo:t0], np.nan, pan.units[ok, p, lo:t0]) / pre_mean[ok, p, t0][:, None]
        with np.errstate(all="ignore"):
            import warnings
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", RuntimeWarning)
                cm = np.nanmean(cu, axis=0)
        T.append(tr); C.append(cm)
    T = np.array(T); C = np.array(C)
    return pd.DataFrame({"rel_week": rel, "treated": np.nanmean(T, axis=0), "control": np.nanmean(C, axis=0),
                         "treated_se": np.nanstd(T, axis=0) / np.sqrt(np.sum(~np.isnan(T), axis=0)),
                         "control_se": np.nanstd(C, axis=0) / np.sqrt(np.sum(~np.isnan(C), axis=0)),
                         "n_events": np.sum(~np.isnan(T), axis=0)})
