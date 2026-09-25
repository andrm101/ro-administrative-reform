"""Tests for B1_extract_lpirf_betas — run from repo root with:
   conda run -n ro-admin-reform pytest scripts/calibration/tests/test_B1.py -v
"""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "scripts" / "calibration"))


def test_imports():
    import B1_extract_lpirf_betas as B1  # noqa: F401 — import must not raise


@pytest.fixture(scope="module")
def result():
    import B1_extract_lpirf_betas as B1
    return B1.extract()


def test_returns_required_keys(result):
    assert "beta_gov" in result
    assert "beta_mig" in result
    assert "diagnostics" in result


def test_beta_gov_value_is_float(result):
    assert isinstance(result["beta_gov"]["value"], float)


def test_beta_mig_value_is_float(result):
    assert isinstance(result["beta_mig"]["value"], float)


def test_beta_mig_sign_flipped_for_subsidy(result):
    """beta_mig is the demotion IRF negated so the engine's retention-subsidy lever
    raises (not lowers) population. The demotion drove out-migration (raw IRF < 0),
    so the reported subsidy elasticity must be positive."""
    assert result["beta_mig"]["value"] > 0, (
        "beta_mig must be positive after the subsidy sign-flip; a retention subsidy "
        "cannot plausibly depopulate the region it subsidizes"
    )


def test_provenance_keys_present(result):
    prov = result["beta_gov"]["provenance"]
    for key in ("method", "n_obs", "boot_se", "boot_ci_90", "estimated_at", "git_sha"):
        assert key in prov, f"missing provenance key: {key}"


def test_sdid_crosscheck_present(result):
    xcheck = result["diagnostics"]["beta_gov_sdid_crosscheck"]
    for key in ("lpirf", "sdid", "ratio", "agree"):
        assert key in xcheck, f"missing crosscheck key: {key}"
