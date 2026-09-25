"""
B2 — Barro β-convergence + IPS unit-root + interaction regime test + lambda diagnostic.

Reads: ro_panel_judet.parquet, ro_nuts3_suitability.parquet
Returns: dict with beta_K_hub, beta_K_sat, regime_test, diagnostics.

The block bootstrap uses vectorized two-way iterative demeaning (alternating
projections) plus a closed-form within-slope. This is the exact two-way
fixed-effects (LSDV) estimator by the Frisch-Waugh-Lovell theorem, but avoids
re-parsing a Patsy formula and rebuilding dummy matrices on every one of the
B=2000 draws. The point estimates (called a handful of times) use smf.ols.

Sign convention: the raw Barro lagged-level coefficient is negative under
convergence (a higher initial GVA level predicts slower subsequent growth).
We report beta_K as the convergence SPEED = -beta_corrected, a positive number,
because (i) the scenario engine multiplies beta_K by an accumulated capital
stock to produce a positive productivity uplift (a positive return-to-capital),
and (ii) half-life = ln(2)/beta_K is only meaningful for a positive speed.
A larger beta_K therefore means faster catch-up; beta_K_sat > beta_K_hub is the
expected "satellites converge faster than the hub" ordering.

Importable: call extract() to get the result dict.
Standalone: python scripts/calibration/B2_barro_convergence_gmm.py
"""
from __future__ import annotations

import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import statsmodels.formula.api as smf
from scipy import stats
from statsmodels.tsa.stattools import adfuller

ROOT = Path(__file__).resolve().parents[2]
PROCESSED = ROOT / "data" / "processed"

B = 2000
RNG_SEED = 42
DEMEAN_ITERS = 200       # alternating-projection sweeps; converges to machine precision
# IPS (2003) Table-style standardization constants for ADF(0) with intercept, T≈28.
IPS_E_T = -1.52
IPS_VAR_T = 0.90


def _git_sha() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=ROOT, stderr=subprocess.DEVNULL,
        ).decode().strip()
    except Exception:
        return "unknown"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _identify_hubs(panel: pd.DataFrame, suit: pd.DataFrame) -> set[str]:
    """Hub = highest-vitality county per NUTS2 (mirrors A0_build_engine_fixtures logic)."""
    suit = suit.copy()
    suit["nuts2_code"] = suit["nuts3_code"].str[:4]
    codes_in_panel = set(panel["nuts3_code"].unique())
    suit = suit[suit["nuts3_code"].isin(codes_in_panel)]
    hub_codes = set(
        suit.sort_values("vitality_index").groupby("nuts2_code").tail(1)["nuts3_code"]
    )
    return hub_codes


def _prepare_barro(panel: pd.DataFrame) -> pd.DataFrame:
    """Add lag and first-difference of ln_gva_per_empl."""
    df = panel.sort_values(["nuts3_code", "year"]).copy()
    df["lag_gva"] = df.groupby("nuts3_code")["ln_gva_per_empl"].shift(1)
    df["dy_gva"] = df.groupby("nuts3_code")["ln_gva_per_empl"].diff()
    return df.dropna(subset=["lag_gva", "dy_gva"])


def _fit_barro(subset: pd.DataFrame) -> tuple[float, float, float, int]:
    """Point estimate: county+year FE regression via LSDV. Returns (beta_corr, se, r2, nobs)."""
    n_periods = int(subset["year"].nunique())
    res = smf.ols(
        "dy_gva ~ lag_gva + C(nuts3_code) + C(year)",
        data=subset,
    ).fit(cov_type="HC3")
    beta_fe = float(res.params["lag_gva"])
    # Nickell (1981) first-order bias correction, derived for one-way individual FE
    # and standard in the Barro growth-empirics tradition (Islam 1995). With two-way
    # FE and T≈28 the residual bias is already small; this slightly over-corrects but
    # stays within the bootstrap CI.
    beta_corrected = beta_fe + (1 + beta_fe) / max(n_periods - 1, 1)
    # Report the convergence SPEED (positive). The Barro lagged-level coefficient is
    # negative under convergence (higher initial level → slower growth); the engine
    # consumes beta_K as a positive return-to-capital / catch-up speed, and
    # half-life = ln(2)/speed requires a positive value. See module note.
    return -beta_corrected, float(res.bse["lag_gva"]), float(res.rsquared), int(res.nobs)


def _demean_twoway(v: np.ndarray, unit_idx: np.ndarray, time_idx: np.ndarray,
                   unit_counts: np.ndarray, time_counts: np.ndarray) -> np.ndarray:
    """Absorb unit + time fixed effects by alternating projections (vectorized)."""
    v = v.astype(float).copy()
    for _ in range(DEMEAN_ITERS):
        um = np.bincount(unit_idx, weights=v, minlength=len(unit_counts)) / unit_counts
        v = v - um[unit_idx]
        tm = np.bincount(time_idx, weights=v, minlength=len(time_counts)) / time_counts
        v = v - tm[time_idx]
    return v


def _within_slope_corrected(dy: np.ndarray, lag: np.ndarray, unit_idx: np.ndarray,
                            time_idx: np.ndarray, n_periods: int) -> float:
    """Two-way FE within-slope of dy on lag, then Nickell bias correction."""
    unit_counts = np.bincount(unit_idx).astype(float)
    time_counts = np.bincount(time_idx).astype(float)
    dy_d = _demean_twoway(dy, unit_idx, time_idx, unit_counts, time_counts)
    lag_d = _demean_twoway(lag, unit_idx, time_idx, unit_counts, time_counts)
    denom = float(lag_d @ lag_d)
    if denom <= 1e-12:
        return float("nan")
    beta_fe = float(lag_d @ dy_d) / denom
    # Nickell one-way-FE bias correction (see _fit_barro for attribution/caveat).
    beta_corrected = beta_fe + (1 + beta_fe) / max(n_periods - 1, 1)
    return -beta_corrected  # convergence speed, positive (see _fit_barro)


def _block_bootstrap(subset: pd.DataFrame) -> tuple[float, float, float]:
    """Bootstrap beta_K by resampling whole county blocks with replacement.
    Each resampled replica gets a unique unit id so duplicates are distinct FE units.
    Returns (boot_se, ci_lo_90, ci_hi_90).
    """
    rng = np.random.default_rng(RNG_SEED)
    counties = subset["nuts3_code"].unique()
    # Pre-extract per-county numpy arrays once (avoid per-draw DataFrame filtering).
    by_county = {
        c: (g["dy_gva"].to_numpy(float), g["lag_gva"].to_numpy(float), g["year"].to_numpy())
        for c, g in subset.groupby("nuts3_code")
    }

    boot_betas: list[float] = []
    for _ in range(B):
        sampled = rng.choice(counties, size=len(counties), replace=True)
        dy_parts, lag_parts, unit_parts, year_parts = [], [], [], []
        for i, c in enumerate(sampled):
            dy_c, lag_c, year_c = by_county[c]
            dy_parts.append(dy_c)
            lag_parts.append(lag_c)
            unit_parts.append(np.full(len(dy_c), i))   # unique unit per replica
            year_parts.append(year_c)
        dy = np.concatenate(dy_parts)
        lag = np.concatenate(lag_parts)
        unit_idx = np.concatenate(unit_parts)
        years = np.concatenate(year_parts)
        time_idx = pd.factorize(years)[0]
        n_periods = int(np.unique(years).size)
        beta = _within_slope_corrected(dy, lag, unit_idx, time_idx, n_periods)
        if not np.isnan(beta):
            boot_betas.append(beta)

    if not boot_betas:
        return float("nan"), float("nan"), float("nan")
    arr = np.array(boot_betas)
    return (
        float(np.std(arr, ddof=1)),
        float(np.percentile(arr, 5)),
        float(np.percentile(arr, 95)),
    )


def _ips_test(panel: pd.DataFrame) -> tuple[float, float, str]:
    """Im-Pesaran-Shin panel unit-root test on ln_gva_per_empl.
    Returns (Z_stat, p_value, conclusion).
    """
    adf_stats: list[float] = []
    used_lags: list[int] = []
    for code in panel["nuts3_code"].unique():
        ts = panel[panel["nuts3_code"] == code]["ln_gva_per_empl"].dropna().values
        if len(ts) < 8:
            continue
        try:
            res_adf = adfuller(ts, autolag="AIC", regression="c")
            adf_stats.append(float(res_adf[0]))
            used_lags.append(int(res_adf[2]))  # AIC-selected lag order
        except Exception:
            continue

    if not adf_stats:
        return float("nan"), float("nan"), "insufficient data"

    t_bar = float(np.mean(adf_stats))
    N = len(adf_stats)
    Z = float(np.sqrt(N) * (t_bar - IPS_E_T) / np.sqrt(IPS_VAR_T))
    p_value = float(stats.norm.cdf(Z))  # left-tail: low p → stationary
    base = (
        "stationary (H0 of unit root rejected at 10%)"
        if p_value < 0.10
        else "non-stationary: unit root not rejected at 10%; Barro spec in Δy on lagged level is robust"
    )
    # The IPS_E_T / IPS_VAR_T constants are the asymptotic (lag p=0) standardization;
    # AIC selects p≥1 for some counties, so the |Z| is mildly overstated. Surface the
    # mean selected lag so this approximation is visible to the reader.
    mean_lag = float(np.mean(used_lags)) if used_lags else float("nan")
    conclusion = f"{base} (IPS constants use asymptotic p=0 approx.; mean AIC lag={mean_lag:.1f})"
    return Z, p_value, conclusion


def _lambda_comovement(panel: pd.DataFrame, hub_codes: set[str]) -> float:
    """Within-NUTS2 hub/satellite net_migration_rate co-movement (mean Pearson r across NUTS2).

    NaN years in net_migration_rate (common in early 1990s data) are dropped pairwise
    before computing the Pearson correlation to avoid propagating missingness into corrcoef.
    """
    panel = panel.copy()
    panel["nuts2_code"] = panel["nuts3_code"].str[:4]
    corrs: list[float] = []
    for nuts2 in panel["nuts2_code"].unique():
        sub = panel[panel["nuts2_code"] == nuts2]
        hubs = sub[sub["nuts3_code"].isin(hub_codes)]
        sats = sub[~sub["nuts3_code"].isin(hub_codes)]
        if hubs.empty or sats.empty:
            continue
        hub_mig = hubs.groupby("year")["net_migration_rate"].mean()
        sat_mig = sats.groupby("year")["net_migration_rate"].mean()
        common = hub_mig.index.intersection(sat_mig.index)
        # Drop years where either hub or satellite mean is NaN (e.g. early 1990s missingness)
        both = pd.DataFrame({"hub": hub_mig[common], "sat": sat_mig[common]}).dropna()
        if len(both) < 5:
            continue
        corr = float(np.corrcoef(both["hub"].values, both["sat"].values)[0, 1])
        if not np.isnan(corr):
            corrs.append(corr)
    return float(np.mean(corrs)) if corrs else float("nan")


def extract() -> dict:
    """Return calibration dict for beta_K_hub, beta_K_sat, regime_test, diagnostics."""
    panel = pd.read_parquet(PROCESSED / "ro_panel_judet.parquet")
    suit = pd.read_parquet(PROCESSED / "ro_nuts3_suitability.parquet")

    sha = _git_sha()
    ts = _now_iso()

    hub_codes = _identify_hubs(panel, suit)
    barro = _prepare_barro(panel)

    hub_df = barro[barro["nuts3_code"].isin(hub_codes)].copy()
    sat_df = barro[~barro["nuts3_code"].isin(hub_codes)].copy()

    # ── Hub Barro ────────────────────────────────────────────────────────────
    beta_hub, se_hub, r2_hub, nobs_hub = _fit_barro(hub_df)
    half_life_hub = float(np.log(2) / max(abs(beta_hub), 1e-9))
    boot_se_hub, ci_lo_hub, ci_hi_hub = _block_bootstrap(hub_df)

    # ── Satellite Barro ──────────────────────────────────────────────────────
    beta_sat, se_sat, r2_sat, nobs_sat = _fit_barro(sat_df)
    half_life_sat = float(np.log(2) / max(abs(beta_sat), 1e-9))
    boot_se_sat, ci_lo_sat, ci_hi_sat = _block_bootstrap(sat_df)

    # ── Interaction regime test ──────────────────────────────────────────────
    barro["is_hub"] = barro["nuts3_code"].isin(hub_codes).astype(int)
    barro["lag_x_hub"] = barro["lag_gva"] * barro["is_hub"]
    res_int = smf.ols(
        "dy_gva ~ lag_gva + lag_x_hub + C(nuts3_code) + C(year)",
        data=barro,
    ).fit(cov_type="HC3")
    regime_p = float(res_int.pvalues["lag_x_hub"])
    regime_t = float(res_int.tvalues["lag_x_hub"])
    regime_df = int(res_int.df_resid)

    # ── Stationarity (IPS) ───────────────────────────────────────────────────
    ips_z, ips_p, ips_concl = _ips_test(panel)

    # ── Lambda co-movement ───────────────────────────────────────────────────
    lc = _lambda_comovement(panel, hub_codes)

    def _prov(method, n_obs, r2, half_life, boot_se, ci_lo, ci_hi) -> dict:
        return {
            "method": method,
            "n_obs": n_obs,
            "r2": r2,
            "half_life_years": half_life,
            "boot_se": boot_se,
            "boot_ci_90": [ci_lo, ci_hi],
            "estimated_at": ts,
            "git_sha": sha,
        }

    return {
        "beta_K_hub": {
            "value": beta_hub,
            "se": boot_se_hub if not np.isnan(boot_se_hub) else se_hub,
            "id_strategy": "Barro LSDV (Nickell-corrected two-way FE), hub subset",
            "source": "ro_panel_judet.parquet",
            # support clamps the lower bound to 0 (engine needs a non-negative speed);
            # the unclipped bootstrap interval is preserved in provenance.boot_ci_90.
            "support": [max(ci_lo_hub, 0.0) if not np.isnan(ci_lo_hub) else 0.0,
                        ci_hi_hub if not np.isnan(ci_hi_hub) else 0.5],
            "provenance": _prov(
                "Barro beta-convergence, Nickell-corrected two-way FE (county+year), HC3 SE point est.; B=2000 block bootstrap (within-demeaning). Value = convergence speed |beta| (positive); half-life = ln(2)/value.",
                nobs_hub, r2_hub, half_life_hub, boot_se_hub, ci_lo_hub, ci_hi_hub,
            ),
        },
        "beta_K_sat": {
            "value": beta_sat,
            "se": boot_se_sat if not np.isnan(boot_se_sat) else se_sat,
            "id_strategy": "Barro LSDV (Nickell-corrected two-way FE), satellite subset",
            "source": "ro_panel_judet.parquet",
            "support": [max(ci_lo_sat, 0.0) if not np.isnan(ci_lo_sat) else 0.0,
                        ci_hi_sat if not np.isnan(ci_hi_sat) else 0.6],
            "provenance": _prov(
                "Barro beta-convergence, Nickell-corrected two-way FE (county+year), HC3 SE point est.; B=2000 block bootstrap (within-demeaning). Value = convergence speed |beta| (positive); half-life = ln(2)/value.",
                nobs_sat, r2_sat, half_life_sat, boot_se_sat, ci_lo_sat, ci_hi_sat,
            ),
        },
        "regime_test": {
            "p_value": regime_p,
            "stat": regime_t,
            "df": regime_df,
        },
        "diagnostics": {
            "ips_stat": ips_z,
            "ips_pvalue": ips_p,
            "conclusion": ips_concl,
            "lambda_comovement": lc,
        },
    }


if __name__ == "__main__":
    result = extract()
    print(json.dumps(result, indent=2, default=str))
