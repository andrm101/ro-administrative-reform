"""
B0 — Calibration orchestrator.

Runs B1 → B2 → B3, merges outputs with v0 literature priors, and writes
data/dashboard/elasticities.json with provenance metadata and regime_test.

Run: python scripts/calibration/B0_run_calibration.py
Idempotent: B1/B2 are seeded (42) and B3 is deterministic, so re-running produces
identical numbers (modulo estimated_at/git_sha, written into provenance).
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "calibration"))

import B1_extract_lpirf_betas as B1
import B2_barro_convergence_gmm as B2
import B3_oos_validation_gate as B3

OUT = ROOT / "data" / "dashboard" / "elasticities.json"


def _literature_priors(lambda_comovement: float) -> dict:
    """Four literature priors. The lambda provenance embeds the actual hub/satellite
    migration co-movement computed by B2, explaining why conservation is not identified."""
    return {
        "lambda": {
            "value": 0.4,
            "se": 0.2,
            "id_strategy": "literature prior (conservation not identified — see diagnostics)",
            "source": "PL intra-regional flows (Baranowska-Rataj & Matysiak 2012)",
            "support": [0.0, 1.0],
            "provenance": {
                "method": (
                    "Literature prior. Post-reform period empty (reform_year=2025), so a "
                    "hub→satellite conservation ratio is unobservable. Historical within-NUTS2 "
                    f"hub/satellite net-migration co-movement = {lambda_comovement:+.3f} "
                    "(they move together under common regional shocks, not in substitution), "
                    "so conservation is not identified from observed data either."
                ),
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
                "method": (
                    "Literature prior. The panel's nat_change_rate LP-IRF shows births falling "
                    "after demotion (a treatment-direction artefact), the wrong sign for a "
                    "pronatalist-transfer elasticity; using it would be a sign error."
                ),
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
                "method": "Literature prior. No skills-investment series exists in panel_judet.",
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
                "method": "Literature prior. No ESPON accessibility dataset ingested (deferred to Plan 3).",
                "citation": "Holl (2007) — Roads and regional economic growth in Spain",
            },
        },
    }


SCALAR_ASSUMPTIONS = {
    "tau": 0.2,
    "delta": 0.05,
    "discount_rate": 0.03,
    "moretti": {
        "T1": 0.025, "T2": 0.020, "T3": 0.015, "T4": 0.012,
        "T5": 0.010, "T6": 0.008, "T7": 0.007, "T8": 0.006,
    },
}


def _sanitize(obj):
    """Recursively coerce to JSON-safe types: numpy scalars → Python scalars, and
    non-finite floats (NaN/±Inf) → None. Bare NaN/Infinity tokens are invalid JSON
    and break the browser engine; null is the honest representation of an
    uncomputable value (e.g. a cross-check whose comparand is absent)."""
    if isinstance(obj, dict):
        return {k: _sanitize(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_sanitize(v) for v in obj]
    if isinstance(obj, np.generic):
        obj = obj.item()
    if isinstance(obj, float):
        return obj if math.isfinite(obj) else None
    return obj


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
    print(f"  IPS p = {b2['diagnostics']['ips_pvalue']:.3f}")
    print(f"  lambda co-movement = {b2['diagnostics']['lambda_comovement']:.3f}")

    print("\n[B3] Running OOS validation gate...")
    b3 = B3.run()
    print(f"  {b3['conclusion']}")

    priors = _literature_priors(b2["diagnostics"]["lambda_comovement"])

    elast = {
        # Empirical β's
        "beta_gov": b1["beta_gov"],
        "beta_K_hub": b2["beta_K_hub"],
        "beta_K_sat": b2["beta_K_sat"],
        "beta_mig": b1["beta_mig"],
        # Literature priors
        **priors,
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

    # Shape assertion before writing
    for key in ("beta_gov", "beta_K_hub", "beta_K_sat", "beta_mig", "lambda",
                "beta_fert", "beta_edu", "gamma", "tau", "delta", "discount_rate",
                "moretti", "regime_test", "diagnostics", "provisional"):
        assert key in elast, f"Missing key in output: {key}"

    # The four empirical betas must be finite (a NaN here is a calibration failure,
    # not a benign missing-diagnostic NaN like the SDiD cross-check).
    for key in ("beta_gov", "beta_K_hub", "beta_K_sat", "beta_mig"):
        v = elast[key]["value"]
        assert math.isfinite(v), f"{key}.value is not finite: {v}"

    OUT.parent.mkdir(parents=True, exist_ok=True)
    # Sanitize before serializing: bare NaN/Infinity are invalid JSON (RFC 8259) and
    # crash the browser's JSON.parse. allow_nan=False is the hard backstop if any slip
    # through _sanitize. Non-finite floats (e.g. the SDiD cross-check when the outcome
    # is absent from the SDiD table) become null; numpy scalars become Python scalars.
    OUT.write_text(json.dumps(_sanitize(elast), indent=2, allow_nan=False))
    print(f"\n✓ Written {OUT}  (provisional={elast['provisional']})")
    print("  Shape assertions passed.")


if __name__ == "__main__":
    main()
