# MegaCampus NUTS3 Investability Score — Design Spec

**Date:** 2026-06-05
**Project:** RO-Administrative-Reform
**Stage:** Pre-Stage-13 (feeds 13_innovation_roi.R)
**Status:** Approved — ready for implementation plan

---

## Problem Statement

The EU-MegaCampus-Siting Gold layer (`suitability_scores.parquet`) operates at NUTS2 level (8 Romanian regions). Stage 13 Innovation ROI needs per-county (NUTS3) investability flags to assign ecosystem-type multipliers to 33 demoted Romanian counties. Two structural problems block direct use:

1. **Granularity mismatch**: NUTS2 → NUTS3 broadcast assigns identical scores to all counties within a region (Cluj and Bistrița-Năsăud both get the same T1 score, despite structural differences).

2. **T4 broadcast inflation**: T4 (Cleantech) uses `renewable_energy_share_pct` at national level, eliminating all within-Romania NUTS2 differentiation. All Romanian counties appear as T4 candidates, which is non-informative for investment targeting.

---

## Design

### Output

One new file: `data/processed/ro_nuts3_suitability.parquet` — 42 rows (one per NUTS3 county).

### Step 1: Vitality Index

Computed from `ro_panel_judet.parquet`, years 2015-2024. Three components, all using **trends not levels** to avoid rewarding already-developed metropoles.

| Component | Variable | Method |
|---|---|---|
| Economic dynamism | `ln_gva_per_empl` | OLS slope on year (2015-2024) → β₁ |
| Demographic retention | `net_migration_rate` | OLS slope on year (2015-2024) → β₂ |
| Biological vitality | `nat_change_rate` | Mean 2020-2024 |

Each z-scored across all 42 counties. Equal weights:
```
V[i] = (z_gva_growth[i] + z_migration_trend[i] + z_nat_change[i]) / 3
```

**Equity principle encoded:** A catching-up peripheral county with improving migration retention scores higher than a stagnant wealthy county. Bucharest-Ilfov (RO32) does not automatically dominate.

**Within-region rank:** For each NUTS2 region r, rank counties by V[i] and normalize to [0,1]:
```
vitality_rank[i] = (rank_within_region(V[i]) - 1) / max(1, n_counties_in_region - 1)
```
Single-county regions default to 0.5 (neutral, no redistribution).

---

### Step 2: General NUTS3 Redistribution Formula

For all types T1–T8 (except T4, see Step 3):
```
suitability_T{k}_NUTS3[i] = suitability_T{k}_NUTS2[r] * (1 + 0.4 * (vitality_rank[i] - 0.5))
```

- `rank = 1.0` → ×1.20 (top county: 20% uplift over NUTS2)
- `rank = 0.5` → ×1.00 (median county: unchanged)
- `rank = 0.0` → ×0.80 (bottom county: 20% discount)

**Properties:**
- Preserves NUTS2 regional mean exactly (symmetric redistribution)
- Maximum deviation ±20% — conservative enough to describe as within-region disaggregation
- Allows catching-up counties to break through a threshold the NUTS2 score alone would not reach

---

### Step 3: T4 Debroadcasting via D35 Employment Anchor

**Theoretical basis:** Cleantech localization literature (Boschma 2017; Neffke et al. 2011) distinguishes *resource presence* (national renewable share) from *absorptive capacity* (industrial base capable of converting resources into economic activity). The country-level renewable share captures the former but says nothing about the latter within Romania.

**Substitution:** Replace the national-level renewable share contribution with D35 employment share at NUTS3 — workers in electricity, gas and steam supply as a fraction of total employment — from `nama_10r_3empers_full.tsv` (already downloaded in `RO-Voting-Prediction/data/raw/eurostat/`).

```
d35_emp_share[i] = employment_D35_NUTS3[i] / employment_TOTAL_NUTS3[i]
d35_rank[i]      = rank_within_region(d35_emp_share[i]), normalized to [0,1]
```

**T4-specific composite weight:**
```
T4_weight[i] = 0.4 * vitality_rank[i] + 0.6 * d35_rank[i]
```

The 60% weight on D35 is justified: T4 is sector-specific, so the sector-level industrial presence proxy should dominate over the general vitality measure.

**T4 adjusted suitability:**
```
suitability_T4_NUTS3[i] = suitability_T4_NUTS2[r] * (1 + 0.4 * (T4_weight[i] - 0.5))
```

**Fallback rule:** If D35 employment is zero or missing for a county, set `T4_weight[i] = vitality_rank[i]` and flag `t4_anchor_source = "vitality_fallback"`. Report footnote: NUTS3 D35 employment data is sparse in rural counties with no major energy infrastructure.

**Expected effect:** Gorj (RO412, lignite/energy), Hunedoara (RO423, hydro/industrial energy), and Constanța (RO223, Black Sea wind + port energy) gain T4 ground relative to purely agricultural counties in the same NUTS2 — directionally correct signal.

---

### Step 4: Threshold Gate

```
tier1_gate[i] = any(suitability_T{k}_NUTS3[i] >= 0.70 for k in {1..8})
```

where `suitability_T4_NUTS3` uses the D35-adjusted score, not the raw T4.

```
tier1_types[i] = "|".join([f"T{k}" for k in 1..8 if suitability_T{k}_NUTS3[i] >= 0.70])
```

Counties with `tier1_gate = False` receive reform-cost-only treatment in Stage 13 (no innovation premium). Counties that clear the gate get a type-specific Moretti-style agglomeration multiplier.

---

## Output Schema

`data/processed/ro_nuts3_suitability.parquet` — 42 rows × ~25 columns:

| Column | Type | Description |
|---|---|---|
| `nuts3_code` | str | NUTS3 code (e.g. RO211) |
| `judet_name` | str | County name |
| `county_seat` | str | Main city |
| `nuts2_code` | str | Parent NUTS2 region |
| `vitality_gva_growth` | float | z-scored OLS slope ln_gva_per_empl, 2015-2024 |
| `vitality_migration_trend` | float | z-scored OLS slope net_migration_rate, 2015-2024 |
| `vitality_nat_change` | float | z-scored mean nat_change_rate, 2020-2024 |
| `vitality_index` | float | Equal-weight composite |
| `vitality_rank_within_region` | float | [0,1] within NUTS2 |
| `d35_emp_share` | float | D35 / TOTAL employment (latest available year) |
| `d35_rank_within_region` | float | [0,1] within NUTS2; NaN if fallback used |
| `t4_anchor_source` | str | `"d35_employment"` or `"vitality_fallback"` |
| `suitability_T1`…`suitability_T8` | float | Downscaled NUTS3 scores (general formula) |
| `suitability_T4_adjusted` | float | T4 with D35 60% / vitality 40% blend |
| `tier1_gate` | bool | True if any type ≥ 0.70 |
| `tier1_types` | str | Pipe-separated, e.g. `"T4\|T6"` |

---

## Inputs

| File | Location | Usage |
|---|---|---|
| `suitability_scores.parquet` | `../EU-MegaCampus-Siting/data/gold/` | NUTS2 T1-T8 baseline scores |
| `ro_panel_judet.parquet` | `data/processed/` | Vitality components |
| `ro_treatment_cities.parquet` | `data/processed/` | County metadata |
| `nama_10r_3empers_full.tsv` | `../RO-Voting-Prediction/data/raw/eurostat/` | D35 employment at NUTS3 |

---

## New File

| File | Action |
|---|---|
| `scripts/build_nuts3_suitability.py` | CREATE |

---

## Downstream Connections

**Stage 13 ROI** (`scripts/r/13_innovation_roi.R`):
- Reads `tier1_gate` and `tier1_types` per county
- `tier1_gate = False` → reform cost only, `innovation_hub` path = null
- `tier1_gate = True` → apply type-specific Moretti agglomeration multiplier to `counterfactual` path from `ro_gsynth_gaps.parquet`, producing the `innovation_hub` forecast path in `ro_pvar_forecasts.parquet`

**React dashboard**:
- `MegaCampusBadge` component: renders per-county ecosystem type badges from `tier1_types`
- `LayerSwitcher`: adds suitability index choropleth layer alongside reform-cost layer

---

## Implementation Notes

- Use `scipy.stats.linregress` for OLS slopes (already a dependency)
- D35 employment: filter `nama_10r_3empers_full.tsv` on `wstatus=EMP`, `nace_r2=D`, `unit=THS`; take most recent non-missing year per NUTS3
- The NUTS3→NUTS2 crosswalk is in `scripts/constants.py` of `RO-Voting-Prediction` (already imported in other scripts via hardcoded dict)
- Clip suitability scores to [0, 1] after redistribution (the ×1.20 uplift on a high base score could theoretically exceed 1.0)
- Seed: `np.random.seed(42)` (no randomness in this script, but document for reproducibility audit)
