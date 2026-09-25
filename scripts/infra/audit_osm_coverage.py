"""
Audit OSM coverage per county before running the scoring pipeline.
GATE: if > 15 counties have < 2 features in ANY pillar, that pillar
needs scope reduction before proceeding to I1.

Run: python scripts/infra/audit_osm_coverage.py
"""
from __future__ import annotations
import sys
import warnings
from pathlib import Path
import geopandas as gpd
import pandas as pd

# Suppress geopandas centroid-in-geographic-CRS warning (we use WGS84 for a
# point-in-polygon count only; sub-metre centroid error is immaterial here).
warnings.filterwarnings("ignore", message="Geometry is in a geographic CRS")

ROOT = Path(__file__).resolve().parents[2]
RAW_OSM = ROOT / "data" / "raw" / "osm"
PILLARS = ["transport", "education", "health", "economic_zones"]
GATE_THRESHOLD = 15  # max counties allowed with < 2 features


def _load_nuts3() -> gpd.GeoDataFrame:
    path = RAW_OSM / "nuts3_romania_bounds.geojson"
    if not path.exists():
        raise FileNotFoundError(f"Missing {path}. Run Step 2 first.")
    gdf = gpd.read_file(path)
    return gdf[["NUTS_ID", "geometry"]].rename(columns={"NUTS_ID": "nuts3_code"})


def _count_per_county(geojson_path: Path, nuts3: gpd.GeoDataFrame) -> pd.Series:
    """Return feature count per county via centroid spatial join."""
    gdf = gpd.read_file(geojson_path).to_crs(nuts3.crs)
    gdf["geometry"] = gdf.geometry.centroid
    joined = gpd.sjoin(gdf, nuts3, how="left", predicate="within")
    counts = joined.groupby("nuts3_code").size()
    return pd.Series(
        [int(counts.get(code, 0)) for code in nuts3["nuts3_code"]],
        index=nuts3["nuts3_code"].values
    )


def main() -> None:
    nuts3 = _load_nuts3()
    pass_all = True

    for pillar in PILLARS:
        path = RAW_OSM / f"{pillar}.geojson"
        if not path.exists():
            print(f"  MISSING: {pillar}.geojson — cannot proceed")
            pass_all = False
            continue

        counts = _count_per_county(path, nuts3.copy())
        sparse = (counts < 2).sum()
        total = len(counts)
        print(f"  {pillar}: {int(counts.sum())} features total, "
              f"{sparse}/{total} counties have <2 features "
              f"({'FAIL' if sparse > GATE_THRESHOLD else 'ok'})")

        if sparse > GATE_THRESHOLD:
            pass_all = False

    if pass_all:
        print("\n✓ AUDIT PASSED — proceed to Task 2 (I1_score_counties.py)")
    else:
        print("\n✗ AUDIT FAILED — reduce scope of sparse pillars before proceeding")
        sys.exit(1)


if __name__ == "__main__":
    main()
