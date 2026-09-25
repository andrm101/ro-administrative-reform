"""
Stage 05 — TWFE Pre-Trends Event Study (Romania Administrative Reform).

All data is pre-treatment (reform hypothetically in 2025, data ends 2024).
Event times k = year − 2025 ∈ {−30, …, −1}; window restricted to k ∈ [−20, −1].
Reference year: k = −1 (2024), coefficient normalised to 0.

Specification:
    Y_{it} = α_i + λ_t + Σ_{k ≠ −1} β_k (treated_i × 1[event_time_{it}=k]) + ε_{it}

SE: clustered at nuts3_code level (conservative; only 9 control counties).

Outputs:
  data/processed/ro_eventstudy_coefs.parquet — event-study coefficients (all outcomes)
  figures/f05_eventstudy_{outcome}.png        — coefficient plots (4 figures)
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from linearmodels.panel import PanelOLS

ROOT = Path(__file__).parent.parent
PROCESSED = ROOT / "data" / "processed"
FIGURES = ROOT / "figures"
FIGURES.mkdir(exist_ok=True)

REFORM_YEAR = 2025
ET_MIN, ET_MAX = -20, -1   # event window (inclusive); omit k=-1 as reference
ET_REF = -1                # reference period (year 2024)

SOURCE_LINE = (
    "Sources: Eurostat NUTS3; author calculations. "
    "TWFE, SE clustered by county."
)

# Unemployment excluded: NUTS2-broadcast → zero within-region variation
OUTCOMES = [
    ("ln_population",      "Log population"),
    ("nat_change_rate",    "Natural change rate per 1,000"),
    ("net_migration_rate", "Net migration rate per 1,000"),
    ("ln_gva_per_empl",    "Log GVA per employed (productivity)"),
]


# ---------------------------------------------------------------------------
# Event-dummy construction
# ---------------------------------------------------------------------------

def add_event_dummies(
    df: pd.DataFrame, et_min: int, et_max: int
) -> tuple[pd.DataFrame, list[str]]:
    """
    Add treated × 1[event_time = k] dummies for k in [et_min, et_max], omitting k = ET_REF.
    All k are negative in this script, so columns are named et_negN.
    Returns modified df and ordered list of dummy column names.
    """
    dummy_cols: list[str] = []
    for k in range(et_min, et_max + 1):
        if k == ET_REF:           # skip reference period (normalised to 0)
            continue
        col = f"et_neg{abs(k)}"   # all k < 0
        df[col] = df["treated"] * (df["event_time"] == k).astype(int)
        dummy_cols.append(col)
    return df, dummy_cols


# ---------------------------------------------------------------------------
# TWFE estimation
# ---------------------------------------------------------------------------

def parse_et(v: str) -> int | float:
    """Map dummy column name → event time integer (negative)."""
    if v.startswith("et_neg"):
        return -int(v.replace("et_neg", ""))
    return np.nan


def run_twfe(
    df: pd.DataFrame,
    outcome: str,
    dummy_cols: list[str],
    entity_col: str = "nuts3_code",
    time_col: str = "year",
    min_obs: int = 50,
) -> pd.DataFrame | None:
    """
    Run TWFE event-study with linearmodels.PanelOLS.

    Parameters
    ----------
    df         : panel DataFrame (long format)
    outcome    : outcome column name
    dummy_cols : list of event-time dummy column names
    entity_col : entity identifier column
    time_col   : time identifier column
    min_obs    : minimum observations required to proceed

    Returns
    -------
    DataFrame with columns [event_time, coef, se, ci_lo, ci_hi] or None.
    """
    if outcome not in df.columns or df[outcome].isna().all():
        print(f"  [SKIP] {outcome}: all NaN.")
        return None

    # Active dummies: those with at least one treated=1 observation where outcome is non-NaN
    obs_years = set(df.loc[df[outcome].notna(), time_col].unique())
    active_dummies = [
        col for col in dummy_cols
        if df.loc[df[col] > 0, time_col].isin(obs_years).any()
    ]

    sub = df[[entity_col, time_col, outcome] + active_dummies].dropna(subset=[outcome])

    # Drop dummies that are all-zero in restricted sample (collinear with FEs)
    active_dummies = [c for c in active_dummies if sub[c].sum() > 0]

    if sub.shape[0] < min_obs:
        print(f"  [SKIP] {outcome}: too few observations ({sub.shape[0]}).")
        return None
    if not active_dummies:
        print(f"  [SKIP] {outcome}: no event-time dummies with variation.")
        return None

    panel_df = sub[[entity_col, time_col, outcome] + active_dummies].set_index(
        [entity_col, time_col]
    )
    formula = f"{outcome} ~ " + " + ".join(active_dummies) + " + EntityEffects + TimeEffects"

    try:
        mod = PanelOLS.from_formula(formula, data=panel_df, drop_absorbed=True)
        res = mod.fit(cov_type="clustered", cluster_entity=True)
    except Exception as exc:
        print(f"  [ERROR] {outcome}: {exc}")
        return None

    # Build coefficient table
    coef = res.params.reset_index()
    coef.columns = ["variable", "coef"]
    se = res.std_errors.reset_index()
    se.columns = ["variable", "se"]
    result = coef.merge(se, on="variable")
    result["ci_lo"] = result["coef"] - 1.96 * result["se"]
    result["ci_hi"] = result["coef"] + 1.96 * result["se"]

    result["event_time"] = result["variable"].map(parse_et)
    result = result.dropna(subset=["event_time"]).sort_values("event_time")

    # Append reference row k = −1 (coef = 0 by normalisation)
    ref_row = pd.DataFrame({
        "variable": ["et_neg1_ref"],
        "coef":     [0.0],
        "se":       [0.0],
        "ci_lo":    [0.0],
        "ci_hi":    [0.0],
        "event_time": [-1.0],
    })
    result = pd.concat([result, ref_row], ignore_index=True).sort_values("event_time")

    # Drop variable column — not needed in output parquet
    result = result.drop(columns=["variable"])

    n_entities = res.entity_info.total
    n_control  = df.loc[df["treated"] == 0, entity_col].nunique()
    print(
        f"  N={res.nobs}, entities={n_entities}, "
        f"R²(within)={res.rsquared_within:.3f} "
        f"[NOTE: only {n_control} control counties → conservative clustered SE]"
    )

    return result


# ---------------------------------------------------------------------------
# Plotting
# ---------------------------------------------------------------------------

def plot_event_study(
    coef_df: pd.DataFrame,
    outcome: str,
    label: str,
) -> None:
    """Plot event-study coefficients with 95% CIs."""
    sub = coef_df.sort_values("event_time")

    fig, ax = plt.subplots(figsize=(10, 5))

    ax.axhline(0, color="black", lw=0.8, ls="-")
    ax.axvline(-0.5, color="red", lw=1.5, ls="--",
               label="Hypothetical reform (2025)")

    ax.errorbar(
        sub["event_time"], sub["coef"],
        yerr=1.96 * sub["se"],
        fmt="o", color="#1f77b4", ms=5, lw=1.5, capsize=3,
        label="β_k (95% CI)",
    )

    # Shade pre-period CI band (all observations are pre-period here)
    if len(sub) > 1:
        ax.fill_between(
            sub["event_time"], sub["ci_lo"], sub["ci_hi"],
            alpha=0.12, color="#1f77b4", label="95% CI band",
        )

    ax.set_xlabel("Years relative to hypothetical 2025 reform")
    ax.set_ylabel(f"Coefficient (Δ {label})")
    ax.set_title(f"Pre-trends event study: {label}", fontweight="bold", fontsize=11)
    ax.legend(fontsize=9)
    ax.text(
        0.01, -0.12, SOURCE_LINE,
        transform=ax.transAxes, fontsize=7, color="grey",
    )

    plt.tight_layout()
    fname = FIGURES / f"f05_eventstudy_{outcome}.png"
    plt.savefig(fname, dpi=300, bbox_inches="tight")
    plt.close()
    print(f"  Saved: {fname.name}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    print("=== Stage 05: TWFE Pre-Trends Event Study ===\n")
    print(
        "NOTE: Romania's reform is hypothetical (2025). "
        "All event times are pre-treatment (k = year − 2025 ∈ {−30, …, −1}).\n"
        "A flat pre-trend pattern supports parallel-trends for gsynth identification.\n"
    )

    df = pd.read_parquet(PROCESSED / "ro_panel_judet.parquet")
    df["event_time"] = df["year"] - REFORM_YEAR   # −30 to −1

    df, dummy_cols = add_event_dummies(df, ET_MIN, ET_MAX)

    all_coefs: dict[str, pd.DataFrame] = {}

    for outcome, label in OUTCOMES:
        print(f"\n[{outcome}]")
        coef_df = run_twfe(df, outcome, dummy_cols)
        if coef_df is not None:
            coef_df["outcome"] = outcome
            all_coefs[outcome] = coef_df
            plot_event_study(coef_df, outcome, label)

    if all_coefs:
        combined = pd.concat(all_coefs.values(), ignore_index=True)
        out_path = PROCESSED / "ro_eventstudy_coefs.parquet"
        combined.to_parquet(out_path, index=False)
        print(f"\nSaved → ro_eventstudy_coefs.parquet  ({len(combined)} rows)")
        print(f"Outcomes in parquet: {list(all_coefs.keys())}")

        # Quick pre-trend flatness summary
        print("\n--- Pre-trend flatness check (|β_k| > 2×SE flags) ---")
        for outcome, cdf in all_coefs.items():
            flags = cdf[(cdf["event_time"] != ET_REF) & (cdf["se"] > 0)]
            flags = flags[flags["coef"].abs() > 2 * flags["se"]]
            if len(flags) == 0:
                print(f"  {outcome}: flat pre-trend (no significant deviations)")
            else:
                print(f"  {outcome}: {len(flags)} significant pre-treatment coefficient(s)")
                print(flags[["event_time", "coef", "se"]].to_string(index=False))

    print("\n=== Stage 05 complete ===")


if __name__ == "__main__":
    main()
