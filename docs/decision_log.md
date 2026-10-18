# Decision log — Trade Promotion Incrementality Analyzer

Kept daily. Each entry: what I chose, what I rejected, why, what it assumes, what would show it is wrong, and what the AI suggested that I overrode. Entries are written in my words; the AI wrote most of the code.

---

## 2026-10-18  Phase 0 — setup, data, promotion definition

**Decision:**
Use dunnhumby "Breakfast at the Frat" only. Define a promoted store-product-week as feature OR display OR TPR flag OR shelf price more than 5% below base. Treat consecutive promoted weeks as one *event* (a run). Keep the user-guide outliers in.

**Alternatives I rejected:**
- "The Complete Journey": a second project, not an extension.
- One promoted week = one event: 72% of runs are longer than a week, so that double counts and puts a run's later weeks into the "post window" of its first week.
- Dropping outliers: they are real, rare (under 0.5%) and the event-level bootstrap absorbs them.

**Why:**
The pitch is in-week lift versus net lift; that needs long clean weekly series, which this data has (156 weeks).

**What this assumes:**
The 5% price threshold separates real price cuts from base-price noise. Checked: zero TPR-flagged weeks fall under 5%, and median discount is 21%.

**What would show this assumption is wrong:**
A pile-up of weeks with 3 to 5% discounts and no flags. There is not one.

**What the AI suggested that I overrode, and why:**
It first read the workbook with the default header row and got `Unnamed: 0` columns everywhere; every sheet has a title row above the header. I had it read the actual file with `header=1` rather than guess names. It also merged the store lookup without noticing two stores (4503, 17627) are listed twice with different segments, which inflated the row count by 13,693; I kept the first listing.

**Findings that changed the plan:**
- Features and price cuts are near chain-wide (median 96 to 100% of stores); displays are store-specific (median 42%). So controls for Method B will mostly come from display events. Found on day one, as the guide said to.
- Promo frequency correlates +0.29 with seasonal baseline demand. Seasonality must be in the baseline.
- Naive lift by product is *negative* for the three Shurgood pretzel items: the stores that promote them are different stores. Store composition matters; a store feature is not optional.

**Environment notes:**
Python 3.13 venv from miniconda. Git is not installed on this machine; install Git for Windows and commit per phase. PuLP 4.x has a new API and no bundled solver; pinned to 2.9.0.

---

## 2026-10-18  Phase 1 — two baselines

**Decision:**
Method A: HistGradientBoostingRegressor with Poisson loss, trained on *clean* non-promo weeks only (more than 4 weeks after the last promotion). Method B: DiD per run against same-product stores that are non-promo for the whole run and have at least 4 clean pre-weeks, minimum 3 controls. Bootstrap at event level, 1,000 draws. Lift % as ratio of sums.

**Alternatives I rejected:**
- Training on all non-promo weeks. If post-promotion weeks are in the training set the model learns any dip as "normal", and Phase 2 then cannot see it. Costs 38% of non-promo rows; still 234k rows.
- Squared-error loss on raw units: heavy tails and zeros. Poisson fits counts and keeps predictions positive.
- Log target with back-transform: needs a smearing correction and biases sums. Poisson avoids that.
- Mean of per-event lift ratios: dominated by events with tiny baselines. Ratio of sums instead.
- Indexing the parallel-trends plot to t-1 as the guide suggests: t-1 is a single noisy week; indexing to the clean pre-window mean is more stable and tests the same thing.

**Why:**
Two methods that share no assumption. A can cover every event but assumes timing is ignorable; B needs no seasonality model but only works where controls exist.

**What this assumes:**
A: promotion timing is unrelated to demand shocks the features cannot see. B: parallel trends between treated and control stores.

**What would show this assumption is wrong:**
A: positive residuals in the weeks around promotions (the baseline under-forecasts locally). Observed: +0.35 units/week before and +0.34 after. Small but there. B: a non-zero placebo or diverging pre-trends. Observed: placebo -0.01 units/week, pre-trend gap at most 1.3%.

**What the AI suggested that I overrode, and why:**
Its first DiD used every non-promoting store as a control. I required controls to also be clean in the pre-window, because a store that promoted two weeks ago is in its own post-period. Its first validation reported the naive benchmark as NaN because of an index misalignment in a fillna; I had it fix and report both naive benchmarks.

**Which method do I trust, and why:**
On the same 10,798 events A gives 39.3% and B gives 31.0%; correlation 0.83. A is higher everywhere, which is the direction you expect if promotions land in locally strong weeks. I trust B more where it exists, because it does not need the model to get seasonality right. But B's events are display events, which are smaller lifts; B's 31% is not the lift of an average promotion. For the headline I report A with the 8-point A-minus-B gap stated as methodological uncertainty.

---

## 2026-10-18  Phase 2 — stress tests

**Decision:**
Post-window is the 4 weeks after the run ends, *truncated* at the first promoted or unobserved week. Headline pull-forward on the 51% of events with a full clean window. Also report a local-demand-adjusted version (post residual minus pre residual). Decomposition uses a second GBM fitted to households so the identity holds against one counterfactual. Classify as penetration-driven when the households term is at least half the log lift, among events with log lift above 0.10.

**Alternatives I rejected:**
- Excluding only the promoted post-weeks and keeping the ones after them: a week after a new promotion is that promotion's post-week, not ours.
- Using the treated store's own pre-mean as the baseline for the decomposition: then Δln(units) would not equal the Method A lift and the two sections would disagree with each other.
- Forcing a pantry-loading story. The guide expected a trough; the data does not show one.

**What the result is:**
Pull-forward ratio -2.5% (CI -2.9 to -2.1); adjusted +0.1% (CI -0.4 to +0.5). No dip in any category. Feature-only events show a +42% carry-over (post-weeks keep selling). 91% of log lift is more households; 95% of events are penetration-driven. Volume-driven events show +5.5 points more pull-forward (CI crosses zero; Welch p = 0.012 on the per-event ratio). Deeper discounts lift more, monotonically. 18 of 21 promo-type pairs differ after BH; display alone, feature alone and price alone do not differ from each other.

**What this assumes:**
That the baseline is right in the post-weeks. The pre-window residual (+0.35) is my check on that; even subtracting it there is no dip.

**What would show this is wrong:**
Pantry loading that lasts longer than 4 weeks (cereal boxes last a month). I cannot see past 4 weeks without running into the next promotion for most events. Or stock-up happening at the household level while new households replace it at the store level; that needs panel data.

**What the AI suggested that I overrode, and why:**
It wrote "the pantry-loading dip is visible" as a template sentence before the number existed. I made every such sentence conditional on the sign of the number. Honest reporting means the text follows the data.

---

## 2026-10-18  Phase 3 and 4 — elasticity and allocation

**Decision:**
Elasticity per product by separate OLS with store and week-of-year fixed effects, feature and display controls, SEs clustered by store; report the same regression without promo controls alongside. Allocation as a 0-1 integer program per store-product-type, solved on point lift and on the bootstrap lower bound, over a budget grid; cost parameters explicit and adjustable in the app.

**Alternatives I rejected:**
- One pooled regression with product interactions: 525k rows times 200 dummies is slow and gives the same per-product slopes.
- Letting the app re-solve on every slider move by default: 5 to 10 s per solve. Precomputed grid plus an explicit "solve with my parameters" button.

**Result:**
55 of 55 elasticities negative, median -1.78, 40 in -1 to -4; dropping promo controls moves the median to -2.13. Allocation plans overlap 89% between point and risk-averse at $20k; ROI falls from 1.14 to 0.65 across the budget grid.

**What this assumes:**
Price exogenous conditional on controls (it is not fully); the cost assumptions in Phase 4 are placeholders until a retailer supplies real ones.

**What would show this is wrong:**
A positive elasticity (none), or an allocation that changes completely when costs move by 20% (it should move, but not flip; the app lets you check).

**What the AI suggested that I overrode, and why:**
Nothing material here; I set the cost and margin parameters.
