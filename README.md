# Trade Promotion Incrementality Analyzer

Measures how much of a trade promotion's sales lift is *incremental* — i.e. caused by the
promotion — versus baseline sales that would have happened anyway, plus the volume merely
pulled forward or stolen from other products.

## What it answers

- **Baseline vs. lift**: what would sales have been without the promo?
- **Incremental volume & revenue**: lift net of baseline.
- **ROI**: incremental margin versus total promo spend (discount depth, trade funds, display costs).
- **Cannibalization**: lift on the promoted SKU that came out of sibling SKUs.
- **Pantry loading / post-promo dip**: demand pulled forward from future weeks.

## Planned approach

1. Build a weekly SKU × store (or SKU × retailer) sales panel.
2. Estimate a counterfactual baseline — seasonal-naive / regression with price, seasonality and
   holiday controls, moving to a difference-in-differences or synthetic-control design where
   untreated stores or SKUs are available.
3. Decompose observed lift into incremental, cannibalized and pulled-forward components.
4. Report per-promotion ROI and rank promotions by efficiency.

## Repo layout

```
data/raw/         source sales, promo calendar and cost files (not committed)
data/processed/   cleaned analysis panels
src/              data prep, baseline models, incrementality + ROI calculations
notebooks/        exploration and validation
reports/          figures and written findings
```

## Status

Scaffold only — no data or models yet.
