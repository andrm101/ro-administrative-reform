# Calibration Pipeline + Interface V1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace v0 literature priors in `elasticities.json` with empirically-estimated coefficients, then refine the Policy Lab panel to show % / p.p. units, four cost framings, and provenance tooltips on every metric.

**Architecture:** Four Python calibration scripts (B0–B3) read from `data/processed/*.parquet` and write a single `data/dashboard/elasticities.json` with enriched provenance metadata; four TypeScript interface tasks then consume the new schema to deliver a decision-maker-ready Policy Lab panel. The engine code in `dashboard/src/engine/` is untouched.

**Tech Stack:** Python 3.11 + pandas 2.2 + statsmodels 0.14 + scipy 1.11 + numpy 1.26; TypeScript 5 + React 18 + Vitest 2 + Tailwind CSS + Recharts.

---

## File Structure

**Created:**
- `scripts/calibration/B1_extract_lpirf_betas.py` — LP-IRF beta_gov + beta_mig extraction + block bootstrap + SDiD cross-check
- `scripts/calibration/B2_barro_convergence_gmm.py` — Barro convergence beta_K + IPS unit-root test + interaction regime test + lambda diagnostic
- `scripts/calibration/B3_oos_validation_gate.py` — hold-out OOS validation, flips `provisional` flag
- `scripts/calibration/B0_run_calibration.py` — orchestrator: calls B1→B2→B3, assembles + writes `elasticities.json`
- `scripts/calibration/tests/test_B1.py` — pytest for B1
- `scripts/calibration/tests/test_B2.py` — pytest for B2
- `scripts/calibration/tests/test_B3.py` — pytest for B3
- `dashboard/src/utils/format.ts` — pure unit-conversion helpers (lnDeltaToPct, formatPct, etc.)
- `dashboard/src/utils/format.test.ts` — Vitest unit tests
- `dashboard/src/components/MetricTooltip.tsx` — ⓘ icon + CSS-hover provenance popover

**Modified:**
- `dashboard/src/types.ts` — extend `Elasticity` with optional `provenance`; add `ElasticityProvenance`, `RegimeTest`, `CalibrationDiagnostics`; extend `Elasticities` with optional `regime_test` + `diagnostics`
- `dashboard/src/components/CostReadout.tsx` — four cost framings, uses format.ts
- `dashboard/src/components/RegimeBadge.tsx` — optional p-value display
- `dashboard/src/components/PolicyLab.tsx` — headline band, % uplift chart, metrics row with ⓘ, collapsed levers, convention legend
- `dashboard/src/components/LeverPanel.tsx` — group-level collapse/expand toggle (default: all collapsed)

---

## Task 1: B1 — LP-IRF beta extraction

**Context:** `data/processed/ro_lp_irfs.parquet` has columns `outcome, horizon, coef, se, ci_lo_90, ci_hi_90, ci_lo_95, ci_hi_95, nobs`. Horizons run 0–24 (years since BASE_YEAR=2000). `data/processed/ro_sdid_estimates.parquet` has `outcome, estimator, att, se, ci_lo, ci_hi, n_units, n_years`. The block bootstrap resamples county indices across the cross-sectional regressions.

**Files:**
- Create: `scripts/calibration/tests/test_B1.py`
- Create: `scripts/calibration/B1_extract_lpirf_betas.py`

- [ ] **Step 1: Create directory and write the failing test**

```bash
mkdir -p scripts/calibration/tests
touch scripts/calibration/__init__.py scripts/calibration/tests/__init__.py
```

Write `scripts/calibration/tests/test_B1.py`:

```python
"""Tests for B1_extract_lpirf_betas — run from repo root with:
   conda run -n ro-admin-reform pytest scripts/calibration/tests/test_B1.py -v
"""
import pytest, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "scripts" / "calibration"))


def test_imports():
    import B1_extract_lpirf_betas as B1  # noqa: F401 — import must not raise


def test_returns_required_keys():
    import B1_extract_lpirf_betas as B1
    result = B1.extract()
    assert "beta_gov" in result
    assert "beta_mig" in result
    assert "diagnostics" in result


def test_beta_gov_value_is_float():
    import B1_extract_lpirf_betas as B1
    result = B1.extract()
    assert isinstance(result["beta_gov"]["value"], float)


def test_beta_mig_value_is_float():
    import B1_extract_lpirf_betas as B1
    result = B1.extract()
    assert isinstance(result["beta_mig"]["value"], float)


def test_provenance_keys_present():
    import B1_extract_lpirf_betas as B1
    result = B1.extract()
    prov = result["beta_gov"]["provenance"]
    for key in ("method", "n_obs", "boot_se", "boot_ci_90", "estimated_at", "git_sha"):
        assert key in prov, f"missing provenance key: {key}"


def test_sdid_crosscheck_present():
    import B1_extract_lpirf_betas as B1
    result = B1.extract()
    xcheck = result["diagnostics"]["beta_gov_sdid_crosscheck"]
    for key in ("lpirf", "sdid", "ratio", "agree"):
        assert key in xcheck, f"missing crosscheck key: {key}"
```

- [ ] **Step 2: Run test — expect ImportError (module doesn't exist yet)**

```powershell
cd C:\Users\andre\Desktop\Sandbox\RO-Administrative-Reform
conda run -n ro-admin-reform pytest scripts/calibration/tests/test_B1.py -v 2>&1 | Select-Object -First 20
```

Expected: `ImportError: No module named 'B1_extract_lpirf_betas'`

- [ ] **Step 3: Write `scripts/calibration/B1_extract_lpirf_betas.py`**

```python
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
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import statsmodels.formula.api as smf

ROOT = Path(__file__).resolve().parents[2]
PROCESSED = ROOT / "data" / "processed"

HORIZONS = [1, 2, 3]
B = 2000
RNG_SEED = 42
BASE_YEAR = 2000
AGREE_RATIO_THRESH = 3.0  # |lpirf/sdid| outside [1/3, 3] → disagree


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
    return float(sub["coef"].mean()), float(sub["se"].mean()), int(sub["nobs"].iloc[0]) if len(sub) else 0


def _bootstrap_lp(panel: pd.DataFrame, outcome: str) -> tuple[float, float, float]:
    """Block bootstrap (resample counties) for mean LP-IRF coef at h=1,2,3.
    Returns (boot_se, ci_lo_90, ci_hi_90).
    """
    rng = np.random.default_rng(RNG_SEED)
    counties = panel["nuts3_code"].unique()
    boot_betas: list[float] = []

    for _ in range(B):
        sampled = rng.choice(counties, size=len(counties), replace=True)
        h_betas: list[float] = []

        for h in HORIZONS:
            target_year = BASE_YEAR + h
            rows = []
            for code in sampled:
                base_row = panel[(panel["nuts3_code"] == code) & (panel["year"] == BASE_YEAR)]
                tgt_row = panel[(panel["nuts3_code"] == code) & (panel["year"] == target_year)]
                if base_row.empty or tgt_row.empty:
                    continue
                rows.append({
                    "lhs": float(tgt_row[outcome].iloc[0]) - float(base_row[outcome].iloc[0]),
                    "treated": float(base_row["treated"].iloc[0]),
                })

            if not rows:
                continue
            df_h = pd.DataFrame(rows).dropna()
            if df_h["treated"].nunique() < 2 or len(df_h) < 10:
                continue
            try:
                coef = smf.ols("lhs ~ treated", data=df_h).fit().params["treated"]
                h_betas.append(float(coef))
            except Exception:
                continue

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
    sub = sdid[(sdid["outcome"] == outcome) & (sdid["estimator"] == "sdid")]
    if sub.empty:
        sub = sdid[sdid["outcome"] == outcome]
    if sub.empty:
        return None
    return float(sub["att"].iloc[0])


def extract() -> dict:
    """Return calibration dict for beta_gov and beta_mig with provenance."""
    irfs = pd.read_parquet(PROCESSED / "ro_lp_irfs.parquet")
    sdid = pd.read_parquet(PROCESSED / "ro_sdid_estimates.parquet")
    panel = pd.read_parquet(PROCESSED / "ro_panel_judet.parquet")

    sha = _git_sha()
    ts = _now_iso()

    # ── beta_gov ────────────────────────────────────────────────────────────
    val_gov, se_gov, nobs_gov = _mean_h1_3(irfs, "ln_gva_per_empl")
    boot_se_gov, ci_lo_gov, ci_hi_gov = _bootstrap_lp(panel, "ln_gva_per_empl")

    # ── beta_mig ────────────────────────────────────────────────────────────
    val_mig, se_mig, nobs_mig = _mean_h1_3(irfs, "net_migration_rate")
    boot_se_mig, ci_lo_mig, ci_hi_mig = _bootstrap_lp(panel, "net_migration_rate")

    # ── SDiD cross-check for beta_gov ───────────────────────────────────────
    sdid_att = _sdid_att(sdid, "ln_gva_per_empl")
    if sdid_att is not None and abs(sdid_att) > 1e-9:
        ratio = val_gov / sdid_att
    else:
        ratio = float("nan")
    agree = (sdid_att is not None) and (1 / AGREE_RATIO_THRESH <= abs(ratio) <= AGREE_RATIO_THRESH)

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
            "id_strategy": "LP-IRF h1-3 (reform-shock PROXY, not €/cap)",
            "source": "ro_lp_irfs.parquet",
            "support": [
                ci_lo_mig if not np.isnan(ci_lo_mig) else 0.0,
                ci_hi_mig if not np.isnan(ci_hi_mig) else 400.0,
            ],
            "provenance": {
                "method": "Cross-sectional LP (Jordà 2005), net_migration_rate, h=1-3 mean. Reform-shock proxy only.",
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
                "sdid": sdid_att if sdid_att is not None else float("nan"),
                "ratio": ratio,
                "agree": agree,
            },
        },
    }


if __name__ == "__main__":
    result = extract()
    print(json.dumps(result, indent=2, default=str))
```

- [ ] **Step 4: Run tests — expect PASS**

```powershell
conda run -n ro-admin-reform pytest scripts/calibration/tests/test_B1.py -v
```

Expected:
```
PASSED tests/test_B1.py::test_imports
PASSED tests/test_B1.py::test_returns_required_keys
PASSED tests/test_B1.py::test_beta_gov_value_is_float
PASSED tests/test_B1.py::test_beta_mig_value_is_float
PASSED tests/test_B1.py::test_provenance_keys_present
PASSED tests/test_B1.py::test_sdid_crosscheck_present
6 passed
```

- [ ] **Step 5: Commit**

```bash
git add scripts/calibration/
git commit -m "feat(calib): B1 LP-IRF beta extraction + block bootstrap"
```

---

## Task 2: B2 — Barro convergence + stationarity + regime test

**Context:** `ro_panel_judet.parquet` has N≈42 counties × T≈30 years with columns `nuts3_code, year, ln_gva_per_empl, ln_population, nat_change_rate, net_migration_rate, treated`. Hub identification uses highest vitality per NUTS2 from `ro_nuts3_suitability.parquet`. Barro convergence: Δln_gva = β_K × lag_ln_gva + county_FE + year_FE. Nickell bias correction: β_corrected = β_FE + (1 + β_FE) / (T − 1). Block bootstrap resamples county IDs with replacement, duplicating their full time series.

**Files:**
- Create: `scripts/calibration/tests/test_B2.py`
- Create: `scripts/calibration/B2_barro_convergence_gmm.py`

- [ ] **Step 1: Write the failing test**

Write `scripts/calibration/tests/test_B2.py`:

```python
"""Tests for B2_barro_convergence_gmm — run from repo root:
   conda run -n ro-admin-reform pytest scripts/calibration/tests/test_B2.py -v
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "scripts" / "calibration"))


def test_imports():
    import B2_barro_convergence_gmm as B2  # noqa: F401


def test_returns_required_keys():
    import B2_barro_convergence_gmm as B2
    result = B2.extract()
    for key in ("beta_K_hub", "beta_K_sat", "regime_test", "diagnostics"):
        assert key in result, f"missing key: {key}"


def test_beta_K_sat_greater_than_hub():
    """Satellites should have higher convergence speed than hub (catch-up > agglomeration)."""
    import B2_barro_convergence_gmm as B2
    result = B2.extract()
    assert result["beta_K_sat"]["value"] > result["beta_K_hub"]["value"], (
        "Expected beta_K_sat > beta_K_hub (satellite catch-up > hub convergence)"
    )


def test_betas_positive():
    import B2_barro_convergence_gmm as B2
    result = B2.extract()
    assert result["beta_K_hub"]["value"] > 0
    assert result["beta_K_sat"]["value"] > 0


def test_regime_test_keys():
    import B2_barro_convergence_gmm as B2
    result = B2.extract()
    rt = result["regime_test"]
    for key in ("p_value", "stat", "df"):
        assert key in rt
    assert 0 <= rt["p_value"] <= 1


def test_ips_diagnostics():
    import B2_barro_convergence_gmm as B2
    result = B2.extract()
    diag = result["diagnostics"]
    for key in ("ips_stat", "ips_pvalue", "conclusion", "lambda_comovement"):
        assert key in diag


def test_lambda_comovement_range():
    import B2_barro_convergence_gmm as B2
    result = B2.extract()
    lc = result["diagnostics"]["lambda_comovement"]
    assert -1 <= lc <= 1, f"lambda_comovement {lc} outside [-1,1]"
```

- [ ] **Step 2: Run test — expect ImportError**

```powershell
conda run -n ro-admin-reform pytest scripts/calibration/tests/test_B2.py -v 2>&1 | Select-Object -First 10
```

Expected: `ImportError: No module named 'B2_barro_convergence_gmm'`

- [ ] **Step 3: Write `scripts/calibration/B2_barro_convergence_gmm.py`**

```python
"""
B2 — Barro β-convergence + IPS unit-root + interaction regime test + lambda diagnostic.

Reads: ro_panel_judet.parquet, ro_nuts3_suitability.parquet
Returns: dict with beta_K_hub, beta_K_sat, regime_test, diagnostics.

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
# IPS (2003) Table 1 constants for ADF(0) with intercept, T≈28
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
    """Fit county + year FE regression. Returns (beta_fe, nickell_corrected, r2, nobs)."""
    T_periods = int(subset["year"].nunique())
    res = smf.ols(
        "dy_gva ~ lag_gva + C(nuts3_code) + C(year)",
        data=subset,
    ).fit(cov_type="HC3")
    beta_fe = float(res.params["lag_gva"])
    # Nickell (1981) bias: plim(β_FE - β) ≈ -(1+β)/(T-1)
    beta_corrected = beta_fe + (1 + beta_fe) / max(T_periods - 1, 1)
    return beta_corrected, float(res.bse["lag_gva"]), float(res.rsquared), int(res.nobs)


def _block_bootstrap(subset: pd.DataFrame, role: str) -> tuple[float, float, float]:
    """Bootstrap beta_K by resampling county blocks. Returns (boot_se, ci_lo_90, ci_hi_90)."""
    rng = np.random.default_rng(RNG_SEED)
    counties = subset["nuts3_code"].unique()
    boot_betas: list[float] = []

    for _ in range(B):
        sampled = rng.choice(counties, size=len(counties), replace=True)
        panels = []
        for i, code in enumerate(sampled):
            chunk = subset[subset["nuts3_code"] == code].copy()
            chunk["nuts3_code"] = f"{code}_{i}"  # unique ID to preserve FE structure
            panels.append(chunk)
        boot_df = pd.concat(panels, ignore_index=True)
        try:
            beta_corr, _, _, _ = _fit_barro(boot_df)
            boot_betas.append(beta_corr)
        except Exception:
            continue

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
    for code in panel["nuts3_code"].unique():
        ts = panel[panel["nuts3_code"] == code]["ln_gva_per_empl"].dropna().values
        if len(ts) < 8:
            continue
        try:
            stat = float(adfuller(ts, autolag="AIC", regression="c")[0])
            adf_stats.append(stat)
        except Exception:
            continue

    if not adf_stats:
        return float("nan"), float("nan"), "insufficient data"

    t_bar = float(np.mean(adf_stats))
    N = len(adf_stats)
    Z = float(np.sqrt(N) * (t_bar - IPS_E_T) / np.sqrt(IPS_VAR_T))
    p_value = float(stats.norm.cdf(Z))  # left-tail: low p → stationary
    conclusion = (
        "stationary (H0 of unit root rejected at 10%)"
        if p_value < 0.10
        else "non-stationary: unit root not rejected at 10%; Barro spec in Δy on lagged level is robust"
    )
    return Z, p_value, conclusion


def _lambda_comovement(panel: pd.DataFrame, hub_codes: set[str]) -> float:
    """Within-NUTS2 hub/satellite net_migration_rate co-movement (Pearson r, mean across NUTS2)."""
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
        if len(common) < 5:
            continue
        corr = float(np.corrcoef(hub_mig[common].values, sat_mig[common].values)[0, 1])
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
    boot_se_hub, ci_lo_hub, ci_hi_hub = _block_bootstrap(hub_df, "hub")

    # ── Satellite Barro ──────────────────────────────────────────────────────
    beta_sat, se_sat, r2_sat, nobs_sat = _fit_barro(sat_df)
    half_life_sat = float(np.log(2) / max(abs(beta_sat), 1e-9))
    boot_se_sat, ci_lo_sat, ci_hi_sat = _block_bootstrap(sat_df, "sat")

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
            "id_strategy": "Barro GMM, hub subset",
            "source": "ro_panel_judet.parquet",
            "support": [max(ci_lo_hub, 0.0) if not np.isnan(ci_lo_hub) else 0.0,
                        ci_hi_hub if not np.isnan(ci_hi_hub) else 0.5],
            "provenance": _prov(
                "Barro β-convergence, Nickell-corrected LSDV (county+year FE), HC3 SEs, B=2000 block bootstrap",
                nobs_hub, r2_hub, half_life_hub, boot_se_hub, ci_lo_hub, ci_hi_hub,
            ),
        },
        "beta_K_sat": {
            "value": beta_sat,
            "se": boot_se_sat if not np.isnan(boot_se_sat) else se_sat,
            "id_strategy": "Barro GMM, satellite subset",
            "source": "ro_panel_judet.parquet",
            "support": [max(ci_lo_sat, 0.0) if not np.isnan(ci_lo_sat) else 0.0,
                        ci_hi_sat if not np.isnan(ci_hi_sat) else 0.6],
            "provenance": _prov(
                "Barro β-convergence, Nickell-corrected LSDV (county+year FE), HC3 SEs, B=2000 block bootstrap",
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
```

- [ ] **Step 4: Run tests — expect PASS**

```powershell
conda run -n ro-admin-reform pytest scripts/calibration/tests/test_B2.py -v
```

Expected: `7 passed`

Note: B2 runs ~2000 bootstraps — allow 5–15 minutes.

- [ ] **Step 5: Commit**

```bash
git add scripts/calibration/B2_barro_convergence_gmm.py scripts/calibration/tests/test_B2.py
git commit -m "feat(calib): B2 Barro GMM + IPS test + block bootstrap"
```

---

## Task 3: B3 — OOS validation gate

**Context:** Hold out 1995–2004 as test set; estimate Barro β on 2005–2023 training set. Predict 1995–2004 growth using training β and training county FE. Gate: RMSE ≤ 1.5 × in-sample residual SD → `provisional: false`. Uses the combined panel (hub + satellites).

**Files:**
- Create: `scripts/calibration/tests/test_B3.py`
- Create: `scripts/calibration/B3_oos_validation_gate.py`

- [ ] **Step 1: Write the failing test**

Write `scripts/calibration/tests/test_B3.py`:

```python
"""Tests for B3_oos_validation_gate — run from repo root:
   conda run -n ro-admin-reform pytest scripts/calibration/tests/test_B3.py -v
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "scripts" / "calibration"))


def test_imports():
    import B3_oos_validation_gate as B3  # noqa: F401


def test_returns_required_keys():
    import B3_oos_validation_gate as B3
    result = B3.run()
    for key in ("provisional", "rmse", "threshold", "conclusion"):
        assert key in result, f"missing key: {key}"


def test_provisional_is_bool():
    import B3_oos_validation_gate as B3
    result = B3.run()
    assert isinstance(result["provisional"], bool)


def test_rmse_positive():
    import B3_oos_validation_gate as B3
    result = B3.run()
    assert result["rmse"] > 0


def test_threshold_positive():
    import B3_oos_validation_gate as B3
    result = B3.run()
    assert result["threshold"] > 0


def test_synthetic_gate_pass():
    """Synthetic test: when RMSE equals threshold, gate passes (provisional=False)."""
    import B3_oos_validation_gate as B3
    # Synthetic result at gate boundary
    assert B3._gate_decision(rmse=1.0, threshold=1.5) is False  # rmse <= threshold → not provisional


def test_synthetic_gate_fail():
    """Synthetic test: RMSE exceeds threshold → provisional=True."""
    import B3_oos_validation_gate as B3
    assert B3._gate_decision(rmse=2.0, threshold=1.5) is True
```

- [ ] **Step 2: Run test — expect ImportError**

```powershell
conda run -n ro-admin-reform pytest scripts/calibration/tests/test_B3.py -v 2>&1 | Select-Object -First 10
```

Expected: `ImportError: No module named 'B3_oos_validation_gate'`

- [ ] **Step 3: Write `scripts/calibration/B3_oos_validation_gate.py`**

```python
"""
B3 — OOS validation gate.

Estimates Barro β on 2005-2023 training data, predicts 1995-2004 hold-out.
RMSE ≤ 1.5 × in-sample residual SD → provisional: False (gate passes).

Importable: call run() to get the result dict.
Standalone: python scripts/calibration/B3_oos_validation_gate.py
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import statsmodels.formula.api as smf

ROOT = Path(__file__).resolve().parents[2]
PROCESSED = ROOT / "data" / "processed"

TRAIN_START = 2005
HOLDOUT_END = 2004
RMSE_MULTIPLIER = 1.5


def _gate_decision(rmse: float, threshold: float) -> bool:
    """Return True (provisional) if RMSE exceeds threshold."""
    return rmse > threshold


def run() -> dict:
    """Run OOS validation. Returns dict with provisional, rmse, threshold, conclusion."""
    panel = pd.read_parquet(PROCESSED / "ro_panel_judet.parquet")
    panel = panel.sort_values(["nuts3_code", "year"]).copy()
    panel["lag_gva"] = panel.groupby("nuts3_code")["ln_gva_per_empl"].shift(1)
    panel["dy_gva"] = panel.groupby("nuts3_code")["ln_gva_per_empl"].diff()
    panel = panel.dropna(subset=["lag_gva", "dy_gva"])

    train = panel[panel["year"] >= TRAIN_START].copy()
    holdout = panel[panel["year"] <= HOLDOUT_END].copy()

    if train.empty or holdout.empty:
        return {
            "provisional": True,
            "rmse": float("nan"),
            "threshold": float("nan"),
            "conclusion": "insufficient data for split",
        }

    # Fit Barro on training period (county + year FE via LSDV)
    res_train = smf.ols(
        "dy_gva ~ lag_gva + C(nuts3_code) + C(year)",
        data=train,
    ).fit()
    beta_train = float(res_train.params["lag_gva"])

    # County FE = mean of (dy_gva - beta * lag_gva) per county in training
    train["resid_no_lag"] = train["dy_gva"] - beta_train * train["lag_gva"]
    county_fe = train.groupby("nuts3_code")["resid_no_lag"].mean().to_dict()

    # Predict on holdout: alpha_i + beta * lag_gva
    holdout = holdout[holdout["nuts3_code"].isin(county_fe)].copy()
    holdout["pred"] = (
        holdout["nuts3_code"].map(county_fe).fillna(0.0) + beta_train * holdout["lag_gva"]
    )
    holdout = holdout.dropna(subset=["pred", "dy_gva"])

    rmse_oos = float(np.sqrt(np.mean((holdout["dy_gva"] - holdout["pred"]) ** 2)))
    resid_sd = float(np.std(res_train.resid))
    threshold = RMSE_MULTIPLIER * resid_sd
    provisional = _gate_decision(rmse_oos, threshold)

    conclusion = (
        f"OOS RMSE {rmse_oos:.4f} ≤ threshold {threshold:.4f} → gate PASSES (provisional=False)"
        if not provisional
        else f"OOS RMSE {rmse_oos:.4f} > threshold {threshold:.4f} → gate FAILS (provisional=True)"
    )

    return {
        "provisional": provisional,
        "rmse": rmse_oos,
        "threshold": threshold,
        "conclusion": conclusion,
    }


if __name__ == "__main__":
    result = run()
    print(json.dumps(result, indent=2))
```

- [ ] **Step 4: Run tests — expect PASS**

```powershell
conda run -n ro-admin-reform pytest scripts/calibration/tests/test_B3.py -v
```

Expected: `7 passed`

- [ ] **Step 5: Commit**

```bash
git add scripts/calibration/B3_oos_validation_gate.py scripts/calibration/tests/test_B3.py
git commit -m "feat(calib): B3 OOS validation gate"
```

---

## Task 4: B0 — Orchestrator + writes elasticities.json

**Context:** B0 calls B1, B2, B3 in order, merges their outputs with the four literature priors (lambda, beta_fert, beta_edu, gamma — unchanged from v0), and writes `data/dashboard/elasticities.json`. The `provisional` flag is set from B3's gate result. All stochastic steps are seeded via B1/B2's internal seeds (already set). B0 adds the top-level `diagnostics` block by merging B1 and B2 diagnostics.

**Files:**
- Create: `scripts/calibration/B0_run_calibration.py`

- [ ] **Step 1: Write `scripts/calibration/B0_run_calibration.py`**

(No separate test file — the integration test is running B0 and verifying the JSON output.)

```python
"""
B0 — Calibration orchestrator.

Runs B1 → B2 → B3, merges outputs with v0 literature priors, and writes
data/dashboard/elasticities.json with provenance metadata and regime_test.

Run: python scripts/calibration/B0_run_calibration.py
Idempotent: re-running produces byte-identical JSON (modulo estimated_at/git_sha).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "calibration"))

import B1_extract_lpirf_betas as B1
import B2_barro_convergence_gmm as B2
import B3_oos_validation_gate as B3

OUT = ROOT / "data" / "dashboard" / "elasticities.json"

# ── Literature priors (unchanged from v0) ─────────────────────────────────────
LITERATURE_PRIORS = {
    "lambda": {
        "value": 0.4,
        "se": 0.2,
        "id_strategy": "literature prior (conservation not identified — see diagnostics)",
        "source": "PL intra-regional flows (Baranowska-Rataj & Matysiak 2012)",
        "support": [0.0, 1.0],
        "provenance": {
            "method": "Literature prior. Post-reform period empty (reform_year=2025). "
                       "Historical hub/satellite co-movement = +0.245 (not conservation).",
            "citation": "Baranowska-Rataj & Matysiak (2012); see diagnostics.lambda_comovement",
        },
    },
    "beta_fert": {
        "value": 0.004,
        "se": 0.0015,
        "id_strategy": "literature prior (no €/cap fertility shock in panel)",
        "source": "Luci-Sobotka (2008); Björklund (2006)",
        "support": [0.0, 600.0],
        "provenance": {
            "method": "Literature prior. Panel LP-IRF shows wrong sign (births fall after demotion — "
                       "treatment-direction artefact). Pronatalist-transfer elasticity from literature.",
            "citation": "Luci-Sobotka & Thévenon (2008); Björklund (2006)",
        },
    },
    "beta_edu": {
        "value": 0.03,
        "se": 0.01,
        "id_strategy": "literature prior (no skills series in panel)",
        "source": "Mincer (1974); OECD returns-to-schooling",
        "support": [0.0, 5.0],
        "provenance": {
            "method": "Literature prior. No skills-investment series in panel_judet.",
            "citation": "Mincer (1974); OECD Education at a Glance 2023",
        },
    },
    "gamma": {
        "value": 0.3,
        "se": 0.15,
        "id_strategy": "literature prior (no accessibility data ingested)",
        "source": "Holl (2007); ESPON accessibility",
        "support": [0.0, 1.0],
        "provenance": {
            "method": "Literature prior. No ESPON accessibility dataset ingested (Plan 3).",
            "citation": "Holl (2007) — Roads and regional economic growth in Spain",
        },
    },
}

# ── Scalar assumptions (unchanged) ────────────────────────────────────────────
SCALAR_ASSUMPTIONS = {
    "tau": 0.2,
    "delta": 0.05,
    "discount_rate": 0.03,
    "moretti": {
        "T1": 0.025, "T2": 0.020, "T3": 0.015, "T4": 0.012,
        "T5": 0.010, "T6": 0.008, "T7": 0.007, "T8": 0.006,
    },
}


def main() -> None:
    print("=== B0: Running calibration pipeline ===\n")

    print("[B1] Extracting LP-IRF betas...")
    b1 = B1.extract()
    print(f"  beta_gov  = {b1['beta_gov']['value']:.4f}")
    print(f"  beta_mig  = {b1['beta_mig']['value']:.4f}")

    print("\n[B2] Running Barro convergence + diagnostics...")
    b2 = B2.extract()
    print(f"  beta_K_hub = {b2['beta_K_hub']['value']:.4f}")
    print(f"  beta_K_sat = {b2['beta_K_sat']['value']:.4f}")
    print(f"  regime_test p = {b2['regime_test']['p_value']:.3f}")
    print(f"  IPS p = {b2['diagnostics']['ips_pvalue']:.3f}  ({b2['diagnostics']['conclusion'][:60]})")
    print(f"  lambda co-movement = {b2['diagnostics']['lambda_comovement']:.3f}")

    print("\n[B3] Running OOS validation gate...")
    b3 = B3.run()
    print(f"  {b3['conclusion']}")

    # ── Merge ────────────────────────────────────────────────────────────────
    elast = {
        # Empirical β's
        "beta_gov": b1["beta_gov"],
        "beta_K_hub": b2["beta_K_hub"],
        "beta_K_sat": b2["beta_K_sat"],
        "beta_mig": b1["beta_mig"],
        # Literature priors
        **LITERATURE_PRIORS,
        # Scalar assumptions
        **SCALAR_ASSUMPTIONS,
        # Structural calibration metadata
        "regime_test": b2["regime_test"],
        "diagnostics": {
            **b2["diagnostics"],
            "beta_gov_sdid_crosscheck": b1["diagnostics"]["beta_gov_sdid_crosscheck"],
        },
        "provisional": b3["provisional"],
    }

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(elast, indent=2, default=str))
    print(f"\n✓ Written {OUT}  (provisional={elast['provisional']})")

    # Shape assertion
    for key in ("beta_gov", "beta_K_hub", "beta_K_sat", "beta_mig", "lambda",
                 "beta_fert", "beta_edu", "gamma", "regime_test", "diagnostics"):
        assert key in elast, f"Missing key in output: {key}"
    print("  Shape assertions passed.")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Run B0 end-to-end**

```powershell
conda run -n ro-admin-reform python scripts/calibration/B0_run_calibration.py
```

Expected output (approximate):
```
=== B0: Running calibration pipeline ===

[B1] Extracting LP-IRF betas...
  beta_gov  = 0.0XXX
  beta_mig  = 0.XXXX

[B2] Running Barro convergence + diagnostics...
  beta_K_hub = 0.XXXX
  beta_K_sat = 0.XXXX
  regime_test p = 0.XXX
  IPS p = X.XXX  (stationary ...)
  lambda co-movement = 0.XXX

[B3] Running OOS validation gate...
  OOS RMSE ... → gate ...

✓ Written data/dashboard/elasticities.json  (provisional=...)
  Shape assertions passed.
```

- [ ] **Step 3: Verify the JSON**

```powershell
conda run -n ro-admin-reform python -c "
import json
from pathlib import Path
e = json.loads((Path('data/dashboard/elasticities.json')).read_text())
print('provisional:', e['provisional'])
print('beta_gov value:', e['beta_gov']['value'])
print('beta_K_sat > beta_K_hub:', e['beta_K_sat']['value'] > e['beta_K_hub']['value'])
print('regime_test p:', e['regime_test']['p_value'])
print('has diagnostics:', 'diagnostics' in e)
"
```

Expected: all assertions true, no KeyError.

- [ ] **Step 4: Commit**

```bash
git add scripts/calibration/B0_run_calibration.py data/dashboard/elasticities.json
git commit -m "feat(calib): B0 orchestrator; calibrated elasticities.json written"
```

---

## Task 5: Extend TypeScript types for calibration provenance

**Context:** The new `elasticities.json` has `provenance` on each coefficient, plus top-level `regime_test` and `diagnostics`. The `Elasticity` interface needs optional `provenance`; `Elasticities` needs optional `regime_test` and `diagnostics`. All additions are optional so existing engine tests keep passing without changes.

**Files:**
- Modify: `dashboard/src/types.ts`

- [ ] **Step 1: Verify current tests pass before any change**

```powershell
cd dashboard; npm test
```

Expected: `23 passed`

- [ ] **Step 2: Add new interfaces and update `Elasticity` + `Elasticities`**

In `dashboard/src/types.ts`, append after the existing `ScenarioResult` interface (at end of file):

```typescript
// ── Calibration provenance ────────────────────────────────────────────────────

export interface ElasticityProvenance {
  method: string;
  n_obs?: number;
  r2?: number;
  half_life_years?: number;
  boot_ci_90?: [number, number];
  boot_se?: number;
  citation?: string;
  estimated_at?: string;
  git_sha?: string;
}

export interface RegimeTest {
  p_value: number;
  stat: number;
  df: number;
}

export interface CalibrationDiagnostics {
  ips_stat: number;
  ips_pvalue: number;
  conclusion: string;
  lambda_comovement: number;
  beta_gov_sdid_crosscheck: {
    lpirf: number;
    sdid: number;
    ratio: number;
    agree: boolean;
  };
}
```

Then update the `Elasticity` interface (around line 153) by adding `provenance?`:

Old:
```typescript
export interface Elasticity {
  value: number;
  se: number;
  id_strategy: string;
  source: string;
  support: [number, number];
}
```

New:
```typescript
export interface Elasticity {
  value: number;
  se: number;
  id_strategy: string;
  source: string;
  support: [number, number];
  provenance?: ElasticityProvenance;
}
```

Then update the `Elasticities` interface (around line 161) by adding two optional fields before `provisional`:

Old:
```typescript
  moretti: Record<string, number>; // tier (e.g. "T4") → annual ln-pop multiplier
  provisional: boolean;  // true until Plan 2 calibration replaces v0 priors
```

New:
```typescript
  moretti: Record<string, number>; // tier (e.g. "T4") → annual ln-pop multiplier
  regime_test?: RegimeTest;
  diagnostics?: CalibrationDiagnostics;
  provisional: boolean;  // true until Plan 2 calibration replaces v0 priors
```

- [ ] **Step 3: Run type check**

```powershell
npx tsc --noEmit
```

Expected: no errors

- [ ] **Step 4: Run tests**

```powershell
npm test
```

Expected: `23 passed` (unchanged)

- [ ] **Step 5: Commit**

```bash
cd ..
git add dashboard/src/types.ts
git commit -m "feat(types): add ElasticityProvenance, RegimeTest, CalibrationDiagnostics"
```

---

## Task 6: format.ts — unit conversion helpers

**Context:** Pure functions used by CostReadout, PolicyLab, and MetricTooltip. Must be unit-tested before any component uses them. The `formatEur` function replaces the inline `eur()` in CostReadout.

**Files:**
- Create: `dashboard/src/utils/format.ts`
- Create: `dashboard/src/utils/format.test.ts`

- [ ] **Step 1: Write the failing tests**

Write `dashboard/src/utils/format.test.ts`:

```typescript
import { describe, it, expect } from 'vitest';
import {
  lnDeltaToPct, formatPct, formatPp, formatEur,
  costPerCapita, costPctGva, costPerPpUplift,
} from './format';

describe('lnDeltaToPct', () => {
  it('returns 0 at delta=0', () => {
    expect(lnDeltaToPct(0)).toBe(0);
  });
  it('returns ~5.127 at delta=0.05', () => {
    expect(lnDeltaToPct(0.05)).toBeCloseTo(5.1271, 3);
  });
  it('handles negative delta', () => {
    expect(lnDeltaToPct(-0.1)).toBeCloseTo(-9.5163, 3);
  });
});

describe('formatPct', () => {
  it('adds + prefix for positive', () => {
    expect(formatPct(3.2)).toBe('+3.2%');
  });
  it('keeps - prefix for negative', () => {
    expect(formatPct(-1.5)).toBe('-1.5%');
  });
  it('respects decimal places', () => {
    expect(formatPct(3.14159, 2)).toBe('+3.14%');
  });
});

describe('formatPp', () => {
  it('formats positive with p.p. suffix', () => {
    expect(formatPp(1.4)).toBe('+1.4 p.p.');
  });
  it('formats negative', () => {
    expect(formatPp(-2.3)).toBe('-2.3 p.p.');
  });
});

describe('formatEur', () => {
  it('formats billions with 2dp', () => {
    expect(formatEur(1.2e9)).toBe('€1.20bn');
  });
  it('formats millions with 1dp', () => {
    expect(formatEur(4.5e6)).toBe('€4.5m');
  });
  it('formats small amounts with toLocaleString', () => {
    // 12345 → varies by locale; just check prefix and no b/m
    const s = formatEur(12345);
    expect(s.startsWith('€')).toBe(true);
    expect(s).not.toContain('bn');
    expect(s).not.toContain('m');
  });
});

describe('costPerCapita', () => {
  it('divides cost by population', () => {
    expect(costPerCapita(1_000_000, 100_000)).toBe(10);
  });
  it('returns 0 when population is 0', () => {
    expect(costPerCapita(1_000_000, 0)).toBe(0);
  });
});

describe('costPctGva', () => {
  it('returns cost as % of GVA', () => {
    expect(costPctGva(100_000, 1_000_000)).toBe(10);
  });
  it('returns 0 when GVA is 0', () => {
    expect(costPctGva(100_000, 0)).toBe(0);
  });
});

describe('costPerPpUplift', () => {
  it('divides cost by uplift', () => {
    expect(costPerPpUplift(1_000_000, 5)).toBe(200_000);
  });
  it('returns null when uplift is near zero', () => {
    expect(costPerPpUplift(1_000_000, 0)).toBeNull();
    expect(costPerPpUplift(1_000_000, 0.0005)).toBeNull();
  });
});
```

- [ ] **Step 2: Run tests — expect FAIL (module not found)**

```powershell
npm test -- --reporter=verbose 2>&1 | Select-Object -Last 20
```

Expected: `Cannot find module './format'`

- [ ] **Step 3: Write `dashboard/src/utils/format.ts`**

```typescript
/** Convert Δ(ln) to % uplift: (e^Δ − 1) × 100 */
export function lnDeltaToPct(deltaLn: number): number {
  return (Math.exp(deltaLn) - 1) * 100;
}

/** Format as "±X.Y%" with explicit sign. */
export function formatPct(x: number, dp = 1): string {
  const sign = x >= 0 ? '+' : '';
  return `${sign}${x.toFixed(dp)}%`;
}

/** Format as "±X.Y p.p." with explicit sign. */
export function formatPp(x: number, dp = 1): string {
  const sign = x >= 0 ? '+' : '';
  return `${sign}${x.toFixed(dp)} p.p.`;
}

/** Format euros: ≥1bn → "€X.XXbn", ≥1m → "€X.Xm", else localized integer. */
export function formatEur(x: number): string {
  if (x >= 1e9) return `€${(x / 1e9).toFixed(2)}bn`;
  if (x >= 1e6) return `€${(x / 1e6).toFixed(1)}m`;
  return `€${Math.round(x).toLocaleString()}`;
}

/** € per capita */
export function costPerCapita(costEur: number, totalPop: number): number {
  return totalPop > 0 ? costEur / totalPop : 0;
}

/** Programme cost as % of regional GVA (0–100). */
export function costPctGva(costEur: number, totalGvaEur: number): number {
  return totalGvaEur > 0 ? (costEur / totalGvaEur) * 100 : 0;
}

/** € per percentage point of productivity uplift, or null when uplift ≈ 0. */
export function costPerPpUplift(costEur: number, upliftPct: number): number | null {
  return Math.abs(upliftPct) > 0.001 ? costEur / upliftPct : null;
}
```

- [ ] **Step 4: Run tests — expect PASS**

```powershell
npm test
```

Expected: `30 passed` (23 existing + 7 new format tests)

- [ ] **Step 5: Commit**

```bash
cd ..
git add dashboard/src/utils/format.ts dashboard/src/utils/format.test.ts
git commit -m "feat(ui): format.ts unit-conversion helpers + tests"
```

---

## Task 7: MetricTooltip.tsx — ⓘ provenance popover

**Context:** Pure presentational component: an ⓘ icon that reveals a CSS-hover popover with provenance details. No React state needed. Used in PolicyLab's metrics row. The popover is positioned above the icon using Tailwind `group/absolute/bottom-full`.

**Files:**
- Create: `dashboard/src/components/MetricTooltip.tsx`

- [ ] **Step 1: Write `dashboard/src/components/MetricTooltip.tsx`**

```typescript
import type { ElasticityProvenance } from '../types';

interface Props {
  provenance?: ElasticityProvenance;
  glossText: string;
}

export default function MetricTooltip({ provenance, glossText }: Props) {
  if (!provenance) return null;
  return (
    <span className="relative group inline-block align-middle ml-0.5 cursor-help select-none">
      <span className="text-violet-400 text-[10px]">ⓘ</span>
      <div className="absolute bottom-full left-1/2 -translate-x-1/2 mb-1 hidden group-hover:block z-50
                      w-64 bg-white border border-gray-200 rounded shadow-lg p-2 text-xs text-gray-700 space-y-1
                      pointer-events-none">
        <p className="font-semibold text-gray-900 leading-snug">{glossText}</p>
        <p><span className="text-gray-400">Method:</span> {provenance.method}</p>
        {provenance.n_obs != null && (
          <p><span className="text-gray-400">N:</span> {provenance.n_obs.toLocaleString()} obs</p>
        )}
        {provenance.boot_ci_90 && (
          <p>
            <span className="text-gray-400">90% CI:</span>{' '}
            [{provenance.boot_ci_90[0].toFixed(3)}, {provenance.boot_ci_90[1].toFixed(3)}]
          </p>
        )}
        {provenance.half_life_years != null && (
          <p>
            <span className="text-gray-400">Half-life:</span>{' '}
            {provenance.half_life_years.toFixed(1)} yrs
          </p>
        )}
        {provenance.citation && (
          <p className="text-gray-400 text-[10px] leading-snug">{provenance.citation}</p>
        )}
      </div>
    </span>
  );
}
```

- [ ] **Step 2: Type-check**

```powershell
npx tsc --noEmit
```

Expected: no errors

- [ ] **Step 3: Run tests (must not regress)**

```powershell
npm test
```

Expected: `30 passed`

- [ ] **Step 4: Commit**

```bash
cd ..
git add dashboard/src/components/MetricTooltip.tsx
git commit -m "feat(ui): MetricTooltip ⓘ hover popover with provenance"
```

---

## Task 8: Updated CostReadout — four money framings

**Context:** CostReadout now shows NPV, € per capita, % of regional GVA, and € per p.p. of uplift. It receives `totalPop` and `totalGva` from PolicyLab (which computes them from the `primitives` map). The `eur()` local helper is deleted in favour of `formatEur` from format.ts. The existing `hubOpportunityCostPct` field in `ScenarioResult` is retained for the Hub opportunity row in the metrics section but is no longer shown in CostReadout itself.

**Files:**
- Modify: `dashboard/src/components/CostReadout.tsx`

- [ ] **Step 1: Read the current file** (already done above — confirmed 24 lines)

- [ ] **Step 2: Rewrite `dashboard/src/components/CostReadout.tsx`**

```typescript
import type { ScenarioResult } from '../types';
import {
  formatEur, formatPct, lnDeltaToPct,
  costPerCapita, costPctGva, costPerPpUplift,
} from '../utils/format';

interface Props {
  result: ScenarioResult;
  totalPop: number;
  totalGva: number;
}

export default function CostReadout({ result, totalPop, totalGva }: Props) {
  const lastPt = result.regionTotal.at(-1);
  const upliftPct = lastPt ? lnDeltaToPct(lastPt.scenario - lastPt.baseline) : 0;
  const perPp = costPerPpUplift(result.cost2040, upliftPct);

  const rows: { label: string; value: string }[] = [
    { label: 'NPV total', value: formatEur(result.cost2040) },
    { label: '€ / capita', value: formatEur(costPerCapita(result.cost2040, totalPop)) },
    {
      label: '% of regional GVA',
      value: `${costPctGva(result.cost2040, totalGva).toFixed(2)}%`,
    },
    {
      label: '€ / p.p. uplift',
      value: perPp !== null ? formatEur(perPp) : '—',
    },
  ];

  return (
    <div className="grid grid-cols-2 gap-1.5 p-3 text-xs">
      {rows.map(({ label, value }) => (
        <div key={label} className="bg-violet-50 rounded p-2">
          <div className="text-violet-500 text-[10px] leading-tight">{label}</div>
          <div className="font-bold text-violet-900 text-sm mt-0.5 tabular-nums">{value}</div>
        </div>
      ))}
    </div>
  );
}
```

- [ ] **Step 3: Type-check**

```powershell
npx tsc --noEmit
```

Expected: error on `PolicyLab.tsx` because `CostReadout` prop signature changed. Fix is in Task 10.

- [ ] **Step 4: Note the PolicyLab error and proceed**

The type error is expected at this point — PolicyLab passes the old props. It will be resolved in Task 10.

- [ ] **Step 5: Commit**

```bash
cd ..
git add dashboard/src/components/CostReadout.tsx
git commit -m "feat(ui): CostReadout — four cost framings (NPV, per capita, % GVA, per p.p.)"
```

---

## Task 9: Updated RegimeBadge — p-value display

**Context:** When `data.elasticities.regime_test` is present (after calibration), RegimeBadge shows the interaction test p-value. The existing `result.regimeMargin` fallback is retained when `regime_test` is absent. The COPY dict is refactored to separate `label` from `description`.

**Files:**
- Modify: `dashboard/src/components/RegimeBadge.tsx`

- [ ] **Step 1: Rewrite `dashboard/src/components/RegimeBadge.tsx`**

```typescript
import type { ScenarioResult } from '../types';

interface Props {
  result: ScenarioResult;
  regimePValue?: number;
}

const COPY: Record<ScenarioResult['regime'], { label: string; description: string; cls: string }> = {
  convergence: {
    label: 'CONVERGENCE',
    description: 'redistribution raises total regional output',
    cls: 'bg-emerald-50 text-emerald-800 border-emerald-200',
  },
  agglomeration: {
    label: 'AGGLOMERATION',
    description: 'redistribution reduces total regional output',
    cls: 'bg-rose-50 text-rose-800 border-rose-200',
  },
  neutral: {
    label: 'NEUTRAL',
    description: 'redistribution is output-neutral for this region',
    cls: 'bg-gray-50 text-gray-700 border-gray-200',
  },
};

export default function RegimeBadge({ result, regimePValue }: Props) {
  const c = COPY[result.regime];
  return (
    <div className={`text-xs rounded border px-2 py-1.5 ${c.cls}`}>
      <span className="font-semibold">{c.label}</span>
      {regimePValue !== undefined ? (
        <span className="ml-1"> · p={regimePValue.toFixed(2)}</span>
      ) : (
        <span className="ml-1 opacity-60">(margin {result.regimeMargin.toFixed(3)})</span>
      )}
      <span className="ml-1">— {c.description}</span>
    </div>
  );
}
```

- [ ] **Step 2: Type-check and test**

```powershell
npx tsc --noEmit
npm test
```

Expected: `30 passed`. (PolicyLab still calls `<RegimeBadge result={result} />` without `regimePValue` — that's fine since the prop is optional.)

- [ ] **Step 3: Commit**

```bash
cd ..
git add dashboard/src/components/RegimeBadge.tsx
git commit -m "feat(ui): RegimeBadge shows regime_test p-value when available"
```

---

## Task 10: Updated PolicyLab + LeverPanel — full V1 redesign

**Context:** Major layout refactor. New panel hierarchy (top→bottom): (1) header strip, (2) headline band with RegimeBadge + two hero KPIs, (3) % uplift chart (not raw ln), (4) CostReadout with new props, (5) metrics row with MetricTooltip, (6) LeverPanel with collapsible groups, (7) convention legend. LeverPanel gains collapse/expand toggle per group, all collapsed by default.

`data.elasticities.regime_test?.p_value` is passed as `regimePValue` to RegimeBadge when present.

**Files:**
- Modify: `dashboard/src/components/PolicyLab.tsx`
- Modify: `dashboard/src/components/LeverPanel.tsx`

- [ ] **Step 1: Update `dashboard/src/components/LeverPanel.tsx`**

Replace the entire file with:

```typescript
import { useState } from 'react';
import type { LeverVector } from '../types';
import { LEVER_BOUNDS, DEFAULT_LEVERS } from '../types';

interface LeverMeta { key: keyof LeverVector; label: string; unit: string; group: string; }

const LEVERS: LeverMeta[] = [
  { key: 'rho',    label: 'Redistribution share',    unit: '',          group: 'Fiscal' },
  { key: 'kappa',  label: 'Cohesion injection',       unit: '€/cap/yr',  group: 'Fiscal' },
  { key: 'gov',    label: 'Gov-efficiency gain',       unit: '',          group: 'Productivity' },
  { key: 'iota',   label: 'MegaCampus intensity',      unit: '×',         group: 'Productivity' },
  { key: 'skills', label: 'Skills investment',         unit: '% GVA',     group: 'Productivity' },
  { key: 'conn',   label: 'Connectivity',              unit: '',          group: 'Productivity' },
  { key: 'mu',     label: 'Migration-retention',       unit: '€/cap/yr',  group: 'Demography' },
  { key: 'family', label: 'Family transfer',           unit: '€/cap/yr',  group: 'Demography' },
  { key: 'offset', label: 'Reform-transition offset',  unit: '',          group: 'Mitigation' },
];

const PRESETS: Record<string, Partial<LeverVector>> = {
  'Status quo': {},
  'Pure agglomeration': { iota: 1.5, gov: 0.6 },
  'Aggressive convergence': { rho: 0.5, mu: 200, conn: 0.8, skills: 3 },
  'EU cohesion-funded': { kappa: 250, conn: 0.6, skills: 2 },
};

const GROUPS = [...new Set(LEVERS.map((l) => l.group))];

interface Props {
  levers: LeverVector;
  onChange: (next: LeverVector) => void;
  provisional: boolean;
}

export default function LeverPanel({ levers, onChange, provisional }: Props) {
  const [collapsed, setCollapsed] = useState<Set<string>>(() => new Set(GROUPS));

  function toggle(g: string) {
    setCollapsed((prev) => {
      const next = new Set(prev);
      if (next.has(g)) next.delete(g); else next.add(g);
      return next;
    });
  }

  function set(key: keyof LeverVector, value: number) {
    onChange({ ...levers, [key]: value });
  }

  return (
    <div className="p-3 space-y-2 text-xs border-t border-gray-100">
      {provisional && (
        <div className="bg-amber-50 text-amber-800 rounded px-2 py-1">
          ⚠ Provisional coefficients (literature priors) — empirical calibration pending.
        </div>
      )}

      {/* Preset buttons */}
      <div className="flex flex-wrap gap-1">
        {Object.keys(PRESETS).map((name) => (
          <button
            key={name}
            onClick={() => onChange({ ...DEFAULT_LEVERS, ...PRESETS[name] })}
            className="px-2 py-0.5 rounded border border-violet-300 text-violet-700 hover:bg-violet-50 text-[11px]"
          >
            {name}
          </button>
        ))}
      </div>

      {/* Collapsible groups */}
      {GROUPS.map((g) => (
        <div key={g} className="rounded border border-gray-100">
          <button
            onClick={() => toggle(g)}
            className="w-full flex items-center justify-between px-2 py-1.5 text-left text-gray-700 font-medium hover:bg-gray-50"
          >
            <span>{g}</span>
            <span className="text-gray-400 text-[10px]">{collapsed.has(g) ? '▶' : '▼'}</span>
          </button>
          {!collapsed.has(g) && (
            <div className="px-2 pb-2 space-y-1">
              {LEVERS.filter((l) => l.group === g).map((l) => {
                const [lo, hi] = LEVER_BOUNDS[l.key];
                const step = hi <= 2 ? 0.05 : 10;
                return (
                  <label key={l.key} className="flex items-center gap-2">
                    <span className="w-36 text-gray-600 text-[11px]">{l.label}</span>
                    <input
                      type="range" min={lo} max={hi} step={step} value={levers[l.key]}
                      onChange={(e) => set(l.key, Number(e.target.value))}
                      className="flex-1"
                    />
                    <span className="w-16 text-right tabular-nums text-[11px]">
                      {levers[l.key]}{l.unit}
                    </span>
                  </label>
                );
              })}
            </div>
          )}
        </div>
      ))}
    </div>
  );
}
```

- [ ] **Step 2: Rewrite `dashboard/src/components/PolicyLab.tsx`**

```typescript
import { useState, useMemo, useEffect } from 'react';
import {
  ComposedChart, Area, XAxis, YAxis, CartesianGrid, Tooltip,
  ReferenceLine, ResponsiveContainer,
} from 'recharts';
import type { CountyPrimitive, DashboardData, LeverVector, RegionGroup } from '../types';
import { applyScenario } from '../engine/scenario';
import { leversToQuery, queryToLevers } from '../utils/scenarioUrl';
import { lnDeltaToPct, formatPct, formatPp } from '../utils/format';
import LeverPanel from './LeverPanel';
import RegimeBadge from './RegimeBadge';
import CostReadout from './CostReadout';
import MetricTooltip from './MetricTooltip';

interface Props {
  nuts3Code: string | null;
  data: DashboardData;
  regionGroups: Map<string, RegionGroup>;
}

export default function PolicyLab({ nuts3Code, data, regionGroups }: Props) {
  const [levers, setLevers] = useState<LeverVector>(() =>
    queryToLevers(new URLSearchParams(window.location.search)),
  );

  useEffect(() => {
    const q = leversToQuery(levers);
    const url = q ? `${window.location.pathname}?${q}` : window.location.pathname;
    window.history.replaceState(null, '', url);
  }, [levers]);

  const primitives = useMemo(
    () => new Map(Object.entries(data.primitivesByCode)),
    [data.primitivesByCode],
  );

  const group = nuts3Code
    ? regionGroups.get(data.suitabilityByCode[nuts3Code]?.nuts2_code ?? '')
    : undefined;

  const result = useMemo(() => {
    if (!group) return null;
    return applyScenario(group, levers, data.elasticities, primitives, data.forecastsByCode);
  }, [group, levers, data.elasticities, data.forecastsByCode, primitives]);

  // Population and GVA aggregates for cost framings
  const members = useMemo<CountyPrimitive[]>(() => {
    if (!group) return [];
    const codes = [group.hubNuts3, ...group.satellites].filter(Boolean) as string[];
    return codes.map((c) => primitives.get(c)).filter((m): m is CountyPrimitive => !!m);
  }, [group, primitives]);

  const totalPop = useMemo(() => members.reduce((s, m) => s + m.population, 0), [members]);
  const totalGva = useMemo(() => members.reduce((s, m) => s + m.gva_pc * m.population, 0), [members]);

  if (!nuts3Code) {
    return (
      <div className="flex flex-col items-center justify-center h-full text-gray-400 text-sm gap-2 p-6">
        <span className="text-2xl">🎛</span>
        <p>Click a county to open the Policy Lab for its region</p>
      </div>
    );
  }
  if (!group || !result) {
    return <div className="p-4 text-gray-400 text-sm">No region data for {nuts3Code}.</div>;
  }

  // ── Computed metrics ──────────────────────────────────────────────────────
  const lastPt = result.regionTotal.at(-1);
  const prodUpliftPct = lastPt ? lnDeltaToPct(lastPt.scenario - lastPt.baseline) : 0;

  const popUpliftPct = useMemo(() => {
    if (members.length === 0) return 0;
    return members.reduce((acc, m) => {
      const pts = result.perCountyPop[m.nuts3_code];
      const last = pts?.at(-1);
      if (!last) return acc;
      return acc + (m.population / (totalPop || 1)) * lnDeltaToPct(last.scenario - last.baseline);
    }, 0);
  }, [members, result.perCountyPop, totalPop]);

  const hdiDeltaPp = useMemo(() => {
    if (members.length === 0) return 0;
    const firstHDI = members.reduce((acc, m) => acc + (result.hdiProxy[m.nuts3_code]?.[0]?.value ?? 0) / members.length, 0);
    const lastHDI = members.reduce((acc, m) => acc + (result.hdiProxy[m.nuts3_code]?.at(-1)?.value ?? 0) / members.length, 0);
    return (lastHDI - firstHDI) * 100;
  }, [members, result.hdiProxy]);

  // ── Chart data: % uplift per year ────────────────────────────────────────
  const chartData = result.regionTotal.map((p) => ({
    year: p.year,
    upliftPct: lnDeltaToPct(p.scenario - p.baseline),
    lo: lnDeltaToPct(p.lo - p.baseline),
    hi: lnDeltaToPct(p.hi - p.baseline),
  }));

  const regimePValue = data.elasticities.regime_test?.p_value;

  // ── Hero KPIs ─────────────────────────────────────────────────────────────
  const heroKpis = [
    { label: 'Region productivity @2040', value: formatPct(prodUpliftPct) },
    { label: 'Programme cost (NPV)', value: result.cost2040 >= 1e9
        ? `€${(result.cost2040 / 1e9).toFixed(2)}bn`
        : `€${(result.cost2040 / 1e6).toFixed(1)}m` },
  ];

  return (
    <div className="flex flex-col h-full overflow-y-auto text-xs">
      {/* Header */}
      <div className="px-4 py-2 bg-violet-50 border-b border-violet-100 shrink-0">
        <div className="font-bold text-violet-900 text-sm">Policy Lab — {group.nuts2Code}</div>
        <div className="text-violet-600 text-[11px]">{group.satellites.length} satellite counties</div>
      </div>

      {/* Headline band: regime + hero KPIs */}
      <div className="p-3 space-y-2 shrink-0">
        <RegimeBadge result={result} regimePValue={regimePValue} />
        <div className="grid grid-cols-2 gap-2">
          {heroKpis.map(({ label, value }) => (
            <div key={label} className="bg-violet-50 rounded p-2">
              <div className="text-violet-500 text-[10px] leading-tight">{label}</div>
              <div className="font-bold text-violet-900 text-base tabular-nums">{value}</div>
            </div>
          ))}
        </div>
      </div>

      {/* % uplift chart */}
      <ResponsiveContainer width="100%" height={180}>
        <ComposedChart data={chartData} margin={{ top: 4, right: 8, bottom: 4, left: 8 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
          <XAxis dataKey="year" tick={{ fontSize: 10 }} interval={2} />
          <YAxis
            tick={{ fontSize: 10 }}
            tickFormatter={(v: number) => `${v >= 0 ? '+' : ''}${v.toFixed(1)}%`}
            width={50}
          />
          <Tooltip
            contentStyle={{ fontSize: 11 }}
            formatter={(v: number) => [`${v >= 0 ? '+' : ''}${v.toFixed(2)}%`, 'Uplift']}
          />
          <ReferenceLine x={2025} stroke="#d97706" strokeDasharray="4 3" />
          <ReferenceLine y={0} stroke="#9ca3af" strokeWidth={1} />
          <Area
            type="monotone" dataKey="upliftPct"
            name="Scenario uplift %"
            stroke="#7c3aed" fill="#ede9fe" strokeWidth={2} dot={false}
          />
        </ComposedChart>
      </ResponsiveContainer>

      {/* Four-framing cost block */}
      <CostReadout result={result} totalPop={totalPop} totalGva={totalGva} />

      {/* Metrics row with ⓘ */}
      <div className="grid grid-cols-2 gap-1.5 px-3 pb-2">
        {([
          {
            label: 'Productivity Δ',
            value: formatPct(prodUpliftPct),
            prov: data.elasticities.beta_K_sat?.provenance,
            gloss: 'ln-GVA/empl % uplift vs baseline at 2040. Driven by capital convergence speed (β_K_sat).',
          },
          {
            label: 'Population Δ',
            value: formatPct(popUpliftPct),
            prov: data.elasticities.beta_mig?.provenance,
            gloss: 'ln-population % uplift vs baseline at 2040. Driven by migration-retention elasticity (β_mig).',
          },
          {
            label: 'HDI proxy Δ',
            value: formatPp(hdiDeltaPp),
            prov: data.elasticities.beta_edu?.provenance,
            gloss: 'Interim HDI proxy change in percentage points (geometric mean of income, health, education indices).',
          },
          {
            label: 'Hub opportunity cost',
            value: formatPp(result.hubOpportunityCostPct),
            prov: data.elasticities.beta_K_hub?.provenance,
            gloss: 'Hub GVA growth change in p.p. — redistribution drains hub capital stock. Negative = hub cost.',
          },
        ] as const).map(({ label, value, prov, gloss }) => (
          <div key={label} className="bg-gray-50 rounded p-2">
            <div className="text-gray-500 text-[10px] leading-tight flex items-center gap-0.5">
              {label}
              <MetricTooltip provenance={prov} glossText={gloss} />
            </div>
            <div className="font-bold text-gray-900 mt-0.5 tabular-nums">{value}</div>
          </div>
        ))}
      </div>

      {/* Collapsible levers */}
      <LeverPanel levers={levers} onChange={setLevers} provisional={data.elasticities.provisional} />

      {/* Convention legend */}
      <div className="px-3 py-2 text-[10px] text-gray-400 border-t border-gray-100 shrink-0">
        Levels (productivity, population): % uplift = (e<sup>Δln</sup> − 1) × 100.
        Rates (HDI, opportunity cost): p.p. = percentage points.
      </div>
    </div>
  );
}
```

- [ ] **Step 3: Type-check**

```powershell
npx tsc --noEmit
```

Expected: no errors

- [ ] **Step 4: Run full test suite**

```powershell
npm test
```

Expected: `30 passed` (no regressions)

- [ ] **Step 5: Build**

```powershell
npm run build
```

Expected: build completes with warnings about chunk size only (no errors).

- [ ] **Step 6: Smoke test**

Start the dev server and open the browser:

```powershell
npm run dev
```

1. Open the dashboard in a browser.
2. Click any county that has forecast data (any of the 8 MG-VAR counties).
3. Navigate to **Policy Lab** layer.
4. Verify:
   - Regime badge shows with p-value if calibration ran, or margin if not.
   - Hero KPIs show valid `%` and `€` values.
   - Chart Y-axis shows `+X.X%` labels (not raw ln values).
   - Chart has a reference line at 2025 and at y=0.
   - Cost grid shows four cells: NPV, €/capita, % GVA, €/p.p.
   - Metrics row shows four values with ⓘ icons.
   - Hovering ⓘ shows a popover with method and CI.
   - Lever groups are collapsed by default; clicking expands them.
   - Footer shows convention legend text.
5. Try "Aggressive convergence" preset — verify all numbers update.
6. Copy the URL — verify it contains lever parameters.
7. Reload the URL — verify levers are restored.

If the amber provisional banner is visible, run `python scripts/calibration/B0_run_calibration.py` and reload — it should disappear when `provisional: false`.

- [ ] **Step 7: Commit**

```bash
cd ..
git add dashboard/src/components/PolicyLab.tsx dashboard/src/components/LeverPanel.tsx
git commit -m "feat(ui): Policy Lab V1 — % chart, headline band, metrics with ⓘ, collapsible levers"
```

---

## Final verification

- [ ] Run the full test suite one last time:

```powershell
cd dashboard
npm test && npx tsc --noEmit && npm run build
```

Expected:
```
Test Files  6 passed (6)
Tests       30 passed (30)
(tsc) no output
(vite build) ✓ built in ...
```

- [ ] Run all calibration tests together:

```powershell
conda run -n ro-admin-reform pytest scripts/calibration/tests/ -v
```

Expected: `20 passed` (6 B1 + 7 B2 + 7 B3)

- [ ] Commit final state if any straggler files remain untracked:

```bash
git status
```

All working-tree changes should be committed.
