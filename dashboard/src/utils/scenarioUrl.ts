import type { LeverVector } from '../types';
import { DEFAULT_LEVERS, LEVER_BOUNDS } from '../types';

const KEYS = Object.keys(DEFAULT_LEVERS) as (keyof LeverVector)[];

/** Serialize a lever vector to a URL query string (only non-default values). */
export function leversToQuery(levers: LeverVector): string {
  const p = new URLSearchParams();
  for (const k of KEYS) {
    if (levers[k] !== DEFAULT_LEVERS[k]) p.set(k, String(levers[k]));
  }
  return p.toString();
}

/** Parse a lever vector from URL params, clamping to bounds and defaulting invalid entries. */
export function queryToLevers(params: URLSearchParams): LeverVector {
  const out: LeverVector = { ...DEFAULT_LEVERS };
  for (const k of KEYS) {
    const raw = params.get(k);
    if (raw == null) continue;
    const n = Number(raw);
    if (!Number.isFinite(n)) continue;
    const [lo, hi] = LEVER_BOUNDS[k];
    out[k] = Math.min(hi, Math.max(lo, n));
  }
  return out;
}
