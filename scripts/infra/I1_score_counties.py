"""
I1 — Score Romanian NUTS3 counties on four OSM infrastructure pillars.

Reads (immutable):
  data/raw/osm/{transport,education,health,economic_zones}.geojson
  data/raw/osm/nuts3_romania_bounds.geojson
  data/dashboard/regions.json  (county names + nuts2_code)

Writes:
  data/processed/infra_scores.parquet   (per-county scores + composite)
  data/dashboard/osm/{pillar}.geojson   (simplified POI GeoJSONs for the web map)

Returns:
  tuple: (dict of nuts3_code -> CountyCapacity-shaped dict, cronbach_alpha, corr_matrix_list)
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path
from typing import Any

import geopandas as gpd
import numpy as np
import pandas as pd
from sklearn.decomposition import PCA
from sklearn.preprocessing import StandardScaler

ROOT = Path(__file__).resolve().parents[2]
RAW_OSM = ROOT / "data" / "raw" / "osm"
OUT_SCORES = ROOT / "data" / "processed" / "infra_scores.parquet"
OUT_OSM_WEB = ROOT / "data" / "dashboard" / "osm"

PILLARS: list[str] = ["transport", "education", "health", "economic_zones"]
PILLAR_KEYS: list[str] = ["transport", "education", "health", "economic"]
EPSILON = 0.01  # floor for geometric mean (log-safe)


# ── Helpers ────────────────────────────────────────────────────────────────────

def _load_nuts3() -> gpd.GeoDataFrame:
    gdf = gpd.read_file(RAW_OSM / "nuts3_romania_bounds.geojson")
    gdf["area_km2"] = gdf.to_crs(epsg=3035).geometry.area / 1e6
    return gdf[["NUTS_ID", "geometry", "area_km2"]].rename(columns={"NUTS_ID": "nuts3_code"})


def _count_per_county(geojson_path: Path, nuts3: gpd.GeoDataFrame) -> pd.Series:
    """Feature count per county; line/polygon geometries → centroid before join."""
    import warnings
    gdf = gpd.read_file(geojson_path).to_crs(nuts3.crs)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        gdf["geometry"] = gdf.geometry.centroid
    joined = gpd.sjoin(gdf, nuts3[["nuts3_code", "geometry"]], how="left", predicate="within")
    counts = joined.groupby("nuts3_code").size()
    return pd.Series(
        {code: int(counts.get(code, 0)) for code in nuts3["nuts3_code"].values}
    )


def _raw_intensity(counts: pd.Series, area_km2: pd.Series, pop: pd.Series,
                   norm_by: str) -> pd.Series:
    """Convert raw counts to size-invariant intensities."""
    if norm_by == "area":
        return counts / area_km2.clip(lower=1.0)
    if norm_by == "pop_1k":
        return counts / (pop / 1000).clip(lower=0.1)
    return counts.astype(float)


def _winsorize_minmax(s: pd.Series, lo: float = 0.05, hi: float = 0.95) -> pd.Series:
    """Winsorise at 5/95 percentile then min–max scale to [0, 100]."""
    lo_val, hi_val = s.quantile(lo), s.quantile(hi)
    if hi_val == lo_val:
        return pd.Series(50.0, index=s.index)
    return (s.clip(lo_val, hi_val) - lo_val) / (hi_val - lo_val) * 100.0


def _geometric_mean(row: pd.Series, epsilon: float = EPSILON) -> float:
    """Geometric mean with floor to avoid log(0). Geometric ≤ arithmetic."""
    vals = np.maximum(row.values.astype(float), epsilon)
    return float(np.exp(np.mean(np.log(vals))))


def _cronbach_alpha(df: pd.DataFrame) -> float:
    """Cronbach's alpha (internal consistency across k=4 pillar columns)."""
    k = df.shape[1]
    if k < 2:
        return float("nan")
    item_var = df.var(ddof=1).sum()
    total_var = df.sum(axis=1).var(ddof=1)
    if total_var == 0:
        return float("nan")
    return float(k / (k - 1) * (1 - item_var / total_var))


def _pca_weights(scores_df: pd.DataFrame) -> np.ndarray:
    """First-component loadings as weights (absolute, normalized to sum 1)."""
    X = StandardScaler().fit_transform(scores_df.values)
    pca = PCA(n_components=1, random_state=42)
    pca.fit(X)
    loadings = np.abs(pca.components_[0])
    return loadings / loadings.sum()


def _data_confidence(raw_count: int, area_km2: float) -> str:
    density = raw_count / max(area_km2, 1.0)
    if density > 0.05 or raw_count > 10:
        return "high"
    if density > 0.005 or raw_count >= 2:
        return "medium"
    return "low"


def _find_peers(code: str, pillar_matrix: pd.DataFrame, n: int = 2) -> list[str]:
    """n nearest counties by Euclidean distance on normalized pillar vector."""
    target = pillar_matrix.loc[code].values
    dists = pillar_matrix.drop(code).apply(
        lambda row: float(np.linalg.norm(row.values - target)), axis=1
    )
    return dists.nsmallest(n).index.tolist()


def _national_percentile(code: str, scores: pd.Series) -> int:
    score = scores.loc[code]
    below = (scores < score).sum()
    return int(round(below / len(scores) * 100))


def _write_web_geojson(raw_path: Path, nuts3: gpd.GeoDataFrame, pillar_key: str) -> None:
    """Write simplified (centroid) POI GeoJSON to data/dashboard/osm/ for the web map."""
    import warnings
    gdf = gpd.read_file(raw_path).to_crs(nuts3.crs)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        gdf["geometry"] = gdf.geometry.centroid
    joined = gpd.sjoin(gdf, nuts3[["nuts3_code", "geometry"]], how="left", predicate="within")
    joined = joined[joined["nuts3_code"].notna()].copy()
    keep = ["geometry", "nuts3_code"]
    for col in ["name", "amenity", "highway", "railway", "aeroway", "landuse", "beds"]:
        if col in joined.columns:
            keep.append(col)
    OUT_OSM_WEB.mkdir(parents=True, exist_ok=True)
    joined[keep].to_file(OUT_OSM_WEB / f"{pillar_key}.geojson", driver="GeoJSON")


# ── Main extract function ──────────────────────────────────────────────────────

def extract() -> tuple[dict[str, Any], float, list]:
    """
    Run the full composite pipeline.
    Returns (counties_dict, cronbach_alpha, corr_matrix_as_list).
    Writes infra_scores.parquet and osm web GeoJSONs.
    """
    nuts3 = _load_nuts3()

    # Load county names from regions.json
    try:
        regions_raw = json.loads((ROOT / "data" / "dashboard" / "regions.json").read_text())
        name_map = {r["nuts3_code"]: r["judet_name"] for r in regions_raw}
        nuts2_map = {r["nuts3_code"]: r.get("nuts2_code", "") for r in regions_raw}
        pop_map = {r["nuts3_code"]: r.get("population", None) for r in regions_raw}
    except Exception:
        name_map = {}
        nuts2_map = {}
        pop_map = {}

    codes = nuts3["nuts3_code"].values
    area = nuts3.set_index("nuts3_code")["area_km2"]
    pop = pd.Series({code: (pop_map.get(code) or area[code] * 100) for code in codes})

    # ── 1. Raw feature counts per pillar
    raw_counts: dict[str, pd.Series] = {}
    for pillar, key in zip(PILLARS, PILLAR_KEYS):
        path = RAW_OSM / f"{pillar}.geojson"
        counts = _count_per_county(path, nuts3.copy())
        raw_counts[key] = counts
        _write_web_geojson(path, nuts3.copy(), key)

    # ── 2. Size-invariant intensities
    intensities: dict[str, pd.Series] = {
        "transport": _raw_intensity(raw_counts["transport"], area, pop, "area"),
        "education": _raw_intensity(raw_counts["education"], area, pop, "pop_1k"),
        "health":    _raw_intensity(raw_counts["health"],    area, pop, "pop_1k"),
        "economic":  _raw_intensity(raw_counts["economic"],  area, pop, "area"),
    }

    # ── 3. Winsorise + min–max normalise to [0, 100]
    normed: dict[str, pd.Series] = {k: _winsorize_minmax(v) for k, v in intensities.items()}
    scores_df = pd.DataFrame(normed, index=codes)

    # ── 4. Construct validity
    alpha = _cronbach_alpha(scores_df)
    corr = scores_df.corr().round(3)
    print(f"  Cronbach alpha = {alpha:.3f}")

    # ── 5. Composite: geometric (default) and arithmetic
    composite_geom = scores_df.apply(_geometric_mean, axis=1)
    n_pillars = len(PILLAR_KEYS)
    equal_w = np.array([1.0 / n_pillars] * n_pillars)
    composite_arith = scores_df.apply(
        lambda r: float(np.average(r.values, weights=equal_w)), axis=1
    )

    # ── 6. Data confidence per pillar per county
    def confidence_series(key: str) -> pd.Series:
        return pd.Series({
            code: _data_confidence(int(raw_counts[key].get(code, 0)), float(area.get(code, 1.0)))
            for code in codes
        })

    conf: dict[str, pd.Series] = {k: confidence_series(k) for k in PILLAR_KEYS}

    # ── 7. Peer counties
    peers: dict[str, list[str]] = {
        code: _find_peers(code, scores_df) for code in codes
    }

    # ── 8. National percentile
    percentiles = {code: _national_percentile(code, composite_geom) for code in codes}

    # ── 9. Save parquet
    OUT_SCORES.parent.mkdir(parents=True, exist_ok=True)
    pq = scores_df.copy()
    pq["capacity_index"] = composite_geom
    pq["capacity_index_arithmetic"] = composite_arith
    pq.to_parquet(OUT_SCORES)

    # ── 10. Build output dict
    result: dict[str, Any] = {}
    for code in codes:
        result[code] = {
            "name": name_map.get(code, code),
            "nuts2_code": nuts2_map.get(code, ""),
            "capacity_index": round(float(composite_geom[code]), 1),
            "capacity_index_arithmetic": round(float(composite_arith[code]), 1),
            "national_percentile": percentiles[code],
            "rank_interval": [0, 0],
            "rank_median": 0,
            "pillars": {
                k: {
                    "score": round(float(scores_df.loc[code, k]), 1),
                    "features": int(raw_counts[k].get(code, 0)),
                    "confidence": conf[k][code],
                }
                for k in PILLAR_KEYS
            },
            "peers": peers[code],
            "divergence": None,
        }

    pca_w = _pca_weights(scores_df)
    print(f"  PCA weights: {dict(zip(PILLAR_KEYS, pca_w.round(3).tolist()))}")
    return result, alpha, corr.values.tolist()


if __name__ == "__main__":
    print("=== I1: Scoring counties ===")
    result, alpha, _ = extract()
    print(f"  {len(result)} counties scored")
    print(f"  Written: {OUT_SCORES}")
    print(f"  Written: {OUT_OSM_WEB}/*.geojson")
