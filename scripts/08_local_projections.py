"""
Stage 08 — Local Projections (Jordà 2005) pre-trends test for Romanian reform assignment.

Since the reform has not yet happened (proposed for 2025), ALL horizons are pre-treatment.
A flat LP coefficient across horizons supports the parallel-trends assumption underlying
the gsynth design used in Stage 03/04.

Framework: Cross-sectional LP per horizon h:
  ΔY_i(h) = Y_{i, BASE_YEAR+h} - Y_{i, BASE_YEAR}
             regressed on treated_i via OLS with HC3 robust SEs

Outputs:
  data/processed/ro_lp_irfs.parquet        — IRF coefficients for all outcomes × horizons
  figures/f08_lp_irf_{outcome}.png         — IRF plots (4 outcomes)
"""
from __future__ import annotations
import sys

sys.stdout.reconfigure(encoding="utf-8")

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import statsmodels.formula.api as smf

ROOT = Path(__file__).resolve().parents[1]
PROCESSED = ROOT / "data" / "processed"
FIGURES = ROOT / "figures"
FIGURES.mkdir(exist_ok=True)

BASE_YEAR = 2000   # first year with near-complete GVA/migration coverage
H_MIN, H_MAX = 0, 24  # horizons: 2000 → 2024

OUTCOMES = [
    ("ln_population",      "Log population"),
    ("nat_change_rate",    "Natural pop. change per 1,000"),
    ("net_migration_rate", "Net migration rate per 1,000"),
    ("ln_gva_per_empl",    "Log GVA per employed (productivity)"),
]
# NOTE: unemployment is NUTS2-broadcast (identical within region → zero within-region
# variation at the cross-sectional LP level), so it is excluded from this analysis.

SOURCE_LINE = (
    "Sources: Eurostat NUTS3; author calculations. "
    "LP cross-sectional specification (Jordà 2005)."
)


def run_lp_single(df: pd.DataFrame, outcome: str, h: int) -> dict | None:
    """
    Cross-sectional LP for horizon h.

    LHS = Y_{i, BASE_YEAR+h} - Y_{i, BASE_YEAR}
    Regressed on treated_i (1 = demoted county, 0 = control) via OLS with HC3 robust SEs.

    Parameters
    ----------
    df : long-format panel (nuts3_code × year)
    outcome : column name of the outcome variable
    h : horizon (years since BASE_YEAR)

    Returns
    -------
    dict with regression outputs, or None if skipped.
    """
    target_year = BASE_YEAR + h

    if target_year not in df["year"].values or BASE_YEAR not in df["year"].values:
        return None

    base = df[df["year"] == BASE_YEAR][["nuts3_code", outcome, "treated"]].copy()
    target = df[df["year"] == target_year][["nuts3_code", outcome]].copy()
    base = base.rename(columns={outcome: "y_base"})
    target = target.rename(columns={outcome: "y_target"})

    merged = base.merge(target, on="nuts3_code", how="inner")
    merged["lhs"] = merged["y_target"] - merged["y_base"]
    merged = merged.dropna(subset=["lhs", "treated"])

    if len(merged) < 15 or merged["treated"].sum() == 0 or merged["treated"].nunique() < 2:
        return None

    try:
        res = smf.ols("lhs ~ treated", data=merged).fit(cov_type="HC3")
        beta = float(res.params["treated"])
        se = float(res.bse["treated"])
        return {
            "horizon": h,
            "coef": beta,
            "se": se,
            "ci_lo_90": beta - 1.645 * se,
            "ci_hi_90": beta + 1.645 * se,
            "ci_lo_95": beta - 1.960 * se,
            "ci_hi_95": beta + 1.960 * se,
            "nobs": int(res.nobs),
        }
    except Exception as e:
        print(f"  [SKIP] h={h}: {e}")
        return None


def run_lp(df: pd.DataFrame, outcome: str) -> pd.DataFrame:
    """Run LP for all horizons for a single outcome.

    Parameters
    ----------
    df : long-format panel
    outcome : column name of the outcome variable

    Returns
    -------
    DataFrame with one row per horizon.
    """
    records = []
    for h in range(H_MIN, H_MAX + 1):
        row = run_lp_single(df, outcome, h)
        if row is not None:
            row["outcome"] = outcome
            records.append(row)
    return pd.DataFrame(records)


def plot_irf(coef_df: pd.DataFrame, outcome: str, label: str) -> None:
    """Plot LP-IRF with 90% and 95% confidence bands.

    The vertical dashed line at h=24.5 marks the hypothetical reform year (2025),
    which lies just outside the data range — it is a visual reference only.

    Parameters
    ----------
    coef_df : output of run_lp()
    outcome : column name (used for filename)
    label : human-readable outcome label
    """
    fig, ax = plt.subplots(figsize=(10, 5))
    sub = coef_df.sort_values("horizon")

    ax.axhline(0, color="black", lw=0.8)

    # Dashed marker for hypothetical reform — outside data range, visual only
    ax.axvline(24.5, color="#e8ff47", lw=1.5, ls="--", label="Hypothetical reform (2025)")

    ax.fill_between(
        sub["horizon"], sub["ci_lo_95"], sub["ci_hi_95"],
        alpha=0.15, color="#4d7cff", label="95% CI",
    )
    ax.fill_between(
        sub["horizon"], sub["ci_lo_90"], sub["ci_hi_90"],
        alpha=0.30, color="#4d7cff", label="90% CI",
    )
    ax.plot(
        sub["horizon"], sub["coef"], "o-", color="#4d7cff",
        ms=4, lw=1.8, label="LP coefficient",
    )

    ax.set_xlabel("Years since 2000 (all pre-reform)")
    ax.set_ylabel(f"LP coefficient (Δ {label})")
    ax.set_title(
        f"Local Projection IRF: {label}\n"
        f"(Treated = 33 demoted counties vs. 9 controls; BASE_YEAR = {BASE_YEAR})",
        fontweight="bold", fontsize=11,
    )
    ax.legend(fontsize=9)
    ax.text(0.01, -0.12, SOURCE_LINE, transform=ax.transAxes, fontsize=7, color="grey")

    plt.tight_layout()
    path = FIGURES / f"f08_lp_irf_{outcome}.png"
    plt.savefig(path, dpi=300, bbox_inches="tight")
    plt.close()
    print(f"  Saved: {path.name}")


def main() -> None:
    print("=== Stage 08: Local Projections (pre-trends test) ===\n")
    print(f"BASE_YEAR = {BASE_YEAR}  |  Horizons: {H_MIN}–{H_MAX}  (years {BASE_YEAR}–{BASE_YEAR + H_MAX})")
    print(f"Treatment: 33 demoted counties (treated=1) vs. 9 controls (treated=0)\n")

    panel = pd.read_parquet(PROCESSED / "ro_panel_judet.parquet")
    print(f"Panel loaded: {panel.shape[0]} rows × {panel.shape[1]} cols")
    print(f"Counties: {panel['nuts3_code'].nunique()}  |  Years: {sorted(panel['year'].unique())}\n")

    all_irfs: list[pd.DataFrame] = []

    for outcome, label in OUTCOMES:
        if outcome not in panel.columns:
            print(f"[SKIP] {outcome} — not in panel columns.")
            continue
        if panel[outcome].isna().all():
            print(f"[SKIP] {outcome} — all NaN.")
            continue

        print(f"\n[{outcome}]  ({label})")
        irf = run_lp(panel, outcome)

        if irf.empty:
            print("  No estimates produced.")
            continue

        all_irfs.append(irf)
        plot_irf(irf, outcome, label)

        h_vals = sorted(irf["horizon"].astype(int).tolist())
        print(f"  Horizons: {h_vals[0]}…{h_vals[-1]}  ({len(irf)} estimates)")
        h0_rows = irf[irf["horizon"] == 0]
        if not h0_rows.empty:
            print(f"  h=0  coef: {h0_rows['coef'].values[0]:+.4f}  "
                  f"(SE={h0_rows['se'].values[0]:.4f})")
        h24_rows = irf[irf["horizon"] == 24]
        if not h24_rows.empty:
            print(f"  h=24 coef: {h24_rows['coef'].values[0]:+.4f}  "
                  f"(SE={h24_rows['se'].values[0]:.4f})")
        nan_coef = irf["coef"].isna().sum()
        if nan_coef > 0:
            print(f"  WARNING: {nan_coef} NaN coefficients detected!")

    print()
    if all_irfs:
        combined = pd.concat(all_irfs, ignore_index=True)
        out_path = PROCESSED / "ro_lp_irfs.parquet"
        combined.to_parquet(out_path, index=False)
        print(f"Saved → ro_lp_irfs.parquet  ({len(combined)} rows × {combined.shape[1]} cols)")
        print(f"Columns: {combined.columns.tolist()}")
        print(f"Outcomes covered: {combined['outcome'].unique().tolist()}")
        nan_total = combined["coef"].isna().sum()
        print(f"NaN in coef column: {nan_total}")
    else:
        print("No IRF estimates produced — check input data.")

    print("\n=== Stage 08 complete ===")


if __name__ == "__main__":
    main()
