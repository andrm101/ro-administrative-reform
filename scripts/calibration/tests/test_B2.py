"""Tests for B2_barro_convergence_gmm — run from repo root:
   conda run -n ro-admin-reform pytest scripts/calibration/tests/test_B2.py -v
"""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "scripts" / "calibration"))


def test_imports():
    import B2_barro_convergence_gmm as B2  # noqa: F401


@pytest.fixture(scope="module")
def result():
    import B2_barro_convergence_gmm as B2
    return B2.extract()


def test_returns_required_keys(result):
    for key in ("beta_K_hub", "beta_K_sat", "regime_test", "diagnostics"):
        assert key in result, f"missing key: {key}"


def test_beta_K_sat_greater_than_hub(result):
    assert result["beta_K_sat"]["value"] > result["beta_K_hub"]["value"], (
        "Expected beta_K_sat > beta_K_hub (satellite catch-up > hub convergence)"
    )


def test_betas_positive(result):
    assert result["beta_K_hub"]["value"] > 0
    assert result["beta_K_sat"]["value"] > 0


def test_regime_test_keys(result):
    rt = result["regime_test"]
    for key in ("p_value", "stat", "df"):
        assert key in rt
    assert 0 <= rt["p_value"] <= 1


def test_ips_diagnostics(result):
    diag = result["diagnostics"]
    for key in ("ips_stat", "ips_pvalue", "conclusion", "lambda_comovement"):
        assert key in diag


def test_lambda_comovement_range(result):
    lc = result["diagnostics"]["lambda_comovement"]
    assert -1 <= lc <= 1, f"lambda_comovement {lc} outside [-1,1]"


def test_demean_twoway_matches_lsdv():
    """The vectorized two-way within-slope must equal smf.ols with explicit dummies (FWL).

    This guards the core estimator used in all 2000 bootstrap draws without needing
    the full (~23s) extract() run.
    """
    import numpy as np
    import pandas as pd
    import statsmodels.formula.api as smf
    import B2_barro_convergence_gmm as B2

    rng = np.random.default_rng(0)
    units, periods = 5, 8
    rows = [
        {"unit": u, "time": t, "x": float(rng.normal()), "y": float(rng.normal())}
        for u in range(units)
        for t in range(periods)
    ]
    df = pd.DataFrame(rows)
    unit_idx = pd.factorize(df["unit"])[0]
    time_idx = pd.factorize(df["time"])[0]
    uc = np.bincount(unit_idx).astype(float)
    tc = np.bincount(time_idx).astype(float)
    x_d = B2._demean_twoway(df["x"].to_numpy(float), unit_idx, time_idx, uc, tc)
    y_d = B2._demean_twoway(df["y"].to_numpy(float), unit_idx, time_idx, uc, tc)
    fwl_slope = float(y_d @ x_d) / float(x_d @ x_d)
    lsdv_slope = float(smf.ols("y ~ x + C(unit) + C(time)", data=df).fit().params["x"])
    assert abs(fwl_slope - lsdv_slope) < 1e-10, f"FWL {fwl_slope} vs LSDV {lsdv_slope}"
