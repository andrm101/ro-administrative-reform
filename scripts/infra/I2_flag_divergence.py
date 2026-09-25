"""
I2 — Structural divergence detection.

Compares recent GVA growth (2019–2023 from regions.json) against the
composite capacity index from I1. Flags counties as structural_bottleneck
or latent_fragility using studentized leave-one-out residuals + LISA.

Returns:
  dict: nuts3_code → DivergenceFlag-shaped dict, or None if no flag.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import geopandas as gpd
import numpy as np
import pandas as pd
import statsmodels.api as sm
import yaml
from libpysal.weights import Queen
from esda.moran import Moran_Local

ROOT = Path(__file__).resolve().parents[2]
RAW_OSM = ROOT / "data" / "raw" / "osm"
HYPOTHESES_PATH = Path(__file__).parent / "structural_hypotheses.yaml"

RESID_THRESHOLD = 2.0   # |externally studentized t| > 2 → flag


# ── Helpers ────────────────────────────────────────────────────────────────────

def _recent_gva_growth() -> pd.Series:
    """4-year GVA growth = actual[2023] - actual[2019] from regions.json."""
    regions = json.loads((ROOT / "data" / "dashboard" / "regions.json").read_text())
    result: dict[str, float] = {}
    for r in regions:
        series = {
            p["year"]: p["actual"]
            for p in r["counterfactualSeries"]
            if p.get("actual") is not None and p["actual"] != 0.0
        }
        if 2019 in series and 2023 in series:
            result[r["nuts3_code"]] = series[2023] - series[2019]
    return pd.Series(result)


def _studentized_loo_residuals(x: np.ndarray, y: np.ndarray) -> np.ndarray:
    """Externally studentized leave-one-out residuals from OLS y ~ 1 + x."""
    X = sm.add_constant(x)
    model = sm.OLS(y, X).fit()
    influence = model.get_influence()
    return influence.resid_studentized_external


def _lisa_quadrants(capacity: pd.Series, nuts3_gdf: gpd.GeoDataFrame) -> pd.Series:
    """Local Moran's I quadrant per county using queen-contiguity weights."""
    merged = nuts3_gdf.set_index("nuts3_code")[["geometry"]].join(
        capacity.rename("cap"), how="inner"
    )
    if len(merged) < 4:
        return pd.Series("NS", index=merged.index)
    w = Queen.from_dataframe(merged, use_index=True, silence_warnings=True)
    w.transform = "r"
    lm = Moran_Local(merged["cap"].values, w, seed=42)
    # esda quadrant convention: 1=HH, 2=LH, 3=LL, 4=HL
    quad_map = {1: "HH", 2: "LH", 3: "LL", 4: "HL"}
    return pd.Series(
        [quad_map.get(int(q), "NS") for q in lm.q],
        index=merged.index,
    )


def _classify_divergence(resid_t: float, lisa_quad: str) -> str | None:
    """Return divergence type or None if within threshold."""
    if resid_t > RESID_THRESHOLD:
        return "structural_bottleneck"   # high capacity, below-trend outcome
    if resid_t < -RESID_THRESHOLD:
        return "latent_fragility"        # low capacity, above-trend outcome
    return None


def _load_hypotheses() -> dict[str, str]:
    if not HYPOTHESES_PATH.exists():
        return {}
    with open(HYPOTHESES_PATH) as f:
        raw = yaml.safe_load(f) or {}
    return {code: v.get("hypothesis", "") for code, v in raw.items()}


def _data_caveat(county_capacity: dict, divtype: str) -> str | None:
    """Return caveat string if the divergence flag rests on a low-confidence pillar."""
    low_pillars = [
        k for k, v in county_capacity["pillars"].items()
        if v["confidence"] == "low"
    ]
    if not low_pillars:
        return None
    return (
        f"The {', '.join(low_pillars)} pillar(s) have low OSM coverage confidence. "
        f"This flag may reflect incomplete data rather than a structural condition."
    )


# ── Main extract function ──────────────────────────────────────────────────────

def extract(counties: dict[str, Any]) -> dict[str, Any | None]:
    """
    Args:
        counties: dict from I1.extract()[0] — nuts3_code → CountyCapacity-shaped dict
    Returns:
        dict: nuts3_code → DivergenceFlag dict, or None if no flag
    """
    hypotheses = _load_hypotheses()

    # Build aligned capacity + growth arrays
    growth = _recent_gva_growth()
    capacity = pd.Series({code: c["capacity_index"] for code, c in counties.items()})

    common = capacity.index.intersection(growth.index)
    cap_arr = capacity.loc[common].values.astype(float)
    gro_arr = growth.loc[common].values.astype(float)

    resids = _studentized_loo_residuals(cap_arr, gro_arr)
    resid_series = pd.Series(resids, index=common)

    # LISA
    nuts3_gdf = gpd.read_file(RAW_OSM / "nuts3_romania_bounds.geojson")[["NUTS_ID", "geometry"]]
    nuts3_gdf = nuts3_gdf.rename(columns={"NUTS_ID": "nuts3_code"})
    nuts3_gdf = nuts3_gdf[nuts3_gdf["nuts3_code"].isin(common)]
    lisa = _lisa_quadrants(capacity.loc[common], nuts3_gdf)

    n_flagged = 0
    result: dict[str, Any | None] = {code: None for code in counties}

    for code in common:
        t = float(resid_series.loc[code])
        quad = str(lisa.loc[code]) if code in lisa.index else "NS"
        divtype = _classify_divergence(t, quad)
        if divtype is None:
            continue

        caveat = _data_caveat(counties[code], divtype)
        generic_hyp = (
            "Structural mismatch between infrastructure endowment and realised growth. "
            "Investigate regulatory, institutional, or compositional factors locally. "
            "Hypothesis for investigation, not a causal claim."
        )
        result[code] = {
            "type": divtype,
            "resid_t": round(t, 3),
            "lisa_quadrant": quad,
            "data_caveat": caveat,
            "structural_hypothesis": hypotheses.get(code, generic_hyp),
        }
        n_flagged += 1

    print(f"  Flagged {n_flagged} counties (threshold |t|>{RESID_THRESHOLD})")
    print(f"  Low-power note: n~{len(common)} counties; ~2 false positives expected under null")
    return result


if __name__ == "__main__":
    sys.path.insert(0, str(ROOT / "scripts" / "infra"))
    import I1_score_counties as I1
    print("=== I2: Divergence detection ===")
    counties, _, _ = I1.extract()
    flags = extract(counties)
    flagged = {k: v for k, v in flags.items() if v is not None}
    print(f"  Flagged: {list(flagged.keys())}")
