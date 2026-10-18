# Trade Promotion Incrementality: methodology note

Aarshad Rathod, October 2026. Code and every number below are reproducible from `scripts/` in this repository.

## 1. The question

A brand manager funding a retailer's promotion wants to know how many units the promotion *created*, because that is what the trade spend buys. The obvious answer, units in the promoted week minus units in a normal week, misleads twice. Some of those units would have sold anyway, and the "normal week" the comparison uses is usually not the week the retailer would have had without the promotion, because retailers time promotions into strong weeks. This note estimates the counterfactual two independent ways, checks the assumptions each one makes, and then asks whether the in-week number survives the four weeks that follow it.

## 2. Data

dunnhumby "Breakfast at the Frat": 524,950 store x product x week rows, 77 stores in Texas, Ohio, Kentucky and Indiana, 55 UPCs in four categories (bag snacks, cold cereal, frozen pizza, oral hygiene), 156 weeks from January 2009 to January 2012. Each row carries units, purchasing households, visits, spend, shelf price, base price, and three support flags: feature (circular), display, and temporary price reduction. Store lookups give segment and size.

A store-product-week is **promoted** if it has a feature, a display, the TPR flag, or a shelf price more than 5% below base price. That covers 28.5% of rows. Promotions run for 3.0 weeks on average and only 28% last one week, so the unit of analysis is a **promotion run** (consecutive promoted weeks), of which there are 49,384.

What the data does not contain: competitor prices, advertising spend, out-of-stocks, cost of goods, the rest of each category's assortment, and any household-level basket. Two stores appear twice in the store lookup with conflicting segments (first listing kept). 185 base prices and 23 shelf prices are missing and were filled forward within the store-product series.

Phase 0 established three structural facts that shaped the method. Promotion frequency correlates +0.29 with seasonal baseline demand across weeks of the year, so a baseline without seasonality would overstate lift. Features and price cuts are near chain-wide (median 96 to 100% of stores carry them in the same week) while displays are store-specific (median 42%), so control stores exist mainly for display-led events. Base prices drift upward over three years, so a trend term is needed.

## 3. Method

**Method A, ML counterfactual.** A gradient-boosted regression (Poisson loss) is trained only on *clean* non-promo weeks, defined as non-promo weeks more than four weeks after the last promotion. The four-week gap exists because post-promotion weeks are exactly what Section 5 measures; training on them would bake any dip into the baseline and shrink the measured effect. That leaves 234,119 training rows (62% of non-promo weeks). Features: store, product, category, store segment, week-of-year as sine and cosine, a linear week index, base price, store size, store traffic, and the store-product's median clean-week units overall and by quarter. The same design is fitted a second time with purchasing households as the target so that Section 5 can decompose lift against the same counterfactual. Incremental units for an event are actual minus predicted summed over the run's weeks.

Method A assumes that promotion timing is unrelated to demand shocks the features cannot see, and that the feature-to-sales relationship is the same in promoted and unpromoted weeks. The first assumption is the weak one and it is the reason Method B exists.

**Method B, difference-in-differences.** For each run, the treated store's change (units in the run minus its own mean over clean weeks in the eight weeks before) is compared to the same change in control stores: stores selling the same product, not promoting it in any week of the run, with at least four clean pre-weeks. At least three controls are required. The estimate is the treated change minus the mean control change, summed over the run.

Method B assumes parallel trends: absent the promotion, the treated store would have moved like its controls. It does not assume the model got seasonality right, because the controls experience the same season. Its weakness is coverage: 22% of runs (10,798) have valid controls, and those are disproportionately store-specific display events with smaller lifts than the chain-wide feature events.

**Confidence intervals** are bootstrapped by resampling *events* with replacement (1,000 draws), never store-weeks, because the weeks of one event are serially correlated. Lift percentages are ratios of sums (total incremental over total baseline) so a few tiny-baseline events cannot dominate.

## 4. Assumption checks

*Baseline validation.* On a held-out 20% of clean non-promo weeks, Method A's RMSE is 5.27 units against 8.93 for a store-product-week-of-year median and 7.39 for a store-product median; MAPE is 42.5% against 60.5% and 50.2%. Aggregate calibration (actual over predicted) on the holdout is 1.001. Random clean weeks relabelled as "promoted" return a lift of -0.1% (CI -0.6% to +0.3%).

*Parallel trends.* Over the eight pre-weeks, the treated and control series, each indexed to its own clean pre-mean, never diverge by more than 0.013 (figure `outputs/figures/phase1_parallel_trends.png`).

*Placebo.* Running the identical DiD on week t-3 as if it were the promotion week gives -0.01 units/week (CI -0.08 to +0.06) against a real per-week effect of 7.8 units. The share of the counterfactual is -0.1%.

*Hand check.* One display-only event (store 6179, private-label twist pretzels, week 12) was recomputed from the raw clean table in a spreadsheet-style script; Method A, Method B and the post-window all reproduce to the last decimal (`outputs/validation.md`).

## 5. Results

All CIs are 95% event-level bootstrap intervals.

**In-week lift.** Across all 49,384 runs, Method A gives 110.5% lift (CI 108.2 to 113.0), i.e. promoted weeks sell about 2.1 times their counterfactual. On the 10,798 runs where both methods can be computed, Method A gives 39.3% (CI 37.3 to 41.5) and Method B gives 31.0% (CI 28.9 to 33.2). The per-event correlation between the two is 0.83. Method A sits above B by 8 points on every category, consistent with promotions landing in weeks the model slightly under-forecasts. I treat B as the more credible number where it exists and A as the one with coverage; the 8-point gap is the honest band of methodological uncertainty on top of the sampling CI.

**Pull-forward.** On the 25,347 runs followed by four clean non-promo weeks, in-week lift is 117.5% (CI 114.2 to 120.8) and net lift over the run plus four weeks is 120.5% (CI 117.1 to 123.8). The pull-forward ratio, 1 minus net over in-week, is **-2.5% (CI -2.9 to -2.1)**: post-promotion weeks sit slightly *above* baseline, not below it. Subtracting the pre-promotion residual (+0.35 units/week, the sign that promotions land in locally strong weeks) gives an adjusted ratio of +0.1% (CI -0.4 to +0.5). The result holds in all four categories (ratios between -4.0% and -1.5%) and in every promotion type except feature-only events, which show a lasting positive carry-over of 42%. There is no measurable pantry-loading dip at the store-week level in this data. The expected correction to the headline number is therefore not pull-forward; it is the choice of counterfactual (Section 3) and the composition of events (chain-wide feature events lift 2.7 times, store-level price-only events 0.5 times).

**Promotion types.** Lift by type: feature+display+price 274% (CI 267 to 281), feature+price 166%, feature+display 150%, display+price 114%, feature only 64%, price only 47% (CI 45 to 49), display only 46% (CI 41 to 52). Of 21 pairwise Welch t-tests on per-event lift, 18 survive Benjamini-Hochberg at 5%. The three that do not are the three "single lever" comparisons: display alone, feature alone and a price cut alone are statistically indistinguishable at roughly 50% lift. Lift rises monotonically with discount depth from 61% (5 to 15% off) to 333% (over 35% off).

**Penetration versus volume.** Writing ln(units/baseline) = ln(households/baseline households) + ln(units per household/baseline), the households term explains 91% of the log lift on average (median 93%) across the 37,932 runs with log lift above 0.10; 95% of runs are penetration-driven. Promotions in this data bring in more buyers; they do not make existing buyers stock up. That is the mechanism behind the pull-forward result: there is little stock-up to be pulled forward from. Volume-driven runs do show more pull-forward than penetration-driven ones, by +5.5 points (CI -3.7 to +14.3, bootstrap p = 0.23; a Welch test on the per-event ratio gives p = 0.012), and within cold cereal and oral hygiene the volume-driven subgroups reach +10% with CIs that just touch zero. The direction is as the mechanism predicts; the magnitude is small and the sample of volume-driven runs (971 with a clean window) is thin.

**Price elasticity (Phase 3).** Per-product OLS of ln(units) on ln(shelf price) with store and week-of-year fixed effects and feature and display controls, SEs clustered by store: all 55 elasticities are negative, median -1.78, 40 of 55 inside -1 to -4. Frozen pizza is the most price-sensitive category (median -2.79), oral hygiene the least (-1.06). Dropping the feature and display controls moves the median to -2.13, which shows how much "price effect" is really display support riding on the price variable. Price is treated as exogenous conditional on the controls; it is not fully, and with cost or competitor data I would instrument it.

**Allocation (Phase 4).** A 0-1 integer program chooses at most one promotion type per store-product under a weekly budget, maximising incremental gross margin under stated cost assumptions (30% margin, $150 per feature slot, $100 per display, price cuts funded on every unit sold). Solved on point-estimate lift and again on the bootstrap lower bound, the two plans overlap 89% at a $20,000 budget; the risk-averse plan buys 875 cheaper, better-measured promotions instead of 731 and trades 7% of expected volume for a higher guaranteed floor. Return per dollar falls from 1.14 at a $2,000 budget to 0.65 at $80,000, which is the diminishing-returns curve a planner needs.

## 6. Limitations

Cannibalisation is not measured. The data has 55 UPCs but no category totals, so the lift measured here may be partly stolen from other products in the same category, especially for the 12 private-label items. Full category scanner data or household baskets would be needed; I would expect net category lift to be materially below the 110% product-level figure.

Promotion assignment is not random. Retailers promote when they expect demand. Week-of-year features, the DiD cross-check and the placebo test limit this but do not remove it, and the 8-point A-minus-B gap is the visible residue.

Only 22% of events have valid controls, and they are a biased subset (store-specific displays). Method B's 31% is not the lift of an average promotion; it is the lift of a display-type promotion.

Only 51% of events have a clean four-week post window. Pull-forward is measured on runs followed by a promotion gap; back-to-back promotions may behave differently and cannot be measured this way.

Four categories, three years, one retailer. No competitor pricing, no advertising, no distribution or out-of-stock data. The elasticities are reduced-form promotional elasticities, not structural ones.

## 7. What I would do with better data

With category-level scanner data: a nested model of category volume and product share, so that cannibalisation and category expansion separate. With household panel data: measure whether the new households are new to the brand, lapsed, or switchers, and whether penetration gains persist. With competitor prices and out-of-stock flags: add them as controls and, for elasticity, instrument shelf price with wholesale cost changes. With cost per promotion from the retailer: replace the Phase 4 cost assumptions and re-solve the allocation on real numbers.
