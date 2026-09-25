import { describe, it, expect } from 'vitest';
import {
  nationalPercentile, peerCounties, exportCapacityCsv,
} from './capacity';
import type { InfraLayer, CountyCapacity } from '../types';

const makePillar = (score: number) => ({
  score, features: 5, confidence: 'high' as const,
});

const makeCounty = (capacity_index: number, peers: string[] = []): CountyCapacity => ({
  name: 'Test',
  nuts2_code: 'RO11',
  capacity_index,
  capacity_index_arithmetic: capacity_index + 2,
  national_percentile: 50,
  rank_interval: [10, 15],
  rank_median: 12,
  pillars: {
    transport: makePillar(60),
    education: makePillar(70),
    health: makePillar(50),
    economic: makePillar(55),
  },
  peers,
  divergence: null,
});

const LAYER: InfraLayer = {
  _meta: {
    overpass_query_date: '2026-06-06',
    script_version: '1.0.0',
    git_sha: 'abc123',
    aggregation_default: 'geometric',
    weighting_default: 'equal',
    cronbach_alpha: 0.72,
    ensemble_variants: 8,
  },
  counties: {
    RO111: makeCounty(67, ['RO421', 'RO126']),
    RO421: makeCounty(70, ['RO111']),
    RO126: makeCounty(65, ['RO111']),
    RO311: makeCounty(30, []),
    RO321: makeCounty(90, []),
  },
};

describe('nationalPercentile', () => {
  it('returns 0 for the lowest-scoring county', () => {
    expect(nationalPercentile('RO311', LAYER)).toBe(0);
  });
  it('returns correct value for the highest-scoring county', () => {
    // 4 counties below RO321 (score=90) → 4/5 × 100 = 80
    expect(nationalPercentile('RO321', LAYER)).toBe(80);
  });
  it('returns a value between 0 and 100', () => {
    const p = nationalPercentile('RO111', LAYER);
    expect(p).toBeGreaterThanOrEqual(0);
    expect(p).toBeLessThanOrEqual(100);
  });
});

describe('peerCounties', () => {
  it('returns CountyCapacity objects for peer codes', () => {
    const peers = peerCounties('RO111', LAYER);
    expect(peers).toHaveLength(2);
    expect(peers[0].capacity_index).toBe(70);   // RO421
  });
  it('returns empty array when county not found', () => {
    expect(peerCounties('UNKNOWN', LAYER)).toEqual([]);
  });
  it('returns empty array when peers list is empty', () => {
    expect(peerCounties('RO311', LAYER)).toEqual([]);
  });
});

describe('exportCapacityCsv', () => {
  it('contains a header row', () => {
    const csv = exportCapacityCsv(LAYER);
    const header = csv.split('\n')[0];
    expect(header).toContain('nuts3_code');
    expect(header).toContain('capacity_index');
  });
  it('has one row per county plus header', () => {
    const csv = exportCapacityCsv(LAYER);
    const lines = csv.split('\n').filter(Boolean);
    expect(lines).toHaveLength(Object.keys(LAYER.counties).length + 1);
  });
  it('includes divergence type column', () => {
    const csv = exportCapacityCsv(LAYER);
    expect(csv.split('\n')[0]).toContain('divergence_type');
  });
});
