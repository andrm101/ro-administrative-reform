"""
I0 -- Infra layer orchestrator (v1b, full).
Runs I1 -> I2 -> I3 and writes data/dashboard/infra_layer.json.

Run: python scripts/infra/I0_build_infra_layer.py
Idempotent: all sub-scripts are seeded (42); re-running produces identical output
modulo overpass_query_date / git_sha in _meta.
"""
from __future__ import annotations

import json
import math
import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "infra"))

import I1_score_counties as I1
import I2_flag_divergence as I2
import I3_sensitivity as I3

OUT = ROOT / "data" / "dashboard" / "infra_layer.json"


def _sanitize(obj):
    """Recursively coerce numpy scalars -> Python, non-finite floats -> None."""
    if isinstance(obj, dict):
        return {k: _sanitize(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_sanitize(v) for v in obj]
    if isinstance(obj, np.generic):
        obj = obj.item()
    if isinstance(obj, float):
        return obj if math.isfinite(obj) else None
    return obj


def _git_sha() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"], cwd=ROOT
        ).decode().strip()
    except Exception:
        return "unknown"


def main() -> None:
    print("=== I0 (v1b): Building infra_layer.json ===\n")

    print("[I1] Scoring counties...")
    counties, alpha, corr = I1.extract()
    print(f"  ✓ {len(counties)} counties scored  (Cronbach alpha={alpha:.3f})")

    print("\n[I2] Flagging divergence...")
    flags = I2.extract(counties)

    print("\n[I3] Computing sensitivity ensemble...")
    scores_df = pd.read_parquet(ROOT / "data" / "processed" / "infra_scores.parquet")[
        ["transport", "education", "health", "economic"]
    ]
    sensitivity = I3.extract(scores_df)

    # Merge I2 and I3 outputs into counties
    for code in counties:
        counties[code]["divergence"] = flags.get(code)
        if code in sensitivity:
            counties[code]["rank_interval"] = sensitivity[code]["rank_interval"]
            counties[code]["rank_median"] = sensitivity[code]["rank_median"]

    ensemble_variants = 8

    meta = {
        "overpass_query_date": "2026-06-06",
        "script_version": "1.0.0",
        "git_sha": _git_sha(),
        "aggregation_default": "geometric",
        "weighting_default": "equal",
        "cronbach_alpha": round(alpha, 3) if math.isfinite(alpha) else None,
        "pillar_correlation": corr,
        "ensemble_variants": ensemble_variants,
    }

    output = {"_meta": meta, "counties": counties}

    # Shape assertions
    for key in ("_meta", "counties"):
        assert key in output, f"Missing top-level key: {key}"
    assert len(output["counties"]) > 0
    # Spot-check first county has all required fields
    first = next(iter(output["counties"].values()))
    for field in ("capacity_index", "pillars", "rank_interval", "divergence"):
        assert field in first, f"County missing field: {field}"

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(_sanitize(output), indent=2, allow_nan=False))
    print(f"\n✓ Written {OUT}")
    flagged = sum(1 for v in counties.values() if v.get("divergence") is not None)
    print(f"  {len(counties)} counties, {flagged} divergence flags, alpha={alpha:.3f}")


if __name__ == "__main__":
    main()
