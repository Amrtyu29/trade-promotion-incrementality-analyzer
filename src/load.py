"""raw -> clean store x product x week table.

Column names come from the actual workbook (verified in scripts/00_profile_raw.py):
transactions: WEEK_END_DATE, STORE_NUM, UPC, UNITS, VISITS, HHS, SPEND, PRICE, BASE_PRICE,
              FEATURE, DISPLAY, TPR_ONLY
products:     UPC, DESCRIPTION, MANUFACTURER, CATEGORY, SUB_CATEGORY, PRODUCT_SIZE
stores:       STORE_ID, STORE_NAME, ADDRESS_CITY_NAME, ADDRESS_STATE_PROV_CODE, MSA_CODE,
              SEG_VALUE_NAME, PARKING_SPACE_QTY, SALES_AREA_SIZE_NUM, AVG_WEEKLY_BASKETS
Every sheet has a one-line title above the header row, hence header=1.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / "data" / "raw" / "extracted" / "dunnhumby_Breakfast-at-the-Frat"
PROC = ROOT / "data" / "processed"
PROC.mkdir(parents=True, exist_ok=True)

# --- promotion definition (Phase 0, step 3) --------------------------------------
# A store-product-week is PROMOTED if a feature (circular) is present, OR a display is
# present, OR the shelf price is more than 5% below base price (a TPR). TPR_ONLY is the
# retailer's own "price cut without support" flag and is treated as a price cut too.
PRICE_CUT_THRESHOLD = 0.05


def _read_sheet(name: str) -> pd.DataFrame:
    xlsx = next(RAW_DIR.glob("*.xlsx"))
    df = pd.read_excel(xlsx, sheet_name=name, header=1)
    df.columns = [str(c).strip().lower() for c in df.columns]
    return df


def load_raw(force: bool = False) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Return (transactions, products, stores) with lower-case headers. Cached as parquet."""
    paths = {k: PROC / f"raw_{k}.parquet" for k in ("transactions", "products", "stores")}
    if not force and all(p.exists() for p in paths.values()):
        return tuple(pd.read_parquet(p) for p in paths.values())
    tx = _read_sheet("dh Transaction Data")
    prod = _read_sheet("dh Products Lookup")
    stores = _read_sheet("dh Store Lookup")
    tx["week_end_date"] = pd.to_datetime(tx["week_end_date"])
    for c in ["store_num", "upc", "units", "visits", "hhs", "feature", "display", "tpr_only"]:
        tx[c] = pd.to_numeric(tx[c]).astype("int64")
    for c in ["spend", "price", "base_price"]:
        tx[c] = pd.to_numeric(tx[c], errors="coerce").astype("float64")
    prod["upc"] = prod["upc"].astype("int64")
    stores = stores.rename(columns={"store_id": "store_num"})
    stores["store_num"] = stores["store_num"].astype("int64")
    # stores 4503 and 17627 appear twice with different segments; keep the first listing
    stores = stores.drop_duplicates(subset="store_num", keep="first")
    for k, df in zip(paths, (tx, prod, stores)):
        df.to_parquet(paths[k], index=False)
    return tx, prod, stores


def build_clean(force: bool = False) -> pd.DataFrame:
    """Clean store x product x week table (Phase 0, step 4). Saved to data/processed/clean.parquet."""
    out = PROC / "clean.parquet"
    if out.exists() and not force:
        return pd.read_parquet(out)

    tx, prod, stores = load_raw()
    df = tx.copy()

    # --- de-duplicate the grain
    df = df.drop_duplicates(subset=["store_num", "upc", "week_end_date"])

    # --- week index 1..156 and calendar features
    first = df["week_end_date"].min()
    df["week_index"] = ((df["week_end_date"] - first).dt.days // 7 + 1).astype("int64")
    df["week_of_year"] = df["week_end_date"].dt.isocalendar().week.astype("int64")
    df["year"] = df["week_end_date"].dt.year.astype("int64")

    # --- price repair. base_price has 185 nulls, price has 23. Fill base_price with the
    #     store-product's most recent known base price (ffill then bfill), price with base_price.
    df = df.sort_values(["store_num", "upc", "week_index"])
    g = df.groupby(["store_num", "upc"], sort=False)
    df["base_price_imputed"] = df["base_price"].isna()
    df["base_price"] = g["base_price"].ffill()
    df["base_price"] = df.groupby(["store_num", "upc"], sort=False)["base_price"].bfill()
    df["price_imputed"] = df["price"].isna()
    df["price"] = df["price"].fillna(df["base_price"])
    # a handful of rows have base_price == 0 or price > base_price (base price lagging a
    # permanent price rise). Clip the discount at 0 and treat base<=0 as missing.
    df.loc[df["base_price"] <= 0, "base_price"] = np.nan
    df["base_price"] = df["base_price"].fillna(df["price"])

    # --- discount depth and promotion definition
    df["discount_depth"] = ((df["base_price"] - df["price"]) / df["base_price"]).clip(lower=0)
    df["price_cut"] = (df["discount_depth"] > PRICE_CUT_THRESHOLD) | (df["tpr_only"] == 1)
    df["is_promo"] = df["price_cut"] | (df["feature"] == 1) | (df["display"] == 1)

    def _ptype(r):
        parts = []
        if r.feature == 1:
            parts.append("feature")
        if r.display == 1:
            parts.append("display")
        if r.price_cut:
            parts.append("price")
        if not parts:
            return "none"
        return "+".join(parts) if len(parts) > 1 else parts[0] + "_only"

    flags = df[["feature", "display", "price_cut"]].drop_duplicates()
    flags["promo_type"] = flags.apply(_ptype, axis=1)
    df = df.merge(flags, on=["feature", "display", "price_cut"], how="left")

    # --- weeks since / until the nearest OTHER promoted week for this store-product.
    #     Computed on the calendar (week_index), not on row position, because series have gaps.
    df = df.sort_values(["store_num", "upc", "week_index"]).reset_index(drop=True)
    df["_promo_week"] = df["week_index"].where(df["is_promo"]).astype("float64")
    g = df.groupby(["store_num", "upc"], sort=False)
    last_promo_before = g["_promo_week"].transform(lambda s: s.shift(1).ffill())
    next_promo_after = g["_promo_week"].transform(lambda s: s.shift(-1).bfill())
    df["weeks_since_promo"] = df["week_index"] - last_promo_before
    df["weeks_until_promo"] = next_promo_after - df["week_index"]
    df = df.drop(columns="_promo_week")

    # --- promotion runs: consecutive promoted calendar weeks form one run
    prev_promo = g["is_promo"].shift(1).fillna(False).astype(bool)
    prev_week = g["week_index"].shift(1)
    run_start = df["is_promo"] & ~(prev_promo & (df["week_index"] - prev_week == 1))
    df["promo_run_id"] = run_start.cumsum().where(df["is_promo"])
    run_len = df.groupby("promo_run_id")["week_index"].transform("size")
    df["promo_run_length"] = run_len.where(df["is_promo"])
    df["promo_run_start"] = run_start

    # --- derived
    df["units_per_hh"] = df["units"] / df["hhs"].replace(0, np.nan)
    df["units_per_visit"] = df["units"] / df["visits"].replace(0, np.nan)

    # --- lookups
    df = df.merge(prod[["upc", "description", "manufacturer", "category", "sub_category", "product_size"]],
                  on="upc", how="left")
    df = df.merge(stores[["store_num", "address_state_prov_code", "seg_value_name", "sales_area_size_num",
                          "avg_weekly_baskets"]], on="store_num", how="left")
    df = df.rename(columns={"address_state_prov_code": "state", "seg_value_name": "store_segment",
                            "sales_area_size_num": "store_sqft"})

    cols = ["store_num", "upc", "week_end_date", "week_index", "week_of_year", "year",
            "units", "visits", "hhs", "spend", "price", "base_price", "discount_depth",
            "feature", "display", "tpr_only", "price_cut", "is_promo", "promo_type",
            "weeks_since_promo", "weeks_until_promo", "promo_run_id", "promo_run_length", "promo_run_start",
            "units_per_hh", "units_per_visit", "price_imputed", "base_price_imputed",
            "description", "manufacturer", "category", "sub_category", "product_size",
            "state", "store_segment", "store_sqft", "avg_weekly_baskets"]
    df = df[cols]
    df.to_parquet(out, index=False)
    return df


if __name__ == "__main__":
    d = build_clean(force=True)
    print(d.shape)
    print(d.head())
    print(d["promo_type"].value_counts())
