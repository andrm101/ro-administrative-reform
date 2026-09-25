import type {
  CountyPrimitive, Elasticities, ForecastCounty, LeverVector, RegionGroup,
  ScenarioPoint, ScenarioResult,
} from '../types';
import { structuralRamp, capitalFlows, perpetualInventory, regimeSign } from './fiscal';
import { computeHDI } from './hdi';
import { programmeCost } from './cost';

const OUTCOME_GVA = 'ln_gva_per_empl';
const OUTCOME_POP = 'ln_population';
const BASE_PATH = 'status_quo';

// National baseline education index for the interim HDI (UNDP RO ~0.75); skills lever adds to it.
const EDU_BASELINE = 0.75;
const EDU_SKILLS_GAIN = 0.02; // index points per cumulative %GVA of skills investment

function baselinePath(county: ForecastCounty | undefined, outcome: string): { year: number; value: number; lo80: number; hi80: number }[] {
  const p = county?.forecasts?.[outcome]?.[BASE_PATH] ?? [];
  return p.map((pt) => ({ year: pt.year, value: pt.value ?? 0, lo80: pt.lo80 ?? pt.value ?? 0, hi80: pt.hi80 ?? pt.value ?? 0 }));
}

/** Core overlay: returns scenario-adjusted growth + population paths, HDI, regime, cost. */
export function applyScenario(
  group: RegionGroup,
  levers: LeverVector,
  coeffs: Elasticities,
  primitives: Map<string, CountyPrimitive>,
  baseline: Record<string, ForecastCounty>,
): ScenarioResult {
  const hub = group.hubNuts3 ? primitives.get(group.hubNuts3) ?? null : null;
  const satellites = group.satellites.map((n) => primitives.get(n)).filter((s): s is CountyPrimitive => !!s);
  const members = [...(hub ? [hub] : []), ...satellites];

  // Year axis from the first available baseline path.
  const anyCounty = baseline[members[0]?.nuts3_code ?? ''];
  const years = baselinePath(anyCounty, OUTCOME_GVA).map((p) => p.year);

  const flows = capitalFlows(hub, satellites, levers, coeffs);
  const a = coeffs.gamma.value + levers.conn;

  // Migration conservation: hub loses λ × Σ satellite migration gains.
  const satMigGain = coeffs.beta_mig.value * levers.mu; // per satellite, rate /1000
  const hubMigDrain = coeffs.lambda.value * satellites.length * satMigGain;

  const perCounty: Record<string, ScenarioPoint[]> = {};
  const perCountyPop: Record<string, ScenarioPoint[]> = {};
  const hdiProxy: Record<string, { year: number; value: number }[]> = {};

  for (const c of members) {
    const isHub = c.role === 'hub';
    const capFlow = isHub ? flows.hubFraction : flows.satFraction.get(c.nuts3_code) ?? 0;
    const betaK = isHub ? coeffs.beta_K_hub.value : coeffs.beta_K_sat.value * a;
    const capStock = perpetualInventory(capFlow, years, coeffs.delta);
    const skillsStock = perpetualInventory(levers.skills / 100, years, coeffs.delta); // %GVA → fraction

    const gvaBase = baselinePath(baseline[c.nuts3_code], OUTCOME_GVA);
    const popBase = baselinePath(baseline[c.nuts3_code], OUTCOME_POP);

    // ── Channel 1: productivity (ln_gva_per_empl) ──
    const growth: ScenarioPoint[] = gvaBase.map((pt) => {
      const phi = structuralRamp(pt.year);
      const structural = phi * (coeffs.beta_gov.value * levers.gov + levers.iota * (coeffs.moretti[c.moretti_tier] ?? 0) * (c.tier1_gate ? 1 : 0));
      const flow = coeffs.beta_edu.value * (skillsStock.get(pt.year) ?? 0) + betaK * (capStock.get(pt.year) ?? 0);
      const delta = structural + flow;
      // Band from the dominant β SE (delta method, first order).
      const seScale = Math.abs(betaK) > 0 ? coeffs.beta_K_sat.se / Math.max(coeffs.beta_K_sat.value, 1e-6) : 0.2;
      const band = Math.abs(delta) * seScale;
      return { year: pt.year, baseline: pt.value, scenario: pt.value + delta, lo: pt.value + delta - band, hi: pt.value + delta + band };
    });
    perCounty[c.nuts3_code] = growth;

    // ── Channel 2: demography (ln_population) ──
    let cum = 0;
    const pop: ScenarioPoint[] = popBase.map((pt) => {
      const phi = structuralRamp(pt.year);
      const dNat = phi * coeffs.beta_fert.value * levers.family;
      const dMig = phi * (isHub ? -hubMigDrain : coeffs.beta_mig.value * levers.mu);
      cum += (dNat + dMig) / 1000; // Δln P ≈ Σ rate/1000
      const band = Math.abs(cum) * 0.2;
      return { year: pt.year, baseline: pt.value, scenario: pt.value + cum, lo: pt.value + cum - band, hi: pt.value + cum + band };
    });
    perCountyPop[c.nuts3_code] = pop;

    // ── Channel 3 mitigation is applied to reform-cost elsewhere; HDI from scenario outcomes ──
    hdiProxy[c.nuts3_code] = growth.map((g) => ({
      year: g.year,
      value: computeHDI({
        lnGvaPc: g.scenario,
        vitality: c.vitality_index,
        eduIndex: EDU_BASELINE + EDU_SKILLS_GAIN * (skillsStock.get(g.year) ?? 0),
      }),
    }));
  }

  // Region aggregate: population-weighted growth across members.
  const totalPop = members.reduce((a2, m) => a2 + m.population, 0) || 1;
  const regionTotal: ScenarioPoint[] = years.map((year, i) => {
    let base = 0, scen = 0;
    for (const m of members) {
      const w = m.population / totalPop;
      base += w * (perCounty[m.nuts3_code][i]?.baseline ?? 0);
      scen += w * (perCounty[m.nuts3_code][i]?.scenario ?? 0);
    }
    return { year, baseline: base, scenario: scen, lo: scen, hi: scen };
  });

  const { regime, margin } = regimeSign(hub, satellites, levers, coeffs);
  const cost2040 = programmeCost(hub, satellites, levers, years, coeffs.discount_rate);
  const hubArr = hub ? perCounty[hub.nuts3_code] : undefined;
  const hubGrowth = hubArr ? hubArr[hubArr.length - 1] : undefined;
  const hubOpportunityCostPct = hubGrowth ? (hubGrowth.scenario - hubGrowth.baseline) * 100 : 0;

  return { perCounty, perCountyPop, hdiProxy, regionTotal, regime, regimeMargin: margin, cost2040, hubOpportunityCostPct };
}
