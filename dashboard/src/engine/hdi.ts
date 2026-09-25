// Interim HDI proxy. Sub-project D swaps healthIndex → life expectancy and the
// education term → mean+expected schooling, behind the unchanged computeHDI signature.

// EU NUTS3 GVA-per-capita bounds (EUR) for the income dimension (UNDP-style log income).
// Documented v0 bounds; refined from Eurostat nama_10r_3gdp in Sub-project D.
const INCOME_FLOOR_EUR = 5000;
const INCOME_CEIL_EUR = 60000;

// Vitality index is z-scored; map the plausible [-2, 2] range to [0,1] as a health proxy.
const VITALITY_LO = -2;
const VITALITY_HI = 2;

function clamp01(x: number): number {
  return Math.min(1, Math.max(0, x));
}

/** Income dimension from ln(GVA per capita), normalized to EU log bounds. */
export function incomeIndex(lnGvaPc: number): number {
  const lo = Math.log(INCOME_FLOOR_EUR);
  const hi = Math.log(INCOME_CEIL_EUR);
  return clamp01((lnGvaPc - lo) / (hi - lo));
}

/** Health proxy from the existing vitality index (interim; replaced by life expectancy in D). */
export function healthIndex(vitality: number): number {
  return clamp01((vitality - VITALITY_LO) / (VITALITY_HI - VITALITY_LO));
}

export interface HdiInputs {
  lnGvaPc: number;
  vitality: number;
  eduIndex: number; // [0,1], national baseline + skills-lever gain
}

/** Geometric mean of income, health, education indices — the interim HDI proxy. */
export function computeHDI({ lnGvaPc, vitality, eduIndex }: HdiInputs): number {
  return Math.cbrt(incomeIndex(lnGvaPc) * healthIndex(vitality) * clamp01(eduIndex));
}
