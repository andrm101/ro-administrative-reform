"""
Stage 03 -- Finalize ro_panel_judet.parquet (Gold layer).

Reads: data/processed/ro_treatment_panel.parquet (Stage 02)

Applies:
  1. Restrict to 1995-2024 and NUTS3-only rows
  2. Reclassify Ilfov (RO322) as control (no county seat to demote)
  3. Winsorize rates at 1st/99th percentile
  4. Add within-unit demeaned columns (_dm suffix) for TWFE/PVAR
  5. Add year_fe column for R SDiD/gsynth scripts

Output:
  data/processed/ro_panel_judet.parquet   canonical Gold panel (mirror of PL panel_powiat)
  data/processed/panel_summary.csv        coverage and descriptives per variable
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
PROCESSED = ROOT / "data" / "processed"

OUTCOME_COLS = [
    "ln_population",
    "nat_change_rate",
    "net_migration_rate",
    "unemployment",
    "gva_per_empl",
    "ln_gva_per_empl",
]


def winsorize_series(s: pd.Series, low: float = 0.01, high: float = 0.99) -> pd.Series:
    lo = s.quantile(low)
    hi = s.quantile(high)
    return s.clip(lower=lo, upper=hi)


def main() -> None:
    print("=== Stage 03: Finalize ro_panel_judet ===\n")

    src = PROCESSED / "ro_treatment_panel.parquet"
    if not src.exists():
        raise FileNotFoundError(f"{src} not found -- run 02_build_treatment.py first.")

    panel = pd.read_parquet(src)
    print(f"Input: {panel.shape} ({panel['nuts3_code'].nunique()} units, "
          f"years {panel['year'].min()}-{panel['year'].max()})")

    # 1. Restrict year range
    panel = panel[panel["year"].between(1995, 2024)].copy()

    # 2. Reclassify Ilfov as control
    for col, val in [("treated", 0), ("post", 0)]:
        panel.loc[panel["nuts3_code"] == "RO322", col] = val
    panel.loc[panel["nuts3_code"] == "RO322", "treated_year"] = np.nan
    panel.loc[panel["nuts3_code"] == "RO322", "relative_year"] = np.nan

    n_treated = panel[panel["treated"] == 1]["nuts3_code"].nunique()
    n_control = panel[panel["treated"] == 0]["nuts3_code"].nunique()
    print(f"Treatment set: {n_treated} treated, {n_control} control")

    # 3. Winsorize rates
    rate_cols = [c for c in ["nat_change_rate", "net_migration_rate", "unemployment"]
                 if c in panel.columns]
    for col in rate_cols:
        b = (panel[col].min(), panel[col].max())
        panel[col] = winsorize_series(panel[col])
        a = (panel[col].min(), panel[col].max())
        print(f"  winsorize {col}: [{b[0]:.2f}, {b[1]:.2f}] -> [{a[0]:.2f}, {a[1]:.2f}]")

    # 4. Within-unit demeaning
    existing = [c for c in OUTCOME_COLS if c in panel.columns]
    for col in existing:
        unit_mean = panel.groupby("nuts3_code")[col].transform("mean")
        panel[f"{col}_dm"] = panel[col] - unit_mean

    # 5. Year FE indicator
    panel["year_fe"] = panel["year"].astype(int)

    panel = panel.sort_values(["nuts3_code", "year"]).reset_index(drop=True)

    out_path = PROCESSED / "ro_panel_judet.parquet"
    panel.to_parquet(out_path, index=False)
    print(f"\nSaved: {out_path.relative_to(ROOT)}")
    print(f"  Shape: {panel.shape}")

    # Summary statistics
    summary_rows = []
    for col in existing:
        s = panel[col].dropna()
        summary_rows.append({
            "variable": col,
            "n_obs": len(s),
            "n_units": panel[panel[col].notna()]["nuts3_code"].nunique(),
            "year_min": int(panel[panel[col].notna()]["year"].min()),
            "year_max": int(panel[panel[col].notna()]["year"].max()),
            "mean": s.mean(),
            "sd": s.std(),
            "p25": s.quantile(0.25),
            "median": s.median(),
            "p75": s.quantile(0.75),
            "coverage_pct": panel[col].notna().mean(),
        })

    summary = pd.DataFrame(summary_rows)
    summary_path = PROCESSED / "panel_summary.csv"
    summary.to_csv(summary_path, index=False, float_format="%.4f")
    print(f"Saved: {summary_path.relative_to(ROOT)}")
    print("\nPanel summary:")
    print(summary[["variable", "n_obs", "n_units", "year_min", "year_max",
                    "mean", "sd", "coverage_pct"]].to_string(index=False))


if __name__ == "__main__":
    main()
