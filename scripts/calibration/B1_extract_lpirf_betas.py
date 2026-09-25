"""
B1 — LP-IRF beta extraction.

Reads ro_lp_irfs.parquet and ro_sdid_estimates.parquet.
Extracts beta_gov (ln_gva_per_empl, h=1-3 mean) and beta_mig
(net_migration_rate, h=1-3 mean) with block-bootstrap SEs and
a SDiD cross-check for beta_gov.

Importable: call extract() to get the result dict.
Standalone: python scripts/calibration/B1_extract_lpirf_betas.py
"""
from __future__ import annotations

import json
import subprocess
import warnings
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
PROCESSED = ROOT / "data" / "processed"

HORIZONS = [1, 2, 3]
B = 2000
RNG_SEED = 42
BASE_YEAR = 2000
AGREE_RATIO_THRESH = 3.0  # |lpirf/sdid| outside [1/3, 3] → disagree
MIN_OBS_FOR_REGRESSION = 10  # OLS needs comfortably more rows than parameters; conservative floor


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


def _mean_h1_3(irfs: pd.DataFrame, outcome: str) -> tuple[float, float, int]:
    """Return (mean_coef, mean_se, nobs) for h=1,2,3 of an outcome."""
    sub = irfs[(irfs["outcome"] == outcome) & (irfs["horizon"].isin(HORIZONS))].sort_values("horizon")
    if sub.empty:
        return float("nan"), float("nan"), 0
    found = set(int(h) for h in sub["horizon"].tolist())
    if found != set(HORIZONS):
        warnings.warn(
            f"_mean_h1_3({outcome!r}): expected horizons {set(HORIZONS)}, found {found}. "
            "Mean computed over available horizons only.",
            stacklevel=2,
        )
    return float(sub["coef"].mean()), float(sub["se"].mean()), int(sub["nobs"].iloc[0])


def _bootstrap_lp(panel: pd.DataFrame, outcome: str) -> tuple[float, float, float]:
    """Block bootstrap (resample counties) for mean LP-IRF coef at h=1,2,3.

    The cross-sectional LP at each horizon regresses (y_target − y_base) on the
    binary ``treated`` indicator. With a single binary regressor and an intercept,
    the OLS slope equals the difference in group means (mean_treated − mean_control),
    so we compute it in closed form. This is numerically identical to
    ``smf.ols("lhs ~ treated")`` but avoids re-parsing a Patsy formula on every one
    of the ~12k bootstrap fits, and a plain dict lookup replaces pandas ``.loc``
    MultiIndex scalar indexing (~14 ms/call, prohibitive in this hot loop).

    Returns (boot_se, ci_lo_90, ci_hi_90).
    """
    rng = np.random.default_rng(RNG_SEED)
    counties = panel["nuts3_code"].unique()

    # O(1) dict lookup keyed by (county, year).
    sub = panel[["nuts3_code", "year", outcome, "treated"]].dropna()
    lookup: dict[tuple[str, int], tuple[float, float]] = {
        (code, int(year)): (float(val), float(treated))
        for code, year, val, treated in sub.itertuples(index=False, name=None)
    }

    boot_betas: list[float] = []
    for _ in range(B):
        sampled = rng.choice(counties, size=len(counties), replace=True)
        h_betas: list[float] = []
        for h in HORIZONS:
            target_year = BASE_YEAR + h
            lhs_vals: list[float] = []
            trt_vals: list[float] = []
            for code in sampled:
                base = lookup.get((code, BASE_YEAR))
                tgt = lookup.get((code, target_year))
                if base is None or tgt is None:
                    continue
                lhs_vals.append(tgt[0] - base[0])
                trt_vals.append(base[1])
            if len(lhs_vals) < MIN_OBS_FOR_REGRESSION:
                continue
            lhs_arr = np.asarray(lhs_vals)
            trt_arr = np.asarray(trt_vals)
            treated_mask = trt_arr == 1
            if treated_mask.all() or not treated_mask.any():
                continue  # need both treated and control to identify the slope
            # OLS slope on a binary regressor = difference in group means.
            h_betas.append(float(lhs_arr[treated_mask].mean() - lhs_arr[~treated_mask].mean()))
        if h_betas:
            boot_betas.append(float(np.mean(h_betas)))

    if not boot_betas:
        return float("nan"), float("nan"), float("nan")
    arr = np.array(boot_betas)
    return (
        float(np.std(arr, ddof=1)),
        float(np.percentile(arr, 5)),
        float(np.percentile(arr, 95)),
    )


def _sdid_att(sdid: pd.DataFrame, outcome: str) -> float | None:
    """Extract SDiD ATT for a given outcome.

    Tries the 'SDiD' estimator first (as stored in ro_sdid_estimates.parquet),
    falls back to any available row for the outcome.
    Returns None if the outcome is not present in the SDiD table.
    """
    # Try exact SDiD estimator (capital-cased as stored in the parquet)
    sub = sdid[(sdid["outcome"] == outcome) & (sdid["estimator"] == "SDiD")]
    if sub.empty:
        # Fallback: case-insensitive match on estimator column
        sub = sdid[(sdid["outcome"] == outcome) & (sdid["estimator"].str.lower() == "sdid")]
    if sub.empty:
        # Last resort: any estimator for this outcome
        sub = sdid[sdid["outcome"] == outcome]
    if sub.empty:
        return None
    return float(sub["att"].iloc[0])


def extract() -> dict:
    """Return calibration dict for beta_gov and beta_mig with provenance.

    LP-IRF estimates (h=1–3 mean) are read directly from ro_lp_irfs.parquet.
    Block-bootstrap SEs are computed by resampling the county index B=2000 times
    and re-running the cross-sectional LP regression for each draw.

    SDiD cross-check: if 'ln_gva_per_empl' appears in ro_sdid_estimates.parquet,
    the LP-IRF/SDiD ratio is computed; otherwise the check reports agree=False
    with ratio=NaN (outcome absent from SDiD table is a data limitation, not a
    contradiction).

    Returns
    -------
    dict with keys: beta_gov, beta_mig, diagnostics.
    """
    irfs = pd.read_parquet(PROCESSED / "ro_lp_irfs.parquet")
    sdid = pd.read_parquet(PROCESSED / "ro_sdid_estimates.parquet")
    panel = pd.read_parquet(PROCESSED / "ro_panel_judet.parquet")

    sha = _git_sha()
    ts = _now_iso()

    # ── beta_gov ─────────────────────────────────────────────────────────────
    val_gov, se_gov, nobs_gov = _mean_h1_3(irfs, "ln_gva_per_empl")
    boot_se_gov, ci_lo_gov, ci_hi_gov = _bootstrap_lp(panel, "ln_gva_per_empl")

    # ── beta_mig ─────────────────────────────────────────────────────────────
    # The IRF is the response of net migration to the reform DEMOTION (a negative
    # shock: demotion drove out-migration, so the raw coefficient is negative). The
    # engine lever `mu` is a retention SUBSIDY — the inverse intervention — so the
    # subsidy elasticity is the negation of the demotion IRF (sign-flipped, magnitude
    # preserved). Without this flip the engine would make a retention subsidy
    # depopulate the region it subsidizes (the same wrong-sign trap that kept
    # beta_fert a prior). The CI bounds flip and reorder accordingly; boot_se is
    # invariant under negation. The estimate is essentially pre-treatment (placeholder
    # reform_year=2025) and very noisy — the wide CI is surfaced honestly.
    val_mig_raw, se_mig, nobs_mig = _mean_h1_3(irfs, "net_migration_rate")
    boot_se_mig, ci_lo_raw, ci_hi_raw = _bootstrap_lp(panel, "net_migration_rate")
    val_mig = -val_mig_raw
    ci_lo_mig = -ci_hi_raw if not np.isnan(ci_hi_raw) else float("nan")
    ci_hi_mig = -ci_lo_raw if not np.isnan(ci_lo_raw) else float("nan")

    # ── SDiD cross-check for beta_gov ────────────────────────────────────────
    # Note: ro_sdid_estimates.parquet covers ln_population, nat_change_rate,
    # and net_migration_rate.  ln_gva_per_empl was not included in the SDiD run,
    # so sdid_att will be None → ratio=nan, agree=False (data limitation).
    sdid_att_gov = _sdid_att(sdid, "ln_gva_per_empl")
    if sdid_att_gov is not None and abs(sdid_att_gov) > 1e-9:
        ratio = val_gov / sdid_att_gov
    else:
        ratio = float("nan")
    agree = (
        sdid_att_gov is not None
        and not np.isnan(ratio)
        and (1 / AGREE_RATIO_THRESH <= abs(ratio) <= AGREE_RATIO_THRESH)
    )

    return {
        "beta_gov": {
            "value": val_gov,
            "se": boot_se_gov if not np.isnan(boot_se_gov) else se_gov,
            "id_strategy": "LP-IRF h1-3 (reform treatment)",
            "source": "ro_lp_irfs.parquet",
            "support": [
                ci_lo_gov if not np.isnan(ci_lo_gov) else 0.0,
                ci_hi_gov if not np.isnan(ci_hi_gov) else 1.0,
            ],
            "provenance": {
                "method": "Cross-sectional LP (Jordà 2005), h=1-3 annualized mean, HC3 SEs",
                "n_obs": nobs_gov,
                "boot_se": boot_se_gov,
                "boot_ci_90": [ci_lo_gov, ci_hi_gov],
                "estimated_at": ts,
                "git_sha": sha,
            },
        },
        "beta_mig": {
            "value": val_mig,
            "se": boot_se_mig if not np.isnan(boot_se_mig) else se_mig,
            "id_strategy": "LP-IRF h1-3, sign-flipped for subsidy (reform-shock PROXY, not €/cap)",
            "source": "ro_lp_irfs.parquet",
            "support": [
                ci_lo_mig if not np.isnan(ci_lo_mig) else 0.0,
                ci_hi_mig if not np.isnan(ci_hi_mig) else 400.0,
            ],
            "provenance": {
                "method": (
                    "Cross-sectional LP (Jordà 2005), net_migration_rate, h=1-3 mean, "
                    "sign-flipped: a retention subsidy is the inverse of the demotion shock "
                    "the IRF identifies. Reform-shock PROXY (not a €/cap subsidy elasticity); "
                    "essentially pre-treatment and noisy — see the wide 90% CI."
                ),
                "n_obs": nobs_mig,
                "boot_se": boot_se_mig,
                "boot_ci_90": [ci_lo_mig, ci_hi_mig],
                "estimated_at": ts,
                "git_sha": sha,
            },
        },
        "diagnostics": {
            "beta_gov_sdid_crosscheck": {
                "lpirf": val_gov,
                "sdid": sdid_att_gov if sdid_att_gov is not None else float("nan"),
                "ratio": ratio,
                "agree": agree,
            },
        },
    }


if __name__ == "__main__":
    result = extract()
    print(json.dumps(result, indent=2, default=str))
