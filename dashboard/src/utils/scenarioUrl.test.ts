import { describe, it, expect } from 'vitest';
import { leversToQuery, queryToLevers } from './scenarioUrl';
import { DEFAULT_LEVERS } from '../types';

describe('scenarioUrl round-trip', () => {
  it('serializes and parses back to the same lever vector', () => {
    const levers = { ...DEFAULT_LEVERS, rho: 0.3, kappa: 120, iota: 1.5 };
    const round = queryToLevers(new URLSearchParams(leversToQuery(levers)));
    expect(round.rho).toBeCloseTo(0.3, 6);
    expect(round.kappa).toBeCloseTo(120, 6);
    expect(round.iota).toBeCloseTo(1.5, 6);
  });
  it('clamps out-of-bound values to the lever bounds', () => {
    const parsed = queryToLevers(new URLSearchParams('rho=5&kappa=-10'));
    expect(parsed.rho).toBe(1);   // clamped to max
    expect(parsed.kappa).toBe(0); // clamped to min
  });
  it('falls back to defaults for missing/invalid params', () => {
    const parsed = queryToLevers(new URLSearchParams('gov=abc'));
    expect(parsed.gov).toBe(DEFAULT_LEVERS.gov);
  });
});
