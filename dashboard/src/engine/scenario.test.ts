import { describe, it, expect } from 'vitest';
import { applyScenario } from './scenario';
import type {
  CountyPrimitive, Elasticities, ForecastCounty, LeverVector, RegionGroup,
} from '../types';
import { DEFAULT_LEVERS } from '../types';

function mk(value: number): Elasticities['beta_gov'] {
  return { value, se: value * 0.2, id_strategy: 't', source: 't', support: [0, 2] };
}
const coeffs: Elasticities = {
  beta_gov: mk(0.04), beta_K_hub: mk(0.10), beta_K_sat: mk(0.25),
  beta_mig: mk(0.5), beta_fert: mk(0.3), beta_edu: mk(0.02),
  gamma: mk(0.3), lambda: mk(0.4),
  tau: 0.2, delta: 0.05, discount_rate: 0.03,
  moretti: { T4: 0.012, T6: 0.008 }, provisional: true,
};

const years = [2025, 2026, 2027, 2028, 2029, 2030];
function path(base: number) {
  return years.map((year, i) => ({
    year, value: base + i * 0.001, lo80: base, hi80: base, lo95: base, hi95: base,
  }));
}
function county(code: string): ForecastCounty {
  return {
    nuts3_code: code, county_name: code,
    forecasts: {
      ln_gva_per_empl: { status_quo: path(3.0), innovation_hub: path(3.0), counterfactual: path(3.0) },
      ln_population: { status_quo: path(13.0), innovation_hub: path(13.0), counterfactual: path(13.0) },
    },
  };
}

const hub: CountyPrimitive = {
  nuts3_code: 'H', nuts2_code: 'RO11', role: 'hub',
  gva_pc: 20000, population: 300000, vitality_index: 1, tier1_gate: true, moretti_tier: 'T4',
};
const sat: CountyPrimitive = {
  nuts3_code: 'S', nuts2_code: 'RO11', role: 'satellite',
  gva_pc: 10000, population: 200000, vitality_index: -1, tier1_gate: true, moretti_tier: 'T4',
};
const group: RegionGroup = { nuts2Code: 'RO11', hubNuts3: 'H', satellites: ['S'] };
const primitives = new Map<string, CountyPrimitive>([['H', hub], ['S', sat]]);
const baseline = { H: county('H'), S: county('S') };

describe('applyScenario — consistency anchors', () => {
  it('all-zero levers reproduce the status_quo baseline (identity)', () => {
    const r = applyScenario(group, DEFAULT_LEVERS, coeffs, primitives, baseline);
    for (const p of r.perCounty['S']) {
      expect(p.scenario).toBeCloseTo(p.baseline, 9);
    }
  });
  it('a positive migration subsidy raises satellite population vs baseline (monotonic)', () => {
    const levers: LeverVector = { ...DEFAULT_LEVERS, mu: 200 };
    const r = applyScenario(group, levers, coeffs, primitives, baseline);
    const last = r.perCountyPop['S'].at(-1)!;
    expect(last.scenario).toBeGreaterThan(last.baseline);
  });
  it('migration conservation pulls hub population down when satellites are subsidized', () => {
    const levers: LeverVector = { ...DEFAULT_LEVERS, mu: 200 };
    const r = applyScenario(group, levers, coeffs, primitives, baseline);
    const last = r.perCountyPop['H'].at(-1)!;
    expect(last.scenario).toBeLessThan(last.baseline);
  });
  it('reports a regime and a finite cost', () => {
    const r2 = applyScenario(group, { ...DEFAULT_LEVERS, kappa: 100 }, coeffs, primitives, baseline);
    expect(['agglomeration', 'convergence', 'neutral']).toContain(r2.regime);
    expect(r2.cost2040).toBeGreaterThan(0);
  });
});
