"""
Build cross-country panel for Stage 11 gsynth.

Combines:
  - Polish non-treated powiats (346 donor units, 1995-2024)
  - Romanian NUTS3 panel (42 units, 1995-2024; 33 treated, 9 control)

Extends to 2025-2035:
  - Donors: linear extrapolation of 2018-2024 trend per unit
  - Romanian treated units: ln_population = NaN (gsynth will impute = counterfactual)

Output: data/processed/cc_panel.parquet
  unit_id (str) | year (int) | ln_population (float|NaN) | country | ro_treated (0/1) | D (0/1)
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

ROOT = Path(__file__).resolve().parents[1]
PL_ROOT = ROOT.parent / "PL-Capital-Reform-DiD"
PROCESSED = ROOT / "data" / "processed"

FORECAST_START = 2024
FORECAST_END   = 2035
TREND_WINDOW   = (2018, 2024)
MIN_OBS        = 20


def linear_extrapolate(
    years: np.ndarray,
    values: np.ndarray,
    future_years: np.ndarray,
    trend_window: tuple[int, int] = TREND_WINDOW,
) -> np.ndarray:
    mask = (years >= trend_window[0]) & (years <= trend_window[1])
    y_fit = values[mask]
    x_fit = years[mask]
    valid = np.isfinite(y_fit) & np.isfinite(x_fit)
    if valid.sum() < 3:
        last_val = values[np.isfinite(values)][-1] if np.isfinite(values).any() else np.nan
        return np.full(len(future_years), last_val)
    slope, intercept, *_ = stats.linregress(x_fit[valid], y_fit[valid])
    return slope * future_years + intercept


def main() -> None:
    PROCESSED.mkdir(parents=True, exist_ok=True)
    future_years = np.arange(FORECAST_START, FORECAST_END + 1)

    pl_path = PL_ROOT / "data" / "processed" / "panel_powiat.parquet"
    if not pl_path.exists():
        raise FileNotFoundError(f"Polish panel not found: {pl_path}")

    pl = pd.read_parquet(pl_path)
    pl_donors = pl[pl["treated"] == 0][["teryt_powiat", "year", "ln_population"]].copy()
    pl_donors["unit_id"] = "PL_" + pl_donors["teryt_powiat"].astype(str)
    pl_donors["country"] = "PL"
    pl_donors["ro_treated"] = 0

    ro = pd.read_parquet(PROCESSED / "ro_panel_judet.parquet")
    ro_panel = ro[["nuts3_code", "year", "ln_population", "treated"]].copy()
    ro_panel["unit_id"] = ro_panel["nuts3_code"]
    ro_panel["country"] = "RO"
    ro_panel["ro_treated"] = ro_panel["treated"]

    combined = pd.concat([
        pl_donors[["unit_id", "year", "ln_population", "country", "ro_treated"]],
        ro_panel[["unit_id", "year", "ln_population", "country", "ro_treated"]],
    ], ignore_index=True)

    obs_count = combined.groupby("unit_id")["ln_population"].apply(lambda x: x.notna().sum())
    keep_units = obs_count[obs_count >= MIN_OBS].index
    combined = combined[combined["unit_id"].isin(keep_units)].copy()
    print(f"After coverage filter (>={MIN_OBS} obs): {combined['unit_id'].nunique()} units")
    print(f"  PL donors: {combined[combined['country']=='PL']['unit_id'].nunique()}")
    print(f"  RO treated: {combined[combined['ro_treated']==1]['unit_id'].nunique()}")
    print(f"  RO control: {combined[(combined['country']=='RO') & (combined['ro_treated']==0)]['unit_id'].nunique()}")

    extension_rows: list[dict] = []
    for uid in combined["unit_id"].unique():
        sub = combined[combined["unit_id"] == uid].sort_values("year")
        yrs = sub["year"].values.astype(float)
        vals = sub["ln_population"].values.astype(float)
        is_ro_treated = int(sub["ro_treated"].iloc[0]) == 1
        country = sub["country"].iloc[0]
        future_vals = (
            np.full(len(future_years), np.nan)
            if is_ro_treated
            else linear_extrapolate(yrs, vals, future_years.astype(float))
        )
        for i, fy in enumerate(future_years):
            extension_rows.append({
                "unit_id": uid,
                "year": int(fy),
                "ln_population": future_vals[i],
                "country": country,
                "ro_treated": int(sub["ro_treated"].iloc[0]),
            })

    extension = pd.DataFrame(extension_rows)
    panel = pd.concat([combined, extension], ignore_index=True)
    # Deduplicate: when FORECAST_START overlaps with original data (e.g. PL has NaN 2024
    # in raw data), keep the extrapolated (non-NaN) row; NaN rows lose the sort.
    panel = panel.sort_values(
        ["unit_id", "year", "ln_population"], na_position="last"
    ).drop_duplicates(subset=["unit_id", "year"], keep="first")
    panel["D"] = ((panel["ro_treated"] == 1) & (panel["year"] >= FORECAST_START)).astype(int)
    panel = panel.sort_values(["unit_id", "year"]).reset_index(drop=True)

    out_path = PROCESSED / "cc_panel.parquet"
    panel.to_parquet(out_path, index=False)

    print(f"\nSaved: data/processed/cc_panel.parquet")
    print(f"  Shape: {panel.shape}")
    print(f"  Years: {panel['year'].min()}-{panel['year'].max()}")
    print(f"  Treated (D=1) unit-years: {panel['D'].sum()}")
    print(f"  NA ln_population (to impute): {panel['ln_population'].isna().sum()}")


if __name__ == "__main__":
    main()
