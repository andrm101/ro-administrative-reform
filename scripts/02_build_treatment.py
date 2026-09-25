"""
Stage 02 -- Build treatment panel.

Reads:
  data/processed/ro_eurostat_interim.parquet  (Stage 01 output)
  data/raw/treatment/ro_capital_status.csv    (treatment definition)

Adds treatment variables to the panel:
  - treated       : 1 if county would be demoted under 2023-2025 reform
  - treated_year  : hypothetical treatment year (2025 for all treated; NaN for controls)
  - post          : 1 if year >= treated_year (0 for all rows currently, reform not enacted)
  - relative_year : year - treated_year (negative = pre-treatment; NaN for controls)

Outputs:
  data/processed/ro_treatment_panel.parquet   (42 units x T years x columns)
  data/processed/ro_treatment_cities.parquet  (42 units x static metadata)
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
PROCESSED = ROOT / "data" / "processed"
RAW_TREATMENT = ROOT / "data" / "raw" / "treatment"


def main() -> None:
    print("=== Stage 02: Build treatment panel ===\n")

    interim_path = PROCESSED / "ro_eurostat_interim.parquet"
    if not interim_path.exists():
        raise FileNotFoundError(f"{interim_path} not found -- run 01_ingest.py first.")
    panel = pd.read_parquet(interim_path)
    print(f"Loaded interim panel: {panel.shape}")

    treatment = pd.read_csv(RAW_TREATMENT / "ro_capital_status.csv", dtype=str)
    treatment["proposed_treatment"] = treatment["proposed_treatment"].astype(int)
    treatment["proposed_regional_capital"] = treatment["proposed_regional_capital"].astype(int)
    treatment["proposed_reform_year"] = pd.to_numeric(
        treatment["proposed_reform_year"], errors="coerce"
    )
    print(f"Treatment table: {len(treatment)} units | "
          f"{treatment['proposed_treatment'].sum()} treated | "
          f"{(treatment['proposed_treatment'] == 0).sum()} control")

    keep_cols = [
        "nuts3_code", "judet_name", "county_seat", "nuts2_code", "siruta",
        "proposed_regional_capital", "proposed_treatment", "proposed_reform_year",
        "current_status",
    ]
    panel = panel.merge(treatment[keep_cols], on="nuts3_code", how="left")

    missing = panel[panel["proposed_treatment"].isna()]["nuts3_code"].unique()
    if len(missing):
        print(f"[WARN] NUTS3 codes not in treatment table: {missing}", flush=True)

    panel = panel.rename(columns={
        "proposed_treatment": "treated",
        "proposed_reform_year": "treated_year",
    })
    panel["treated"] = panel["treated"].fillna(0).astype(int)

    panel["post"] = (
        panel["year"] >= panel["treated_year"]
    ).where(panel["treated"] == 1, other=0).astype(int)

    panel["relative_year"] = (
        panel["year"] - panel["treated_year"]
    ).where(panel["treated"] == 1)

    if "gva_per_empl" in panel.columns:
        panel["ln_gva_per_empl"] = np.log(panel["gva_per_empl"].clip(lower=1))

    cities = treatment[keep_cols].rename(columns={
        "proposed_treatment": "treated",
        "proposed_reform_year": "treated_year",
    }).copy()

    PROCESSED.mkdir(parents=True, exist_ok=True)

    panel_path = PROCESSED / "ro_treatment_panel.parquet"
    panel.to_parquet(panel_path, index=False)
    print(f"\nSaved: {panel_path.relative_to(ROOT)}")
    print(f"  Shape: {panel.shape}")
    print(f"  Treated units: {panel[panel['treated']==1]['nuts3_code'].nunique()}")
    print(f"  Control units: {panel[panel['treated']==0]['nuts3_code'].nunique()}")
    print(f"  Years: {panel['year'].min()}-{panel['year'].max()}")

    cities_path = PROCESSED / "ro_treatment_cities.parquet"
    cities.to_parquet(cities_path, index=False)
    print(f"Saved: {cities_path.relative_to(ROOT)}")
    print(f"  {len(cities)} units ({cities['treated'].sum()} treated, "
          f"{(cities['treated']==0).sum()} control)")

    print("\nColumn coverage in panel (non-null %):")
    skip = {"nuts3_code", "year", "treated", "post", "relative_year", "treated_year",
            "siruta", "judet_name", "county_seat", "nuts2_code", "current_status",
            "proposed_regional_capital"}
    for col in panel.columns:
        if col in skip:
            continue
        pct = panel[col].notna().mean()
        print(f"  {col:30s}: {pct:.0%}")


if __name__ == "__main__":
    main()
