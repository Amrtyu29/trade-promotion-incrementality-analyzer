"""Phase 4: promotion allocation under a trade budget (0-1 integer program, PuLP/CBC).

Decision  x[s,p,type] in {0,1}: run promotion `type` for product p in store s for one week.
Objective maximise sum incremental_margin[s,p,type] * x
Constraints sum cost[s,p,type] * x <= budget ;  sum_type x[s,p,type] <= 1 for each (s,p)

Inputs are built from the Phase 1/2 event table:
  lift[p,type] (and its bootstrap lower bound)  = sum incremental / sum baseline over that product-type's events
  baseline[s,p]                                 = store-product median weekly units in clean non-promo weeks
  expected incremental units = lift * baseline ; incremental margin = incremental units * price * margin_rate
Cost model (all parameters, see Assumptions):
  feature:  fixed cost per store-week (circular slot)
  display:  fixed cost per store-week (shelf space / labour)
  price:    discount_depth * price * (baseline + incremental units)  -- markdown funded on every unit sold
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd
import pulp

from .bootstrap import boot_ratio_ci


@dataclass
class Assumptions:
    margin_rate: float = 0.30          # gross margin as a share of shelf price
    cost_feature: float = 150.0        # $ per store-week for a circular slot
    cost_display: float = 100.0        # $ per store-week for a display
    discount_by_type: dict = field(default_factory=dict)  # mean discount depth per type, filled from data
    min_events: int = 30               # product-type cells with fewer events fall back to the category-type lift


def build_candidates(ev: pd.DataFrame, df: pd.DataFrame, a: Assumptions, n_boot: int = 500) -> pd.DataFrame:
    """One row per (store, product, promo_type) with expected incremental units, CI lower bound, cost."""
    # lift per product-type with CI, fallback to category-type
    rows = []
    for (upc, t), g in ev.groupby(["upc", "promo_type"]):
        if len(g) >= a.min_events:
            r, lo, hi, n = boot_ratio_ci(g.incr_A.to_numpy(), g.baseline_units.to_numpy(), n_boot=n_boot, seed=1)
            rows.append({"upc": upc, "promo_type": t, "lift": r, "lift_lo": lo, "lift_hi": hi, "n_events": n, "level": "product"})
    lp = pd.DataFrame(rows)
    rows = []
    for (c, t), g in ev.groupby(["category", "promo_type"]):
        r, lo, hi, n = boot_ratio_ci(g.incr_A.to_numpy(), g.baseline_units.to_numpy(), n_boot=n_boot, seed=1)
        rows.append({"category": c, "promo_type": t, "lift_c": r, "lift_lo_c": lo, "lift_hi_c": hi, "n_events_c": n})
    lc = pd.DataFrame(rows)
    disc = ev.groupby("promo_type").discount_depth.mean().to_dict()
    a.discount_by_type = {t: (d if "price" in t else 0.0) for t, d in disc.items()}

    # store-product baseline (clean weeks) and typical price
    clean = df[(~df.is_promo) & (df.weeks_since_promo.isna() | (df.weeks_since_promo > 4))]
    sp = clean.groupby(["store_num", "upc"]).agg(baseline=("units", "median"), price=("base_price", "median"),
                                                  category=("category", "first"), description=("description", "first")).reset_index()
    sp = sp[sp.baseline > 0]
    types = sorted(ev.promo_type.unique())
    cand = sp.merge(pd.DataFrame({"promo_type": types}), how="cross")
    cand = cand.merge(lp, on=["upc", "promo_type"], how="left").merge(lc, on=["category", "promo_type"], how="left")
    cand["lift_used"] = cand.lift.fillna(cand.lift_c); cand["lift_lo_used"] = cand.lift_lo.fillna(cand.lift_lo_c)
    cand["level"] = cand.level.fillna("category")
    cand["incr_units"] = cand.lift_used * cand.baseline
    cand["incr_units_lo"] = cand.lift_lo_used * cand.baseline
    cand["incr_margin"] = cand.incr_units * cand.price * a.margin_rate
    cand["incr_margin_lo"] = cand.incr_units_lo * cand.price * a.margin_rate
    cand["discount"] = cand.promo_type.map(a.discount_by_type)
    cand["cost"] = (cand.promo_type.str.contains("feature") * a.cost_feature + cand.promo_type.str.contains("display") * a.cost_display
                    + cand.discount * cand.price * (cand.baseline + cand.incr_units))
    # drop dominated / useless candidates
    cand = cand[(cand.incr_margin > 0) & (cand.cost > 0)].reset_index(drop=True)
    return cand


def solve(cand: pd.DataFrame, budget: float, objective: str = "incr_margin", time_limit: int = 60) -> pd.DataFrame:
    """Return the chosen rows of `cand` for the given budget, maximising `objective` ('incr_margin' or 'incr_margin_lo')."""
    c = cand[cand[objective] > 0].reset_index(drop=True)
    prob = pulp.LpProblem("promo_allocation", pulp.LpMaximize)
    x = [pulp.LpVariable(f"x_{i}", cat="Binary") for i in range(len(c))]
    obj = c[objective].to_numpy(); cost = c["cost"].to_numpy()
    prob += pulp.lpSum(obj[i] * x[i] for i in range(len(c)))
    prob += pulp.lpSum(cost[i] * x[i] for i in range(len(c))) <= budget
    for _, idx in c.groupby(["store_num", "upc"]).indices.items():
        if len(idx) > 1:
            prob += pulp.lpSum(x[i] for i in idx) <= 1
    prob.solve(pulp.PULP_CBC_CMD(msg=False, timeLimit=time_limit, gapRel=0.002))
    chosen = c[[v.value() is not None and v.value() > 0.5 for v in x]].copy()
    chosen["objective"] = objective
    chosen["status"] = pulp.LpStatus[prob.status]
    return chosen


def summarise_solution(chosen: pd.DataFrame) -> dict:
    return {"n_promos": int(len(chosen)), "spend": float(chosen.cost.sum()),
            "incr_units": float(chosen.incr_units.sum()), "incr_units_lo": float(chosen.incr_units_lo.sum()),
            "incr_margin": float(chosen.incr_margin.sum()), "incr_margin_lo": float(chosen.incr_margin_lo.sum()),
            "mix": chosen.promo_type.value_counts().to_dict(),
            "by_category": chosen.groupby("category").incr_units.sum().round(0).to_dict()}
