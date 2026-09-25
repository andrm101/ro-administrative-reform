// Sequential color interpolation for choropleth layers.
// All functions return CSS rgb() strings.

function lerp(a: number, b: number, t: number): number {
  return Math.round(a + (b - a) * Math.min(1, Math.max(0, t)));
}

function rgb(r: number, g: number, b: number): string {
  return `rgb(${r},${g},${b})`;
}

/** White → red scale for reform cost (higher |att| = darker). */
export function reformCostColor(attAvgPre: number | null, maxAbs: number): string {
  if (attAvgPre === null || maxAbs === 0) return '#e5e7eb';
  const t = Math.abs(attAvgPre) / maxAbs;
  return rgb(lerp(255, 185, t), lerp(237, 28, t), lerp(237, 28, t));
}

/** White → blue scale for suitability (higher max-T score = darker). */
export function suitabilityColor(maxScore: number | null): string {
  if (maxScore === null) return '#e5e7eb';
  const t = maxScore;
  return rgb(lerp(239, 30, t), lerp(246, 64, t), lerp(255, 175, t));
}

/** White → green scale for ROI uplift (higher innovation uplift = darker). */
export function roiColor(upliftPct: number | null, maxUplift: number): string {
  if (upliftPct === null || maxUplift === 0) return '#e5e7eb';
  const t = Math.max(0, upliftPct) / maxUplift;
  return rgb(lerp(240, 5, t), lerp(253, 150, t), lerp(244, 105, t));
}

/** Suitability score (0–1) → hex colour. score=0 → #8b5cf6 (grey-purple), score=1 → #10b981 (blue-green). */
export function suitabilityToHex(score: number): string {
  const r = lerp(139, 16,  score);
  const g = lerp(92,  185, score);
  const b = lerp(246, 129, score);
  return `#${r.toString(16).padStart(2, '0')}${g.toString(16).padStart(2, '0')}${b.toString(16).padStart(2, '0')}`;
}

/** Max T1-T8 suitability score for a county (use T4_adjusted instead of T4). */
export function maxSuitability(s: {
  suitability_T1: number; suitability_T2: number; suitability_T3: number;
  suitability_T4_adjusted: number; suitability_T5: number; suitability_T6: number;
  suitability_T7: number; suitability_T8: number;
}): number {
  return Math.max(
    s.suitability_T1, s.suitability_T2, s.suitability_T3,
    s.suitability_T4_adjusted, s.suitability_T5, s.suitability_T6,
    s.suitability_T7, s.suitability_T8,
  );
}
