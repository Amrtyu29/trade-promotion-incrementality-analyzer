"""Phase 0, step 1: profile the raw dunnhumby workbook. Prints everything, builds no models.

Reads the actual Excel file (every sheet), caches each sheet as CSV in data/raw/csv/
so later steps do not pay the 30 MB xlsx parse again.
"""
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw" / "extracted" / "dunnhumby_Breakfast-at-the-Frat"
CSV_DIR = ROOT / "data" / "raw" / "csv"
CSV_DIR.mkdir(parents=True, exist_ok=True)

pd.set_option("display.width", 200)
pd.set_option("display.max_columns", 50)

xlsx = next(RAW.glob("*.xlsx"))
print("File:", xlsx.name, f"({xlsx.stat().st_size/1e6:.1f} MB)")

sheets = pd.read_excel(xlsx, sheet_name=None)
for name, df in sheets.items():
    safe = name.replace(" ", "_").replace("-", "_").lower()
    df.to_csv(CSV_DIR / f"{safe}.csv", index=False)
    print("\n" + "=" * 80)
    print(f"SHEET: {name!r}  shape={df.shape}")
    print("-" * 80)
    print(df.dtypes.to_string())
    print("\nNull counts:")
    print(df.isna().sum().to_string())
    print("\nHead:")
    print(df.head(5).to_string())
    num = df.select_dtypes("number")
    if not num.empty:
        print("\nDescribe:")
        print(num.describe().T.to_string())
    for c in df.columns:
        if df[c].nunique() <= 30:
            print(f"\nvalue_counts[{c}]:")
            print(df[c].value_counts(dropna=False).to_string())
print("\nCSV cache written to", CSV_DIR)
