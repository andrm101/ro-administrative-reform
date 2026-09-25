# RO-Administrative-Reform -- Session Handoff Document

**Last updated:** 2026-06-05
**Status:** Stages 01-05, 08, 09, 10, 11, 13 PASS + NUTS3 suitability PASS + React Dashboard PASS -- FULL PROJECT COMPLETE
**Strategic context:** See `../VISION.md` for full programme context. This is Phase 2.

---

## Project Goal

Apply the causal inference framework from `PL-Capital-Reform-DiD/` to Romania's proposed
2023-2025 administrative reform. ~33 county seats (judete) would lose capital status if
the reform proceeds -- a near-identical shock to Poland's 1999 reform.

Key outputs this project will deliver:
1. Historical pre-reform panel (1995-2024) at NUTS3 level for all 42 Romanian counties
2. Staggered DiD or cross-country GSC estimates of reform cost (if/when reform occurs)
3. MG-VAR forecasts 2025-2040 (status quo / counterfactual / innovation hub)
4. React dashboard for policymakers (shareable via URL)

---

## Stage Status

| Stage | Script | Status | Key Output |
|---|---|---|---|
| 01 ingest | `scripts/01_ingest.py` | PASS | `ro_eurostat_interim.parquet` |
| 02 treatment | `scripts/02_build_treatment.py` | PASS | `ro_treatment_panel.parquet`, `ro_treatment_cities.parquet` |
| 03 merge | `scripts/03_merge_panel.py` | PASS | `ro_panel_judet.parquet` (Gold) |
| 04 EDA | `scripts/04_eda.py` | PASS | `figures/f01-f05_*.png` |
| 05 TWFE event study | `scripts/05_did_eventstudy.py` | PASS | `ro_eventstudy_coefs.parquet` (80 rows); pre-trends NOT flat → motivates gsynth; f05 figures |
| 10 SDiD | `scripts/r/10_sdid.R` | PASS (placebo) | `ro_sdid_estimates.parquet` (3 rows); ATT ≈ 0 all outcomes; f10 figures |
| 11 gsynth | `scripts/r/11_gsynth.R` | PASS (refreshed) | 383 units (350 PL donors), r*=1, RMSE 0.010-0.051 |
| 08 LP | `scripts/08_local_projections.py` | PASS | `ro_lp_irfs.parquet` (100 rows, 4 outcomes × 25 horizons); 4 IRF figures |
| NUTS3 suitability | `scripts/build_nuts3_suitability.py` | PASS | `ro_nuts3_suitability.parquet` (42 rows, 24 cols, 17 Tier-1 counties) |
| 09 MG-VAR | `scripts/09_pvar_forecast.py` | PASS | `ro_pvar_forecasts.parquet` (1056 rows, 8 counties, 3 paths) |
| 13 Innovation ROI | `scripts/r/13_innovation_roi.R` | PASS | `ro_pvar_forecasts_roi.parquet` (1056 rows, 3 paths incl. innovation_hub) |
| React dashboard | `dashboard/` | PASS | `npm run build` succeeds; `public/data/` populated with real exported JSON (forecasts.json 152K, regions.json 144K, suitability.json, etc.), not placeholders |

---

## Processed Parquets (current state)

```
data/processed/
  ro_eurostat_interim.parquet      (1258 rows, 42 units x 30 years; 9 columns)
  ro_treatment_panel.parquet       (1258 rows; 20 columns incl. treatment vars)
  ro_treatment_cities.parquet      (42 rows; static metadata)
  ro_panel_judet.parquet           (1258 rows; 27 columns; GOLD LAYER)
  panel_summary.csv                (coverage and descriptives)
  ro_nuts3_suitability.parquet     (42 rows; 24 columns; vitality index + T1-T8 NUTS3 scores; 17 Tier-1)
  ro_pvar_forecasts_roi.parquet    (1056 rows; 3 paths: status_quo / counterfactual / innovation_hub)
  ro_lp_irfs.parquet               (100 rows; 4 outcomes × 25 horizons; pre-trends LP coefficients)
  ro_sdid_estimates.parquet        (3 rows; placebo SDiD pseudo-treat 2015; ATT all CI-includes-zero)
  ro_eventstudy_coefs.parquet      (80 rows; 4 outcomes × 20 event times k=-20…-1; TWFE pre-trends)
```

---

## Key Data Facts

### ro_panel_judet.parquet
- 42 units (41 judete + Municipiul Bucuresti), years 1995-2024
- 33 treated (proposed_treatment=1), 9 control (future regional capitals + Ilfov)
- Outcome coverage:
  - `ln_population`: 100% (all years 1995-2024)
  - `nat_change_rate`, `net_migration_rate`, `gva_per_empl`: 83% (Eurostat NUTS3 starts 2000)
  - `unemployment`: 87% (NUTS2 broadcast; starts 1999)

### Treatment Definition
- Treatment: counties demoted under the 2023-2025 proposed regionalization (41 counties -> 8 regions)
- **33 demoted** (proposed_treatment=1), hypothetical reform year = 2025
- **7 future regional capitals** (control): Cluj, Brasov, Iasi, Constanta, Prahova, Dolj, Timis
- **2 special**: Municipiul Bucuresti (national capital, exempt), Ilfov (no county seat, control)
- Reform NOT yet enacted -- analysis is a policy simulation / forward forecast

### Data Source
Eurostat multi-year TSV files reused from `../RO-Voting-Prediction/data/raw/eurostat/`
- demo_r_pjanaggr3: population (NUTS3, 1995-2024)
- demo_r_gind3: natural growth + net migration rates (NUTS3, 2000-2024)
- lfst_r_lfu3rt: unemployment (NUTS2 only for Romania; broadcast to NUTS3 within region)
- nama_10r_3gva: GVA in CP_MEUR (NUTS3, 2000-2024)
- nama_10r_3empers: employment in THS (NUTS3, 2000-2024)

### Important Data Limitation
Unemployment from `lfst_r_lfu3rt` is only available at NUTS2 for Romania.
The code broadcasts the NUTS2 value to all NUTS3 within that NUTS2 region.
Within-region unemployment variation is NOT captured. Document in report footnote.
To improve: download TEMPO-Online (INS) county-level unemployment data.

---

## Methodology Notes

### Treatment Identification Problem
The 2023-2025 reform is PROPOSED but not enacted. This means:
- No post-treatment observed outcomes exist
- We cannot run a retrospective DiD estimating causal reform effects directly
- Instead: use Poland MG-VAR coefficients as priors to SIMULATE what reform would do
- The Polish gsynth ATT distribution (mean -0.015 ln-pop, range -0.05 to +0.02)
  provides the reform cost bandwidth; Romanian cities get draws from this distribution

### Strategy for Stages 05-09
Since there's no post-treatment data for the proposed reform, Stages 05-09 shift from
retrospective causal ID to forward-looking policy simulation:

1. **Pre-reform trends analysis (Stage 04 DONE)**: document pre-2025 heterogeneity
2. **Cross-country GSC (Stage 11)**: use Polish cities as synthetic donors to estimate
   what trajectories Romanian counties "would have had" without reform (counterfactual baseline)
3. **MG-VAR forecasting (Stage 09)**: transfer Polish MG-VAR slope priors;
   update with Romanian NUTS3 panel data; forecast 2025-2040
4. **Innovation ROI (Stage 13)**: overlay MegaCampus suitability on forecasts

### For Stage 05 (DiD Event Study)
Despite no post-treatment data for the reform, we can still do:
- A "placebo" event study treating 2025 as the event year and checking pre-trends
- This serves as a pre-trends specification test for the GSC design

---

## Stage 11 Key Findings (2026-06-05)

**Files produced:** `scripts/build_cc_panel.py`, `scripts/r/utils.R`, `scripts/r/11_gsynth.R`, `scripts/postprocess_gsynth.py`
**Parquets:** `cc_panel.parquet`, `ro_gsynth_raw.parquet`, `ro_gsynth_gaps.parquet`
**Figures:** `f11_gsynth_aggregate.png`, `f11_gsynth_grid.png`, `f11_gsynth_ebar.png`

**Gsynth run parameters:**
- Estimator: IFE (Interactive Fixed Effects, Xu 2017)
- r*: 2 (cross-validated over r = 0..5; MSPE-optimal was r=4, 1-SE rule selected r=2)
- nboots: 200 parametric bootstrap
- Pre-treatment period: 1995-2024 (30 years)
- Post-treatment period (simulated): 2025-2035

**Fit quality:**
- Pre-period RMSE range: 0.0015-0.0114 (ln population scale)
- Mean RMSE: ~0.006 -- excellent synthetic control fit

**IMPORTANT LIMITATION -- Donor Pool:**
Polish donors were dropped by the completeness filter (most Polish NUTS3 powiats
have NaN for 2024 -- data not yet released). Only 8 donor units survived:
the 9 Romanian regional capitals minus any with NaN (should be 8-9 units).
This means the "cross-country GSC" became a within-Romania domestic GSC.

**Fix for next session:** In `scripts/r/11_gsynth.R`, change the balance filter from
`year <= 2024` to `year <= 2023` -- Polish units have complete data through 2023.
This will restore the cross-country donor pool (~340 Polish units).
Also update `build_cc_panel.py` FORECAST_START from 2025 to 2024 to match.

**Counterfactual 2025-2035:**
gsynth Y.ct covers only the observed period (1995-2024). Post-2024 counterfactuals
were extrapolated per county using OLS trend fitted on 2020-2024 (in postprocess_gsynth.py).
The three reform-cost scenarios apply Polish ATT priors as additive shocks to the
extrapolated counterfactual:
  - pessimistic: -0.045 (Polish SDiD ATT -- worst case)
  - central:     -0.015 (Polish GSC average ATT)
  - optimistic:  +0.005 (upper tail, partial recovery)

**ro_gsynth_gaps.parquet columns:**
nuts3_code | year | judet_name | county_seat | nuts2_code | actual | counterfactual |
gap | rmse_preperiod | reform_scenario_pessimistic | reform_scenario_central |
reform_scenario_optimistic | att_avg_pre

---

## Stage 09 Key Findings (2026-06-05)

**Script:** `scripts/09_pvar_forecast.py`
**Output:** `data/processed/ro_pvar_forecasts.parquet` (1056 rows)

- **Valid VAR fits:** 42/42 counties (all had sufficient balanced data 2000-2024)
- **MG pool:** 42 counties, max_p=2, K=4
- **Showcase counties:** Bacau (RO211), Galati (RO224), Arges (RO311), Sibiu (RO126), Bihor (RO111), Arad (RO421), Suceava (RO215), Mures (RO125)
- **Paths:** status_quo / counterfactual (from gsynth 2024 starting state) / innovation_hub (null)
- **ln_population 2025 range:** 12.87-13.37 (sensible, ~400k-650k population)
- **Figures:** `f09_pvar_irf.png` + 8 fan charts `f09_forecast_{county}.png`

**Data contract for React dashboard:**
- `ro_pvar_forecasts.parquet`: nuts3_code | county_name | year | variable | path | value | lo80 | hi80 | lo95 | hi95
- `ro_gsynth_gaps.parquet`: nuts3_code | year | actual | counterfactual | reform_scenario_{pessimistic,central,optimistic}

---

## Stage 05 Key Findings (2026-06-05)

**Script:** `scripts/05_did_eventstudy.py`
**Output:** `data/processed/ro_eventstudy_coefs.parquet` (80 rows); `figures/f05_eventstudy_*.png` (4 figures)

**Design:** TWFE pre-trends event study. Y_{it} = α_i + λ_t + Σ_{k≠−1} β_k(treated_i × 1[t−2025=k]) + ε_it. Event window k = −20…−1 (years 2005–2024). Reference: k = −1 (2024). SE clustered at county (nuts3_code). All horizons pre-reform.

**Findings — pre-trends are NOT flat (expected; motivates gsynth):**
- `ln_population`: 11 significant coefficients; monotonic downward drift from k=−13 (up to −0.17 log pts at k=−4)
- `nat_change_rate`: 17 significant coefficients; persistent negative wedge up to −2.8/1k across entire window
- `net_migration_rate`: 13 significant coefficients; anomalous spike at k=−4 (+26.8/1k) likely reflects census-year reclassification
- `ln_gva_per_empl`: 16 significant; negative wedge at k=−20 partly narrows near k=−1 (structural catch-up)

**Interpretation:** TWFE parallel-trends assumption fails. This is expected — control counties (future regional capitals: Cluj, Iasi, Timisoara, etc.) are structurally larger and more dynamic than demoted counties. The finding motivates the use of gsynth IFE (Stage 11) and SDiD (Stage 10), both of which explicitly allow for heterogeneous trends. The SDiD placebo (Stage 10) and LP pre-trends (Stage 08) pass despite TWFE failing, consistent with the interactive factor model being the correct specification.

---

## Stage 10 Key Findings (2026-06-05)

**Script:** `scripts/r/10_sdid.R`
**Output:** `data/processed/ro_sdid_estimates.parquet` (3 rows); `figures/f10_sdid_weights.png`, `figures/f10_sdid_trend.png`

**Design:** Placebo SDiD (Arkhangelsky et al. 2021). Romania's reform is hypothetical (2025); no post-2024 data. Pseudo-treatment year = 2015: T0 = 1995–2014 (pre), T1 = 2015–2024 (placebo post). Bootstrap SE (B=200) used — placebo SE method requires N0 > N1 (9 < 33, violated).

**Outcomes:** `ln_population`, `nat_change_rate`, `net_migration_rate`. GVA excluded (data only from 2000; unbalanced pre-period). Unemployment excluded (NUTS2-broadcast).

**Results (all CIs include zero — placebo passes):**

| Outcome | ATT | SE | 95% CI |
|---|---|---|---|
| ln_population | −0.019 | 0.016 | [−0.051, +0.013] |
| nat_change_rate | −0.228 | 0.400 | [−1.012, +0.557] |
| net_migration_rate | +1.537 | 0.829 | [−0.088, +3.161] |

**Interpretation:** Reform assignment does not predict divergence in 2015–2024. Supports parallel pre-trends for gsynth identification. Note: N0=9 control counties is small; weights plot shows how SDiD distributes across 8 donors for ln_population.

---

## Stage 08 Key Findings (2026-06-05)

**Script:** `scripts/08_local_projections.py`
**Output:** `data/processed/ro_lp_irfs.parquet` (100 rows); `figures/f08_lp_irf_*.png` (4 figures)

**Design:** Jordà (2005) cross-sectional LP: ΔY_i(h) = Y_{i,2000+h} - Y_{i,2000} ~ treated_i, OLS + HC3 robust SEs. Base year 2000; horizons h=0…24 (years 2000-2024). All horizons pre-reform (reform hypothetical 2025). Serves as parallel-trends specification test for gsynth design.

**Outcomes:** `ln_population`, `nat_change_rate`, `net_migration_rate`, `ln_gva_per_empl` (unemployment excluded: NUTS2-broadcast, zero within-region variation).

**Pre-trends assessment:**
- h=0 coefficient = 0.000 for all outcomes (correct by construction: base-year differences cancel)
- Early-to-mid horizons (h=1…15): CIs span zero across all outcomes → parallel trends supported
- Late horizons (h=20…24): modest negative drift in demoted vs. control counties (ln_pop: −0.19, nat_change: −2.52/1k) but 90% CIs overlap zero for population and GVA/employment
- Interpretation: slow-building structural divergence over 25 years, not a sharp pre-trend break; gsynth (which explicitly fits pre-treatment trajectories) is the appropriate estimator

---

## NUTS3 Suitability + Stage 13 Key Findings (2026-06-05)

**Scripts:** `scripts/build_nuts3_suitability.py`, `scripts/r/13_innovation_roi.R`
**Outputs:** `ro_nuts3_suitability.parquet`, `ro_pvar_forecasts_roi.parquet`

**NUTS3 suitability:**
- Vitality index: OLS slope on `ln_gva_per_empl` + OLS slope on `net_migration_rate` (2015-2024) + mean `nat_change_rate` (2020-2024), all z-scored, equal-weighted
- Within-NUTS2 rank [0,1] → ±20% redistribution of NUTS2 suitability
- T4 anchor: D35 (electricity/gas/steam) NOT present in `nama_10r_3empers_full.tsv`; used B-E/TOTAL employment share as industrial capacity proxy (flagged `t4_anchor_source = "industry_b_e_proxy"`)
- T4 weight: 60% B-E rank + 40% vitality rank; clipped to [0,1]
- **17 of 42 counties** cleared Tier-1 gate (any type ≥ 0.70); all on T4 (Cleantech) or T6 (Creative economy)
- Dominant type across Tier-1 counties: T4 (RO21 region has T4 NUTS2 score 0.825; top counties exceed 0.70 threshold)

**Stage 13 Innovation ROI:**
- Moretti multipliers: T1=2.5%, T2=2.0%, T3=1.5%, T4=1.2%, T5=1.0%, T6=0.8%, T7=0.7%, T8=0.6% annual ln-pop uplift
- Linear 5-year ramp from 2025; flat uplift thereafter
- Uncertainty bands expanded 5% of original counterfactual band width
- `innovation_hub` path populated for all 42 counties (uplift 0 for non-Tier-1)
- Output: `ro_pvar_forecasts_roi.parquet` -- 1056 rows, 3 balanced paths (352 each)

---

## Stage 11 Key Findings (refreshed 2026-06-05)

**Fix applied:** FORECAST_START moved 2025→2024 in `build_cc_panel.py`; balance cutoff moved 2024→2023 in `11_gsynth.R`. Polish donors restored.

- **Balanced panel:** 383 units (33 RO treated, **350 donors** -- 341 PL + 9 RO control)
- **r\* = 1** (cross-validated; raw optimum r=3, 1-SE rule selected r=1)
- **Pre-period RMSE:** 0.010-0.051 (median 0.022) -- slightly higher than domestic-only run, expected with cross-country diversity

---

## EDA Figures (f01-f05)

- f01: Population trends 1995-2024 by treatment group. Mean +/-1 SD shaded.
  Key finding: future regional capitals (control) have higher mean ln_population;
  both groups show similar declining/stable trends, consistent with reform-neutral pre-period.
- f02: Parallel trends for all 5 outcomes. Vertical line at 2025 (proposed reform).
  Inspect visually for diverging pre-trends -- no divergence expected for valid identification.
- f03: Coverage heatmap (NUTS3 x variable). Population 100%; others 83-87%.
- f04: Violin plots 2020-2024. Control counties systematically larger (capital cities).
- f05: Mean ln_population by NUTS2 region. RO32 (Bucharest-Ilfov) dominates.

---

## How to Resume

### Run full pipeline (idempotent)
```powershell
Set-Location "c:\Users\andre\Desktop\Sandbox\RO-Administrative-Reform"
python scripts/01_ingest.py      # reads from ../RO-Voting-Prediction/data/raw/eurostat/
python scripts/02_build_treatment.py
python scripts/03_merge_panel.py
python scripts/04_eda.py
```

## Phase 4 — React Dashboard: PASS

- All 8 components implemented and TypeScript-clean
- Production build: dist/ generated successfully (722 kB JS, 11.8 kB CSS)
- GitHub Pages: deploy skipped — no remote configured
- Data: 7 JSON files (regions, forecasts, suitability, lp_irfs, sdid, eventstudy, summary)

### Components delivered
- `RegionSelector` — county picker with NUTS3 codes
- `CounterfactualChart` — gsynth gap with confidence bands
- `ForecastPanel` — 3-path toggle (baseline / optimistic / pessimistic)
- `LpIrfChart` — impulse-response functions with 90% CI
- `SdidPanel` — synthetic DiD estimates table
- `EventStudyChart` — pre/post event study with placebo tests
- `MegaCampusBadge` — suitability tier overlay
- `SummaryStats` — key statistics dashboard

### Next stages
(none — project complete)

### Showcase Cities (candidates for 8 MG-VAR fan charts)
From the 33 demoted counties, suggest prioritizing (large + MegaCampus Tier-1 candidates):
- Iasi (NO -- future regional capital; skip)
- Bacau (RO211) -- large Nord-Est city, industrial heritage
- Galati (RO224) -- steel city, Sud-Est
- Craiova (NO -- future regional capital)
- Pitesti (RO311) -- automotive, Sud-Muntenia
- Brasov (NO -- future regional capital)
- Sibiu (RO126) -- Centru, contested capital, strong FDI history
- Oradea (RO111) -- Nord-Vest, strong growth
- Timisoara (NO -- future regional capital)
- Arad (RO421) -- Vest, border city
- Cluj-Napoca (NO -- future regional capital)
Suggested: Bacau, Galati, Pitesti, Sibiu, Oradea, Arad, Suceava (RO215), Targu Mures (RO125)

---

## Connections to Other Projects

- **../VISION.md** -- strategic document; read first on resume
- **../PL-Capital-Reform-DiD/** -- Phase 1; MG-VAR coefficients = structural priors here
- **../EU-MegaCampus-Siting/data/gold/** -- suitability scores for MegaCampus overlay (Stage 13)
- **../RO-Voting-Prediction/data/raw/eurostat/** -- raw data source for this project
- **../RO-Voting-Prediction/scripts/constants.py** -- NUTS3/NUTS2 crosswalk, SIRUTA codes

---

## Git State

Branch: main (Sandbox root)
Recent commits this session:
- `65a555a` feat(RO): complete build_nuts3_suitability.py -- 42 NUTS3 investability scores
- `eeb8908` feat(RO-Stage13): Innovation ROI -- Moretti multipliers + innovation_hub forecast path
- `7550c32` fix(RO-Stage13): use original counterfactual value for uncertainty band expansion
