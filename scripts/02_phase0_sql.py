"""Phase 0, step 5: load the clean table into SQLite and do the aggregations in SQL.

Creates data/processed/promo.db with table `promo_weeks`, runs the queries in sql/phase0_queries.sql
and writes the results to outputs/phase0_sql.md.
"""
import sqlite3
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.load import build_clean, PROC  # noqa: E402

DB = PROC / "promo.db"
SQL_DIR = ROOT / "sql"
SQL_DIR.mkdir(exist_ok=True)
OUT = ROOT / "outputs" / "phase0_sql.md"

df = build_clean()
df = df.drop(columns=["promo_run_id"])  # float NaN id is not useful in SQL
df["week_end_date"] = df["week_end_date"].dt.strftime("%Y-%m-%d")
for c in ["is_promo", "price_cut", "promo_run_start", "price_imputed", "base_price_imputed"]:
    df[c] = df[c].astype(int)

if DB.exists():
    DB.unlink()
con = sqlite3.connect(DB)
df.to_sql("promo_weeks", con, index=False, chunksize=50_000)
con.execute("CREATE INDEX ix_sp ON promo_weeks(store_num, upc, week_index)")
con.execute("CREATE INDEX ix_pw ON promo_weeks(upc, week_index)")
con.commit()

QUERIES = {
"Promotion counts by store (top 10 by promo share)": """
SELECT store_num, store_segment, state,
       COUNT(*)                         AS store_product_weeks,
       SUM(is_promo)                    AS promo_weeks,
       ROUND(1.0 * SUM(is_promo) / COUNT(*), 3) AS promo_share,
       SUM(feature) AS feature_weeks, SUM(display) AS display_weeks, SUM(price_cut) AS price_cut_weeks
FROM promo_weeks
GROUP BY store_num, store_segment, state
ORDER BY promo_share DESC
LIMIT 10;
""",
"Promotion share by store segment": """
SELECT store_segment, COUNT(DISTINCT store_num) AS stores,
       ROUND(1.0 * SUM(is_promo) / COUNT(*), 3) AS promo_share,
       ROUND(AVG(CASE WHEN is_promo = 1 THEN discount_depth END), 3) AS avg_discount_when_promoted
FROM promo_weeks GROUP BY store_segment ORDER BY promo_share DESC;
""",
"Naive average lift by product (promo mean units / non-promo mean units - 1)": """
WITH p AS (
  SELECT upc, description, category,
         AVG(CASE WHEN is_promo = 1 THEN units END) AS promo_units,
         AVG(CASE WHEN is_promo = 0 THEN units END) AS base_units,
         SUM(is_promo) AS promo_weeks
  FROM promo_weeks GROUP BY upc, description, category)
SELECT upc, description, category, promo_weeks,
       ROUND(base_units, 1) AS base_units, ROUND(promo_units, 1) AS promo_units,
       ROUND(promo_units / base_units - 1, 3) AS naive_lift_pct
FROM p ORDER BY naive_lift_pct DESC;
""",
"Naive average lift by category": """
SELECT category,
       ROUND(AVG(CASE WHEN is_promo = 0 THEN units END), 1) AS base_units,
       ROUND(AVG(CASE WHEN is_promo = 1 THEN units END), 1) AS promo_units,
       ROUND(AVG(CASE WHEN is_promo = 1 THEN units END) / AVG(CASE WHEN is_promo = 0 THEN units END) - 1, 3) AS naive_lift_pct
FROM promo_weeks GROUP BY category ORDER BY naive_lift_pct DESC;
""",
"Window function: rolling 8-week pre-promo average per store-product (sample rows)": """
WITH ordered AS (
  SELECT store_num, upc, week_index, units, is_promo,
         -- units in non-promo weeks only, so the rolling mean is a clean baseline
         CASE WHEN is_promo = 0 THEN units END AS clean_units
  FROM promo_weeks),
rolled AS (
  SELECT store_num, upc, week_index, units, is_promo,
         AVG(clean_units) OVER (
             PARTITION BY store_num, upc ORDER BY week_index
             ROWS BETWEEN 8 PRECEDING AND 1 PRECEDING) AS pre8_clean_avg,
         COUNT(clean_units) OVER (
             PARTITION BY store_num, upc ORDER BY week_index
             ROWS BETWEEN 8 PRECEDING AND 1 PRECEDING) AS pre8_clean_n,
         LAG(is_promo, 1) OVER (PARTITION BY store_num, upc ORDER BY week_index) AS prev_is_promo
  FROM ordered)
SELECT store_num, upc, week_index, units, is_promo, ROUND(pre8_clean_avg, 2) AS pre8_clean_avg, pre8_clean_n,
       ROUND(units / pre8_clean_avg - 1, 3) AS lift_vs_pre8
FROM rolled
WHERE is_promo = 1 AND prev_is_promo = 0 AND pre8_clean_n >= 4
ORDER BY store_num, upc, week_index
LIMIT 12;
""",
"Window function: average lift vs rolling pre-promo baseline, by promo type (first week of each run)": """
WITH ordered AS (
  SELECT store_num, upc, week_index, units, is_promo, promo_type,
         CASE WHEN is_promo = 0 THEN units END AS clean_units
  FROM promo_weeks),
rolled AS (
  SELECT *,
         AVG(clean_units) OVER (PARTITION BY store_num, upc ORDER BY week_index
                                ROWS BETWEEN 8 PRECEDING AND 1 PRECEDING) AS pre8_clean_avg,
         COUNT(clean_units) OVER (PARTITION BY store_num, upc ORDER BY week_index
                                  ROWS BETWEEN 8 PRECEDING AND 1 PRECEDING) AS pre8_clean_n,
         LAG(is_promo, 1) OVER (PARTITION BY store_num, upc ORDER BY week_index) AS prev_is_promo
  FROM ordered)
SELECT promo_type, COUNT(*) AS events,
       ROUND(AVG(units / pre8_clean_avg - 1), 3) AS mean_lift_vs_pre8,
       ROUND(AVG(units - pre8_clean_avg), 2) AS mean_incremental_units
FROM rolled
WHERE is_promo = 1 AND prev_is_promo = 0 AND pre8_clean_n >= 4 AND pre8_clean_avg > 0
GROUP BY promo_type ORDER BY mean_lift_vs_pre8 DESC;
""",
"Window function: simultaneous promoting stores per product-week (share), ranked": """
WITH pw AS (
  SELECT upc, week_index, COUNT(*) AS n_stores, SUM(is_promo) AS n_promo
  FROM promo_weeks GROUP BY upc, week_index)
SELECT upc, week_index, n_stores, n_promo, ROUND(1.0 * n_promo / n_stores, 2) AS share_promo,
       RANK() OVER (PARTITION BY upc ORDER BY n_promo DESC) AS rank_within_product
FROM pw WHERE n_promo > 0
ORDER BY share_promo DESC, upc LIMIT 10;
""",
}

(SQL_DIR / "phase0_queries.sql").write_text(
    "\n\n".join(f"-- {k}\n{v.strip()}" for k, v in QUERIES.items()), encoding="utf-8")

lines = ["# Phase 0 SQL aggregations (data/processed/promo.db, table promo_weeks)\n",
         "Queries live in sql/phase0_queries.sql and are executed by scripts/02_phase0_sql.py.\n"]
for title, q in QUERIES.items():
    res = pd.read_sql_query(q, con)
    if "upc" in res.columns:
        res["upc"] = res["upc"].astype("int64").astype(str)
    lines.append(f"## {title}\n")
    lines.append("```sql\n" + q.strip() + "\n```\n")
    lines.append(res.to_markdown(index=False))
    lines.append("")
con.close()
OUT.write_text("\n".join(lines), encoding="utf-8")
print("\n".join(lines))
