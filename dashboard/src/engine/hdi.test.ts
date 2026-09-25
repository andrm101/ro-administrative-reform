import { describe, it, expect } from 'vitest';
import { computeHDI, incomeIndex, healthIndex } from './hdi';

describe('incomeIndex', () => {
  it('is 0 at the EU floor and 1 at the EU ceiling', () => {
    expect(incomeIndex(Math.log(5000))).toBeCloseTo(0, 6);
    expect(incomeIndex(Math.log(60000))).toBeCloseTo(1, 6);
  });
  it('clamps below the floor', () => {
    expect(incomeIndex(Math.log(1000))).toBe(0);
  });
});

describe('healthIndex', () => {
  it('maps the vitality range [-2,2] into [0,1]', () => {
    expect(healthIndex(-2)).toBeCloseTo(0, 6);
    expect(healthIndex(2)).toBeCloseTo(1, 6);
    expect(healthIndex(0)).toBeCloseTo(0.5, 6);
  });
});

describe('computeHDI', () => {
  it('is the geometric mean of the three indices', () => {
    const h = computeHDI({ lnGvaPc: Math.log(20000), vitality: 0, eduIndex: 0.8 });
    const expected = Math.cbrt(incomeIndex(Math.log(20000)) * 0.5 * 0.8);
    expect(h).toBeCloseTo(expected, 6);
  });
});
