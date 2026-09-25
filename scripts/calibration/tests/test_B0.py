"""Tests for B0_run_calibration — run from repo root:
   conda run -n ro-admin-reform pytest scripts/calibration/tests/test_B0.py -v

Focuses on _sanitize, the load-bearing coercion that keeps the written JSON valid
for the browser (bare NaN/Infinity are invalid per RFC 8259 and crash JSON.parse).
"""
import json
import math
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "scripts" / "calibration"))


def test_imports():
    import B0_run_calibration as B0  # noqa: F401


def test_sanitize_nan_to_none():
    import B0_run_calibration as B0
    assert B0._sanitize(float("nan")) is None
    assert B0._sanitize(float("inf")) is None
    assert B0._sanitize(float("-inf")) is None


def test_sanitize_finite_float_unchanged():
    import B0_run_calibration as B0
    assert B0._sanitize(1.5) == 1.5
    assert B0._sanitize(0.0) == 0.0


def test_sanitize_numpy_scalars_to_python():
    import B0_run_calibration as B0
    out = B0._sanitize(np.float64(2.5))
    assert isinstance(out, float) and out == 2.5
    assert B0._sanitize(np.bool_(True)) is True
    assert B0._sanitize(np.int64(7)) == 7


def test_sanitize_nested_structure():
    import B0_run_calibration as B0
    nested = {"a": float("nan"), "b": np.float64(1.5), "c": [float("inf"), 2.0], "d": {"e": np.bool_(False)}}
    out = B0._sanitize(nested)
    assert out == {"a": None, "b": 1.5, "c": [None, 2.0], "d": {"e": False}}


def test_sanitize_output_is_valid_json():
    """The whole point: a sanitized structure must serialize with allow_nan=False."""
    import B0_run_calibration as B0
    dirty = {"x": float("nan"), "y": [np.float64(3.0), float("inf")]}
    text = json.dumps(B0._sanitize(dirty), allow_nan=False)
    parsed = json.loads(text)
    assert parsed == {"x": None, "y": [3.0, None]}
