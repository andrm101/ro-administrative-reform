"""
Stage 11b -- Post-process gsynth output into canonical ro_gsynth_gaps.parquet.

Polish ATT priors (from PL-Capital-Reform-DiD Stage 10-11):
  pessimistic: -0.045  (Polish SDiD ATT -- most negative estimate)
  central:     -0.015  (Polish GSC average ATT across 29 cities)
  optimistic:  +0.005  (upper tail of PL GSC ATT distribution)

For years >= 2025: reform_scenario = counterfactual_projected + ATT_prior
For years <  2025: reform_scenario = counterfactual_fitted (gsynth IFE fit)

Post-2024 counterfactuals: extrapolated from per-county OLS trend on 2020-2024.

Reads:
  data/processed/ro_gsynth_raw.parquet
  data/processed/ro_treatment_cities.parquet

Writes:
  data/processed/ro_gsynth_gaps.parquet
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

ROOT = Path(__file__).resolve().parents[1]
PROCESSED = ROOT / "data" / "processed"

PL_ATT = {
    "pessimistic": -0.045,
    "central":     -0.015,
    "optimistic":   0.005,
}

TREND_WINDOW = (2020, 2024)
FORECAST_YEARS = list(range(2025, 2036))


def extrapolate_counterfactual(df: pd.DataFrame) -> pd.DataFrame:
    """
    For each unit_id, fill NaN counterfactual values in years >= 2025
    by extrapolating the OLS trend fitted on TREND_WINDOW years.
    """
    df = df.copy()
    for uid, grp in df.groupby("unit_id"):
        fit_mask = (grp["year"] >= TREND_WINDOW[0]) & (grp["year"] <= TREND_WINDOW[1])
        fit_data = grp[fit_mask].dropna(subset=["counterfactual"])
        if len(fit_data) < 2:
            # Not enough data: use last observed counterfactual (flat extrapolation)
            last_val = grp.loc[grp["counterfactual"].notna(), "counterfactual"].iloc[-1] \
                if grp["counterfactual"].notna().any() else np.nan
            for fy in FORECAST_YEARS:
                mask = (df["unit_id"] == uid) & (df["year"] == fy) & df["counterfactual"].isna()
                df.loc[mask, "counterfactual"] = last_val
            continue
        slope, intercept, *_ = stats.linregress(
            fit_data["year"].values.astype(float),
            fit_data["counterfactual"].values.astype(float)
        )
        for fy in FORECAST_YEARS:
            mask = (df["unit_id"] == uid) & (df["year"] == fy) & df["counterfactual"].isna()
            df.loc[mask, "counterfactual"] = slope * fy + intercept
    return df


def main() -> None:
    raw    = pd.read_parquet(PROCESSED / "ro_gsynth_raw.parquet")
    cities = pd.read_parquet(PROCESSED / "ro_treatment_cities.parquet")

    # Fill post-2024 counterfactual NaNs via extrapolation
    n_na_before = raw["counterfactual"].isna().sum()
    raw = extrapolate_counterfactual(raw)
    n_na_after = raw["counterfactual"].isna().sum()
    print(f"Counterfactual NaN: {n_na_before} -> {n_na_after} (extrapolated {n_na_before - n_na_after} values)")

    # Merge county metadata
    meta = cities[["nuts3_code", "judet_name", "county_seat", "nuts2_code"]].drop_duplicates()
    gaps = raw.merge(meta, left_on="unit_id", right_on="nuts3_code", how="left")

    # Reform scenario columns
    future = gaps["year"] >= 2025
    for scenario, att in PL_ATT.items():
        col = f"reform_scenario_{scenario}"
        gaps[col] = gaps["counterfactual"].copy()
        gaps.loc[future, col] = gaps.loc[future, "counterfactual"] + att

    # Per-county pre-period mean gap
    att_pre = (
        gaps[gaps["year"] <= 2024]
        .groupby("unit_id")["gap"]
        .mean()
        .reset_index()
        .rename(columns={"gap": "att_avg_pre"})
    )
    gaps = gaps.merge(att_pre, on="unit_id", how="left")

    # Final output
    if "nuts3_code" in gaps.columns:
        gaps["nuts3_code"] = gaps["nuts3_code"].fillna(gaps["unit_id"])
    else:
        gaps["nuts3_code"] = gaps["unit_id"]

    keep = [
        "nuts3_code", "year", "judet_name", "county_seat", "nuts2_code",
        "actual", "counterfactual", "gap", "rmse_preperiod",
        "reform_scenario_pessimistic", "reform_scenario_central",
        "reform_scenario_optimistic", "att_avg_pre",
    ]
    keep_present = [c for c in keep if c in gaps.columns]
    out = gaps[keep_present].sort_values(["nuts3_code", "year"]).reset_index(drop=True)

    out_path = PROCESSED / "ro_gsynth_gaps.parquet"
    out.to_parquet(out_path, index=False)

    print(f"Saved: data/processed/ro_gsynth_gaps.parquet")
    print(f"  Shape: {out.shape}")
    print(f"  Counties: {out['nuts3_code'].nunique()}")
    print(f"  Years: {out['year'].min()}-{out['year'].max()}")
    print(f"  Remaining NaN in counterfactual: {out['counterfactual'].isna().sum()}")
    print("\nSample (2025, reform scenarios):")
    sample = (out[out["year"] == 2025]
              [["nuts3_code", "counterfactual",
                "reform_scenario_pessimistic", "reform_scenario_central"]]
              .head(6))
    print(sample.to_string(index=False))


if __name__ == "__main__":
    main()
