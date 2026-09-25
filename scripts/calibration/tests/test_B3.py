"""Tests for B3_oos_validation_gate — run from repo root:
   conda run -n ro-admin-reform pytest scripts/calibration/tests/test_B3.py -v
"""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "scripts" / "calibration"))


def test_imports():
    import B3_oos_validation_gate as B3  # noqa: F401


@pytest.fixture(scope="module")
def result():
    import B3_oos_validation_gate as B3
    return B3.run()


def test_returns_required_keys(result):
    for key in ("provisional", "rmse", "threshold", "conclusion"):
        assert key in result, f"missing key: {key}"


def test_provisional_is_bool(result):
    assert isinstance(result["provisional"], bool)


def test_rmse_positive(result):
    assert result["rmse"] > 0


def test_threshold_positive(result):
    assert result["threshold"] > 0


def test_synthetic_gate_pass():
    """When RMSE is below threshold, gate passes (provisional=False)."""
    import B3_oos_validation_gate as B3
    assert B3._gate_decision(rmse=1.0, threshold=1.5) is False  # rmse <= threshold → not provisional


def test_synthetic_gate_fail():
    """RMSE above threshold → provisional=True."""
    import B3_oos_validation_gate as B3
    assert B3._gate_decision(rmse=2.0, threshold=1.5) is True
