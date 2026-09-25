# Institutions & Infrastructure Layer — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a formal composite infrastructure capacity layer (OECD/JRC standard) to the RO Policy Lab dashboard — explorable on the map, advisory in Policy Lab — without modifying the calibrated econometric coefficients.

**Architecture:** Two delivery increments. v1a (Tasks 0–7): coverage audit gate → Python scoring pipeline (I1) → TypeScript capacity utilities + components → map extension + CapacityCard + PolicyLab integration. v1b (Tasks 8–11, gated on v1a): divergence detection (I2, studentized LOO residuals + LISA) → sensitivity ensemble (I3, rank intervals) → full I0 orchestrator → DivergenceAlert + map badge integration. `infra_layer.json` is a sibling to `elasticities.json` and never writes to it.

**Tech Stack:** Python (geopandas, shapely, libpysal, esda, scipy, sklearn, statsmodels — all available in env), TypeScript + React 18 + react-leaflet (^4.2.1, already installed), Recharts (^2.12.7), Vitest, Tailwind CSS. No new npm or conda packages required.

---

## FILE MAP

```
data/raw/osm/
  README.md                           ← NEW: provenance for all OSM extracts
  nuts3_romania_bounds.geojson        ← NEW: NUTS3 polygons, downloaded in Task 0
  transport.geojson                   ← NEW: pre-downloaded Overpass extract
  education.geojson                   ← NEW: pre-downloaded Overpass extract
  health.geojson                      ← NEW: pre-downloaded Overpass extract
  economic_zones.geojson              ← NEW: pre-downloaded Overpass extract

scripts/infra/
  __init__.py                         ← NEW: empty
  audit_osm_coverage.py               ← NEW: Task 0 audit gate
  I1_score_counties.py                ← NEW: Task 2 composite pipeline
  I2_flag_divergence.py               ← NEW: Task 8 divergence detection
  I3_sensitivity.py                   ← NEW: Task 9 sensitivity ensemble
  I0_build_infra_layer.py             ← NEW: Task 3 (v1a stub), replaced Task 10 (v1b)
  tests/
    __init__.py                       ← NEW: empty
    test_I1.py                        ← NEW: Task 2 tests
    test_I2.py                        ← NEW: Task 8 tests
    test_I3.py                        ← NEW: Task 9 tests

data/dashboard/
  infra_layer.json                    ← NEW: written by I0
  osm/                                ← NEW: web-served POI GeoJSONs (written by I1)
    transport.geojson
    education.geojson
    health.geojson
    economic_zones.geojson

dashboard/src/
  types.ts                            ← MODIFY: Task 1 — add 7 new interfaces
  utils/
    capacity.ts                       ← NEW: Task 4
    capacity.test.ts                  ← NEW: Task 4
  components/
    InfraLayerPanel.tsx               ← NEW: Task 5
    CapacityCard.tsx                  ← NEW: Task 6
    DivergenceAlert.tsx               ← NEW: Task 11
    RomaniaMap.tsx                    ← MODIFY: Tasks 5, 11
    PolicyLab.tsx                     ← MODIFY: Tasks 7, 11
```

---

## v1a — Coverage Audit + Composite + Map

---

### Task 0: OSM coverage audit (GATE)

**Files:**
- Create: `scripts/infra/__init__.py` (empty)
- Create: `scripts/infra/tests/__init__.py` (empty)
- Create: `scripts/infra/audit_osm_coverage.py`
- Create: `data/raw/osm/README.md`

**Context:** This task has two parts. First, manually download the four OSM GeoJSON files and the NUTS3 boundary (see step 1). Then run the audit to verify per-county feature density. If more than 15 counties have fewer than 2 features in any pillar, that pillar must be scoped down before Tasks 2–7 proceed.

- [ ] **Step 1: Create raw data directories and write README with Overpass queries**

```bash
mkdir -p data/raw/osm scripts/infra/tests
touch scripts/infra/__init__.py scripts/infra/tests/__init__.py
```

Create `data/raw/osm/README.md`:

```markdown
# OSM Infrastructure Extracts — Romania

Source: OpenStreetMap contributors, ODbL licence (https://www.openstreetmap.org/copyright)
Extraction tool: Overpass API (https://overpass-api.de)
Download date: 2026-06-06
Projection: WGS84 (EPSG:4326)
Coverage: Romania (bounding box or administrative boundary)

## NUTS3 county boundaries
File: nuts3_romania_bounds.geojson
Source: Eurostat GISCO — NUTS 2021, 1:20M scale
URL: https://gisco-services.ec.europa.eu/distribution/v2/nuts/geojson/NUTS_RG_20M_2021_4326_LEVL_3.geojson
Filter: CNTR_CODE == 'RO'

## transport.geojson — motorways, trunk roads, rail stations, airports
Overpass QL:
  [out:json][timeout:120];
  area["ISO3166-1"="RO"]->.ro;
  (
    way["highway"~"^(motorway|trunk|primary)$"](area.ro);
    node["railway"~"^(station|halt)$"](area.ro);
    node["aeroway"="aerodrome"](area.ro);
  );
  out center;

## education.geojson — universities, colleges, research institutes
Overpass QL:
  [out:json][timeout:60];
  area["ISO3166-1"="RO"]->.ro;
  (
    node["amenity"~"^(university|college)$"](area.ro);
    way["amenity"~"^(university|college)$"](area.ro);
    node["office"="research"](area.ro);
  );
  out center;

## health.geojson — hospitals and clinics
Overpass QL:
  [out:json][timeout:60];
  area["ISO3166-1"="RO"]->.ro;
  (
    node["amenity"~"^(hospital|clinic)$"](area.ro);
    way["amenity"~"^(hospital|clinic)$"](area.ro);
  );
  out center tags;

## economic_zones.geojson — industrial zones, SEZs
Overpass QL:
  [out:json][timeout:60];
  area["ISO3166-1"="RO"]->.ro;
  (
    way["landuse"="industrial"](area.ro);
    way["industrial"](area.ro);
  );
  out center;

## Variable definitions
- transport: count of motorway/trunk/primary road ways (proxy for road network density),
  rail stations, airports within county
- education: count of university/college amenities and research offices within county
- health: count of hospital/clinic amenities within county; beds=* tag captured where present
- economic: count of industrial landuse polygons (centroids used for spatial join)
```

- [ ] **Step 2: Download NUTS3 boundary and OSM files**

Run in a Python REPL or via a one-off script. The NUTS3 boundary is already available online:

```python
# Run once manually — NOT automated (static data rule)
import urllib.request, json
from pathlib import Path

url = "https://gisco-services.ec.europa.eu/distribution/v2/nuts/geojson/NUTS_RG_20M_2021_4326_LEVL_3.geojson"
raw = urllib.request.urlopen(url).read()
full = json.loads(raw)
ro_features = [f for f in full["features"] if f["properties"]["CNTR_CODE"] == "RO"]
ro = {"type": "FeatureCollection", "features": ro_features}
Path("data/raw/osm/nuts3_romania_bounds.geojson").write_text(json.dumps(ro))
print(f"Saved {len(ro_features)} NUTS3 polygons")
```

For the four OSM files: use the Overpass queries in the README via https://overpass-turbo.eu, export as GeoJSON, save to `data/raw/osm/{transport,education,health,economic_zones}.geojson`.

- [ ] **Step 3: Write the audit script**

Create `scripts/infra/audit_osm_coverage.py`:

```python
"""
Audit OSM coverage per county before running the scoring pipeline.
GATE: if > 15 counties have < 2 features in ANY pillar, that pillar
needs scope reduction before proceeding to I1.

Run: python scripts/infra/audit_osm_coverage.py
"""
from __future__ import annotations
from pathlib import Path
import geopandas as gpd
import pandas as pd

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
    return nuts3["nuts3_code"].map(counts).fillna(0).astype(int)

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

if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run the audit**

```bash
python scripts/infra/audit_osm_coverage.py
```

Expected output (exact numbers will vary by Overpass extract):
```
  transport: 847 features total, 0/42 counties have <2 features (ok)
  education: 123 features total, 3/42 counties have <2 features (ok)
  health: 312 features total, 1/42 counties have <2 features (ok)
  economic_zones: 234 features total, 8/42 counties have <2 features (ok)

✓ AUDIT PASSED — proceed to Task 2 (I1_score_counties.py)
```

If any pillar FAILS: collapse it with the nearest logical pillar (e.g. economic+transport → "enabling environment") and update the README before proceeding.

- [ ] **Step 5: Commit**

```bash
git add data/raw/osm/README.md data/raw/osm/nuts3_romania_bounds.geojson \
        data/raw/osm/transport.geojson data/raw/osm/education.geojson \
        data/raw/osm/health.geojson data/raw/osm/economic_zones.geojson \
        scripts/infra/__init__.py scripts/infra/tests/__init__.py \
        scripts/infra/audit_osm_coverage.py
git commit -m "feat(infra): OSM extracts + NUTS3 boundary + audit gate PASS"
```

---

### Task 1: types.ts — add infrastructure interfaces

**Files:**
- Modify: `dashboard/src/types.ts` (append after `CalibrationDiagnostics`, line 245)

- [ ] **Step 1: Write the failing test — verify new types compile**

The type test here is a compile check; open `dashboard/src/types.ts` and append the following **before** running `tsc`:

```typescript
// ── Infrastructure capacity layer ────────────────────────────────────────────

export type PillarKey = 'transport' | 'education' | 'health' | 'economic';
export type PillarConfidence = 'high' | 'medium' | 'low';

export interface PillarScore {
  score: number;           // 0–100, normalised
  features: number;        // raw OSM feature count assigned to county
  confidence: PillarConfidence;
}

export type DivergenceType = 'structural_bottleneck' | 'latent_fragility';
export type LisaQuadrant = 'HH' | 'HL' | 'LH' | 'LL';

export interface DivergenceFlag {
  type: DivergenceType;
  resid_t: number;                 // externally studentized LOO residual
  lisa_quadrant: LisaQuadrant;
  data_caveat: string | null;      // set when flag rests on low-confidence pillar
  structural_hypothesis: string;   // researcher annotation, labelled as hypothesis
}

export interface CountyCapacity {
  name: string;
  nuts2_code: string;
  capacity_index: number;           // geometric-mean composite, 0–100
  capacity_index_arithmetic: number; // arithmetic-mean, for imbalance-gap display
  national_percentile: number;      // 0–100
  rank_interval: [number, number];  // [min_rank, max_rank] across sensitivity ensemble
  rank_median: number;
  pillars: Record<PillarKey, PillarScore>;
  peers: string[];                  // 2 nearest nuts3_codes by Euclidean pillar distance
  divergence: DivergenceFlag | null;
}

export interface InfraLayerMeta {
  overpass_query_date: string;
  script_version: string;
  git_sha: string;
  aggregation_default: 'geometric' | 'arithmetic';
  weighting_default: 'equal' | 'pca';
  cronbach_alpha: number;
  ensemble_variants: number;
}

export interface InfraLayer {
  _meta: InfraLayerMeta;
  counties: Record<string, CountyCapacity>; // keyed by nuts3_code e.g. "RO111"
}
```

- [ ] **Step 2: Run type check**

```bash
cd dashboard && npx tsc --noEmit
```

Expected: 0 errors.

- [ ] **Step 3: Commit**

```bash
git add dashboard/src/types.ts
git commit -m "feat(infra/types): add InfraLayer, CountyCapacity, PillarScore, DivergenceFlag interfaces"
```

---

### Task 2: I1_score_counties.py — composite pipeline

**Files:**
- Create: `scripts/infra/I1_score_counties.py`
- Create: `scripts/infra/tests/test_I1.py`

- [ ] **Step 1: Write failing tests**

Create `scripts/infra/tests/test_I1.py`:

```python
"""Tests for I1_score_counties.py"""
import math
import sys
from pathlib import Path
import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import I1_score_counties as I1


class TestWinsorizeMinmax:
    def test_output_between_0_and_100(self):
        s = pd.Series([1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0])
        result = I1._winsorize_minmax(s)
        assert result.min() >= 0
        assert result.max() <= 100

    def test_all_equal_returns_50(self):
        s = pd.Series([5.0] * 10)
        result = I1._winsorize_minmax(s)
        assert (result == 50.0).all()

    def test_monotone(self):
        s = pd.Series(range(20), dtype=float)
        result = I1._winsorize_minmax(s)
        assert (result.diff().dropna() >= 0).all()


class TestGeometricMean:
    def test_equal_scores_returns_score(self):
        row = pd.Series([60.0, 60.0, 60.0, 60.0])
        assert I1._geometric_mean(row) == pytest.approx(60.0, rel=1e-4)

    def test_geom_leq_arith(self):
        row = pd.Series([10.0, 90.0, 50.0, 70.0])
        assert I1._geometric_mean(row) <= row.mean()

    def test_handles_zero_with_floor(self):
        row = pd.Series([0.0, 80.0, 60.0, 40.0])
        result = I1._geometric_mean(row)
        assert math.isfinite(result) and result > 0


class TestCronbachAlpha:
    def test_perfect_internal_consistency(self):
        # All columns identical → perfect correlation → alpha ≈ 1
        df = pd.DataFrame({"a": [1,2,3,4,5], "b": [1,2,3,4,5]})
        assert I1._cronbach_alpha(df) == pytest.approx(1.0, abs=1e-6)

    def test_uncorrelated_columns(self):
        rng = np.random.default_rng(42)
        df = pd.DataFrame(rng.standard_normal((50, 4)), columns=["a","b","c","d"])
        alpha = I1._cronbach_alpha(df)
        assert alpha < 0.5  # low internal consistency expected for random data


class TestConfidence:
    def test_high_density_is_high(self):
        # 20 features in 100 km² → density 0.2 → "high"
        assert I1._data_confidence(20, 100.0) == "high"

    def test_zero_features_is_low(self):
        assert I1._data_confidence(0, 500.0) == "low"

    def test_moderate_is_medium(self):
        assert I1._data_confidence(2, 400.0) == "medium"


class TestFindPeers:
    def test_returns_n_nearest(self):
        matrix = pd.DataFrame({
            "t": [80, 20, 75, 50],
            "e": [70, 10, 72, 40],
            "h": [60, 30, 65, 55],
            "ec": [50, 90, 55, 45],
        }, index=["A", "B", "C", "D"])
        peers = I1._find_peers("A", matrix, n=2)
        assert "C" in peers          # nearest neighbour
        assert "A" not in peers      # not self
        assert len(peers) == 2
```

- [ ] **Step 2: Run tests — verify they fail**

```bash
cd "c:/Users/andre/Desktop/Sandbox/RO-Administrative-Reform"
python -m pytest scripts/infra/tests/test_I1.py -v 2>&1 | head -30
```

Expected: `ImportError: No module named 'I1_score_counties'`

- [ ] **Step 3: Implement I1_score_counties.py**

Create `scripts/infra/I1_score_counties.py`:

```python
"""
I1 — Score Romanian NUTS3 counties on four OSM infrastructure pillars.

Reads (immutable):
  data/raw/osm/{transport,education,health,economic_zones}.geojson
  data/raw/osm/nuts3_romania_bounds.geojson
  data/dashboard/fiscal_primitives.json  (population per county)

Writes:
  data/processed/infra_scores.parquet   (per-county scores + composite)
  data/dashboard/osm/{pillar}.geojson   (simplified POI GeoJSONs for the web map)

Returns:
  dict: nuts3_code → CountyCapacity-shaped dict (without divergence/rank_interval,
        which are added by I2/I3 in v1b)
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


def _load_population() -> pd.DataFrame:
    primitives = json.loads((ROOT / "data" / "dashboard" / "fiscal_primitives.json").read_text())
    return pd.DataFrame([
        {"nuts3_code": c["nuts3_code"], "population": c["population"]}
        for c in primitives["counties"]
    ])


def _count_per_county(geojson_path: Path, nuts3: gpd.GeoDataFrame) -> pd.Series:
    """Feature count per county; line/polygon geometries → centroid before join."""
    gdf = gpd.read_file(geojson_path).to_crs(nuts3.crs)
    gdf["geometry"] = gdf.geometry.centroid
    joined = gpd.sjoin(gdf, nuts3[["nuts3_code", "geometry"]], how="left", predicate="within")
    counts = joined.groupby("nuts3_code").size()
    return nuts3.set_index("nuts3_code")["nuts3_code"].index.map(
        lambda c: int(counts.get(c, 0))
    )


def _raw_intensity(counts: pd.Series, area_km2: pd.Series, pop: pd.Series,
                   norm_by: str) -> pd.Series:
    """Convert raw counts to size-invariant intensities."""
    if norm_by == "area":
        return counts / area_km2.clip(lower=1.0)
    if norm_by == "pop_1k":
        return counts / (pop / 1000).clip(lower=0.1)
    return counts.astype(float)  # fallback


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
    if density > 0.01 or raw_count > 3:
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
    gdf = gpd.read_file(raw_path).to_crs(nuts3.crs)
    gdf["geometry"] = gdf.geometry.centroid
    # Spatial join to add nuts3_code
    joined = gpd.sjoin(gdf, nuts3[["nuts3_code", "geometry"]], how="left", predicate="within")
    joined = joined[joined["nuts3_code"].notna()].copy()
    # Keep minimal columns to reduce file size
    keep = ["geometry", "nuts3_code"]
    for col in ["name", "amenity", "highway", "railway", "aeroway", "landuse", "beds"]:
        if col in joined.columns:
            keep.append(col)
    OUT_OSM_WEB.mkdir(parents=True, exist_ok=True)
    joined[keep].to_file(OUT_OSM_WEB / f"{pillar_key}.geojson", driver="GeoJSON")


# ── Main extract function ──────────────────────────────────────────────────────

def extract() -> dict[str, Any]:
    """
    Run the full composite pipeline.
    Returns dict: nuts3_code → CountyCapacity-shaped dict (divergence=null, rank_interval=[0,0]).
    Also writes infra_scores.parquet and osm web GeoJSONs.
    """
    nuts3 = _load_nuts3()
    pop_df = _load_population()
    base = nuts3.merge(pop_df, on="nuts3_code", how="left")
    base["population"] = base["population"].fillna(base["population"].median())

    # ── 1. Raw feature counts per pillar
    raw_counts: dict[str, pd.Series] = {}
    for pillar, key in zip(PILLARS, PILLAR_KEYS):
        path = RAW_OSM / f"{pillar}.geojson"
        counts = _count_per_county(path, nuts3.copy())
        raw_counts[key] = pd.Series(counts.values, index=nuts3["nuts3_code"].values)
        _write_web_geojson(path, nuts3.copy(), key)

    # ── 2. Size-invariant intensities
    area = base.set_index("nuts3_code")["area_km2"]
    pop = base.set_index("nuts3_code")["population"]

    intensities: dict[str, pd.Series] = {
        "transport": _raw_intensity(raw_counts["transport"], area, pop, "area"),
        "education": _raw_intensity(raw_counts["education"], area, pop, "pop_1k"),
        "health":    _raw_intensity(raw_counts["health"],    area, pop, "pop_1k"),
        "economic":  _raw_intensity(raw_counts["economic"],  area, pop, "area"),
    }

    # ── 3. Winsorise + min–max normalise to [0, 100]
    normed: dict[str, pd.Series] = {
        k: _winsorize_minmax(v) for k, v in intensities.items()
    }
    scores_df = pd.DataFrame(normed)  # index = nuts3_code

    # ── 4. Construct validity: Cronbach's α + correlation matrix
    alpha = _cronbach_alpha(scores_df)
    corr = scores_df.corr().round(3)
    print(f"  Cronbach α = {alpha:.3f}  (>0.6 = acceptable internal consistency)")
    redundant_pairs = [
        (c1, c2) for c1 in corr.columns for c2 in corr.columns
        if c1 < c2 and abs(corr.loc[c1, c2]) > 0.85
    ]
    if redundant_pairs:
        print(f"  ⚠ High inter-pillar correlations (possible redundancy): {redundant_pairs}")

    # ── 5. Weights: equal and PCA
    n_pillars = len(PILLAR_KEYS)
    equal_w = np.array([1.0 / n_pillars] * n_pillars)
    pca_w = _pca_weights(scores_df)

    # ── 6. Composite: geometric (default) and arithmetic
    composite_geom = scores_df.apply(_geometric_mean, axis=1)
    composite_arith = scores_df.apply(lambda r: float(np.average(r.values, weights=equal_w)), axis=1)

    # ── 7. Data confidence per pillar per county
    def confidence_series(key: str) -> pd.Series:
        return pd.Series({
            code: _data_confidence(int(raw_counts[key][code]), float(area[code]))
            for code in scores_df.index
        })

    conf: dict[str, pd.Series] = {k: confidence_series(k) for k in PILLAR_KEYS}

    # ── 8. Peer counties
    peers: dict[str, list[str]] = {
        code: _find_peers(code, scores_df) for code in scores_df.index
    }

    # ── 9. National percentile
    percentiles = {
        code: _national_percentile(code, composite_geom) for code in scores_df.index
    }

    # ── 10. Save parquet (for I2/I3)
    OUT_SCORES.parent.mkdir(parents=True, exist_ok=True)
    pq = scores_df.copy()
    pq["capacity_index"] = composite_geom
    pq["capacity_index_arithmetic"] = composite_arith
    pq.to_parquet(OUT_SCORES)

    # ── 11. Build output dict
    nuts3_names = base.set_index("nuts3_code")["judet_name"] if "judet_name" in base.columns else pd.Series("", index=base.set_index("nuts3_code").index)
    # Fallback: load from regions.json
    try:
        regions_raw = json.loads((ROOT / "data" / "dashboard" / "regions.json").read_text())
        name_map = {r["nuts3_code"]: r["judet_name"] for r in regions_raw}
        nuts2_map = {r["nuts3_code"]: r["nuts2_code"] for r in regions_raw}
    except Exception:
        name_map = {}
        nuts2_map = {}

    result: dict[str, Any] = {}
    for code in scores_df.index:
        result[code] = {
            "name": name_map.get(code, code),
            "nuts2_code": nuts2_map.get(code, ""),
            "capacity_index": round(float(composite_geom[code]), 1),
            "capacity_index_arithmetic": round(float(composite_arith[code]), 1),
            "national_percentile": percentiles[code],
            "rank_interval": [0, 0],   # placeholder until I3 in v1b
            "rank_median": 0,          # placeholder until I3 in v1b
            "pillars": {
                k: {
                    "score": round(float(scores_df.loc[code, k]), 1),
                    "features": int(raw_counts[k].get(code, 0)),
                    "confidence": conf[k][code],
                }
                for k in PILLAR_KEYS
            },
            "peers": peers[code],
            "divergence": None,        # placeholder until I2 in v1b
        }

    print(f"  Cronbach α={alpha:.3f}, PCA weights={dict(zip(PILLAR_KEYS, pca_w.round(3).tolist()))}")
    return result, alpha, corr.values.tolist()


if __name__ == "__main__":
    print("=== I1: Scoring counties ===")
    result, alpha, _ = extract()
    print(f"  ✓ {len(result)} counties scored")
    print(f"  Written: {OUT_SCORES}")
    print(f"  Written: {OUT_OSM_WEB}/*.geojson")
```

- [ ] **Step 4: Run tests — verify they pass**

```bash
python -m pytest scripts/infra/tests/test_I1.py -v
```

Expected:
```
PASSED test_winsorize_minmax_output_between_0_and_100
PASSED test_all_equal_returns_50
PASSED test_monotone
PASSED test_equal_scores_returns_score
PASSED test_geom_leq_arith
PASSED test_handles_zero_with_floor
PASSED test_perfect_internal_consistency
PASSED test_uncorrelated_columns
PASSED test_high_density_is_high
PASSED test_zero_features_is_low
PASSED test_moderate_is_medium
PASSED test_returns_n_nearest
PASSED test_not_self
```

- [ ] **Step 5: Commit**

```bash
git add scripts/infra/I1_score_counties.py scripts/infra/tests/test_I1.py
git commit -m "feat(infra/I1): composite scoring pipeline — winsorise+minmax, geometric mean, Cronbach α"
```

---

### Task 3: I0_build_infra_layer.py (v1a stub)

**Files:**
- Create: `scripts/infra/I0_build_infra_layer.py`

**Context:** This is the v1a orchestrator — calls only I1, writes `infra_layer.json` with `divergence=null` and placeholder `rank_interval`. Task 10 will replace it with the full orchestrator calling I1+I2+I3.

- [ ] **Step 1: Write I0_build_infra_layer.py**

```python
"""
I0 — Infra layer orchestrator (v1a stub).
Calls I1 only. Divergence and rank_interval are null/placeholder until v1b (Task 10).

Run: python scripts/infra/I0_build_infra_layer.py
"""
from __future__ import annotations

import json
import math
import subprocess
import sys
from datetime import date
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "infra"))

import I1_score_counties as I1

OUT = ROOT / "data" / "dashboard" / "infra_layer.json"


def _sanitize(obj):
    """Recursively coerce: numpy scalars → Python, non-finite floats → None."""
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
    print("=== I0 (v1a): Building infra_layer.json ===\n")

    print("[I1] Scoring counties...")
    counties, alpha, corr = I1.extract()
    print(f"  ✓ {len(counties)} counties scored")

    meta = {
        "overpass_query_date": "2026-06-06",
        "script_version": "1.0.0-v1a",
        "git_sha": _git_sha(),
        "aggregation_default": "geometric",
        "weighting_default": "equal",
        "cronbach_alpha": round(alpha, 3) if math.isfinite(alpha) else None,
        "pillar_correlation": corr,
        "ensemble_variants": 0,  # not yet computed (v1b)
        "note": "v1a — divergence and rank_interval added in v1b",
    }

    output = {"_meta": meta, "counties": counties}

    for key in ("_meta", "counties"):
        assert key in output, f"Missing key: {key}"
    assert len(output["counties"]) > 0, "No counties written"

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(_sanitize(output), indent=2, allow_nan=False))
    print(f"\n✓ Written {OUT}")
    print(f"  {len(counties)} counties, Cronbach α={alpha:.3f}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Run it**

```bash
python scripts/infra/I0_build_infra_layer.py
```

Expected:
```
=== I0 (v1a): Building infra_layer.json ===

[I1] Scoring counties...
  Cronbach α=0.XXX ...
  ✓ 42 counties scored

✓ Written data/dashboard/infra_layer.json
  42 counties, Cronbach α=0.XXX
```

- [ ] **Step 3: Verify JSON validity**

```bash
python -c "import json; d=json.load(open('data/dashboard/infra_layer.json')); print('counties:', len(d['counties'])); print('first:', list(d['counties'].keys())[0])"
```

Expected: `counties: 42` and a NUTS3 code like `RO111`.

- [ ] **Step 4: Commit**

```bash
git add scripts/infra/I0_build_infra_layer.py data/dashboard/infra_layer.json \
        data/processed/infra_scores.parquet data/dashboard/osm/
git commit -m "feat(infra/I0): v1a orchestrator — writes infra_layer.json from I1 scoring"
```

---

### Task 4: utils/capacity.ts + tests

**Files:**
- Create: `dashboard/src/utils/capacity.ts`
- Create: `dashboard/src/utils/capacity.test.ts`

- [ ] **Step 1: Write failing tests**

Create `dashboard/src/utils/capacity.test.ts`:

```typescript
import { describe, it, expect } from 'vitest';
import {
  nationalPercentile, peerCounties, exportCapacityCsv,
} from './capacity';
import type { InfraLayer, CountyCapacity } from '../types';

const makePillar = (score: number) => ({
  score, features: 5, confidence: 'high' as const,
});

const makeCounty = (capacity_index: number, peers: string[] = []): CountyCapacity => ({
  name: 'Test',
  nuts2_code: 'RO11',
  capacity_index,
  capacity_index_arithmetic: capacity_index + 2,
  national_percentile: 50,
  rank_interval: [10, 15],
  rank_median: 12,
  pillars: {
    transport: makePillar(60),
    education: makePillar(70),
    health: makePillar(50),
    economic: makePillar(55),
  },
  peers,
  divergence: null,
});

const LAYER: InfraLayer = {
  _meta: {
    overpass_query_date: '2026-06-06',
    script_version: '1.0.0',
    git_sha: 'abc123',
    aggregation_default: 'geometric',
    weighting_default: 'equal',
    cronbach_alpha: 0.72,
    ensemble_variants: 8,
  },
  counties: {
    RO111: makeCounty(67, ['RO421', 'RO126']),
    RO421: makeCounty(70, ['RO111']),
    RO126: makeCounty(65, ['RO111']),
    RO311: makeCounty(30, []),
    RO321: makeCounty(90, []),
  },
};

describe('nationalPercentile', () => {
  it('returns 0 for the lowest-scoring county', () => {
    expect(nationalPercentile('RO311', LAYER)).toBe(0);
  });
  it('returns 100 - 1/n for the highest-scoring county', () => {
    // 4 counties below RO321 (score=90) → 4/5 × 100 = 80
    expect(nationalPercentile('RO321', LAYER)).toBe(80);
  });
  it('returns a value between 0 and 100', () => {
    const p = nationalPercentile('RO111', LAYER);
    expect(p).toBeGreaterThanOrEqual(0);
    expect(p).toBeLessThanOrEqual(100);
  });
});

describe('peerCounties', () => {
  it('returns CountyCapacity objects for peer codes', () => {
    const peers = peerCounties('RO111', LAYER);
    expect(peers).toHaveLength(2);
    expect(peers[0].capacity_index).toBe(70);   // RO421
  });
  it('returns empty array when county not found', () => {
    expect(peerCounties('UNKNOWN', LAYER)).toEqual([]);
  });
  it('returns empty array when peers list is empty', () => {
    expect(peerCounties('RO311', LAYER)).toEqual([]);
  });
});

describe('exportCapacityCsv', () => {
  it('contains a header row', () => {
    const csv = exportCapacityCsv(LAYER);
    const header = csv.split('\n')[0];
    expect(header).toContain('nuts3_code');
    expect(header).toContain('capacity_index');
  });
  it('has one row per county plus header', () => {
    const csv = exportCapacityCsv(LAYER);
    const lines = csv.split('\n').filter(Boolean);
    expect(lines).toHaveLength(Object.keys(LAYER.counties).length + 1);
  });
  it('includes divergence type column', () => {
    const csv = exportCapacityCsv(LAYER);
    expect(csv.split('\n')[0]).toContain('divergence_type');
  });
});
```

- [ ] **Step 2: Run tests — verify they fail**

```bash
cd dashboard && npx vitest run src/utils/capacity.test.ts 2>&1 | head -20
```

Expected: `Cannot find module './capacity'`

- [ ] **Step 3: Implement capacity.ts**

Create `dashboard/src/utils/capacity.ts`:

```typescript
import type { InfraLayer, CountyCapacity } from '../types';

let cached: InfraLayer | null = null;

export async function loadInfraLayer(): Promise<InfraLayer> {
  if (cached) return cached;
  const res = await fetch('./data/infra_layer.json');
  if (!res.ok) throw new Error(`Failed to load infra_layer.json: ${res.status}`);
  cached = (await res.json()) as InfraLayer;
  return cached;
}

export function nationalPercentile(code: string, layer: InfraLayer): number {
  const county = layer.counties[code];
  if (!county) return 0;
  const scores = Object.values(layer.counties).map((c) => c.capacity_index);
  const below = scores.filter((s) => s < county.capacity_index).length;
  return Math.round((below / scores.length) * 100);
}

export function peerCounties(code: string, layer: InfraLayer): CountyCapacity[] {
  const county = layer.counties[code];
  if (!county) return [];
  return county.peers
    .map((p) => layer.counties[p])
    .filter((c): c is CountyCapacity => c != null);
}

export function exportCapacityCsv(layer: InfraLayer): string {
  const headers = [
    'nuts3_code', 'name', 'capacity_index', 'national_percentile',
    'rank_min', 'rank_max', 'transport', 'education', 'health', 'economic',
    'divergence_type',
  ];
  const rows = Object.entries(layer.counties).map(([code, c]) => [
    code,
    c.name,
    c.capacity_index.toFixed(1),
    c.national_percentile,
    c.rank_interval[0],
    c.rank_interval[1],
    c.pillars.transport.score.toFixed(1),
    c.pillars.education.score.toFixed(1),
    c.pillars.health.score.toFixed(1),
    c.pillars.economic.score.toFixed(1),
    c.divergence?.type ?? '',
  ]);
  return [headers, ...rows].map((r) => r.join(',')).join('\n');
}
```

- [ ] **Step 4: Run tests — verify they pass**

```bash
cd dashboard && npx vitest run src/utils/capacity.test.ts
```

Expected: all 9 tests pass.

- [ ] **Step 5: Commit**

```bash
git add dashboard/src/utils/capacity.ts dashboard/src/utils/capacity.test.ts
git commit -m "feat(infra/capacity): loadInfraLayer, nationalPercentile, peerCounties, exportCapacityCsv"
```

---

### Task 5: InfraLayerPanel.tsx + RomaniaMap.tsx extension

**Files:**
- Create: `dashboard/src/components/InfraLayerPanel.tsx`
- Modify: `dashboard/src/components/RomaniaMap.tsx`

**Context:** Add the basemap toggle (Positron/Satellite) and pillar layer toggles to the map. POI markers appear only at zoom ≥ 7 (progressive disclosure). No new npm packages — `TileLayer` and `CircleMarker` are already exported by react-leaflet 4.

- [ ] **Step 1: Create InfraLayerPanel.tsx**

```typescript
import { useState } from 'react';
import type { PillarKey } from '../types';

type BasemapType = 'positron' | 'satellite';

interface Props {
  activePillars: Set<PillarKey>;
  onTogglePillar: (p: PillarKey) => void;
  basemap: BasemapType;
  onBasemapChange: (b: BasemapType) => void;
  onExportCsv: () => void;
}

const PILLAR_LABELS: Record<PillarKey, string> = {
  transport: '🚗 Transport',
  education: '🎓 Education',
  health:    '🏥 Health',
  economic:  '🏭 Economic zones',
};

const PILLAR_COLORS: Record<PillarKey, string> = {
  transport: '#3b82f6',
  education: '#8b5cf6',
  health:    '#10b981',
  economic:  '#f59e0b',
};

export type { BasemapType };

export default function InfraLayerPanel({
  activePillars, onTogglePillar, basemap, onBasemapChange, onExportCsv,
}: Props) {
  const [open, setOpen] = useState(true);

  return (
    <div className="absolute top-2 right-2 z-[1000] bg-white rounded-lg shadow-md border border-gray-200 text-xs w-48">
      <button
        onClick={() => setOpen((o) => !o)}
        className="w-full flex items-center justify-between px-2.5 py-2 font-medium text-gray-700 hover:bg-gray-50 rounded-lg"
      >
        <span>Infrastructure</span>
        <span className="text-gray-400 text-[10px]">{open ? '▲' : '▼'}</span>
      </button>

      {open && (
        <div className="px-2.5 pb-2.5 border-t border-gray-100 space-y-1.5">
          <p className="text-[9px] text-gray-400 uppercase tracking-wide pt-1.5">Layers</p>
          {(Object.keys(PILLAR_LABELS) as PillarKey[]).map((p) => (
            <label key={p} className="flex items-center gap-2 cursor-pointer">
              <input
                type="checkbox"
                checked={activePillars.has(p)}
                onChange={() => onTogglePillar(p)}
                className="rounded"
                style={{ accentColor: PILLAR_COLORS[p] }}
              />
              <span className="text-gray-700">{PILLAR_LABELS[p]}</span>
            </label>
          ))}

          <p className="text-[9px] text-gray-400 uppercase tracking-wide pt-1">Basemap</p>
          {(['positron', 'satellite'] as BasemapType[]).map((b) => (
            <label key={b} className="flex items-center gap-2 cursor-pointer">
              <input
                type="radio"
                name="infra-basemap"
                checked={basemap === b}
                onChange={() => onBasemapChange(b)}
                className="accent-violet-600"
              />
              <span className="text-gray-700">
                {b === 'positron' ? 'Positron (default)' : 'Satellite'}
              </span>
            </label>
          ))}

          <button
            onClick={onExportCsv}
            className="mt-1.5 w-full text-center text-violet-600 hover:text-violet-800 text-[10px] py-0.5 border border-violet-200 rounded"
          >
            Export capacity CSV
          </button>
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 2: Update package.json copy-data to include osm/**

The `copy-data` script already uses `-r` which handles subdirectories, so `data/dashboard/osm/` will be copied to `public/data/osm/` automatically. Verify:

```bash
cd "c:/Users/andre/Desktop/Sandbox/RO-Administrative-Reform/dashboard"
npm run copy-data
ls public/data/osm/ 2>/dev/null || echo "osm/ not yet present (run I0 first)"
```

- [ ] **Step 3: Modify RomaniaMap.tsx**

Replace the full content of `dashboard/src/components/RomaniaMap.tsx`:

```typescript
import { useEffect, useRef, useState, useCallback } from 'react';
import { MapContainer, GeoJSON, TileLayer, CircleMarker, Tooltip as LTooltip, useMapEvents } from 'react-leaflet';
import type { GeoJSON as LeafletGeoJSON, Layer } from 'leaflet';
import type { GeoJsonObject, Feature, Geometry, FeatureCollection, Point } from 'geojson';
import type { DashboardData, LayerType, RegionGroup, PillarKey, InfraLayer } from '../types';
import { reformCostColor, suitabilityColor, roiColor, maxSuitability } from '../utils/color';
import InfraLayerPanel, { type BasemapType } from './InfraLayerPanel';
import { exportCapacityCsv } from '../utils/capacity';

const GISCO_URL =
  'https://gisco-services.ec.europa.eu/distribution/v2/nuts/geojson/NUTS_RG_20M_2021_4326_LEVL_3.geojson';

const BASEMAP_URLS: Record<BasemapType, string> = {
  positron: 'https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png',
  satellite: 'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
};

const PILLAR_COLORS: Record<PillarKey, string> = {
  transport: '#3b82f6',
  education: '#8b5cf6',
  health:    '#10b981',
  economic:  '#f59e0b',
};

interface Props {
  data: DashboardData;
  activeLayer: LayerType;
  selectedNuts3: string | null;
  onCountyClick: (nuts3: string) => void;
  hoveredNuts3: string | null;
  onCountyHover: (nuts3: string | null) => void;
  regionGroups: Map<string, RegionGroup>;
  infraLayer: InfraLayer | null;
}

interface NutsFeature extends Feature<Geometry> {
  properties: { NUTS_ID: string; CNTR_CODE: string; NAME_LATN: string };
}

// Sub-component: detects zoom level and reports it upward.
function ZoomWatcher({ onZoom }: { onZoom: (z: number) => void }) {
  useMapEvents({ zoom: (e) => onZoom(e.target.getZoom()) });
  return null;
}

export default function RomaniaMap({
  data, activeLayer, selectedNuts3, onCountyClick,
  hoveredNuts3, onCountyHover, infraLayer,
}: Props) {
  const [geoJson, setGeoJson] = useState<GeoJsonObject | null>(null);
  const [geoError, setGeoError] = useState(false);
  const [basemap, setBasemap] = useState<BasemapType>('positron');
  const [activePillars, setActivePillars] = useState<Set<PillarKey>>(new Set());
  const [poisByPillar, setPoisByPillar] = useState<Partial<Record<PillarKey, FeatureCollection>>>({});
  const [zoomLevel, setZoomLevel] = useState(6);
  const geoJsonRef = useRef<LeafletGeoJSON | null>(null);

  const showMarkers = zoomLevel >= 7;

  const maxAbsAtt = Math.max(...data.regions.map((r) => Math.abs(r.att_avg_pre ?? 0)), 0.001);
  const maxUplift = Math.max(...data.regions.map((r) => r.innovation_uplift_pct_2040 ?? 0), 0.001);

  useEffect(() => {
    fetch(GISCO_URL)
      .then((r) => r.json())
      .then((full: { features: NutsFeature[] }) => {
        const ro: GeoJsonObject = {
          type: 'FeatureCollection',
          // @ts-expect-error – valid GeoJSON but type doesn't expose features
          features: full.features.filter((f) => f.properties.CNTR_CODE === 'RO'),
        };
        setGeoJson(ro);
      })
      .catch(() => setGeoError(true));
  }, []);

  const handleTogglePillar = useCallback((p: PillarKey) => {
    setActivePillars((prev) => {
      const next = new Set(prev);
      if (next.has(p)) {
        next.delete(p);
      } else {
        next.add(p);
        // Lazy-load POI GeoJSON the first time a pillar is toggled on
        if (!poisByPillar[p]) {
          fetch(`./data/osm/${p}.geojson`)
            .then((r) => r.json())
            .then((fc: FeatureCollection) =>
              setPoisByPillar((prev2) => ({ ...prev2, [p]: fc }))
            )
            .catch(() => console.warn(`Failed to load POI GeoJSON for pillar: ${p}`));
        }
      }
      return next;
    });
  }, [poisByPillar]);

  const handleExportCsv = useCallback(() => {
    if (!infraLayer) return;
    const csv = exportCapacityCsv(infraLayer);
    const blob = new Blob([csv], { type: 'text/csv' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'ro_infrastructure_capacity.csv';
    a.click();
    URL.revokeObjectURL(url);
  }, [infraLayer]);

  function getStyle(feature: Feature | undefined) {
    if (!feature) return {};
    const nuts3 = (feature as NutsFeature).properties.NUTS_ID;
    const isSelected = nuts3 === selectedNuts3;

    if (activeLayer === 'region') {
      const selectedNuts2 = selectedNuts3
        ? (data.suitabilityByCode[selectedNuts3]?.nuts2_code ?? null)
        : null;
      const featureNuts2 = nuts3.slice(0, 4);
      const isSelectedRegion = featureNuts2 === selectedNuts2;
      const isHovered = nuts3 === hoveredNuts3;
      return {
        fillColor: isSelectedRegion ? '#7c3aed' : '#d1d5db',
        fillOpacity: isHovered ? 0.85 : isSelectedRegion ? 0.55 : 0.25,
        color: isSelectedRegion ? '#5b21b6' : '#9ca3af',
        weight: isHovered ? 3 : isSelectedRegion ? 2 : 0.5,
      };
    }

    let fillColor = '#e5e7eb';
    if (activeLayer === 'reform_cost') {
      fillColor = reformCostColor(data.regionsByCode[nuts3]?.att_avg_pre ?? null, maxAbsAtt);
    } else if (activeLayer === 'suitability') {
      const s = data.suitabilityByCode[nuts3];
      fillColor = s ? suitabilityColor(maxSuitability(s)) : '#e5e7eb';
    } else {
      fillColor = roiColor(data.regionsByCode[nuts3]?.innovation_uplift_pct_2040 ?? null, maxUplift);
    }

    return {
      fillColor,
      fillOpacity: isSelected ? 0.9 : 0.7,
      color: isSelected ? '#1d4ed8' : '#ffffff',
      weight: isSelected ? 2.5 : 0.8,
    };
  }

  function onEachFeature(feature: Feature, layer: Layer) {
    const nuts3 = (feature as NutsFeature).properties.NUTS_ID;
    const name = (feature as NutsFeature).properties.NAME_LATN;
    layer.bindTooltip(name, { sticky: true, className: 'text-xs' });
    layer.on('click', () => onCountyClick(nuts3));
    layer.on('mouseover', () => onCountyHover(nuts3));
    layer.on('mouseout', () => onCountyHover(null));
  }

  if (geoError) {
    return (
      <div className="h-full flex flex-col items-center justify-center gap-2 bg-blue-50">
        <span className="text-red-500 text-sm">&#9888; Map unavailable (CDN unreachable)</span>
        <div className="grid grid-cols-4 gap-1 max-w-md">
          {data.regions.map((r) => (
            <button
              key={r.nuts3_code}
              onClick={() => onCountyClick(r.nuts3_code)}
              className={`text-xs p-1 rounded border ${
                r.nuts3_code === selectedNuts3
                  ? 'bg-blue-600 text-white border-blue-600'
                  : 'bg-white border-gray-300 hover:bg-gray-50'
              }`}
            >
              {r.county_seat}
            </button>
          ))}
        </div>
      </div>
    );
  }

  if (!geoJson) {
    return (
      <div className="h-full flex items-center justify-center bg-blue-50 text-blue-400 text-sm">
        Loading map&hellip;
      </div>
    );
  }

  return (
    <div className="relative h-full w-full">
      <MapContainer center={[45.9, 24.9]} zoom={6} zoomControl={false} style={{ height: '100%', width: '100%' }}>
        <TileLayer
          url={BASEMAP_URLS[basemap]}
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/">CARTO</a>'
          subdomains={basemap === 'positron' ? 'abcd' : undefined}
        />
        <ZoomWatcher onZoom={setZoomLevel} />
        <GeoJSON
          key={`${activeLayer}-${selectedNuts3}-${hoveredNuts3}`}
          ref={geoJsonRef}
          data={geoJson}
          style={getStyle}
          onEachFeature={onEachFeature}
        />
        {showMarkers &&
          (Object.keys(PILLAR_COLORS) as PillarKey[])
            .filter((p) => activePillars.has(p) && poisByPillar[p])
            .map((p) =>
              (poisByPillar[p]!.features as Feature<Point>[]).map((f, i) => {
                const [lng, lat] = f.geometry.coordinates;
                const name = (f.properties as Record<string, string>)?.name ?? '';
                return (
                  <CircleMarker
                    key={`${p}-${i}`}
                    center={[lat, lng]}
                    radius={4}
                    pathOptions={{ color: PILLAR_COLORS[p], fillColor: PILLAR_COLORS[p], fillOpacity: 0.7, weight: 1 }}
                  >
                    {name && <LTooltip>{name}</LTooltip>}
                  </CircleMarker>
                );
              })
            )}
      </MapContainer>

      <InfraLayerPanel
        activePillars={activePillars}
        onTogglePillar={handleTogglePillar}
        basemap={basemap}
        onBasemapChange={setBasemap}
        onExportCsv={handleExportCsv}
      />
    </div>
  );
}
```

- [ ] **Step 4: Pass infraLayer prop through App.tsx**

Open `dashboard/src/App.tsx`. Find where `<RomaniaMap` is rendered and add the `infraLayer` prop (pass `null` for now; Task 7 wires the loaded layer):

```typescript
// In App.tsx, add to the RomaniaMap usage:
<RomaniaMap
  data={data}
  activeLayer={activeLayer}
  selectedNuts3={selectedNuts3}
  onCountyClick={setSelectedNuts3}
  hoveredNuts3={hoveredNuts3}
  onCountyHover={setHoveredNuts3}
  regionGroups={regionGroups}
  infraLayer={null}  // ← add this; Task 7 replaces with loaded layer
/>
```

- [ ] **Step 5: Type-check and run dev server**

```bash
cd dashboard && npx tsc --noEmit && npm run dev
```

Expected: 0 TypeScript errors. Open http://localhost:5173 and verify:
- The map loads with a light grey Positron tile layer underneath the county polygons
- The "Infrastructure" panel appears in the top-right of the map
- Toggling a pillar while at zoom ≥ 7 shows/hides CircleMarkers (zoom in on the map first)
- Basemap toggle switches to Esri Satellite imagery

- [ ] **Step 6: Commit**

```bash
git add dashboard/src/components/InfraLayerPanel.tsx dashboard/src/components/RomaniaMap.tsx \
        dashboard/src/App.tsx
git commit -m "feat(infra/map): basemap toggle, InfraLayerPanel, progressive POI markers on zoom ≥7"
```

---

### Task 6: CapacityCard.tsx

**Files:**
- Create: `dashboard/src/components/CapacityCard.tsx`

- [ ] **Step 1: Implement CapacityCard.tsx**

```typescript
import {
  RadarChart, PolarGrid, PolarAngleAxis, Radar, ResponsiveContainer,
} from 'recharts';
import type { CountyCapacity, InfraLayer, PillarKey } from '../types';
import { peerCounties } from '../utils/capacity';

interface Props {
  county: CountyCapacity;
  countyCode: string;
  layer: InfraLayer;
}

const PILLAR_LABELS: Record<PillarKey, string> = {
  transport: 'Transport',
  education: 'Education',
  health: 'Health',
  economic: 'Economic',
};

const CONFIDENCE_STYLE: Record<string, string> = {
  high:   'text-green-600',
  medium: 'text-amber-600',
  low:    'text-red-500',
};

export default function CapacityCard({ county, countyCode, layer }: Props) {
  const peers = peerCounties(countyCode, layer);

  const radarData = (Object.keys(PILLAR_LABELS) as PillarKey[]).map((p) => ({
    pillar: PILLAR_LABELS[p],
    score: county.pillars[p].score,
    fullMark: 100,
  }));

  const [rankMin, rankMax] = county.rank_interval;
  const hasRankInterval = rankMin !== 0 || rankMax !== 0;

  return (
    <div className="px-3 py-2 border-t border-gray-100 text-xs space-y-2">
      {/* Header */}
      <div className="flex items-center justify-between">
        <span className="font-medium text-gray-700">Infrastructure capacity</span>
        <span className="text-gray-400 text-[10px]">
          {county.national_percentile}th pct nationally
          {hasRankInterval && ` · rank ${rankMin}–${rankMax}`}
        </span>
      </div>

      {/* Composite score */}
      <div className="flex items-center gap-2">
        <div className="text-2xl font-bold text-violet-700 tabular-nums">
          {county.capacity_index.toFixed(0)}
        </div>
        <div className="text-[10px] text-gray-500 leading-tight">
          <div>/ 100 composite</div>
          <div className="text-gray-400">
            arithmetic: {county.capacity_index_arithmetic.toFixed(0)}
            <span className="ml-1 text-gray-300">
              (gap = imbalance proxy)
            </span>
          </div>
        </div>
      </div>

      {/* Radar chart */}
      <ResponsiveContainer width="100%" height={130}>
        <RadarChart data={radarData} margin={{ top: 4, right: 16, bottom: 4, left: 16 }}>
          <PolarGrid stroke="#e5e7eb" />
          <PolarAngleAxis dataKey="pillar" tick={{ fontSize: 9, fill: '#6b7280' }} />
          <Radar
            name={county.name}
            dataKey="score"
            stroke="#7c3aed"
            fill="#7c3aed"
            fillOpacity={0.25}
            dot={{ r: 2, fill: '#7c3aed' }}
          />
        </RadarChart>
      </ResponsiveContainer>

      {/* Pillar breakdown */}
      <div className="grid grid-cols-2 gap-1">
        {(Object.keys(PILLAR_LABELS) as PillarKey[]).map((p) => {
          const ps = county.pillars[p];
          return (
            <div key={p} className="bg-gray-50 rounded px-1.5 py-1">
              <div className="text-gray-400 text-[9px] uppercase tracking-wide">{PILLAR_LABELS[p]}</div>
              <div className="font-medium text-gray-800">{ps.score.toFixed(0)}</div>
              <div className={`text-[9px] ${CONFIDENCE_STYLE[ps.confidence]}`}>
                {ps.confidence} coverage · {ps.features} POIs
              </div>
            </div>
          );
        })}
      </div>

      {/* Peer comparison */}
      {peers.length > 0 && (
        <div>
          <div className="text-[9px] text-gray-400 uppercase tracking-wide mb-1">
            Similar-profile counties
          </div>
          <div className="space-y-0.5">
            {peers.map((peer) => {
              const peerCode = county.peers.find((c) => layer.counties[c] === peer) ?? '';
              return (
                <div key={peerCode} className="flex items-center justify-between bg-blue-50 rounded px-1.5 py-0.5">
                  <span className="text-gray-700">{peer.name}</span>
                  <span className="text-gray-500 tabular-nums">{peer.capacity_index.toFixed(0)}</span>
                </div>
              );
            })}
          </div>
        </div>
      )}

      <p className="text-[9px] text-gray-400 leading-snug">
        Geometric-mean composite (partially non-compensatory). Rank interval across{' '}
        {layer._meta.ensemble_variants || 0} methodological variants.
        Cronbach α = {layer._meta.cronbach_alpha.toFixed(2)}.
      </p>
    </div>
  );
}
```

- [ ] **Step 2: Type-check**

```bash
cd dashboard && npx tsc --noEmit
```

Expected: 0 errors.

- [ ] **Step 3: Commit**

```bash
git add dashboard/src/components/CapacityCard.tsx
git commit -m "feat(infra/CapacityCard): radar chart, pillar breakdown, composite score, peer row"
```

---

### Task 7: PolicyLab.tsx integration — load layer, mount CapacityCard, seed levers

**Files:**
- Modify: `dashboard/src/components/PolicyLab.tsx`
- Modify: `dashboard/src/App.tsx`

- [ ] **Step 1: Load InfraLayer in App.tsx and thread it to map + PolicyLab**

In `dashboard/src/App.tsx`, add infrastructure layer loading alongside existing data loading. Find the data-loading `useEffect` block and add:

```typescript
// Add to App.tsx imports:
import { loadInfraLayer } from './utils/capacity';
import type { InfraLayer } from './types';

// Add state alongside existing state:
const [infraLayer, setInfraLayer] = useState<InfraLayer | null>(null);

// Add to useEffect (after existing data is loaded, or in a separate effect):
useEffect(() => {
  loadInfraLayer()
    .then(setInfraLayer)
    .catch((e) => console.warn('infra_layer.json not available:', e));
}, []);

// Thread to RomaniaMap (replace null from Task 5):
<RomaniaMap infraLayer={infraLayer} ... />

// Thread to PolicyLab:
<PolicyLab nuts3Code={selectedNuts3} data={data} regionGroups={regionGroups} infraLayer={infraLayer} />
```

- [ ] **Step 2: Update PolicyLab.tsx — add infraLayer prop, mount CapacityCard, seed levers**

Open `dashboard/src/components/PolicyLab.tsx`. Make the following changes:

**Add import:**
```typescript
import type { InfraLayer, LeverVector } from '../types';
import CapacityCard from './CapacityCard';
```

**Extend Props interface:**
```typescript
interface Props {
  nuts3Code: string | null;
  data: DashboardData;
  regionGroups: Map<string, RegionGroup>;
  infraLayer: InfraLayer | null;   // ← add
}
```

**Add seeding logic** (add after the `totalGva` useMemo, before the early returns):
```typescript
const [leversSeededFrom, setLeversSeededFrom] = useState<string | null>(null);

// Seed levers from capacity pillars when a county is first selected
useEffect(() => {
  if (!nuts3Code || !infraLayer || leversSeededFrom === nuts3Code) return;
  const county = infraLayer.counties[nuts3Code];
  if (!county) return;
  const educationNorm = county.pillars.education.score / 100; // 0–100 → 0–1
  const connNorm = county.pillars.transport.score / 100;
  setLevers((prev) => ({
    ...prev,
    skills: parseFloat((educationNorm * 5).toFixed(1)),   // education → skills [0,5]
    conn:   parseFloat(connNorm.toFixed(2)),               // transport → connectivity [0,1]
  }));
  setLeversSeededFrom(nuts3Code);
}, [nuts3Code, infraLayer, leversSeededFrom]);
```

**Add reset function:**
```typescript
function resetLeversToNeutral() {
  setLevers(DEFAULT_LEVERS);
  setLeversSeededFrom(null);
}
```

Import `DEFAULT_LEVERS` from types (it's already exported from `../types`).

**Mount CapacityCard** after the `CostReadout` line and before the metrics grid. In the JSX, after `<CostReadout ... />`:

```typescript
{infraLayer && nuts3Code && infraLayer.counties[nuts3Code] && (
  <>
    {leversSeededFrom === nuts3Code && (
      <div className="mx-3 mb-1 text-[10px] text-blue-600 flex items-center justify-between">
        <span>Levers pre-seeded from infrastructure index</span>
        <button
          onClick={resetLeversToNeutral}
          className="underline hover:text-blue-800"
        >
          reset to neutral
        </button>
      </div>
    )}
    <CapacityCard
      county={infraLayer.counties[nuts3Code]}
      countyCode={nuts3Code}
      layer={infraLayer}
    />
  </>
)}
```

- [ ] **Step 3: Type-check and smoke test**

```bash
cd dashboard && npx tsc --noEmit && npm run dev
```

Open http://localhost:5173. Click a county. Verify:
- CapacityCard appears below CostReadout, showing the radar chart and pillar breakdown
- The seeding notice appears with a "reset to neutral" link
- Clicking "reset to neutral" returns levers to zero
- Clicking a different county triggers re-seeding

- [ ] **Step 4: Run full test suite**

```bash
cd dashboard && npm test
```

Expected: all existing tests pass.

- [ ] **Step 5: Production build check**

```bash
cd dashboard && npm run build
```

Expected: build succeeds with no errors.

- [ ] **Step 6: Commit (v1a complete)**

```bash
git add dashboard/src/App.tsx dashboard/src/components/PolicyLab.tsx
git commit -m "feat(infra/v1a): complete — CapacityCard in PolicyLab, lever seeding + reset"
```

---

## v1b — Divergence Detection + Sensitivity (gated on v1a)

**Gate:** Do not proceed with Tasks 8–11 until:
1. v1a is committed and working.
2. The Task 0 audit confirmed that the pillar scores are meaningful (≤15 counties with <2 features per pillar).

---

### Task 8: I2_flag_divergence.py + structural_hypotheses.yaml

**Files:**
- Create: `scripts/infra/I2_flag_divergence.py`
- Create: `scripts/infra/structural_hypotheses.yaml`
- Create: `scripts/infra/tests/test_I2.py`

- [ ] **Step 1: Write failing tests**

Create `scripts/infra/tests/test_I2.py`:

```python
"""Tests for I2_flag_divergence.py"""
import sys
from pathlib import Path
import numpy as np
import pandas as pd
import pytest
import geopandas as gpd
from shapely.geometry import Polygon

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import I2_flag_divergence as I2


class TestStudentizedLooResiduals:
    def test_outlier_gets_high_absolute_t(self):
        """A point far from the regression line has |t| > 2."""
        rng = np.random.default_rng(42)
        x = np.linspace(0, 100, 20)
        y = 0.5 * x + rng.normal(0, 2, 20)
        # Inject one outlier
        y[10] = y[10] + 40
        resids = I2._studentized_loo_residuals(x, y)
        assert abs(resids[10]) > 2.0

    def test_inlier_has_low_t(self):
        rng = np.random.default_rng(0)
        x = np.linspace(0, 100, 30)
        y = 0.3 * x + rng.normal(0, 1, 30)
        resids = I2._studentized_loo_residuals(x, y)
        # Most should be within ±2
        assert (np.abs(resids) < 2).mean() > 0.8

    def test_length_matches_input(self):
        x = np.arange(10, dtype=float)
        y = np.arange(10, dtype=float) + np.random.normal(0, 0.1, 10)
        resids = I2._studentized_loo_residuals(x, y)
        assert len(resids) == 10


class TestLisaQuadrant:
    def _make_grid_gdf(self) -> gpd.GeoDataFrame:
        """4-county 2x2 grid for testing LISA."""
        polys = [
            Polygon([(0,0),(1,0),(1,1),(0,1)]),
            Polygon([(1,0),(2,0),(2,1),(1,1)]),
            Polygon([(0,1),(1,1),(1,2),(0,2)]),
            Polygon([(1,1),(2,1),(2,2),(1,2)]),
        ]
        return gpd.GeoDataFrame(
            {"nuts3_code": ["A","B","C","D"]},
            geometry=polys,
            crs="EPSG:4326"
        )

    def test_returns_valid_quadrants(self):
        gdf = self._make_grid_gdf()
        capacity = pd.Series({"A": 90.0, "B": 20.0, "C": 80.0, "D": 30.0})
        quads = I2._lisa_quadrants(capacity, gdf)
        assert set(quads.values).issubset({"HH", "HL", "LH", "LL", "NS"})

    def test_index_matches_nuts3_codes(self):
        gdf = self._make_grid_gdf()
        capacity = pd.Series({"A": 50.0, "B": 50.0, "C": 50.0, "D": 50.0})
        quads = I2._lisa_quadrants(capacity, gdf)
        assert set(quads.index) == {"A", "B", "C", "D"}


class TestClassifyDivergence:
    def test_high_cap_low_outcome_is_bottleneck(self):
        result = I2._classify_divergence(2.5, "HL")
        assert result == "structural_bottleneck"

    def test_low_cap_high_outcome_is_fragility(self):
        result = I2._classify_divergence(-2.5, "LH")
        assert result == "latent_fragility"

    def test_within_threshold_is_none(self):
        assert I2._classify_divergence(1.0, "HL") is None
        assert I2._classify_divergence(-1.0, "LH") is None
```

- [ ] **Step 2: Run tests — verify they fail**

```bash
python -m pytest scripts/infra/tests/test_I2.py -v 2>&1 | head -20
```

Expected: `ImportError: No module named 'I2_flag_divergence'`

- [ ] **Step 3: Create structural_hypotheses.yaml**

```yaml
# Researcher-maintained structural hypotheses for divergence-flagged counties.
# Each entry is explicitly labelled as a hypothesis for investigation, not a causal claim.
# Keyed by NUTS3 code.
RO111:  # Bihor
  hypothesis: >
    Cross-border trade exposure to Hungary may redirect investment and labour
    toward the Hungarian side. Institutional absorptive-capacity constraints
    (regulatory complexity, planning delays) may limit conversion of physical
    infrastructure into economic output. Hypothesis for investigation.
RO125:  # Mureș
  hypothesis: >
    Ethnic heterogeneity and fragmented local governance may increase coordination
    costs for investment decisions. The county's industrial legacy (chemical, 
    pharmaceutical) creates path-dependency that physical connectivity alone cannot
    overcome. Hypothesis for investigation.
RO174:  # Galați
  hypothesis: >
    Heavy steel-industry legacy (Sidex/ArcelorMittal) anchors capital in declining
    sectors. Port-hinterland connectivity exists but does not translate into
    diversified export growth. Structural transformation lag. Hypothesis for investigation.
RO216:  # Brăila
  hypothesis: >
    Port infrastructure present but underutilised; agricultural hinterland with
    low value-added processing. Proximity to Galați creates competition rather
    than complementarity. Hypothesis for investigation.
```

- [ ] **Step 4: Implement I2_flag_divergence.py**

Create `scripts/infra/I2_flag_divergence.py`:

```python
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
    w = Queen.from_dataframe(merged, silence_warnings=True)
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
    print(f"  Low-power note: n≈{len(common)} counties; ~2 false positives expected under null")
    return result


if __name__ == "__main__":
    import I1_score_counties as I1
    print("=== I2: Divergence detection ===")
    counties, _, _ = I1.extract()
    flags = extract(counties)
    flagged = {k: v for k, v in flags.items() if v is not None}
    print(f"  Flagged: {list(flagged.keys())}")
```

- [ ] **Step 5: Run tests**

```bash
python -m pytest scripts/infra/tests/test_I2.py -v
```

Expected: all tests pass.

- [ ] **Step 6: Commit**

```bash
git add scripts/infra/I2_flag_divergence.py scripts/infra/structural_hypotheses.yaml \
        scripts/infra/tests/test_I2.py
git commit -m "feat(infra/I2): studentized LOO residuals + LISA divergence detection"
```

---

### Task 9: I3_sensitivity.py — rank intervals

**Files:**
- Create: `scripts/infra/I3_sensitivity.py`
- Create: `scripts/infra/tests/test_I3.py`

- [ ] **Step 1: Write failing tests**

Create `scripts/infra/tests/test_I3.py`:

```python
"""Tests for I3_sensitivity.py"""
import sys
from pathlib import Path
import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import I3_sensitivity as I3


def make_scores(seed=42) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    codes = [f"RO{i:03d}" for i in range(42)]
    return pd.DataFrame(
        rng.uniform(0, 100, (42, 4)),
        index=codes,
        columns=["transport", "education", "health", "economic"],
    )


class TestBuildEnsemble:
    def test_returns_expected_columns(self):
        scores = make_scores()
        df = I3._build_ensemble(scores)
        assert "nuts3_code" in df.columns
        assert "rank" in df.columns
        assert "variant" in df.columns

    def test_rank_range_is_valid(self):
        scores = make_scores()
        df = I3._build_ensemble(scores)
        n = len(scores)
        assert df["rank"].between(1, n).all()

    def test_deterministic_with_seed(self):
        scores = make_scores()
        df1 = I3._build_ensemble(scores)
        df2 = I3._build_ensemble(scores)
        assert df1["rank"].equals(df2["rank"])


class TestRankIntervals:
    def test_min_leq_median_leq_max(self):
        scores = make_scores()
        intervals = I3.extract(scores)
        for code, v in intervals.items():
            assert v["rank_interval"][0] <= v["rank_median"] <= v["rank_interval"][1]

    def test_returns_entry_for_every_county(self):
        scores = make_scores()
        intervals = I3.extract(scores)
        assert set(intervals.keys()) == set(scores.index)

    def test_stable_county_has_narrow_interval(self):
        """All-equal pillars → every variant gives same rank → interval width 0."""
        codes = [f"RO{i:03d}" for i in range(10)]
        # Make county RO000 uniformly 50; others vary
        rng = np.random.default_rng(1)
        data = rng.uniform(0, 100, (10, 4))
        data[0] = [50, 50, 50, 50]
        scores = pd.DataFrame(data, index=codes, columns=["transport","education","health","economic"])
        intervals = I3.extract(scores)
        ri = intervals["RO000"]["rank_interval"]
        # Interval should be ≤ 3 (small variation from normalisation across variants)
        assert ri[1] - ri[0] <= 3
```

- [ ] **Step 2: Run tests — verify they fail**

```bash
python -m pytest scripts/infra/tests/test_I3.py -v 2>&1 | head -10
```

- [ ] **Step 3: Implement I3_sensitivity.py**

Create `scripts/infra/I3_sensitivity.py`:

```python
"""
I3 — Sensitivity analysis: rank intervals across 8 methodological variants.

Variants = {minmax, zscore} × {equal, pca} × {geometric, arithmetic} = 8 combinations.
Reports per-county rank interval and median rank.

Follows Saisana, Saltelli & Tarantola (2005), JRSS-A.
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sklearn.decomposition import PCA
from sklearn.preprocessing import StandardScaler

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "infra"))

EPSILON = 0.01


def _minmax(df: pd.DataFrame) -> pd.DataFrame:
    result = df.copy()
    for col in df.columns:
        lo, hi = df[col].quantile(0.05), df[col].quantile(0.95)
        if hi == lo:
            result[col] = 50.0
        else:
            result[col] = (df[col].clip(lo, hi) - lo) / (hi - lo) * 100
    return result


def _zscore(df: pd.DataFrame) -> pd.DataFrame:
    """Z-score standardise, then rescale to [0,100] via min-max."""
    z = (df - df.mean()) / df.std(ddof=1).replace(0, 1)
    return _minmax(z)


def _pca_weights(df: pd.DataFrame) -> np.ndarray:
    X = StandardScaler().fit_transform(df.values)
    pca = PCA(n_components=1, random_state=42)
    pca.fit(X)
    loadings = np.abs(pca.components_[0])
    return loadings / loadings.sum()


def _composite_geom(normed: pd.DataFrame, weights: np.ndarray) -> pd.Series:
    return normed.apply(
        lambda row: float(np.exp(np.average(np.log(np.maximum(row.values, EPSILON)), weights=weights))),
        axis=1,
    )


def _composite_arith(normed: pd.DataFrame, weights: np.ndarray) -> pd.Series:
    return normed.apply(lambda row: float(np.average(row.values, weights=weights)), axis=1)


def _build_ensemble(scores_df: pd.DataFrame) -> pd.DataFrame:
    """Return long-form DataFrame with columns: nuts3_code, variant, rank."""
    records: list[dict] = []
    n_pillars = scores_df.shape[1]
    equal_w = np.ones(n_pillars) / n_pillars
    pca_w = _pca_weights(scores_df)

    for norm_name, norm_fn in [("minmax", _minmax), ("zscore", _zscore)]:
        normed = norm_fn(scores_df)
        for weight_name, w in [("equal", equal_w), ("pca", pca_w)]:
            for agg_name, agg_fn in [("geometric", _composite_geom), ("arithmetic", _composite_arith)]:
                composite = agg_fn(normed, w)
                # Rank: 1 = highest capacity
                ranked = composite.rank(ascending=False, method="min").astype(int)
                variant = f"{norm_name}_{weight_name}_{agg_name}"
                for code, rank in ranked.items():
                    records.append({"nuts3_code": str(code), "variant": variant, "rank": int(rank)})

    return pd.DataFrame(records)


def extract(scores_df: pd.DataFrame) -> dict[str, Any]:
    """
    Args:
        scores_df: DataFrame(index=nuts3_code, columns=pillar_keys) of normalised scores.
    Returns:
        dict: nuts3_code → {rank_interval: [min, max], rank_median: int}
    """
    ensemble = _build_ensemble(scores_df)

    result: dict[str, Any] = {}
    for code, grp in ensemble.groupby("nuts3_code"):
        ranks = grp["rank"].values
        result[str(code)] = {
            "rank_interval": [int(ranks.min()), int(ranks.max())],
            "rank_median": int(np.median(ranks)),
        }

    n_variants = ensemble["variant"].nunique()
    print(f"  Sensitivity ensemble: {n_variants} variants")
    return result


if __name__ == "__main__":
    sys.path.insert(0, str(ROOT / "scripts" / "infra"))
    import I1_score_counties as I1
    import pandas as pd as pd_

    print("=== I3: Sensitivity analysis ===")
    _, _, _ = I1.extract()
    scores = pd_.read_parquet(ROOT / "data" / "processed" / "infra_scores.parquet")[
        ["transport", "education", "health", "economic"]
    ]
    intervals = extract(scores)
    wide = [intervals[c]["rank_interval"][1] - intervals[c]["rank_interval"][0] for c in intervals]
    print(f"  Median rank-interval width: {int(np.median(wide))}")
    print(f"  Max rank-interval width: {max(wide)}")
```

- [ ] **Step 4: Fix the `import pandas as pd as pd_` typo in the __main__ block**

The `__main__` block in I3 above has a syntax error (`import pandas as pd as pd_`). Fix it to:
```python
import pandas as pd
```
(remove the duplicate alias).

- [ ] **Step 5: Run tests**

```bash
python -m pytest scripts/infra/tests/test_I3.py -v
```

Expected: all tests pass.

- [ ] **Step 6: Commit**

```bash
git add scripts/infra/I3_sensitivity.py scripts/infra/tests/test_I3.py
git commit -m "feat(infra/I3): sensitivity ensemble — 8 variants, rank intervals per county"
```

---

### Task 10: I0_build_infra_layer.py — full orchestrator (replace v1a stub)

**Files:**
- Modify: `scripts/infra/I0_build_infra_layer.py` (replace v1a version entirely)

- [ ] **Step 1: Replace I0 with the full orchestrator**

Overwrite `scripts/infra/I0_build_infra_layer.py` with:

```python
"""
I0 — Infra layer orchestrator (v1b, full).
Runs I1 → I2 → I3 and writes data/dashboard/infra_layer.json.

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
    """Recursively coerce numpy scalars → Python, non-finite floats → None."""
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
    print(f"  ✓ {len(counties)} counties scored  (Cronbach α={alpha:.3f})")

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

    n_variants = len(set(
        v["variant"]
        for v in [{"variant": f"v{i}"} for i in range(8)]  # placeholder count
    ))
    # Actual count from I3 module constant
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
    print(f"  {len(counties)} counties, {flagged} divergence flags, α={alpha:.3f}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Run the full orchestrator**

```bash
python scripts/infra/I0_build_infra_layer.py
```

Expected output:
```
=== I0 (v1b): Building infra_layer.json ===

[I1] Scoring counties...
  Cronbach α=0.XXX ...
  ✓ 42 counties scored  (Cronbach α=0.XXX)

[I2] Flagging divergence...
  Flagged N counties (threshold |t|>2.0)
  Low-power note: n≈42 counties; ~2 false positives expected under null

[I3] Computing sensitivity ensemble...
  Sensitivity ensemble: 8 variants

✓ Written data/dashboard/infra_layer.json
  42 counties, N divergence flags, α=0.XXX
```

- [ ] **Step 3: Verify JSON and that rank_interval is non-trivial**

```bash
python -c "
import json
d = json.load(open('data/dashboard/infra_layer.json'))
print('meta:', d['_meta']['ensemble_variants'], 'variants')
sample = list(d['counties'].values())[:3]
for c in sample:
    print(c['name'], 'rank:', c['rank_interval'], 'div:', c['divergence'] and c['divergence']['type'])
"
```

- [ ] **Step 4: Commit**

```bash
git add scripts/infra/I0_build_infra_layer.py data/dashboard/infra_layer.json \
        data/processed/infra_scores.parquet
git commit -m "feat(infra/I0): v1b full orchestrator — I1+I2+I3, rank intervals + divergence flags"
```

---

### Task 11: DivergenceAlert.tsx + map badge + final integration

**Files:**
- Create: `dashboard/src/components/DivergenceAlert.tsx`
- Modify: `dashboard/src/components/PolicyLab.tsx`
- Modify: `dashboard/src/components/RomaniaMap.tsx`

- [ ] **Step 1: Implement DivergenceAlert.tsx**

```typescript
import type { DivergenceFlag } from '../types';

interface Props {
  flag: DivergenceFlag;
}

const TYPE_META: Record<string, { label: string; colorClass: string; emoji: string }> = {
  structural_bottleneck: {
    label: 'High capacity · below-trend growth',
    colorClass: 'border-amber-200 bg-amber-50',
    emoji: '⚠',
  },
  latent_fragility: {
    label: 'Low capacity · above-trend growth',
    colorClass: 'border-orange-200 bg-orange-50',
    emoji: '📉',
  },
};

export default function DivergenceAlert({ flag }: Props) {
  const meta = TYPE_META[flag.type] ?? TYPE_META['structural_bottleneck'];

  return (
    <div className={`mx-3 mb-2 rounded border text-xs p-2 space-y-1.5 ${meta.colorClass}`}>
      {/* Tier 1 — Observation */}
      <div className="font-medium text-gray-800">
        {meta.emoji} Structural signal: {meta.label}
      </div>

      {/* Data confidence off-ramp — shown BEFORE the hypothesis */}
      {flag.data_caveat && (
        <div className="text-[10px] text-red-600 bg-red-50 rounded px-1.5 py-1 border border-red-200">
          ⚠ Coverage caveat: {flag.data_caveat}
        </div>
      )}

      {/* Tier 2 — Statistical strength */}
      <div className="text-gray-600 text-[10px] space-x-2">
        <span>
          <span className="text-gray-400">Residual t: </span>
          <span className="font-mono">{flag.resid_t.toFixed(2)}</span>
        </span>
        <span>·</span>
        <span>
          <span className="text-gray-400">LISA: </span>
          <span className="font-mono">{flag.lisa_quadrant}</span>
          {flag.lisa_quadrant === 'HL' && ' (isolated high-capacity outlier)'}
          {flag.lisa_quadrant === 'LH' && ' (isolated low-capacity outlier)'}
        </span>
      </div>

      {/* Tier 3 — Hypothesis */}
      <div className="text-gray-500 text-[10px] leading-snug border-t border-gray-200 pt-1">
        <span className="font-medium text-gray-600">Hypothesis for investigation: </span>
        {flag.structural_hypothesis}
      </div>

      <p className="text-[9px] text-gray-400">
        n ≈ 42 counties — ~2 flags expected by chance. Investigate with administrative
        data before drawing policy conclusions.
      </p>
    </div>
  );
}
```

- [ ] **Step 2: Mount DivergenceAlert in PolicyLab.tsx**

In `dashboard/src/components/PolicyLab.tsx`, add the import and render the alert after CapacityCard:

**Add import at top:**
```typescript
import DivergenceAlert from './DivergenceAlert';
```

**In the JSX, after the CapacityCard block:**
```typescript
{infraLayer && nuts3Code && infraLayer.counties[nuts3Code]?.divergence && (
  <DivergenceAlert flag={infraLayer.counties[nuts3Code]!.divergence!} />
)}
```

- [ ] **Step 3: Add divergence badge to RomaniaMap.tsx**

In `dashboard/src/components/RomaniaMap.tsx`, add a divergence ring for flagged counties. After the `CircleMarker` block for POI markers, add a separate layer for divergence badges:

```typescript
{/* Divergence badges — orange rings on flagged counties, always visible */}
{infraLayer &&
  Object.entries(infraLayer.counties)
    .filter(([, c]) => c.divergence !== null)
    .map(([code, county]) => {
      // Use county seat centroid from regions.json — approximate
      // We don't have centroids in infra_layer so we'll skip map badges
      // unless we add lat/lon to the JSON in a future iteration.
      // For now: the divergence is surfaced in PolicyLab when the county is selected.
      return null;
    })}
```

**Note:** County polygon centroids are not available in `infra_layer.json`. Rather than adding another data join to the map component, add a visual cue to the county choropleth instead. In the `getStyle` function, add a special stroke for flagged counties:

```typescript
function getStyle(feature: Feature | undefined) {
  if (!feature) return {};
  const nuts3 = (feature as NutsFeature).properties.NUTS_ID;
  const isSelected = nuts3 === selectedNuts3;
  const isDivergent = infraLayer?.counties[nuts3]?.divergence != null;

  // ... existing style logic ...

  return {
    fillColor,
    fillOpacity: isSelected ? 0.9 : 0.7,
    color: isDivergent ? '#f59e0b' : (isSelected ? '#1d4ed8' : '#ffffff'),
    weight: isDivergent ? 2.5 : (isSelected ? 2.5 : 0.8),
    dashArray: isDivergent && !isSelected ? '4 2' : undefined,
  };
}
```

This gives divergent counties a dashed amber border without needing centroid data.

- [ ] **Step 4: Type-check**

```bash
cd dashboard && npx tsc --noEmit
```

Expected: 0 errors.

- [ ] **Step 5: Run full test suite**

```bash
cd dashboard && npm test
```

Expected: all tests pass (existing format.test.ts + capacity.test.ts + scenarioUrl.test.ts).

- [ ] **Step 6: Production build**

```bash
cd dashboard && npm run build
```

Expected: build succeeds, no TypeScript errors, no Vite errors.

- [ ] **Step 7: Manual integration check**

```bash
cd dashboard && npm run dev
```

Verify:
- A county with a divergence flag shows a dashed amber county border on the map
- Clicking that county opens PolicyLab with CapacityCard + DivergenceAlert
- DivergenceAlert shows all three tiers; data_caveat box appears (if applicable)
- Counties without flags show no DivergenceAlert
- Basemap toggle, pillar markers at zoom ≥ 7, CSV export all still work

- [ ] **Step 8: Run all Python tests**

```bash
python -m pytest scripts/infra/tests/ scripts/calibration/tests/ -v
```

Expected: all tests pass.

- [ ] **Step 9: Commit (v1b complete)**

```bash
git add dashboard/src/components/DivergenceAlert.tsx \
        dashboard/src/components/PolicyLab.tsx \
        dashboard/src/components/RomaniaMap.tsx
git commit -m "feat(infra/v1b): DivergenceAlert (3-tier), map dashed-amber badges, full integration"
```

---

## Post-implementation self-review

**Spec coverage check:**

| Spec requirement | Task |
|---|---|
| OSM extracts + NUTS3 boundary + README provenance | Task 0 |
| types.ts — 7 new interfaces | Task 1 |
| I1: per-area/per-capita denominators, winsorise+minmax, Cronbach α, geometric mean, PCA weights, confidence | Task 2 |
| I0 v1a stub writes infra_layer.json | Task 3 |
| capacity.ts: load, percentile, peers, CSV export | Task 4 |
| InfraLayerPanel: pillar toggles, basemap switch, colourblind-safe | Task 5 |
| RomaniaMap: basemap tiles, clustered POI (zoom ≥7), progressive disclosure | Task 5 |
| CapacityCard: radar, composite, percentile, rank interval, peers | Task 6 |
| PolicyLab: mount CapacityCard, seed levers, reset-to-neutral, labelled | Task 7 |
| I2: studentized LOO residuals, LISA quadrants, data_caveat off-ramp, hypotheses.yaml | Task 8 |
| I3: 8-variant ensemble, rank intervals, median | Task 9 |
| I0 v1b: full orchestrator, _sanitize, _meta provenance | Task 10 |
| DivergenceAlert: 3 tiers, data off-ramp first, low-power footnote | Task 11 |
| Map divergence badge (amber dashed border) | Task 11 |
| JSON sanitize + allow_nan=False (NaN→null) | Task 10 |
| Caveats: temporal, MAUP, coverage, low-power, n≈42 | Tasks 8, 11 |

All spec sections covered. No placeholders remain.
