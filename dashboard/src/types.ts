// ── Data shapes matching the 7 JSON files ────────────────────────────────────

export interface CounterfactualPoint {
  year: number;
  actual: number | null;
  counterfactual: number | null;
  gap: number | null;
}

export interface RegionData {
  nuts3_code: string;
  judet_name: string;
  county_seat: string;
  nuts2_code: string;
  att_avg_pre: number | null;
  reform_cost_pct: number | null;
  reform_scenario_pessimistic: number | null;
  reform_scenario_central: number | null;
  reform_scenario_optimistic: number | null;
  vitality_index: number | null;
  tier1_gate: boolean;
  tier1_types: string;
  innovation_uplift_pct_2040: number | null;
  counterfactualSeries: CounterfactualPoint[];
}

export interface ForecastPoint {
  year: number;
  value: number | null;
  lo80: number | null;
  hi80: number | null;
  lo95: number | null;
  hi95: number | null;
}

export interface ForecastCounty {
  nuts3_code: string;
  county_name: string;
  forecasts: Record<string, Record<string, ForecastPoint[]>>;
}

export interface SuitabilityData {
  nuts3_code: string;
  judet_name: string;
  county_seat: string;
  nuts2_code: string;
  vitality_index: number | null;
  vitality_rank_within_region: number | null;
  suitability_T1: number;
  suitability_T2: number;
  suitability_T3: number;
  suitability_T4: number;
  suitability_T5: number;
  suitability_T6: number;
  suitability_T7: number;
  suitability_T8: number;
  suitability_T4_adjusted: number;
  tier1_gate: boolean;
  tier1_types: string;
  t4_anchor_source: string;
}

export interface LpIrf {
  outcome: string;
  horizon: number;
  coef: number | null;
  se: number | null;
  ci_lo_90: number | null;
  ci_hi_90: number | null;
  ci_lo_95: number | null;
  ci_hi_95: number | null;
  nobs: number;
}

export interface SdidEstimate {
  outcome: string;
  estimator: string;
  att: number | null;
  se: number | null;
  ci_lo: number | null;
  ci_hi: number | null;
  n_units: number;
  n_years: number;
  pseudo_treat_year: number;
}

export interface EventStudyCoef {
  outcome: string;
  event_time: number;
  coef: number | null;
  se: number | null;
  ci_lo: number | null;
  ci_hi: number | null;
}

export interface Summary {
  n_demoted: number;
  n_tier1: number;
  reform_year: number;
  sdid_att_ln_pop: number | null;
  sdid_pop_loss_pct: number | null;
  gsc_avg_att: number | null;
  data_note: string;
}

export type LayerType = 'reform_cost' | 'suitability' | 'roi' | 'region' | 'policy_lab';

export interface RegionGroup {
  nuts2Code: string;
  hubNuts3: string | null;
  satellites: string[];
}

export interface DashboardData {
  regions: RegionData[];
  regionsByCode: Record<string, RegionData>;
  forecasts: ForecastCounty[];
  forecastsByCode: Record<string, ForecastCounty>;
  suitability: SuitabilityData[];
  suitabilityByCode: Record<string, SuitabilityData>;
  lpIrfs: LpIrf[];
  sdid: SdidEstimate[];
  eventstudy: EventStudyCoef[];
  summary: Summary;
  elasticities: Elasticities;
  primitivesByCode: Record<string, CountyPrimitive>;
}

// ── Scenario engine ──────────────────────────────────────────────────────────

export interface LeverVector {
  rho: number;     // redistribution share of hub tax base [0,1]
  kappa: number;   // cohesion injection €/capita/yr [0,500]
  gov: number;     // gov-efficiency gain, index [0,1]
  mu: number;      // migration-retention subsidy €/capita/yr [0,400]
  iota: number;    // MegaCampus intensity, multiplier [0,2]
  conn: number;    // connectivity index [0,1]
  family: number;  // pronatalist transfer €/capita/yr [0,600]
  skills: number;  // skills investment, % of GVA/yr [0,5]
  offset: number;  // reform-transition offset [0,1]
}

export const DEFAULT_LEVERS: LeverVector = {
  rho: 0, kappa: 0, gov: 0, mu: 0, iota: 0, conn: 0, family: 0, skills: 0, offset: 0,
};

/** [min, max] UI bounds per lever, keyed by LeverVector field. */
export const LEVER_BOUNDS: Record<keyof LeverVector, [number, number]> = {
  rho: [0, 1], kappa: [0, 500], gov: [0, 1], mu: [0, 400], iota: [0, 2],
  conn: [0, 1], family: [0, 600], skills: [0, 5], offset: [0, 1],
};

export interface Elasticity {
  value: number;
  se: number;
  id_strategy: string;
  source: string;
  support: [number, number];
  provenance?: ElasticityProvenance;
}

export interface Elasticities {
  beta_gov: Elasticity;
  beta_K_hub: Elasticity;
  beta_K_sat: Elasticity;
  beta_mig: Elasticity;
  beta_fert: Elasticity;
  beta_edu: Elasticity;
  gamma: Elasticity;     // connectivity absorption modulator
  lambda: Elasticity;    // migration conservation (hub→satellite)
  tau: number;           // effective tax-retention rate (assumption)
  delta: number;         // annual capital depreciation (assumption)
  discount_rate: number; // social discount rate
  moretti: Record<string, number>; // tier (e.g. "T4") → annual ln-pop multiplier
  regime_test?: RegimeTest;
  diagnostics?: CalibrationDiagnostics;
  provisional: boolean;  // true until Plan 2 calibration replaces v0 priors
}

export interface CountyPrimitive {
  nuts3_code: string;
  nuts2_code: string;
  role: 'hub' | 'satellite';
  gva_pc: number;         // GVA per capita, EUR, 2025
  population: number;     // persons, 2025
  vitality_index: number;
  tier1_gate: boolean;
  moretti_tier: string;   // dominant suitability tier, e.g. "T4"
}

export interface FiscalPrimitives {
  counties: CountyPrimitive[];
}

export interface ScenarioPoint {
  year: number;
  baseline: number;
  scenario: number;
  lo: number;
  hi: number;
}

export interface ScenarioResult {
  perCounty: Record<string, ScenarioPoint[]>; // nuts3 → growth (ln_gva_per_empl) path
  perCountyPop: Record<string, ScenarioPoint[]>; // nuts3 → ln_population path
  hdiProxy: Record<string, { year: number; value: number }[]>; // nuts3 → HDI proxy
  regionTotal: ScenarioPoint[];                // population-weighted growth aggregate
  regime: 'agglomeration' | 'convergence' | 'neutral';
  regimeMargin: number;                        // Σβ_sat·a·w − β_hub
  cost2040: number;                            // discounted programme cost (EUR)
  hubOpportunityCostPct: number;               // hub growth pts lost at 2040
}

// ── Calibration provenance ────────────────────────────────────────────────────

export interface ElasticityProvenance {
  method: string;
  n_obs?: number;
  r2?: number;
  half_life_years?: number;
  boot_ci_90?: [number, number];
  boot_se?: number;
  citation?: string;
  estimated_at?: string;
  git_sha?: string;
}

export interface RegimeTest {
  p_value: number;
  stat: number;
  df: number;
}

export interface CalibrationDiagnostics {
  ips_stat: number;
  ips_pvalue: number;
  conclusion: string;
  lambda_comovement: number;
  beta_gov_sdid_crosscheck: {
    lpirf: number;
    sdid: number | null;
    ratio: number | null;
    agree: boolean;
  };
}

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
