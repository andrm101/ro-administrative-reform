# Institutions & Infrastructure Layer — Design Spec

**Date:** 2026-06-06
**Status:** Approved for planning
**Predecessor:** `2026-06-05-calibration-interface-v1-design.md` (Plan 2 shipped empirical betas + Interface V1; `provisional: true` because the OOS gate honestly fails on the 1995–2004 transition era)
**Scope:** Add an institutions & infrastructure layer to the Policy Lab. Two coordinated workstreams — (1) a Python pipeline that turns pre-downloaded OpenStreetMap extracts into a **formal composite capacity indicator** per NUTS3 county, with spatial divergence detection and uncertainty quantification; (2) dashboard components that surface the index on the map and inside Policy Lab as **advisory context**, never as model input.

---

## 1. Goals & Governing Principle

1. **Map what exists.** Connectivity, skills, health, and economic-zone infrastructure are hidden attributes that shape a county's capacity for development. Make them explorable on the real map, close to a normal GIS experience.
2. **Quantify capacity honestly.** Express each county's endowment as a composite indicator built to the OECD/JRC standard (Nardo et al., 2008) — normalised, validity-checked, non-compensatory, and uncertainty-bounded — matching the rigour of the calibration layer.
3. **Treat incoherence as signal, not error.** Where realised outcomes diverge from what capacity predicts, flag it as a *structural hypothesis for investigation*, not a data fault and not a causal claim.

**Governing invariant — separation of concerns.** The capacity index lives in a **sibling artefact** (`infra_layer.json`) to `elasticities.json`. It colours the *display* — a context card, a divergence narrative, suggested lever starting points — and **never modifies a calibrated coefficient**. Lever baselines seeded from pillar scores are labelled suggestions with a one-click reset, not parameters.

**Non-goals (deferred, documented in §9):** historical accessibility vintages; full spatial lag/error regression; DEA/AHP weighting; live weight sliders; ingestion of official INSSE NUTS3 infrastructure registers.

---

## 2. Architecture

```
data/raw/osm/                          scripts/infra/                       data/dashboard/
  transport.geojson      ─┐             I1_score_counties.py    ─┐
  education.geojson      ─┼───────────► I2_flag_divergence.py   ─┼──────────► infra_layer.json
  health.geojson         ─┤             I3_sensitivity.py       ─┘             (+ _meta provenance)
  economic_zones.geojson ─┘             I0_build_infra_layer.py (orchestrator, seeded, idempotent)
  README.md (provenance)

dashboard/src/
  utils/capacity.ts            (NEW — loader, percentile/peer helpers, CSV export)
  utils/capacity.test.ts       (NEW)
  components/InfraLayerPanel.tsx (NEW — pillar toggles, basemap switch, legend)
  components/CapacityCard.tsx    (NEW — radar, composite, percentile, rank interval, peers)
  components/DivergenceAlert.tsx (NEW — three-tier framing with data off-ramp)
  components/RomaniaMap.tsx      (MODIFY — basemap tiles, clustered POI, divergence badge)
  components/PolicyLab.tsx       (MODIFY — mount cards on select, seed lever baselines)
  components/MetricTooltip.tsx   (REUSE — provenance tooltip on every score & flag)
  types.ts                       (MODIFY — InfraLayer, CapacityIndex, PillarScore, DivergenceFlag, RankInterval)
```

The pipeline reads **only** from `data/raw/osm/` (new immutable extracts) and `data/dashboard/regions.json` (existing — for the recent-outcome series used in divergence detection). It writes one `infra_layer.json`. No TypeScript engine changes; no changes to `elasticities.json`.

---

## 3. Raw Data — OpenStreetMap extracts

Four pre-downloaded GeoJSON files under `data/raw/osm/`, produced once via Overpass and treated as immutable per project convention. Each is a FeatureCollection of points/lines clipped to Romania.

| File | OSM selectors (indicative) | Pillar |
|---|---|---|
| `transport.geojson` | `highway=motorway/trunk/primary`, `railway=station/halt`, `aeroway=aerodrome` | Transport / connectivity |
| `education.geojson` | `amenity=university/college`, `office=research`, `building=university` | Education & research |
| `health.geojson` | `amenity=hospital/clinic`, `healthcare=hospital` (+ `beds=*` where tagged) | Health capacity |
| `economic_zones.geojson` | `landuse=industrial`, `industrial=*`, special-economic-zone relations, `office=company` clusters | Economic zones & industry |

`data/raw/osm/README.md` **must** cite, per CLAUDE.md: Overpass query date, the exact Overpass QL for each file, the OSM tag set, the clipping boundary, and the licence (ODbL). Variable definitions accompany each pillar.

**Spatial join:** each feature is assigned to a NUTS3 county by point-in-polygon against the NUTS3 boundaries already used by `RomaniaMap.tsx` (GISCO `NUTS_RG_20M_2021_4326_LEVL_3`), cached locally to keep the pipeline offline.

---

## 4. Pipeline — `I1_score_counties.py` (composite construction)

Implements the OECD/JRC composite-indicator workflow. Output: per-county pillar scores + composite, both equal- and PCA-weighted, geometric- and arithmetic-aggregated.

**a. Denominators (not raw counts).** Size-invariant intensities:
- Transport: motorway+trunk km per km², rail stations per km², airport present (0/1).
- Education: university/research seats (proxy: institution count) per 1,000 inhabitants.
- Health: hospitals per 1,000 inhabitants; beds per 1,000 where `beds=*` tagged, else hospital count.
- Economic: industrial-zone area share of county area; SEZ present (0/1).

Population and area per county come from `regions.json` (or a small static `county_geo.csv` derived from the NUTS3 polygons; documented in the README).

**b. Normalisation.** Winsorise each indicator at the 5th/95th percentile, then min–max rescale to [0, 100]. Winsorisation prevents Bucharest-Ilfov / Cluj from compressing the scale.

**c. Construct validity.** Compute the 4×4 inter-pillar Pearson correlation matrix and **Cronbach's α** (Cronbach, 1951). Emit both into diagnostics. If any pillar pair |r| > 0.85, log a redundancy warning (implicit double-weighting of a latent dimension) — a documented limitation, not a build failure.

**d. Weighting.** Two schemes, both stored: **equal** (default, transparent) and **PCA** (first-component loadings, data-driven cross-check). Disagreement between them is informative and feeds §6.

**e. Aggregation.** **Geometric mean across pillars** is the default (partially non-compensatory: a hollow pillar cannot be fully masked by a strong one — Munda, 2008; UNDP HDI methodology since 2010). The **arithmetic mean** is also computed and stored so the UI can toggle and expose the gap (the arithmetic−geometric gap is itself an imbalance measure). Zero-valued pillars are floored at a small ε before the geometric mean to keep it defined; ε documented.

**f. Data confidence.** Per pillar per county, classify OSM coverage as `high | medium | low` from feature density relative to population (sparse rural counties flag `low`). Stored per pillar; consumed by the divergence off-ramp (§5) and surfaced in tooltips.

---

## 5. Pipeline — `I2_flag_divergence.py` (structural anomaly detection)

A county is flagged only when its realised outcome diverges from what its capacity predicts — not on two independent ±SD cuts.

**a. Recent outcome.** `recent_gva_growth` = `actual` ln-GVA at 2023 minus 2019 from `regions.json.counterfactualSeries` (existing data; a 4-year window where the 2026 OSM snapshot is a defensible proxy for the contemporary cross-section). This is explicitly **cross-sectional and contemporary, not longitudinal or causal.**

**b. Residual outlier.** Robust regression `recent_gva_growth ~ capacity_index` (Huber). Compute **studentized leave-one-out residuals**; flag `|t_i| > 2`. Leave-one-out prevents the anomalies from bending the very line meant to detect them (masking).

**c. Spatial lens.** **Local Moran's I / LISA** (Anselin, 1995) on the capacity index using a queen-contiguity NUTS3 weights matrix. Classify each county HH / LL / **HL** / **LH**. A high-capacity/low-outcome county that is *also* an HL spatial outlier (isolated among prosperous neighbours) is a stronger, distinct signal from one embedded in a depressed macro-region.

**d. Classification & narrative.**
- `structural_bottleneck`: high capacity, below-trend outcome (resid t > 2).
- `latent_fragility`: low capacity, above-trend outcome (resid t < −2).
- `null`: otherwise.

**e. Data off-ramp (mandatory, before any narrative).** If the flag rests on a pillar whose `data_confidence == "low"`, set `data_caveat` to an explanatory string. A coverage gap must never masquerade as a societal structural problem.

**f. Structural hypotheses.** A small researcher-maintained `structural_hypotheses.yaml` (keyed by NUTS3 code) supplies domain-informed candidate explanations for the counties most likely to flag (e.g., cross-border trade exposure, heavy-industry legacy, port–hinterland disconnect). Each is rendered with the explicit label *"hypothesis for investigation, not a causal claim."* Counties without an entry show the generic narrative only.

---

## 6. Pipeline — `I3_sensitivity.py` (uncertainty quantification)

Following Saisana, Saltelli & Tarantola (2005): construct an ensemble over the modelling choices and report **rank intervals**, not point ranks.

- Ensemble = {min–max, z-score} normalisation × {equal, PCA} weights × {geometric, arithmetic} aggregation = up to 8 base variants (extensible). Recompute the full ranking under each.
- Per county: store `rank_interval = [min_rank, max_rank]` across the ensemble and the median rank.
- Counties with wide intervals are flagged as *methodology-sensitive* in the UI (the standing is an artefact of choices, not a robust fact).

Seeded (`np.random.seed(42)`) and deterministic; reproducible top-to-bottom per CLAUDE.md.

---

## 7. Pipeline — `I0_build_infra_layer.py` (orchestrator) & data contract

Runs I1 → I2 → I3, merges, sanitises, writes `data/dashboard/infra_layer.json`. Reuses the calibration pipeline's `_sanitize()` (NaN/Inf → `null`) and `json.dumps(..., allow_nan=False)` backstop (browser-safe JSON, per [[feedback-bootstrap-perf]]). Emits a `_meta` provenance block.

```jsonc
{
  "_meta": {
    "overpass_query_date": "2026-05",
    "script_version": "1.0.0",
    "git_sha": "…",
    "aggregation_default": "geometric",
    "weighting_default": "equal",
    "cronbach_alpha": 0.71,
    "pillar_correlation": [[1,0.42,...], ...],
    "ensemble_variants": 8
  },
  "RO111": {
    "name": "Bihor",
    "nuts2_code": "RO11",
    "capacity_index": 67.2,               // geometric, equal-weighted, 0–100
    "capacity_index_arithmetic": 71.8,    // for the imbalance-gap toggle
    "national_percentile": 73,
    "rank_interval": [12, 18],
    "rank_median": 14,
    "pillars": {
      "transport": { "score": 72, "features": 14, "confidence": "high" },
      "education": { "score": 81, "features": 6,  "confidence": "high" },
      "health":    { "score": 55, "features": 9,  "confidence": "medium" },
      "economic":  { "score": 61, "features": 3,  "confidence": "low" }
    },
    "peers": ["RO421", "RO126"],          // nearest capacity profile (Euclidean on pillar vector)
    "divergence": {                       // null if no flag
      "type": "structural_bottleneck",
      "resid_t": 2.41,
      "lisa_quadrant": "HL",
      "data_caveat": null,
      "structural_hypothesis": "Cross-border trade exposure to Hungary; possible institutional absorptive-capacity constraint. Hypothesis for investigation, not a causal claim."
    }
  }
}
```

POI geometries are **not** embedded in this JSON (size). The map reads the four `*.geojson` files directly (copied to `dashboard/public/data/osm/` at build, like the existing served data).

---

## 8. Dashboard components

### 8.1 `utils/capacity.ts` (+ test)
- `loadInfraLayer(): Promise<InfraLayer>` — fetch + parse `infra_layer.json`.
- `nationalPercentile(code, layer)`, `peerCounties(code, layer)`.
- `exportCapacityCsv(layer): string` — capacity table + flags for the written report.
- Pure functions, unit-tested (percentile, peer ordering, CSV shape, null-divergence handling).

### 8.2 `InfraLayerPanel.tsx` (NEW)
Right-side collapsible panel in the map. Pillar toggles (Transport / Education / Health / Economic), basemap switch (**Carto Positron default**, Satellite optional), and a legend that updates with the active layer. Colourblind-safe ramps; the divergence palette uses **blue↔orange diverging** (not red-green) and is visually distinct from POI markers.

### 8.3 `RomaniaMap.tsx` (MODIFY)
- Add a basemap `TileLayer` (Positron / Esri Satellite per toggle).
- Render POI markers per active pillar with **clustering** (leaflet.markercluster) and **progressive disclosure**: choropleth-only at low zoom; markers appear on zoom-in.
- Render a **divergence badge** on flagged counties (distinct icon/ring); clicking it selects the county and opens its Policy Lab card.
- Capacity index becomes a selectable choropleth layer alongside the existing GVA/suitability layers.

### 8.4 `CapacityCard.tsx` (NEW)
Mounted in Policy Lab on county-select. Shows: composite score with **national percentile**; **rank interval** (e.g., "rank 12–18", never a false-precision point rank); a **4-axis radar chart** of pillar scores (the composite is never shown without its shape); a **peer row** (2–3 nearest-profile counties + their recent outcome for contrast); and a `MetricTooltip` on every figure carrying method, weighting/aggregation, Cronbach α, and data confidence.

### 8.5 `DivergenceAlert.tsx` (NEW)
Renders only when `divergence != null`. Three labelled tiers:
1. **Observation** — plain-language statement ("high infrastructure capacity, below-trend recent growth").
2. **Statistical strength** — residual t and LISA quadrant ("isolated high-capacity spatial outlier").
3. **Candidate explanations** — the `structural_hypothesis`, explicitly labelled as hypotheses, not conclusions.

If `data_caveat` is set, it renders **above** tier 3 as a prominent off-ramp ("This flag may reflect incomplete OSM coverage of the *economic* pillar rather than a structural condition").

### 8.6 `PolicyLab.tsx` (MODIFY)
On county-select: load the county's capacity record; mount `CapacityCard` and (conditionally) `DivergenceAlert`; **seed lever baselines** from pillar scores (e.g., skills lever pre-set from the education pillar) shown with a *"pre-seeded from infrastructure index — adjust freely"* note and a **reset-to-neutral** control. Seeding is presentation only; the engine still consumes calibrated betas unchanged.

### 8.7 `types.ts` (MODIFY)
Add `InfraLayer`, `CountyCapacity`, `PillarScore`, `DivergenceFlag`, `RankInterval`, mirroring §7's contract.

---

## 9. Delivery increments

The implementation is split into two gated increments to de-risk the lowest-power section (divergence + sensitivity) and surface coverage problems early.

### v1a — Coverage audit + composite + map (Tasks 0–5)
**Task 0 (gate):** Download the four OSM GeoJSON extracts and run a quick per-county feature count. If any pillar returns fewer than 2 features for more than 15 counties, flag it for scope reduction (e.g., collapse health + economic into a single pillar) before investing in the full scoring pipeline. v1a does not proceed until this audit passes.

Once the audit passes:
- `I1_score_counties.py` + unit tests
- `data/raw/osm/README.md`
- `utils/capacity.ts` + tests
- `InfraLayerPanel.tsx`, `CapacityCard.tsx` (radar, percentile, rank interval, peers)
- `RomaniaMap.tsx` map layer + basemap toggle + clustered POI markers
- `PolicyLab.tsx` capacity-card mounting + lever seeding + reset
- `types.ts` additions
- `tsc` clean, Vitest pass, production build

**Deliverable:** a working infrastructure layer and capacity card. No divergence flags yet.

### v1b — Divergence + sensitivity (Tasks 6–8), gated on v1a
Only implemented after v1a ships and the coverage audit confirms that the pillar scores are meaningful enough to support anomaly detection.
- `I2_flag_divergence.py` (residuals + LISA) + unit tests
- `I3_sensitivity.py` (ensemble + rank intervals)
- `I0_build_infra_layer.py` orchestrator integrating all three
- `DivergenceAlert.tsx` + tests
- `structural_hypotheses.yaml` (initial entries for most likely flagged counties)
- Re-run integration; tsc + Vitest + build

**Deliverable:** divergence badges on the map, three-tier alert in PolicyLab, rank intervals in CapacityCard.

---

## 10. Deferred / future work (YAGNI)

| Item | Why deferred |
|---|---|
| Historical accessibility vintages | New ingestion; replaced by recent-window scoping + explicit contemporary-cross-section caveat |
| Full spatial lag/error regression | LISA is the right-sized tool for v1; spatial econometrics is its own project |
| DEA "benefit-of-the-doubt" & AHP weighting | Equal + PCA + the sensitivity ensemble already address the weighting question |
| Live in-UI weight sliders | Overlaps with the I3 ensemble; ship the ensemble first |
| INSSE official NUTS3 infrastructure registers | Cross-validation of OSM coverage; valuable but out of scope for v1 |

---

## 11. Testing & reproducibility

- **Pipeline:** unit tests for denominator normalisation, winsorisation bounds, geometric vs arithmetic aggregation (geometric ≤ arithmetic, equality iff all pillars equal), Cronbach α on a synthetic set, studentized-residual outlier detection, LISA quadrant assignment on a toy contiguity graph, and rank-interval monotonicity. `_sanitize()` reused with its existing tests.
- **Dashboard:** Vitest for `capacity.ts` helpers; component render tests for `CapacityCard` (radar + percentile + rank interval), `DivergenceAlert` (three tiers + off-ramp branch), and the `PolicyLab` seeding/reset path. `tsc` clean; production build succeeds.
- **Reproducibility:** seeded, idempotent, offline; `infra_layer.json` regenerates identically from raw. `_meta.git_sha` records provenance.

---

## 12. Caveats stated in-product & in methodology

- **Temporal:** OSM is a contemporary (2026) snapshot; the divergence analysis relates it to 2019–2023 outcomes and is not longitudinal or causal.
- **MAUP / ecological** (Openshaw, 1984): NUTS3 averages hide within-county heterogeneity; the index characterises counties, not localities.
- **Coverage:** OSM completeness is uneven; the `data_confidence` field and divergence off-ramp exist precisely so a data gap is never read as a structural finding.
- **Index is contestable by design:** equal weights are an assumption; the rank interval and arithmetic/geometric toggle expose how standings depend on that choice.
- **Statistical power:** with n ≈ 42 NUTS3 counties, studentized-residual outlier detection (|t| > 2) will flag roughly 2 counties by chance under the null; LISA on a 42-unit queen contiguity graph is similarly noisy. Divergence flags are **hypothesis-generating**, not confirmatory. Any flagged county should be investigated with richer administrative data before policy inference is drawn.

---

## 13. Literature anchors

- Nardo, Saisana, Saltelli, Tarantola (2008). *Handbook on Constructing Composite Indicators.* OECD/JRC. — composite-indicator workflow.
- Munda (2008). *Social Multicriteria Evaluation for a Sustainable Economy.* — (non-)compensatory aggregation.
- UNDP (2010). *Human Development Report* methodology — geometric-mean adoption.
- Saisana, Saltelli & Tarantola (2005), *JRSS-A* — uncertainty & sensitivity analysis of composite indicators; rank intervals.
- Anselin (1995), *Geographical Analysis* — Local Indicators of Spatial Association (LISA).
- Openshaw (1984) — the Modifiable Areal Unit Problem.
- Cronbach (1951), *Psychometrika* — internal-consistency reliability (α).
