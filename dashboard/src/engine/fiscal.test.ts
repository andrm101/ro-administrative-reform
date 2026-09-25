import { describe, it, expect } from 'vitest';
import { structuralRamp, needWeights, capitalFlows, perpetualInventory, regimeSign } from './fiscal';
import type { CountyPrimitive, LeverVector, Elasticities } from '../types';
import { DEFAULT_LEVERS } from '../types';

const hub: CountyPrimitive = {
  nuts3_code: 'RO_HUB', nuts2_code: 'RO11', role: 'hub',
  gva_pc: 20000, population: 300000, vitality_index: 1.0, tier1_gate: true, moretti_tier: 'T4',
};
const satA: CountyPrimitive = {
  nuts3_code: 'RO_A', nuts2_code: 'RO11', role: 'satellite',
  gva_pc: 10000, population: 200000, vitality_index: -1.0, tier1_gate: false, moretti_tier: 'T6',
};
const satB: CountyPrimitive = {
  nuts3_code: 'RO_B', nuts2_code: 'RO11', role: 'satellite',
  gva_pc: 12000, population: 100000, vitality_index: 0.0, tier1_gate: true, moretti_tier: 'T4',
};

const coeffs: Elasticities = {
  beta_gov: mk(0.04), beta_K_hub: mk(0.10), beta_K_sat: mk(0.25),
  beta_mig: mk(0.5), beta_fert: mk(0.3), beta_edu: mk(0.02),
  gamma: mk(0.3), lambda: mk(0.4),
  tau: 0.2, delta: 0.05, discount_rate: 0.03,
  moretti: { T4: 0.012, T6: 0.008 }, provisional: true,
};
function mk(value: number): Elasticities['beta_gov'] {
  return { value, se: value * 0.2, id_strategy: 'test', source: 'test', support: [0, 1] };
}

describe('structuralRamp', () => {
  it('is 0 at and before reform year', () => {
    expect(structuralRamp(2024)).toBe(0);
    expect(structuralRamp(2025)).toBe(0);
  });
  it('is 1 at and after ramp end', () => {
    expect(structuralRamp(2030)).toBe(1);
    expect(structuralRamp(2040)).toBe(1);
  });
  it('is linear in between', () => {
    expect(structuralRamp(2027)).toBeCloseTo(0.4, 6);
  });
});

describe('needWeights', () => {
  it('sums to 1 and gives the lowest-vitality satellite the largest share', () => {
    const w = needWeights([satA, satB]);
    const total = (w.get('RO_A') ?? 0) + (w.get('RO_B') ?? 0);
    expect(total).toBeCloseTo(1, 6);
    expect(w.get('RO_A')! ).toBeGreaterThan(w.get('RO_B')!);
  });
});

describe('capitalFlows', () => {
  it('drains the hub by rho*tau as a fraction of its own GVA', () => {
    const levers: LeverVector = { ...DEFAULT_LEVERS, rho: 0.5 };
    const f = capitalFlows(hub, [satA, satB], levers, coeffs);
    expect(f.hubFraction).toBeCloseTo(-0.5 * 0.2, 6); // -0.1
  });
  it('gives satellites a positive inflow fraction under cohesion', () => {
    const levers: LeverVector = { ...DEFAULT_LEVERS, kappa: 100 };
    const f = capitalFlows(hub, [satA, satB], levers, coeffs);
    // satA: 100 €/cap → fraction = 100/10000 = 0.01
    expect(f.satFraction.get('RO_A')).toBeCloseTo(0.01, 6);
  });
});

describe('perpetualInventory', () => {
  it('accumulates with depreciation', () => {
    const stock = perpetualInventory(0.1, [2025, 2026, 2027], 0.05);
    expect(stock.get(2025)).toBeCloseTo(0.1, 6);
    expect(stock.get(2026)).toBeCloseTo(0.1 * 0.95 + 0.1, 6); // 0.195
    expect(stock.get(2027)).toBeCloseTo((0.1 * 0.95 + 0.1) * 0.95 + 0.1, 6);
  });
});

describe('regimeSign', () => {
  it('flags convergence when satellite MPK dominates', () => {
    const levers: LeverVector = { ...DEFAULT_LEVERS, conn: 1 };
    const { regime } = regimeSign(hub, [satA, satB], levers, coeffs);
    expect(regime).toBe('convergence'); // beta_K_sat 0.25 * (0.3+1) > beta_K_hub 0.10
  });
  it('flags agglomeration when hub MPK dominates', () => {
    const hubStrong: Elasticities = { ...coeffs, beta_K_hub: mk(0.9) };
    const { regime } = regimeSign(hub, [satA, satB], { ...DEFAULT_LEVERS, conn: 0 }, hubStrong);
    expect(regime).toBe('agglomeration');
  });
});
