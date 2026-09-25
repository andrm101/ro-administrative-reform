"""Build v0 engine fixtures: fiscal_primitives.json (derived) + elasticities.json (literature priors).

Reproducible from processed parquets. Elasticity values are PROVISIONAL literature priors
(provisional=true); Plan 2 calibration replaces them with estimated coefficients.
Run: python scripts/A0_build_engine_fixtures.py
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
PROCESSED = ROOT / "data" / "processed"
OUT = ROOT / "data" / "dashboard"

# Employment-to-population ratio to convert GVA-per-employed → GVA-per-capita (v0 constant).
EMP_POP_RATIO = 0.42
REFORM_YEAR = 2025


def build_primitives() -> dict:
    fc = pd.read_parquet(PROCESSED / "ro_pvar_forecasts_roi.parquet")
    suit = pd.read_parquet(PROCESSED / "ro_nuts3_suitability.parquet")

    # Get 2025 status_quo values
    sq = fc[(fc["path"] == "status_quo") & (fc["year"] == REFORM_YEAR)]
    gva = sq[sq["variable"] == "ln_gva_per_empl"].set_index("nuts3_code")["value"]
    pop = sq[sq["variable"] == "ln_population"].set_index("nuts3_code")["value"]

    # Filter suitability to counties present in forecast data
    forecast_codes = set(gva.index) & set(pop.index)
    suit_filtered = suit[suit["nuts3_code"].isin(forecast_codes)].copy()

    # Identify suitability tier columns (T1-T8, using T4_adjusted where available)
    tier_cols = [c for c in suit_filtered.columns if c.startswith("suitability_T")]
    # Prefer T4_adjusted over T4 if it exists
    if "suitability_T4_adjusted" in tier_cols and "suitability_T4" in tier_cols:
        tier_cols = [c for c in tier_cols if c != "suitability_T4"]

    # Infer hub = highest-vitality county per NUTS2 (within forecast counties only)
    suit_filtered["_nuts2"] = suit_filtered["nuts3_code"].str.slice(0, 4)
    hub_codes = set(
        suit_filtered.sort_values("vitality_index", ascending=True)
        .groupby("_nuts2")
        .tail(1)["nuts3_code"]
    )

    counties = []
    for _, r in suit_filtered.iterrows():
        code = r["nuts3_code"]
        if code not in gva.index or code not in pop.index:
            continue
        gva_pc = float(np.exp(gva[code]) * EMP_POP_RATIO)
        population = float(np.exp(pop[code]))
        # Dominant tier: highest suitability score among tier columns
        if tier_cols:
            dom_col = max(tier_cols, key=lambda c: r[c])
            # Convert column name to tier label: suitability_T4_adjusted → T4, suitability_T1 → T1
            dom_tier = dom_col.replace("suitability_", "").replace("_adjusted", "").upper()
        else:
            dom_tier = "T4"
        counties.append({
            "nuts3_code": code,
            "nuts2_code": str(r["nuts2_code"]),
            "role": "hub" if code in hub_codes else "satellite",
            "gva_pc": round(gva_pc, 2),
            "population": round(population, 0),
            "vitality_index": float(r["vitality_index"]),
            "tier1_gate": bool(r["tier1_gate"]),
            "moretti_tier": dom_tier,
        })

    return {"counties": counties}


def build_elasticities() -> dict:
    def e(value, se, ids, src, support):
        return {"value": value, "se": se, "id_strategy": ids, "source": src, "support": list(support)}

    return {
        "beta_gov": e(0.04, 0.015, "PL-1999 RD prior", "literature v0", [0, 1]),
        "beta_K_hub": e(0.08, 0.03, "convergence prior (agglomeration)", "literature v0", [0, 0.5]),
        "beta_K_sat": e(0.22, 0.06, "convergence prior (catch-up)", "literature v0", [0, 0.6]),
        "beta_mig": e(0.6, 0.25, "PL migration prior", "literature v0", [0, 400]),
        "beta_fert": e(0.004, 0.0015, "Rodzina 500+ prior", "literature v0", [0, 600]),
        "beta_edu": e(0.03, 0.01, "Mincerian prior", "literature v0", [0, 5]),
        "gamma": e(0.3, 0.15, "accessibility prior", "literature v0 (weak)", [0, 1]),
        "lambda": e(0.4, 0.2, "PL intra-regional flows prior", "literature v0", [0, 1]),
        "tau": 0.2,
        "delta": 0.05,
        "discount_rate": 0.03,
        "moretti": {"T1": 0.025, "T2": 0.020, "T3": 0.015, "T4": 0.012,
                     "T5": 0.010, "T6": 0.008, "T7": 0.007, "T8": 0.006},
        "provisional": True,
    }


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    primitives = build_primitives()
    print(f"Built {len(primitives['counties'])} counties:")
    for c in primitives["counties"]:
        print(f"  {c['nuts3_code']} ({c['nuts2_code']}) role={c['role']} vitality={c['vitality_index']:.3f} tier={c['moretti_tier']}")
    (OUT / "fiscal_primitives.json").write_text(json.dumps(primitives, indent=2))
    (OUT / "elasticities.json").write_text(json.dumps(build_elasticities(), indent=2))
    print(f"\nWrote fiscal_primitives.json and elasticities.json to {OUT}")


if __name__ == "__main__":
    main()
