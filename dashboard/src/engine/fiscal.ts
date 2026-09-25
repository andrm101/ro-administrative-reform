import type { CountyPrimitive, LeverVector, Elasticities } from '../types';

export const REFORM_YEAR = 2025;
export const RAMP_END = 2030;

/** Linear structural ramp: 0 at REFORM_YEAR, 1 at RAMP_END, held flat thereafter. */
export function structuralRamp(year: number): number {
  if (year <= REFORM_YEAR) return 0;
  if (year >= RAMP_END) return 1;
  return (year - REFORM_YEAR) / (RAMP_END - REFORM_YEAR);
}

/** Need weights ∝ (vitality gap from the most-vital satellite); poorer counties get more. Sums to 1. */
export function needWeights(satellites: CountyPrimitive[]): Map<string, number> {
  if (satellites.length === 0) return new Map();
  const vmax = Math.max(...satellites.map((s) => s.vitality_index));
  const raw = satellites.map((s) => (vmax - s.vitality_index) + 0.01); // +ε keeps all strictly positive
  const total = raw.reduce((a, b) => a + b, 0);
  const m = new Map<string, number>();
  satellites.forEach((s, i) => m.set(s.nuts3_code, raw[i] / total));
  return m;
}

export interface CapitalFlows {
  hubFraction: number;               // negative drain, fraction of hub GVA / yr
  satFraction: Map<string, number>;  // positive inflow, fraction of own GVA / yr
}

/** Annual capital flow per county as a fraction of its own total GVA (gva_pc × population). */
export function capitalFlows(
  hub: CountyPrimitive | null,
  satellites: CountyPrimitive[],
  levers: LeverVector,
  coeffs: Elasticities,
): CapitalFlows {
  const w = needWeights(satellites);
  const gvaHub = hub ? hub.gva_pc * hub.population : 0;
  const fEur = levers.rho * coeffs.tau * gvaHub; // € redistributed / yr
  const hubFraction = gvaHub > 0 ? -fEur / gvaHub : 0; // = -rho*tau
  const satFraction = new Map<string, number>();
  for (const s of satellites) {
    const gvaS = s.gva_pc * s.population;
    const inflowEur = fEur * (w.get(s.nuts3_code) ?? 0) + levers.kappa * s.population;
    satFraction.set(s.nuts3_code, gvaS > 0 ? inflowEur / gvaS : 0);
  }
  return { hubFraction, satFraction };
}

/** Perpetual-inventory accumulation of an annual flow with depreciation δ, per year. */
export function perpetualInventory(annualFlow: number, years: number[], delta: number): Map<number, number> {
  const stock = new Map<number, number>();
  let prev = 0;
  for (const y of years) {
    const current = prev * (1 - delta) + annualFlow;
    stock.set(y, current);
    prev = current;
  }
  return stock;
}

export interface RegimeResult {
  regime: 'agglomeration' | 'convergence' | 'neutral';
  margin: number; // Σ β_sat·a_s·w_s − β_hub
}

/** Sign of the net regional return to redistribution: convergence if satellites dominate. */
export function regimeSign(
  _hub: CountyPrimitive | null,
  satellites: CountyPrimitive[],
  levers: LeverVector,
  coeffs: Elasticities,
): RegimeResult {
  const w = needWeights(satellites);
  const a = coeffs.gamma.value + levers.conn; // absorption
  const satTerm = satellites.reduce(
    (acc, s) => acc + coeffs.beta_K_sat.value * a * (w.get(s.nuts3_code) ?? 0),
    0,
  );
  const margin = satTerm - coeffs.beta_K_hub.value;
  const regime = Math.abs(margin) < 1e-9 ? 'neutral' : margin > 0 ? 'convergence' : 'agglomeration';
  return { regime, margin };
}
