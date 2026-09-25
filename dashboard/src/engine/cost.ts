import type { CountyPrimitive, LeverVector } from '../types';
import { REFORM_YEAR } from './fiscal';

// v0 prices only the explicitly €-denominated flows. Gov-efficiency, connectivity and
// MegaCampus capital costs are out of scope for v0 (documented limitation in the spec §8).

/** Discounted total programme cost (EUR) of the €-denominated flow levers over the horizon. */
export function programmeCost(
  hub: CountyPrimitive | null,
  satellites: CountyPrimitive[],
  levers: LeverVector,
  years: number[],
  discountRate: number,
): number {
  const popSatellites = satellites.reduce((a, s) => a + s.population, 0);
  const popAll = popSatellites + (hub?.population ?? 0);

  // Per-year € spend: cohesion + migration subsidy to satellites; family transfer region-wide; skills as %GVA region-wide.
  const cohesion = levers.kappa * popSatellites;
  const migration = levers.mu * popSatellites;
  const family = levers.family * popAll;
  const gvaAll =
    (hub ? hub.gva_pc * hub.population : 0) + satellites.reduce((a, s) => a + s.gva_pc * s.population, 0);
  const skills = (levers.skills / 100) * gvaAll;

  const annual = cohesion + migration + family + skills;
  return years.reduce((acc, y) => acc + annual / Math.pow(1 + discountRate, y - REFORM_YEAR), 0);
}
