# Phase 0 SQL aggregations (data/processed/promo.db, table promo_weeks)

Queries live in sql/phase0_queries.sql and are executed by scripts/02_phase0_sql.py.

## Promotion counts by store (top 10 by promo share)

```sql
SELECT store_num, store_segment, state,
       COUNT(*)                         AS store_product_weeks,
       SUM(is_promo)                    AS promo_weeks,
       ROUND(1.0 * SUM(is_promo) / COUNT(*), 3) AS promo_share,
       SUM(feature) AS feature_weeks, SUM(display) AS display_weeks, SUM(price_cut) AS price_cut_weeks
FROM promo_weeks
GROUP BY store_num, store_segment, state
ORDER BY promo_share DESC
LIMIT 10;
```

|   store_num | store_segment   | state   |   store_product_weeks |   promo_weeks |   promo_share |   feature_weeks |   display_weeks |   price_cut_weeks |
|------------:|:----------------|:--------|----------------------:|--------------:|--------------:|----------------:|----------------:|------------------:|
|        6179 | UPSCALE         | OH      |                  7804 |          2639 |         0.338 |             535 |            1295 |              2073 |
|       21221 | VALUE           | OH      |                  7140 |          2388 |         0.334 |             531 |             886 |              1945 |
|       19265 | MAINSTREAM      | KY      |                  7611 |          2508 |         0.33  |             543 |            1190 |              2015 |
|       23075 | MAINSTREAM      | OH      |                  7675 |          2525 |         0.329 |             544 |            1220 |              2036 |
|        4245 | MAINSTREAM      | IN      |                  7663 |          2505 |         0.327 |             545 |            1031 |              2125 |
|       13609 | MAINSTREAM      | OH      |                  7815 |          2553 |         0.327 |             547 |            1133 |              2103 |
|       15531 | VALUE           | OH      |                  6925 |          2259 |         0.326 |             531 |             896 |              1963 |
|       28909 | MAINSTREAM      | OH      |                  7848 |          2545 |         0.324 |             553 |            1046 |              2100 |
|       21237 | MAINSTREAM      | OH      |                  7865 |          2535 |         0.322 |             551 |            1210 |              2097 |
|       26981 | MAINSTREAM      | OH      |                  7342 |          2355 |         0.321 |             540 |            1026 |              2123 |

## Promotion share by store segment

```sql
SELECT store_segment, COUNT(DISTINCT store_num) AS stores,
       ROUND(1.0 * SUM(is_promo) / COUNT(*), 3) AS promo_share,
       ROUND(AVG(CASE WHEN is_promo = 1 THEN discount_depth END), 3) AS avg_discount_when_promoted
FROM promo_weeks GROUP BY store_segment ORDER BY promo_share DESC;
```

| store_segment   |   stores |   promo_share |   avg_discount_when_promoted |
|:----------------|---------:|--------------:|-----------------------------:|
| MAINSTREAM      |       43 |         0.288 |                        0.201 |
| VALUE           |       19 |         0.287 |                        0.211 |
| UPSCALE         |       15 |         0.271 |                        0.2   |

## Naive average lift by product (promo mean units / non-promo mean units - 1)

```sql
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
```

|         upc | description               | category              |   promo_weeks |   base_units |   promo_units |   naive_lift_pct |
|------------:|:--------------------------|:----------------------|--------------:|-------------:|--------------:|-----------------:|
|  3800039118 | KELL FROOT LOOPS          | COLD CEREAL           |          3169 |         18.1 |          94.5 |            4.211 |
|  7218063979 | FRSC PEPPERONI PIZZA      | FROZEN PIZZA          |          3088 |          3.8 |          15.7 |            3.163 |
|  3000006340 | QKER LIFE ORIGINAL        | COLD CEREAL           |          3304 |          8.4 |          34.5 |            3.091 |
|  1600027528 | GM CHEERIOS               | COLD CEREAL           |          1422 |         23   |          87.8 |            2.814 |
|  7218063052 | FRSC BRCK OVN ITL PEP PZ  | FROZEN PIZZA          |          3252 |          4.2 |          16.1 |            2.808 |
|  3000006610 | QKER CAP N CRUNCH         | COLD CEREAL           |          3065 |         13.5 |          49.2 |            2.636 |
| 88491212971 | POST FRUITY PEBBLES       | COLD CEREAL           |          2076 |         18.7 |          67.7 |            2.611 |
|  7218063983 | FRSC 4 CHEESE PIZZA       | FROZEN PIZZA          |          2768 |          3.7 |          12.2 |            2.241 |
|  3800031838 | KELL FROSTED FLAKES       | COLD CEREAL           |          2945 |         31.1 |          96.8 |            2.117 |
|  7192100336 | DIGIORNO THREE MEAT       | FROZEN PIZZA          |          4877 |          6.5 |          19.5 |            1.978 |
|  3000006560 | QKER CAP N CRUNCH BERRIES | COLD CEREAL           |          2532 |         22.7 |          63.8 |            1.807 |
|  7192100337 | DIGRN SUPREME PIZZA       | FROZEN PIZZA          |          4872 |          9.4 |          25.8 |            1.755 |
|  1600027527 | GM HONEY NUT CHEERIOS     | COLD CEREAL           |          2741 |         48.1 |         131.1 |            1.724 |
|  7192100339 | DIGRN PEPP PIZZA          | FROZEN PIZZA          |          4886 |         12.9 |          34.5 |            1.675 |
|  2066200532 | NWMN OWN SUPREME PIZZA    | FROZEN PIZZA          |           323 |          4.2 |          10.5 |            1.477 |
|  3700019521 | CREST PH WHTG CLN MINT TP | ORAL HYGIENE PRODUCTS |          4481 |          2.6 |           6.2 |            1.402 |
|  2066200530 | NWMN OWN PEPPERONI PIZZA  | FROZEN PIZZA          |           524 |          5.8 |          13.3 |            1.291 |
|  1111087398 | PL SR CRUST PEPPRN PIZZA  | FROZEN PIZZA          |          3093 |         11.8 |          25.2 |            1.128 |
| 31254742725 | LSTRNE CL MINT ANTSPTC MW | ORAL HYGIENE PRODUCTS |          2614 |          3.3 |           6.8 |            1.099 |
|  3800031829 | KELL BITE SIZE MINI WHEAT | COLD CEREAL           |          2156 |         27.8 |          58.2 |            1.096 |
|  2066200531 | NWMN OWN 4 CHEESE PIZZA   | FROZEN PIZZA          |           402 |          6   |          12.5 |            1.072 |
|  1111087395 | PL SR CRUST SUPRM PIZZA   | FROZEN PIZZA          |          2995 |          9.6 |          19.5 |            1.033 |
|  1111087396 | PL SR CRUST 3 MEAT PIZZA  | FROZEN PIZZA          |          3035 |         10.1 |          19.3 |            0.919 |
|  2840004768 | RLDGLD TINY TWISTS PRTZL  | BAG SNACKS            |          1415 |         12.7 |          24.2 |            0.915 |
|  1111038080 | PL ANTSPTC SPG MNT MTHWS  | ORAL HYGIENE PRODUCTS |          4605 |          4.6 |           8.7 |            0.9   |
| 88491201427 | POST FM SZ HNYBNCH OT ALM | COLD CEREAL           |          1245 |         23.2 |          43.4 |            0.871 |
|  7797502248 | SNYDR PRETZEL RODS        | BAG SNACKS            |          2889 |          8.6 |          15.5 |            0.8   |
| 88491201426 | POST HNY BN OTS HNY RSTD  | COLD CEREAL           |          1178 |         26.2 |          46.7 |            0.785 |
|  1111038078 | PL BL MINT ANTSPTC RINSE  | ORAL HYGIENE PRODUCTS |          4824 |          5.8 |          10.1 |            0.75  |
|  2840004770 | RLDGLD PRETZEL STICKS     | BAG SNACKS            |          1459 |          9.7 |          16.9 |            0.747 |
|  1111009497 | PL PRETZEL STICKS         | BAG SNACKS            |          4356 |         35   |          60.9 |            0.742 |
| 31254742835 | LSTRNE FRS BRST ANTSPC MW | ORAL HYGIENE PRODUCTS |          3591 |          3.8 |           6.4 |            0.676 |
|  7797508006 | SNYDR FF MINI PRETZELS    | BAG SNACKS            |          4645 |          9.5 |          15.6 |            0.641 |
| 31254742735 | LSTRNE CL MINT ANTSPTC MW | ORAL HYGIENE PRODUCTS |          3834 |          4.9 |           7.8 |            0.604 |
|  7797508004 | SNYDR SOURDOUGH NIBBLERS  | BAG SNACKS            |          4421 |         10.6 |          16.9 |            0.603 |
|  1111009507 | PL TWIST PRETZELS         | BAG SNACKS            |          3202 |         19.3 |          30.5 |            0.581 |
|  2840002333 | RLDGLD BRAIDED HONEY WHT  | BAG SNACKS            |          1046 |          8   |          12.4 |            0.552 |
|  1111085350 | PL BT SZ FRSTD SHRD WHT   | COLD CEREAL           |          3462 |         33.8 |          52.3 |            0.551 |
|  1600027564 | GM CHEERIOS               | COLD CEREAL           |          5591 |         34.8 |          52.8 |            0.518 |
|  1111009477 | PL MINI TWIST PRETZELS    | BAG SNACKS            |          4362 |         47.3 |          71.7 |            0.516 |
|  1111085319 | PL HONEY NUT TOASTD OATS  | COLD CEREAL           |          2625 |         20   |          28.5 |            0.423 |
|  3700031613 | SCOPE ORIG MINT MOUTHWASH | ORAL HYGIENE PRODUCTS |          3009 |          3.6 |           5.1 |            0.419 |
|  1111085345 | PL RAISIN BRAN            | COLD CEREAL           |          2705 |         28.5 |          38.6 |            0.354 |
|  3700044982 | CREST PH CLN MINT RINSE   | ORAL HYGIENE PRODUCTS |          4651 |          3.9 |           5.1 |            0.301 |
|  4116709428 | ACT MINT A/CAV FLUOR RNS  | ORAL HYGIENE PRODUCTS |           932 |          2.2 |           2.8 |            0.293 |
|  4116709448 | ACT KIDS BBLGUM FLUOR RNS | ORAL HYGIENE PRODUCTS |           962 |          2.3 |           2.8 |            0.243 |
|  4116709565 | ACT RSTR CL SPLSH MINT MW | ORAL HYGIENE PRODUCTS |          1344 |          2   |           2.4 |            0.157 |
|  7110410455 | MKSL MINI TWIST PRETZELS  | BAG SNACKS            |          1005 |          6.8 |           7.8 |            0.148 |
|  3500068914 | COLG SPEARMINT WISP       | ORAL HYGIENE PRODUCTS |           241 |          1.3 |           1.4 |            0.11  |
|  7110410471 | MKSL PRETZEL STICKS       | BAG SNACKS            |           970 |          5.2 |           5.5 |            0.052 |
|  7110410470 | MKSL DUTCH PRETZELS       | BAG SNACKS            |           978 |          6.5 |           6.8 |            0.043 |
|  1111035398 | PL BL MINT ANTSPTC RINSE  | ORAL HYGIENE PRODUCTS |          1225 |          3.3 |           2.8 |           -0.156 |
|  7027316404 | SHURGD PRETZEL STICKS     | BAG SNACKS            |          2788 |         26.4 |          21.1 |           -0.201 |
|  7027312504 | SHURGD PRETZEL RODS       | BAG SNACKS            |          2492 |         20.5 |          15.9 |           -0.225 |
|  7027316204 | SHURGD MINI PRETZELS      | BAG SNACKS            |          2714 |         28   |          19.7 |           -0.294 |

## Naive average lift by category

```sql
SELECT category,
       ROUND(AVG(CASE WHEN is_promo = 0 THEN units END), 1) AS base_units,
       ROUND(AVG(CASE WHEN is_promo = 1 THEN units END), 1) AS promo_units,
       ROUND(AVG(CASE WHEN is_promo = 1 THEN units END) / AVG(CASE WHEN is_promo = 0 THEN units END) - 1, 3) AS naive_lift_pct
FROM promo_weeks GROUP BY category ORDER BY naive_lift_pct DESC;
```

| category              |   base_units |   promo_units |   naive_lift_pct |
|:----------------------|-------------:|--------------:|-----------------:|
| FROZEN PIZZA          |          7.9 |          21.5 |            1.721 |
| COLD CEREAL           |         25.5 |          62.8 |            1.463 |
| ORAL HYGIENE PRODUCTS |          3.5 |           6.6 |            0.873 |
| BAG SNACKS            |         16.8 |          28.7 |            0.707 |

## Window function: rolling 8-week pre-promo average per store-product (sample rows)

```sql
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
```

|   store_num |         upc |   week_index |   units |   is_promo |   pre8_clean_avg |   pre8_clean_n |   lift_vs_pre8 |
|------------:|------------:|-------------:|--------:|-----------:|-----------------:|---------------:|---------------:|
|         367 | 1.11101e+09 |           15 |      27 |          1 |            11.75 |              8 |          1.298 |
|         367 | 1.11101e+09 |           27 |      15 |          1 |            12.5  |              6 |          0.2   |
|         367 | 1.11101e+09 |           48 |      27 |          1 |            26.25 |              8 |          0.029 |
|         367 | 1.11101e+09 |           98 |      10 |          1 |            16.25 |              8 |         -0.385 |
|         367 | 1.11101e+09 |           15 |       7 |          1 |            15.5  |              8 |         -0.548 |
|         367 | 1.11101e+09 |           27 |      12 |          1 |            13.67 |              6 |         -0.122 |
|         367 | 1.11101e+09 |           48 |      21 |          1 |            18.88 |              8 |          0.113 |
|         367 | 1.11101e+09 |           15 |      10 |          1 |             8.63 |              8 |          0.159 |
|         367 | 1.11101e+09 |           27 |      13 |          1 |            11.83 |              6 |          0.099 |
|         367 | 1.11101e+09 |           48 |      12 |          1 |            18.88 |              8 |         -0.364 |
|         367 | 1.11101e+09 |          120 |      10 |          1 |             9.5  |              8 |          0.053 |
|         367 | 1.11104e+09 |           22 |       1 |          1 |             1    |              5 |          0     |

## Window function: average lift vs rolling pre-promo baseline, by promo type (first week of each run)

```sql
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
```

| promo_type            |   events |   mean_lift_vs_pre8 |   mean_incremental_units |
|:----------------------|---------:|--------------------:|-------------------------:|
| feature+display+price |     9170 |               4.09  |                    55.51 |
| feature+price         |     8338 |               2.445 |                    26.58 |
| display+price         |     2544 |               2.321 |                    23.82 |
| feature+display       |      653 |               2.079 |                    43.81 |
| feature_only          |     1261 |               0.487 |                     9.08 |
| price_only            |    15209 |               0.42  |                     3.38 |
| display_only          |     2672 |               0.301 |                     4.95 |

## Window function: simultaneous promoting stores per product-week (share), ranked

```sql
WITH pw AS (
  SELECT upc, week_index, COUNT(*) AS n_stores, SUM(is_promo) AS n_promo
  FROM promo_weeks GROUP BY upc, week_index)
SELECT upc, week_index, n_stores, n_promo, ROUND(1.0 * n_promo / n_stores, 2) AS share_promo,
       RANK() OVER (PARTITION BY upc ORDER BY n_promo DESC) AS rank_within_product
FROM pw WHERE n_promo > 0
ORDER BY share_promo DESC, upc LIMIT 10;
```

|         upc |   week_index |   n_stores |   n_promo |   share_promo |   rank_within_product |
|------------:|-------------:|-----------:|----------:|--------------:|----------------------:|
| 1.11101e+09 |           48 |         76 |        76 |             1 |                     1 |
| 1.11101e+09 |           52 |         76 |        76 |             1 |                     1 |
| 1.11101e+09 |           48 |         77 |        77 |             1 |                     1 |
| 1.11101e+09 |           49 |         77 |        77 |             1 |                     1 |
| 1.11101e+09 |           52 |         77 |        77 |             1 |                     1 |
| 1.11101e+09 |           48 |         65 |        65 |             1 |                     1 |
| 1.11101e+09 |           52 |         65 |        65 |             1 |                     1 |
| 1.11101e+09 |           49 |         64 |        64 |             1 |                     3 |
| 1.11104e+09 |            2 |         76 |        76 |             1 |                     1 |
| 1.11104e+09 |           16 |         76 |        76 |             1 |                     1 |
