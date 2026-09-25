/** Convert Δ(ln) to % uplift: (e^Δ − 1) × 100 */
export function lnDeltaToPct(deltaLn: number): number {
  return (Math.exp(deltaLn) - 1) * 100;
}

/** Format as "±X.Y%" with explicit sign. */
export function formatPct(x: number, dp = 1): string {
  const sign = x >= 0 ? '+' : '';
  return `${sign}${x.toFixed(dp)}%`;
}

/** Format as "±X.Y p.p." with explicit sign. */
export function formatPp(x: number, dp = 1): string {
  const sign = x >= 0 ? '+' : '';
  return `${sign}${x.toFixed(dp)} p.p.`;
}

/** Format euros: ≥1bn → "€X.XXbn", ≥1m → "€X.Xm", else localized integer. */
export function formatEur(x: number): string {
  if (x >= 1e9) return `€${(x / 1e9).toFixed(2)}bn`;
  if (x >= 1e6) return `€${(x / 1e6).toFixed(1)}m`;
  return `€${Math.round(x).toLocaleString()}`;
}

/** € per capita */
export function costPerCapita(costEur: number, totalPop: number): number {
  return totalPop > 0 ? costEur / totalPop : 0;
}

/** Programme cost as % of regional GVA (0–100). */
export function costPctGva(costEur: number, totalGvaEur: number): number {
  return totalGvaEur > 0 ? (costEur / totalGvaEur) * 100 : 0;
}

/** € per percentage point of productivity uplift, or null when uplift ≈ 0. */
export function costPerPpUplift(costEur: number, upliftPct: number): number | null {
  return Math.abs(upliftPct) > 0.001 ? costEur / upliftPct : null;
}
