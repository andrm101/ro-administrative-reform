import { describe, it, expect } from 'vitest';
import {
  lnDeltaToPct, formatPct, formatPp, formatEur,
  costPerCapita, costPctGva, costPerPpUplift,
} from './format';

describe('lnDeltaToPct', () => {
  it('returns 0 at delta=0', () => {
    expect(lnDeltaToPct(0)).toBe(0);
  });
  it('returns ~5.127 at delta=0.05', () => {
    expect(lnDeltaToPct(0.05)).toBeCloseTo(5.1271, 3);
  });
  it('handles negative delta', () => {
    expect(lnDeltaToPct(-0.1)).toBeCloseTo(-9.5163, 3);
  });
});

describe('formatPct', () => {
  it('adds + prefix for positive', () => {
    expect(formatPct(3.2)).toBe('+3.2%');
  });
  it('keeps - prefix for negative', () => {
    expect(formatPct(-1.5)).toBe('-1.5%');
  });
  it('respects decimal places', () => {
    expect(formatPct(3.14159, 2)).toBe('+3.14%');
  });
});

describe('formatPp', () => {
  it('formats positive with p.p. suffix', () => {
    expect(formatPp(1.4)).toBe('+1.4 p.p.');
  });
  it('formats negative', () => {
    expect(formatPp(-2.3)).toBe('-2.3 p.p.');
  });
});

describe('formatEur', () => {
  it('formats billions with 2dp', () => {
    expect(formatEur(1.2e9)).toBe('€1.20bn');
  });
  it('formats millions with 1dp', () => {
    expect(formatEur(4.5e6)).toBe('€4.5m');
  });
  it('formats small amounts with toLocaleString', () => {
    const s = formatEur(12345);
    expect(s.startsWith('€')).toBe(true);
    expect(s).not.toContain('bn');
    expect(s).not.toContain('m');
  });
});

describe('costPerCapita', () => {
  it('divides cost by population', () => {
    expect(costPerCapita(1_000_000, 100_000)).toBe(10);
  });
  it('returns 0 when population is 0', () => {
    expect(costPerCapita(1_000_000, 0)).toBe(0);
  });
});

describe('costPctGva', () => {
  it('returns cost as % of GVA', () => {
    expect(costPctGva(100_000, 1_000_000)).toBe(10);
  });
  it('returns 0 when GVA is 0', () => {
    expect(costPctGva(100_000, 0)).toBe(0);
  });
});

describe('costPerPpUplift', () => {
  it('divides cost by uplift', () => {
    expect(costPerPpUplift(1_000_000, 5)).toBe(200_000);
  });
  it('returns null when uplift is near zero', () => {
    expect(costPerPpUplift(1_000_000, 0)).toBeNull();
    expect(costPerPpUplift(1_000_000, 0.0005)).toBeNull();
  });
});
