import type { InfraLayer, CountyCapacity } from '../types';

let cached: InfraLayer | null = null;

export async function loadInfraLayer(): Promise<InfraLayer> {
  if (cached) return cached;
  const res = await fetch('./data/infra_layer.json');
  if (!res.ok) throw new Error(`Failed to load infra_layer.json: ${res.status}`);
  cached = (await res.json()) as InfraLayer;
  return cached;
}

export function nationalPercentile(code: string, layer: InfraLayer): number {
  const county = layer.counties[code];
  if (!county) return 0;
  const scores = Object.values(layer.counties).map((c) => c.capacity_index);
  const below = scores.filter((s) => s < county.capacity_index).length;
  return Math.round((below / scores.length) * 100);
}

export function peerCounties(code: string, layer: InfraLayer): CountyCapacity[] {
  const county = layer.counties[code];
  if (!county) return [];
  return county.peers
    .map((p) => layer.counties[p])
    .filter((c): c is CountyCapacity => c != null);
}

export function exportCapacityCsv(layer: InfraLayer): string {
  const headers = [
    'nuts3_code', 'name', 'capacity_index', 'national_percentile',
    'rank_min', 'rank_max', 'transport', 'education', 'health', 'economic',
    'divergence_type',
  ];
  const rows = Object.entries(layer.counties).map(([code, c]) => [
    code,
    c.name,
    c.capacity_index.toFixed(1),
    c.national_percentile,
    c.rank_interval[0],
    c.rank_interval[1],
    c.pillars.transport.score.toFixed(1),
    c.pillars.education.score.toFixed(1),
    c.pillars.health.score.toFixed(1),
    c.pillars.economic.score.toFixed(1),
    c.divergence?.type ?? '',
  ]);
  return [headers, ...rows].map((r) => r.join(',')).join('\n');
}
