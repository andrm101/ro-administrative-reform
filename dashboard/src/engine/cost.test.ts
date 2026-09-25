import { describe, it, expect } from 'vitest';
import { programmeCost } from './cost';
import type { CountyPrimitive, LeverVector } from '../types';
import { DEFAULT_LEVERS } from '../types';

const hub: CountyPrimitive = {
  nuts3_code: 'H', nuts2_code: 'RO11', role: 'hub',
  gva_pc: 20000, population: 100000, vitality_index: 1, tier1_gate: true, moretti_tier: 'T4',
};
const sat: CountyPrimitive = {
  nuts3_code: 'S', nuts2_code: 'RO11', role: 'satellite',
  gva_pc: 10000, population: 100000, vitality_index: -1, tier1_gate: false, moretti_tier: 'T6',
};

describe('programmeCost', () => {
  it('is zero when no spending levers are set', () => {
    expect(programmeCost(hub, [sat], DEFAULT_LEVERS, [2025], 0.03)).toBe(0);
  });
  it('counts cohesion as €/capita across satellites, discounted', () => {
    const levers: LeverVector = { ...DEFAULT_LEVERS, kappa: 100 };
    // year 2025 (undiscounted): 100 €/cap × 100000 = 10,000,000
    const cost = programmeCost(hub, [sat], levers, [2025], 0.03);
    expect(cost).toBeCloseTo(10_000_000, 0);
  });
  it('discounts future years', () => {
    const levers: LeverVector = { ...DEFAULT_LEVERS, kappa: 100 };
    const cost = programmeCost(hub, [sat], levers, [2026], 0.03);
    expect(cost).toBeCloseTo(10_000_000 / 1.03, 0);
  });
});
