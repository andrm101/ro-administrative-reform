# Policy-Lever Scenario Engine — Implementation Plan (Plan 1 of 2: Engine + Policy Lab)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the client-side, calibrated-elasticity scenario engine and a "Policy Lab" dashboard mode that lets a policymaker move 9 reform levers and see growth, HDI-proxy, the agglomeration↔convergence regime, and programme cost — overlaid live on the existing MG-VAR baseline.

**Architecture:** A pure TypeScript engine (`src/engine/*`) reads two new static JSON inputs (`elasticities.json`, `fiscal_primitives.json`) plus the existing `forecasts.json` baseline, and returns a `ScenarioResult` with no side effects. React components in `src/components/` render it. This Plan ships a **v0 literature-prior fixture** (flagged `provisional: true`); Plan 2 replaces it with empirically-calibrated coefficients. The engine never mutates baseline data, so the existing dashboard is unaffected when Policy Lab is off.

**Tech Stack:** React 18 + TypeScript, Vitest (added here), Recharts, Tailwind, Vite. One small Python fixture-builder reuses existing processed data.

**Spec:** `docs/superpowers/specs/2026-06-05-scenario-engine-design.md`

---

## File Structure

| Action | File | Responsibility |
|---|---|---|
| Modify | `dashboard/package.json` | add Vitest + test scripts |
| Create | `dashboard/vitest.config.ts` | test runner config |
| Modify | `dashboard/src/types.ts` | `LeverVector`, `Elasticity`, `Elasticities`, `CountyPrimitive`, `FiscalPrimitives`, `ScenarioResult`, `DEFAULT_LEVERS`, `LEVER_BOUNDS` |
| Create | `dashboard/src/engine/fiscal.ts` | ramp, need-weights, capital flows, perpetual inventory, regime sign |
| Create | `dashboard/src/engine/fiscal.test.ts` | fiscal unit tests |
| Create | `dashboard/src/engine/hdi.ts` | interim HDI proxy (swappable for Sub-project D) |
| Create | `dashboard/src/engine/hdi.test.ts` | HDI unit tests |
| Create | `dashboard/src/engine/cost.ts` | discounted programme cost |
| Create | `dashboard/src/engine/cost.test.ts` | cost unit tests |
| Create | `dashboard/src/engine/scenario.ts` | three-channel overlay, population accounting, consistency anchors, bands |
| Create | `dashboard/src/engine/scenario.test.ts` | scenario + consistency unit tests |
| Create | `dashboard/src/utils/scenarioUrl.ts` | lever ↔ URL query-param (de)serialization |
| Create | `dashboard/src/utils/scenarioUrl.test.ts` | URL round-trip tests |
| Create | `scripts/A0_build_engine_fixtures.py` | derive v0 `fiscal_primitives.json` + write v0 `elasticities.json` |
| Create | `data/dashboard/elasticities.json` | engine coefficients (v0, provisional) |
| Create | `data/dashboard/fiscal_primitives.json` | per-county GVA/pop/vitality/role |
| Modify | `dashboard/src/hooks/useDashboardData.ts` | load the two new JSON inputs |
| Create | `dashboard/src/components/LeverPanel.tsx` | grouped sliders + presets |
| Create | `dashboard/src/components/RegimeBadge.tsx` | agglomeration/convergence badge |
| Create | `dashboard/src/components/CostReadout.tsx` | cost + 2040 KPI readouts |
| Create | `dashboard/src/components/PolicyLab.tsx` | container: wires engine + URL + chart |
| Modify | `dashboard/src/components/LayerSwitcher.tsx` | add `policy_lab` toggle |
| Modify | `dashboard/src/App.tsx` | render PolicyLab when layer = policy_lab |

**Engine unit conventions (read before coding):** `fiscal_primitives.json` stores `gva_pc` = GVA per capita (EUR, 2025) and `population` = persons (2025). All € levers (`kappa`, `mu`, `family`) are €/capita/yr; `skills` is % of GVA/yr; capital terms are computed as **fraction of own total GVA** (`gva_pc × population`), so every β is a dimensionless output elasticity. Rates (`nat`, `mig`) are per-1000.

---

### Task 1: Add Vitest test infrastructure

**Files:**
- Modify: `dashboard/package.json`
- Create: `dashboard/vitest.config.ts`

- [ ] **Step 1: Install Vitest**

Run: `cd dashboard && npm install -D vitest@^2.0.0`
Expected: `vitest` added to devDependencies, no errors.

- [ ] **Step 2: Add test scripts to package.json**

In `dashboard/package.json`, add two entries to the `"scripts"` block (after `"preview"`):

```json
    "preview": "vite preview",
    "test": "vitest run",
    "test:watch": "vitest",
```

- [ ] **Step 3: Create vitest.config.ts**

Create `dashboard/vitest.config.ts`:

```typescript
import { defineConfig } from 'vitest/config';

export default defineConfig({
  test: {
    environment: 'node',
    include: ['src/**/*.test.ts'],
  },
});
```

- [ ] **Step 4: Add a smoke test and confirm the runner works**

Create `dashboard/src/engine/smoke.test.ts`:

```typescript
import { describe, it, expect } from 'vitest';

describe('vitest', () => {
  it('runs', () => {
    expect(1 + 1).toBe(2);
  });
});
```

Run: `cd dashboard && npm test`
Expected: 1 passing test.

- [ ] **Step 5: Remove the smoke test and commit**

Run: `cd dashboard && rm src/engine/smoke.test.ts`

```bash
git add dashboard/package.json dashboard/vitest.config.ts dashboard/package-lock.json
git commit -m "test(RO-dashboard): add Vitest runner for the scenario engine"
```

---

### Task 2: Engine types and lever defaults

**Files:**
- Modify: `dashboard/src/types.ts`

- [ ] **Step 1: Append the engine types to types.ts**

Add at the end of `dashboard/src/types.ts`:

```typescript
// ── Scenario engine ──────────────────────────────────────────────────────────

export interface LeverVector {
  rho: number;     // redistribution share of hub tax base [0,1]
  kappa: number;   // cohesion injection €/capita/yr [0,500]
  gov: number;     // gov-efficiency gain, index [0,1]
  mu: number;      // migration-retention subsidy €/capita/yr [0,400]
  iota: number;    // MegaCampus intensity, multiplier [0,2]
  conn: number;    // connectivity index [0,1]
  family: number;  // pronatalist transfer €/capita/yr [0,600]
  skills: number;  // skills investment, % of GVA/yr [0,5]
  offset: number;  // reform-transition offset [0,1]
}

export const DEFAULT_LEVERS: LeverVector = {
  rho: 0, kappa: 0, gov: 0, mu: 0, iota: 0, conn: 0, family: 0, skills: 0, offset: 0,
};

/** [min, max] UI bounds per lever, keyed by LeverVector field. */
export const LEVER_BOUNDS: Record<keyof LeverVector, [number, number]> = {
  rho: [0, 1], kappa: [0, 500], gov: [0, 1], mu: [0, 400], iota: [0, 2],
  conn: [0, 1], family: [0, 600], skills: [0, 5], offset: [0, 1],
};

export interface Elasticity {
  value: number;
  se: number;
  id_strategy: string;
  source: string;
  support: [number, number];
}

export interface Elasticities {
  beta_gov: Elasticity;
  beta_K_hub: Elasticity;
  beta_K_sat: Elasticity;
  beta_mig: Elasticity;
  beta_fert: Elasticity;
  beta_edu: Elasticity;
  gamma: Elasticity;     // connectivity absorption modulator
  lambda: Elasticity;    // migration conservation (hub→satellite)
  tau: number;           // effective tax-retention rate (assumption)
  delta: number;         // annual capital depreciation (assumption)
  discount_rate: number; // social discount rate
  moretti: Record<string, number>; // tier (e.g. "T4") → annual ln-pop multiplier
  provisional: boolean;  // true until Plan 2 calibration replaces v0 priors
}

export interface CountyPrimitive {
  nuts3_code: string;
  nuts2_code: string;
  role: 'hub' | 'satellite';
  gva_pc: number;         // GVA per capita, EUR, 2025
  population: number;     // persons, 2025
  vitality_index: number;
  tier1_gate: boolean;
  moretti_tier: string;   // dominant suitability tier, e.g. "T4"
}

export interface FiscalPrimitives {
  counties: CountyPrimitive[];
}

export interface ScenarioPoint {
  year: number;
  baseline: number;
  scenario: number;
  lo: number;
  hi: number;
}

export interface ScenarioResult {
  perCounty: Record<string, ScenarioPoint[]>; // nuts3 → growth (ln_gva_per_empl) path
  perCountyPop: Record<string, ScenarioPoint[]>; // nuts3 → ln_population path
  hdiProxy: Record<string, { year: number; value: number }[]>; // nuts3 → HDI proxy
  regionTotal: ScenarioPoint[];                // population-weighted growth aggregate
  regime: 'agglomeration' | 'convergence' | 'neutral';
  regimeMargin: number;                        // Σβ_sat·a·w − β_hub
  cost2040: number;                            // discounted programme cost (EUR)
  hubOpportunityCostPct: number;               // hub growth pts lost at 2040
}
```

- [ ] **Step 2: Verify it compiles**

Run: `cd dashboard && npx tsc --noEmit`
Expected: No errors.

- [ ] **Step 3: Commit**

```bash
git add dashboard/src/types.ts
git commit -m "feat(RO-engine): scenario engine types, lever vector, bounds"
```

---

### Task 3: Fiscal block (`fiscal.ts`)

**Files:**
- Create: `dashboard/src/engine/fiscal.ts`
- Test: `dashboard/src/engine/fiscal.test.ts`

- [ ] **Step 1: Write the failing tests**

Create `dashboard/src/engine/fiscal.test.ts`:

```typescript
import { describe, it, expect } from 'vitest';
import { structuralRamp, needWeights, capitalFlows, perpetualInventory, regimeSign } from './fiscal';
import type { CountyPrimitive, LeverVector, Elasticities } from '../types';
import { DEFAULT_LEVERS } from '../types';

const hub: CountyPrimitive = {
  nuts3_code: 'RO_HUB', nuts2_code: 'RO11', role: 'hub',
  gva_pc: 20000, population: 300000, vitality_index: 1.0, tier1_gate: true, moretti_tier: 'T4',
};
const satA: CountyPrimitive = {
  nuts3_code: 'RO_A', nuts2_code: 'RO11', role: 'satellite',
  gva_pc: 10000, population: 200000, vitality_index: -1.0, tier1_gate: false, moretti_tier: 'T6',
};
const satB: CountyPrimitive = {
  nuts3_code: 'RO_B', nuts2_code: 'RO11', role: 'satellite',
  gva_pc: 12000, population: 100000, vitality_index: 0.0, tier1_gate: true, moretti_tier: 'T4',
};

const coeffs: Elasticities = {
  beta_gov: mk(0.04), beta_K_hub: mk(0.10), beta_K_sat: mk(0.25),
  beta_mig: mk(0.5), beta_fert: mk(0.3), beta_edu: mk(0.02),
  gamma: mk(0.3), lambda: mk(0.4),
  tau: 0.2, delta: 0.05, discount_rate: 0.03,
  moretti: { T4: 0.012, T6: 0.008 }, provisional: true,
};
function mk(value: number): Elasticities['beta_gov'] {
  return { value, se: value * 0.2, id_strategy: 'test', source: 'test', support: [0, 1] };
}

describe('structuralRamp', () => {
  it('is 0 at and before reform year', () => {
    expect(structuralRamp(2024)).toBe(0);
    expect(structuralRamp(2025)).toBe(0);
  });
  it('is 1 at and after ramp end', () => {
    expect(structuralRamp(2030)).toBe(1);
    expect(structuralRamp(2040)).toBe(1);
  });
  it('is linear in between', () => {
    expect(structuralRamp(2027)).toBeCloseTo(0.4, 6);
  });
});

describe('needWeights', () => {
  it('sums to 1 and gives the lowest-vitality satellite the largest share', () => {
    const w = needWeights([satA, satB]);
    const total = (w.get('RO_A') ?? 0) + (w.get('RO_B') ?? 0);
    expect(total).toBeCloseTo(1, 6);
    expect(w.get('RO_A')! ).toBeGreaterThan(w.get('RO_B')!);
  });
});

describe('capitalFlows', () => {
  it('drains the hub by rho*tau as a fraction of its own GVA', () => {
    const levers: LeverVector = { ...DEFAULT_LEVERS, rho: 0.5 };
    const f = capitalFlows(hub, [satA, satB], levers, coeffs);
    expect(f.hubFraction).toBeCloseTo(-0.5 * 0.2, 6); // -0.1
  });
  it('gives satellites a positive inflow fraction under cohesion', () => {
    const levers: LeverVector = { ...DEFAULT_LEVERS, kappa: 100 };
    const f = capitalFlows(hub, [satA, satB], levers, coeffs);
    // satA: 100 €/cap → fraction = 100/10000 = 0.01
    expect(f.satFraction.get('RO_A')).toBeCloseTo(0.01, 6);
  });
});

describe('perpetualInventory', () => {
  it('accumulates with depreciation', () => {
    const stock = perpetualInventory(0.1, [2025, 2026, 2027], 0.05);
    expect(stock.get(2025)).toBeCloseTo(0.1, 6);
    expect(stock.get(2026)).toBeCloseTo(0.1 * 0.95 + 0.1, 6); // 0.195
    expect(stock.get(2027)).toBeCloseTo((0.1 * 0.95 + 0.1) * 0.95 + 0.1, 6);
  });
});

describe('regimeSign', () => {
  it('flags convergence when satellite MPK dominates', () => {
    const levers: LeverVector = { ...DEFAULT_LEVERS, conn: 1 };
    const { regime } = regimeSign(hub, [satA, satB], levers, coeffs);
    expect(regime).toBe('convergence'); // beta_K_sat 0.25 * (0.3+1) > beta_K_hub 0.10
  });
  it('flags agglomeration when hub MPK dominates', () => {
    const hubStrong: Elasticities = { ...coeffs, beta_K_hub: mk(0.9) };
    const { regime } = regimeSign(hub, [satA, satB], { ...DEFAULT_LEVERS, conn: 0 }, hubStrong);
    expect(regime).toBe('agglomeration');
  });
});
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd dashboard && npm test -- fiscal`
Expected: FAIL — `fiscal.ts` does not export these functions.

- [ ] **Step 3: Implement fiscal.ts**

Create `dashboard/src/engine/fiscal.ts`:

```typescript
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
  hub: CountyPrimitive | null,
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
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd dashboard && npm test -- fiscal`
Expected: PASS (all fiscal tests green).

- [ ] **Step 5: Commit**

```bash
git add dashboard/src/engine/fiscal.ts dashboard/src/engine/fiscal.test.ts
git commit -m "feat(RO-engine): fiscal block — ramp, need-weights, capital flows, regime sign"
```

---

### Task 4: Interim HDI proxy (`hdi.ts`)

**Files:**
- Create: `dashboard/src/engine/hdi.ts`
- Test: `dashboard/src/engine/hdi.test.ts`

- [ ] **Step 1: Write the failing tests**

Create `dashboard/src/engine/hdi.test.ts`:

```typescript
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
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd dashboard && npm test -- hdi`
Expected: FAIL — `hdi.ts` not found.

- [ ] **Step 3: Implement hdi.ts**

Create `dashboard/src/engine/hdi.ts`:

```typescript
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
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd dashboard && npm test -- hdi`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add dashboard/src/engine/hdi.ts dashboard/src/engine/hdi.test.ts
git commit -m "feat(RO-engine): interim HDI proxy (income/health/education geometric mean)"
```

---

### Task 5: Programme cost (`cost.ts`)

**Files:**
- Create: `dashboard/src/engine/cost.ts`
- Test: `dashboard/src/engine/cost.test.ts`

- [ ] **Step 1: Write the failing tests**

Create `dashboard/src/engine/cost.test.ts`:

```typescript
import { describe, it, expect } from 'vitest';
import { programmeCost } from './cost';
import type { CountyPrimitive, LeverVector } from '../types';
import { DEFAULT_LEVERS } from '../types';

const hub: CountyPrimitive = {
  nuts3_code: 'H', nuts2_code: 'RO11', role: 'hub',
  gva_pc: 20000, population: 100000, vitality_index: 1, tier1_gate: true, moretti_tier: 'T4',
};
const sat: CountyPrimitive = {
  nuts3_code: 'S', nuts2_code: 'RO11', role: 'satellite',
  gva_pc: 10000, population: 100000, vitality_index: -1, tier1_gate: false, moretti_tier: 'T6',
};

describe('programmeCost', () => {
  it('is zero when no spending levers are set', () => {
    expect(programmeCost(hub, [sat], DEFAULT_LEVERS, [2025, 2026], 0.03)).toBe(0);
  });
  it('counts cohesion as €/capita across satellites, discounted', () => {
    const levers: LeverVector = { ...DEFAULT_LEVERS, kappa: 100 };
    // year 2025 (undiscounted): 100 €/cap × 100000 = 10,000,000
    const cost = programmeCost(hub, [sat], levers, [2025], 0.03);
    expect(cost).toBeCloseTo(10_000_000, 0);
  });
  it('discounts future years', () => {
    const levers: LeverVector = { ...DEFAULT_LEVERS, kappa: 100 };
    const cost = programmeCost(hub, [sat], levers, [2026], 0.03);
    expect(cost).toBeCloseTo(10_000_000 / 1.03, 0);
  });
});
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd dashboard && npm test -- cost`
Expected: FAIL — `cost.ts` not found.

- [ ] **Step 3: Implement cost.ts**

Create `dashboard/src/engine/cost.ts`:

```typescript
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
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd dashboard && npm test -- cost`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add dashboard/src/engine/cost.ts dashboard/src/engine/cost.test.ts
git commit -m "feat(RO-engine): discounted programme-cost accounting"
```

---

### Task 6: Scenario URL serialization (`scenarioUrl.ts`)

**Files:**
- Create: `dashboard/src/utils/scenarioUrl.ts`
- Test: `dashboard/src/utils/scenarioUrl.test.ts`

- [ ] **Step 1: Write the failing tests**

Create `dashboard/src/utils/scenarioUrl.test.ts`:

```typescript
import { describe, it, expect } from 'vitest';
import { leversToQuery, queryToLevers } from './scenarioUrl';
import { DEFAULT_LEVERS } from '../types';

describe('scenarioUrl round-trip', () => {
  it('serializes and parses back to the same lever vector', () => {
    const levers = { ...DEFAULT_LEVERS, rho: 0.3, kappa: 120, iota: 1.5 };
    const round = queryToLevers(new URLSearchParams(leversToQuery(levers)));
    expect(round.rho).toBeCloseTo(0.3, 6);
    expect(round.kappa).toBeCloseTo(120, 6);
    expect(round.iota).toBeCloseTo(1.5, 6);
  });
  it('clamps out-of-bound values to the lever bounds', () => {
    const parsed = queryToLevers(new URLSearchParams('rho=5&kappa=-10'));
    expect(parsed.rho).toBe(1);   // clamped to max
    expect(parsed.kappa).toBe(0); // clamped to min
  });
  it('falls back to defaults for missing/invalid params', () => {
    const parsed = queryToLevers(new URLSearchParams('gov=abc'));
    expect(parsed.gov).toBe(DEFAULT_LEVERS.gov);
  });
});
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd dashboard && npm test -- scenarioUrl`
Expected: FAIL — module not found.

- [ ] **Step 3: Implement scenarioUrl.ts**

Create `dashboard/src/utils/scenarioUrl.ts`:

```typescript
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
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd dashboard && npm test -- scenarioUrl`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add dashboard/src/utils/scenarioUrl.ts dashboard/src/utils/scenarioUrl.test.ts
git commit -m "feat(RO-engine): shareable scenario URL (de)serialization with clamping"
```

---

### Task 7: Scenario engine core (`scenario.ts`)

**Files:**
- Create: `dashboard/src/engine/scenario.ts`
- Test: `dashboard/src/engine/scenario.test.ts`

Context: the engine consumes the existing baseline as `Record<nuts3, Record<outcome, Record<path, ForecastPoint[]>>>` — i.e. `forecastsByCode[nuts3].forecasts[outcome][path]`. It overlays on the `status_quo` path. `ForecastPoint` has `{ year, value, lo80, hi80, lo95, hi95 }` (see types.ts).

- [ ] **Step 1: Write the failing tests (consistency anchors + monotonicity)**

Create `dashboard/src/engine/scenario.test.ts`:

```typescript
import { describe, it, expect } from 'vitest';
import { applyScenario } from './scenario';
import type {
  CountyPrimitive, Elasticities, ForecastCounty, LeverVector, RegionGroup,
} from '../types';
import { DEFAULT_LEVERS } from '../types';

function mk(value: number): Elasticities['beta_gov'] {
  return { value, se: value * 0.2, id_strategy: 't', source: 't', support: [0, 2] };
}
const coeffs: Elasticities = {
  beta_gov: mk(0.04), beta_K_hub: mk(0.10), beta_K_sat: mk(0.25),
  beta_mig: mk(0.5), beta_fert: mk(0.3), beta_edu: mk(0.02),
  gamma: mk(0.3), lambda: mk(0.4),
  tau: 0.2, delta: 0.05, discount_rate: 0.03,
  moretti: { T4: 0.012, T6: 0.008 }, provisional: true,
};

const years = [2025, 2026, 2027, 2028, 2029, 2030];
function path(base: number) {
  return years.map((year, i) => ({
    year, value: base + i * 0.001, lo80: base, hi80: base, lo95: base, hi95: base,
  }));
}
function county(code: string): ForecastCounty {
  return {
    nuts3_code: code, county_name: code,
    forecasts: {
      ln_gva_per_empl: { status_quo: path(3.0), innovation_hub: path(3.0), counterfactual: path(3.0) },
      ln_population: { status_quo: path(13.0), innovation_hub: path(13.0), counterfactual: path(13.0) },
    },
  };
}

const hub: CountyPrimitive = {
  nuts3_code: 'H', nuts2_code: 'RO11', role: 'hub',
  gva_pc: 20000, population: 300000, vitality_index: 1, tier1_gate: true, moretti_tier: 'T4',
};
const sat: CountyPrimitive = {
  nuts3_code: 'S', nuts2_code: 'RO11', role: 'satellite',
  gva_pc: 10000, population: 200000, vitality_index: -1, tier1_gate: true, moretti_tier: 'T4',
};
const group: RegionGroup = { nuts2Code: 'RO11', hubNuts3: 'H', satellites: ['S'] };
const primitives = new Map<string, CountyPrimitive>([['H', hub], ['S', sat]]);
const baseline = { H: county('H'), S: county('S') };

describe('applyScenario — consistency anchors', () => {
  it('all-zero levers reproduce the status_quo baseline (identity)', () => {
    const r = applyScenario(group, DEFAULT_LEVERS, coeffs, primitives, baseline);
    for (const p of r.perCounty['S']) {
      expect(p.scenario).toBeCloseTo(p.baseline, 9);
    }
  });
  it('a positive migration subsidy raises satellite population vs baseline (monotonic)', () => {
    const levers: LeverVector = { ...DEFAULT_LEVERS, mu: 200 };
    const r = applyScenario(group, levers, coeffs, primitives, baseline);
    const last = r.perCountyPop['S'].at(-1)!;
    expect(last.scenario).toBeGreaterThan(last.baseline);
  });
  it('migration conservation pulls hub population down when satellites are subsidized', () => {
    const levers: LeverVector = { ...DEFAULT_LEVERS, mu: 200 };
    const r = applyScenario(group, levers, coeffs, primitives, baseline);
    const last = r.perCountyPop['H'].at(-1)!;
    expect(last.scenario).toBeLessThan(last.baseline);
  });
  it('reports a regime and a finite cost', () => {
    const r = applyScenario({ ...DEFAULT_LEVERS } as never, DEFAULT_LEVERS, coeffs, primitives, baseline) as never;
    void r;
    const r2 = applyScenario(group, { ...DEFAULT_LEVERS, kappa: 100 }, coeffs, primitives, baseline);
    expect(['agglomeration', 'convergence', 'neutral']).toContain(r2.regime);
    expect(r2.cost2040).toBeGreaterThan(0);
  });
});
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd dashboard && npm test -- scenario`
Expected: FAIL — `scenario.ts` not found.

- [ ] **Step 3: Implement scenario.ts**

Create `dashboard/src/engine/scenario.ts`:

```typescript
import type {
  CountyPrimitive, Elasticities, ForecastCounty, LeverVector, RegionGroup,
  ScenarioPoint, ScenarioResult,
} from '../types';
import { structuralRamp, capitalFlows, perpetualInventory, regimeSign, REFORM_YEAR } from './fiscal';
import { computeHDI } from './hdi';
import { programmeCost } from './cost';

const OUTCOME_GVA = 'ln_gva_per_empl';
const OUTCOME_POP = 'ln_population';
const BASE_PATH = 'status_quo';

// National baseline education index for the interim HDI (UNDP RO ~0.75); skills lever adds to it.
const EDU_BASELINE = 0.75;
const EDU_SKILLS_GAIN = 0.02; // index points per cumulative %GVA of skills investment

function baselinePath(county: ForecastCounty | undefined, outcome: string): { year: number; value: number; lo80: number; hi80: number }[] {
  const p = county?.forecasts?.[outcome]?.[BASE_PATH] ?? [];
  return p.map((pt) => ({ year: pt.year, value: pt.value ?? 0, lo80: pt.lo80 ?? pt.value ?? 0, hi80: pt.hi80 ?? pt.value ?? 0 }));
}

/** Core overlay: returns scenario-adjusted growth + population paths, HDI, regime, cost. */
export function applyScenario(
  group: RegionGroup,
  levers: LeverVector,
  coeffs: Elasticities,
  primitives: Map<string, CountyPrimitive>,
  baseline: Record<string, ForecastCounty>,
): ScenarioResult {
  const hub = group.hubNuts3 ? primitives.get(group.hubNuts3) ?? null : null;
  const satellites = group.satellites.map((n) => primitives.get(n)).filter((s): s is CountyPrimitive => !!s);
  const members = [...(hub ? [hub] : []), ...satellites];

  // Year axis from the first available baseline path.
  const anyCounty = baseline[members[0]?.nuts3_code ?? ''];
  const years = baselinePath(anyCounty, OUTCOME_GVA).map((p) => p.year);

  const flows = capitalFlows(hub, satellites, levers, coeffs);
  const a = coeffs.gamma.value + levers.conn;

  // Migration conservation: hub loses λ × Σ satellite migration gains.
  const satMigGain = coeffs.beta_mig.value * levers.mu; // per satellite, rate /1000
  const hubMigDrain = coeffs.lambda.value * satellites.length * satMigGain;

  const perCounty: Record<string, ScenarioPoint[]> = {};
  const perCountyPop: Record<string, ScenarioPoint[]> = {};
  const hdiProxy: Record<string, { year: number; value: number }[]> = {};

  for (const c of members) {
    const isHub = c.role === 'hub';
    const capFlow = isHub ? flows.hubFraction : flows.satFraction.get(c.nuts3_code) ?? 0;
    const betaK = isHub ? coeffs.beta_K_hub.value : coeffs.beta_K_sat.value * a;
    const capStock = perpetualInventory(capFlow, years, coeffs.delta);
    const skillsStock = perpetualInventory(levers.skills / 100, years, coeffs.delta); // %GVA → fraction

    const gvaBase = baselinePath(baseline[c.nuts3_code], OUTCOME_GVA);
    const popBase = baselinePath(baseline[c.nuts3_code], OUTCOME_POP);

    // ── Channel 1: productivity (ln_gva_per_empl) ──
    const growth: ScenarioPoint[] = gvaBase.map((pt) => {
      const phi = structuralRamp(pt.year);
      const structural = phi * (coeffs.beta_gov.value * levers.gov + levers.iota * (coeffs.moretti[c.moretti_tier] ?? 0) * (c.tier1_gate ? 1 : 0));
      const flow = coeffs.beta_edu.value * (skillsStock.get(pt.year) ?? 0) + betaK * (capStock.get(pt.year) ?? 0);
      const delta = structural + flow;
      // Band from the dominant β SE (delta method, first order).
      const seScale = Math.abs(betaK) > 0 ? coeffs.beta_K_sat.se / Math.max(coeffs.beta_K_sat.value, 1e-6) : 0.2;
      const band = Math.abs(delta) * seScale;
      return { year: pt.year, baseline: pt.value, scenario: pt.value + delta, lo: pt.value + delta - band, hi: pt.value + delta + band };
    });
    perCounty[c.nuts3_code] = growth;

    // ── Channel 2: demography (ln_population) ──
    let cum = 0;
    const pop: ScenarioPoint[] = popBase.map((pt) => {
      const phi = structuralRamp(pt.year);
      const dNat = phi * coeffs.beta_fert.value * levers.family;
      const dMig = phi * (isHub ? -hubMigDrain : coeffs.beta_mig.value * levers.mu);
      cum += (dNat + dMig) / 1000; // Δln P ≈ Σ rate/1000
      const band = Math.abs(cum) * 0.2;
      return { year: pt.year, baseline: pt.value, scenario: pt.value + cum, lo: pt.value + cum - band, hi: pt.value + cum + band };
    });
    perCountyPop[c.nuts3_code] = pop;

    // ── Channel 3 mitigation is applied to reform-cost elsewhere; HDI from scenario outcomes ──
    hdiProxy[c.nuts3_code] = growth.map((g, i) => ({
      year: g.year,
      value: computeHDI({
        lnGvaPc: g.scenario,
        vitality: c.vitality_index,
        eduIndex: EDU_BASELINE + EDU_SKILLS_GAIN * (skillsStock.get(g.year) ?? 0),
      }),
    }));
  }

  // Region aggregate: population-weighted growth across members.
  const totalPop = members.reduce((a2, m) => a2 + m.population, 0) || 1;
  const regionTotal: ScenarioPoint[] = years.map((year, i) => {
    let base = 0, scen = 0;
    for (const m of members) {
      const w = m.population / totalPop;
      base += w * (perCounty[m.nuts3_code][i]?.baseline ?? 0);
      scen += w * (perCounty[m.nuts3_code][i]?.scenario ?? 0);
    }
    return { year, baseline: base, scenario: scen, lo: scen, hi: scen };
  });

  const { regime, margin } = regimeSign(hub, satellites, levers, coeffs);
  const cost2040 = programmeCost(hub, satellites, levers, years, coeffs.discount_rate);
  const hubGrowth = hub ? perCounty[hub.nuts3_code]?.at(-1) : undefined;
  const hubOpportunityCostPct = hubGrowth ? (hubGrowth.scenario - hubGrowth.baseline) * 100 : 0;

  return { perCounty, perCountyPop, hdiProxy, regionTotal, regime, regimeMargin: margin, cost2040, hubOpportunityCostPct };
}
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd dashboard && npm test -- scenario`
Expected: PASS (identity, monotonicity, conservation, regime+cost).

- [ ] **Step 5: Run the full engine suite and the type check**

Run: `cd dashboard && npm test && npx tsc --noEmit`
Expected: all tests pass; no type errors.

- [ ] **Step 6: Commit**

```bash
git add dashboard/src/engine/scenario.ts dashboard/src/engine/scenario.test.ts
git commit -m "feat(RO-engine): scenario overlay — three channels, HDI, regime, cost, bands"
```

---

### Task 8: v0 fixture builder (Python) → JSON inputs

**Files:**
- Create: `scripts/A0_build_engine_fixtures.py`
- Create: `data/dashboard/elasticities.json`
- Create: `data/dashboard/fiscal_primitives.json`

Context: reuses `data/processed/ro_pvar_forecasts_roi.parquet` (status_quo paths → 2025 GVA & population) and `ro_nuts3_suitability.parquet` (vitality, tier gate, dominant tier). Hub = county in suitability NOT treated; satellites = treated. The script writes both JSONs idempotently.

- [ ] **Step 1: Write the fixture builder**

Create `scripts/A0_build_engine_fixtures.py`:

```python
"""Build v0 engine fixtures: fiscal_primitives.json (derived) + elasticities.json (literature priors).

Reproducible from processed parquets. Elasticity values are PROVISIONAL literature priors
(provisional=true); Plan 2 calibration replaces them with estimated coefficients.
Run: python scripts/A0_build_engine_fixtures.py
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
PROCESSED = ROOT / "data" / "processed"
OUT = ROOT / "data" / "dashboard"

# Employment-to-population ratio to convert GVA-per-employed → GVA-per-capita (v0 constant; refined in D).
EMP_POP_RATIO = 0.42
REFORM_YEAR = 2025


def build_primitives() -> dict:
    fc = pd.read_parquet(PROCESSED / "ro_pvar_forecasts_roi.parquet")
    suit = pd.read_parquet(PROCESSED / "ro_nuts3_suitability.parquet")

    sq = fc[(fc["path"] == "status_quo") & (fc["year"] == REFORM_YEAR)]
    gva = sq[sq["variable"] == "ln_gva_per_empl"].set_index("nuts3_code")["value"]
    pop = sq[sq["variable"] == "ln_population"].set_index("nuts3_code")["value"]

    tier_cols = [c for c in suit.columns if c.startswith("suitability_T")]
    counties = []
    treated = set(fc[fc.get("path") == "status_quo"]["nuts3_code"])  # all forecast counties
    # Role: proposed_regional_capital flag if present, else infer hub = highest vitality in NUTS2.
    suit = suit.copy()
    suit["_nuts2"] = suit["nuts3_code"].str.slice(0, 4)
    hub_codes = set(suit.sort_values("vitality_index").groupby("_nuts2").tail(1)["nuts3_code"])

    for _, r in suit.iterrows():
        code = r["nuts3_code"]
        if code not in gva.index or code not in pop.index:
            continue
        gva_pc = float(np.exp(gva[code]) * EMP_POP_RATIO)
        population = float(np.exp(pop[code]))
        dom_tier = max(tier_cols, key=lambda c: r[c]) if tier_cols else "T4"
        counties.append({
            "nuts3_code": code,
            "nuts2_code": code[:4],
            "role": "hub" if code in hub_codes else "satellite",
            "gva_pc": round(gva_pc, 2),
            "population": round(population, 0),
            "vitality_index": float(r.get("vitality_index", 0.0)),
            "tier1_gate": bool(r.get("tier1_gate", False)),
            "moretti_tier": dom_tier.replace("suitability_", "").replace("_adjusted", ""),
        })
    return {"counties": counties}


def build_elasticities() -> dict:
    def e(value, se, ids, src, support):
        return {"value": value, "se": se, "id_strategy": ids, "source": src, "support": list(support)}

    return {
        "beta_gov": e(0.04, 0.015, "PL-1999 RD prior", "literature v0", [0, 1]),
        "beta_K_hub": e(0.08, 0.03, "convergence prior (agglomeration)", "literature v0", [0, 0.5]),
        "beta_K_sat": e(0.22, 0.06, "convergence prior (catch-up)", "literature v0", [0, 0.6]),
        "beta_mig": e(0.6, 0.25, "PL migration prior", "literature v0", [0, 400]),
        "beta_fert": e(0.004, 0.0015, "Rodzina 500+ prior", "literature v0", [0, 600]),
        "beta_edu": e(0.03, 0.01, "Mincerian prior", "literature v0", [0, 5]),
        "gamma": e(0.3, 0.15, "accessibility prior", "literature v0 (weak)", [0, 1]),
        "lambda": e(0.4, 0.2, "PL intra-regional flows prior", "literature v0", [0, 1]),
        "tau": 0.2,
        "delta": 0.05,
        "discount_rate": 0.03,
        "moretti": {"T1": 0.025, "T2": 0.020, "T3": 0.015, "T4": 0.012,
                     "T5": 0.010, "T6": 0.008, "T7": 0.007, "T8": 0.006},
        "provisional": True,
    }


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "fiscal_primitives.json").write_text(json.dumps(build_primitives(), indent=2))
    (OUT / "elasticities.json").write_text(json.dumps(build_elasticities(), indent=2))
    print(f"Wrote fiscal_primitives.json and elasticities.json to {OUT}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Run the builder**

Run: `cd "c:\Users\andre\Desktop\Sandbox\RO-Administrative-Reform" && python scripts/A0_build_engine_fixtures.py`
Expected: prints "Wrote fiscal_primitives.json and elasticities.json"; both files exist under `data/dashboard/`.

- [ ] **Step 3: Sanity-check the output**

Run: `cd "c:\Users\andre\Desktop\Sandbox\RO-Administrative-Reform" && python -c "import json; d=json.load(open('data/dashboard/fiscal_primitives.json')); print(len(d['counties']), 'counties;', sum(c['role']=='hub' for c in d['counties']), 'hubs')"`
Expected: ~42 counties, ≥1 hub per NUTS2 region.

- [ ] **Step 4: Commit**

```bash
git add scripts/A0_build_engine_fixtures.py data/dashboard/elasticities.json data/dashboard/fiscal_primitives.json
git commit -m "feat(RO-engine): v0 fixture builder + provisional elasticities & fiscal primitives"
```

---

### Task 9: Load the new JSON inputs in useDashboardData

**Files:**
- Modify: `dashboard/src/hooks/useDashboardData.ts`
- Modify: `dashboard/src/types.ts` (extend `DashboardData`)

- [ ] **Step 1: Extend DashboardData in types.ts**

In `dashboard/src/types.ts`, add two fields to the `DashboardData` interface (after `summary: Summary;`):

```typescript
  elasticities: Elasticities;
  primitivesByCode: Record<string, CountyPrimitive>;
```

- [ ] **Step 2: Load them in the hook**

In `dashboard/src/hooks/useDashboardData.ts`:

Add to the import type list (line 2-5):

```typescript
import type {
  DashboardData, RegionData, ForecastCounty, SuitabilityData,
  LpIrf, SdidEstimate, EventStudyCoef, Summary, Elasticities, FiscalPrimitives, CountyPrimitive,
} from '../types';
```

Add two fetches to the `Promise.all` array (after the `summary.json` fetch):

```typescript
      fetchJson<Summary>('summary.json'),
      fetchJson<Elasticities>('elasticities.json'),
      fetchJson<FiscalPrimitives>('fiscal_primitives.json'),
```

Update the destructuring and `setData` block:

```typescript
      .then(([regions, forecasts, suitability, lpIrfs, sdid, eventstudy, summary, elasticities, fiscalPrimitives]) => {
        setData({
          regions,
          regionsByCode: Object.fromEntries(regions.map((r) => [r.nuts3_code, r])),
          forecasts,
          forecastsByCode: Object.fromEntries(forecasts.map((f) => [f.nuts3_code, f])),
          suitability,
          suitabilityByCode: Object.fromEntries(suitability.map((s) => [s.nuts3_code, s])),
          lpIrfs,
          sdid,
          eventstudy,
          summary,
          elasticities,
          primitivesByCode: Object.fromEntries(
            (fiscalPrimitives as FiscalPrimitives).counties.map((c: CountyPrimitive) => [c.nuts3_code, c]),
          ),
        });
      })
```

- [ ] **Step 3: Verify it compiles**

Run: `cd dashboard && npx tsc --noEmit`
Expected: No errors.

- [ ] **Step 4: Commit**

```bash
git add dashboard/src/hooks/useDashboardData.ts dashboard/src/types.ts
git commit -m "feat(RO-engine): load elasticities & fiscal primitives into dashboard data"
```

---

### Task 10: LeverPanel + presets component

**Files:**
- Create: `dashboard/src/components/LeverPanel.tsx`

- [ ] **Step 1: Create LeverPanel.tsx**

Create `dashboard/src/components/LeverPanel.tsx`:

```typescript
import type { LeverVector } from '../types';
import { LEVER_BOUNDS, DEFAULT_LEVERS } from '../types';

interface LeverMeta { key: keyof LeverVector; label: string; unit: string; group: string; }

const LEVERS: LeverMeta[] = [
  { key: 'rho', label: 'Redistribution share', unit: '', group: 'Fiscal' },
  { key: 'kappa', label: 'Cohesion injection', unit: '€/cap/yr', group: 'Fiscal' },
  { key: 'gov', label: 'Gov-efficiency gain', unit: '', group: 'Productivity' },
  { key: 'iota', label: 'MegaCampus intensity', unit: '×', group: 'Productivity' },
  { key: 'skills', label: 'Skills investment', unit: '% GVA', group: 'Productivity' },
  { key: 'conn', label: 'Connectivity', unit: '', group: 'Productivity' },
  { key: 'mu', label: 'Migration-retention', unit: '€/cap/yr', group: 'Demography' },
  { key: 'family', label: 'Family transfer', unit: '€/cap/yr', group: 'Demography' },
  { key: 'offset', label: 'Reform-transition offset', unit: '', group: 'Mitigation' },
];

const PRESETS: Record<string, Partial<LeverVector>> = {
  'Status quo': {},
  'Pure agglomeration': { iota: 1.5, gov: 0.6 },
  'Aggressive convergence': { rho: 0.5, mu: 200, conn: 0.8, skills: 3 },
  'EU cohesion-funded': { kappa: 250, conn: 0.6, skills: 2 },
};

interface Props {
  levers: LeverVector;
  onChange: (next: LeverVector) => void;
  provisional: boolean;
}

export default function LeverPanel({ levers, onChange, provisional }: Props) {
  const groups = [...new Set(LEVERS.map((l) => l.group))];
  function set(key: keyof LeverVector, value: number) {
    onChange({ ...levers, [key]: value });
  }
  return (
    <div className="p-3 space-y-3 text-xs">
      {provisional && (
        <div className="bg-amber-50 text-amber-800 rounded px-2 py-1">
          ⚠ Provisional coefficients (literature priors) — not yet empirically calibrated.
        </div>
      )}
      <div className="flex flex-wrap gap-1">
        {Object.keys(PRESETS).map((name) => (
          <button
            key={name}
            onClick={() => onChange({ ...DEFAULT_LEVERS, ...PRESETS[name] })}
            className="px-2 py-0.5 rounded border border-violet-300 text-violet-700 hover:bg-violet-50"
          >
            {name}
          </button>
        ))}
      </div>
      {groups.map((g) => (
        <div key={g}>
          <div className="font-semibold text-gray-700 mb-1">{g}</div>
          {LEVERS.filter((l) => l.group === g).map((l) => {
            const [lo, hi] = LEVER_BOUNDS[l.key];
            const step = hi <= 2 ? 0.05 : 10;
            return (
              <label key={l.key} className="flex items-center gap-2 mb-1">
                <span className="w-36 text-gray-600">{l.label}</span>
                <input
                  type="range" min={lo} max={hi} step={step} value={levers[l.key]}
                  onChange={(e) => set(l.key, Number(e.target.value))}
                  className="flex-1"
                />
                <span className="w-16 text-right tabular-nums">
                  {levers[l.key]}{l.unit}
                </span>
              </label>
            );
          })}
        </div>
      ))}
    </div>
  );
}
```

- [ ] **Step 2: Verify it compiles**

Run: `cd dashboard && npx tsc --noEmit`
Expected: No errors.

- [ ] **Step 3: Commit**

```bash
git add dashboard/src/components/LeverPanel.tsx
git commit -m "feat(RO-dashboard): LeverPanel with grouped sliders and scenario presets"
```

---

### Task 11: RegimeBadge + CostReadout components

**Files:**
- Create: `dashboard/src/components/RegimeBadge.tsx`
- Create: `dashboard/src/components/CostReadout.tsx`

- [ ] **Step 1: Create RegimeBadge.tsx**

Create `dashboard/src/components/RegimeBadge.tsx`:

```typescript
import type { ScenarioResult } from '../types';

const COPY: Record<ScenarioResult['regime'], { text: string; cls: string }> = {
  convergence: { text: 'CONVERGENCE regime — redistribution raises total regional output', cls: 'bg-emerald-50 text-emerald-800 border-emerald-200' },
  agglomeration: { text: 'AGGLOMERATION regime — redistribution reduces total regional output', cls: 'bg-rose-50 text-rose-800 border-rose-200' },
  neutral: { text: 'NEUTRAL — redistribution is output-neutral for this region', cls: 'bg-gray-50 text-gray-700 border-gray-200' },
};

export default function RegimeBadge({ result }: { result: ScenarioResult }) {
  const c = COPY[result.regime];
  return (
    <div className={`text-xs rounded border px-2 py-1.5 ${c.cls}`}>
      {c.text}
      <span className="ml-1 opacity-70">(margin {result.regimeMargin.toFixed(3)})</span>
    </div>
  );
}
```

- [ ] **Step 2: Create CostReadout.tsx**

Create `dashboard/src/components/CostReadout.tsx`:

```typescript
import type { ScenarioResult } from '../types';

function eur(x: number): string {
  if (x >= 1e9) return `€${(x / 1e9).toFixed(2)}bn`;
  if (x >= 1e6) return `€${(x / 1e6).toFixed(1)}m`;
  return `€${Math.round(x).toLocaleString()}`;
}

export default function CostReadout({ result }: { result: ScenarioResult }) {
  return (
    <div className="grid grid-cols-2 gap-2 p-3 text-xs">
      <div className="bg-violet-50 rounded p-2">
        <div className="text-violet-500">Programme cost (NPV, 3%)</div>
        <div className="font-bold text-violet-900 text-sm">{eur(result.cost2040)}</div>
      </div>
      <div className="bg-blue-50 rounded p-2">
        <div className="text-blue-500">Hub growth Δ @2040</div>
        <div className="font-bold text-blue-900 text-sm">
          {result.hubOpportunityCostPct >= 0 ? '+' : ''}{result.hubOpportunityCostPct.toFixed(2)} pts
        </div>
      </div>
    </div>
  );
}
```

- [ ] **Step 3: Verify it compiles**

Run: `cd dashboard && npx tsc --noEmit`
Expected: No errors.

- [ ] **Step 4: Commit**

```bash
git add dashboard/src/components/RegimeBadge.tsx dashboard/src/components/CostReadout.tsx
git commit -m "feat(RO-dashboard): RegimeBadge and CostReadout KPI components"
```

---

### Task 12: PolicyLab container

**Files:**
- Create: `dashboard/src/components/PolicyLab.tsx`

Context: reuses the existing `RegionGroup` derivation (a `Map<string, RegionGroup>` already passed around in App). PolicyLab takes the selected county → its NUTS2 group → runs `applyScenario` → renders a Recharts overlay + the panels. Lever state syncs to the URL via `scenarioUrl`.

- [ ] **Step 1: Create PolicyLab.tsx**

Create `dashboard/src/components/PolicyLab.tsx`:

```typescript
import { useState, useMemo, useEffect } from 'react';
import {
  ComposedChart, Area, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend,
  ReferenceLine, ResponsiveContainer,
} from 'recharts';
import type { DashboardData, RegionGroup, LeverVector } from '../types';
import { DEFAULT_LEVERS } from '../types';
import { applyScenario } from '../engine/scenario';
import { leversToQuery, queryToLevers } from '../utils/scenarioUrl';
import LeverPanel from './LeverPanel';
import RegimeBadge from './RegimeBadge';
import CostReadout from './CostReadout';

interface Props {
  nuts3Code: string | null;
  data: DashboardData;
  regionGroups: Map<string, RegionGroup>;
}

export default function PolicyLab({ nuts3Code, data, regionGroups }: Props) {
  const [levers, setLevers] = useState<LeverVector>(() =>
    queryToLevers(new URLSearchParams(window.location.search)),
  );

  // Sync lever state → URL query (shareable scenarios).
  useEffect(() => {
    const q = leversToQuery(levers);
    const url = q ? `${window.location.pathname}?${q}` : window.location.pathname;
    window.history.replaceState(null, '', url);
  }, [levers]);

  const primitives = useMemo(
    () => new Map(Object.entries(data.primitivesByCode)),
    [data.primitivesByCode],
  );

  const group = nuts3Code
    ? regionGroups.get(data.suitabilityByCode[nuts3Code]?.nuts2_code ?? '')
    : undefined;

  const result = useMemo(() => {
    if (!group) return null;
    return applyScenario(group, levers, data.elasticities, primitives, data.forecastsByCode);
  }, [group, levers, data.elasticities, data.forecastsByCode, primitives]);

  if (!nuts3Code) {
    return (
      <div className="flex flex-col items-center justify-center h-full text-gray-400 text-sm gap-2 p-6">
        <span className="text-2xl">🎛</span>
        <p>Click a county to open the Policy Lab for its region</p>
      </div>
    );
  }
  if (!group || !result) {
    return <div className="p-4 text-gray-400 text-sm">No region data for {nuts3Code}.</div>;
  }

  const chartData = result.regionTotal.map((p) => ({
    year: p.year, baseline: p.baseline, scenario: p.scenario,
  }));

  return (
    <div className="flex flex-col h-full overflow-y-auto">
      <div className="px-4 py-2 bg-violet-50 border-b border-violet-100 shrink-0">
        <div className="font-bold text-violet-900 text-sm">Policy Lab — {group.nuts2Code}</div>
        <div className="text-violet-600 text-xs">{group.satellites.length} satellite counties</div>
      </div>

      <div className="p-3">
        <RegimeBadge result={result} />
      </div>

      <ResponsiveContainer width="100%" height={200}>
        <ComposedChart data={chartData} margin={{ top: 4, right: 8, bottom: 4, left: 8 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
          <XAxis dataKey="year" tick={{ fontSize: 10 }} interval={2} />
          <YAxis tick={{ fontSize: 10 }} tickFormatter={(v: number) => v.toFixed(2)} width={45} />
          <Tooltip contentStyle={{ fontSize: 11 }} />
          <Legend iconSize={10} wrapperStyle={{ fontSize: 10 }} />
          <ReferenceLine x={2025} stroke="#d97706" strokeDasharray="4 3" />
          <Area type="monotone" dataKey="scenario" name="Scenario" stroke="#7c3aed" fill="#ede9fe" strokeWidth={2} dot={false} />
          <Line type="monotone" dataKey="baseline" name="Baseline" stroke="#6b7280" strokeWidth={1.5} strokeDasharray="4 2" dot={false} />
        </ComposedChart>
      </ResponsiveContainer>

      <CostReadout result={result} />
      <LeverPanel levers={levers} onChange={setLevers} provisional={data.elasticities.provisional} />
    </div>
  );
}
```

- [ ] **Step 2: Verify it compiles**

Run: `cd dashboard && npx tsc --noEmit`
Expected: No errors.

- [ ] **Step 3: Commit**

```bash
git add dashboard/src/components/PolicyLab.tsx
git commit -m "feat(RO-dashboard): PolicyLab container — engine wiring, overlay chart, URL sync"
```

---

### Task 13: Wire Policy Lab into LayerSwitcher and App

**Files:**
- Modify: `dashboard/src/types.ts` (LayerType)
- Modify: `dashboard/src/components/LayerSwitcher.tsx`
- Modify: `dashboard/src/App.tsx`

- [ ] **Step 1: Add `policy_lab` to LayerType**

In `dashboard/src/types.ts`, change the `LayerType` union:

```typescript
export type LayerType = 'reform_cost' | 'suitability' | 'roi' | 'region' | 'policy_lab';
```

- [ ] **Step 2: Add the LayerSwitcher button**

In `dashboard/src/components/LayerSwitcher.tsx`, add to the `LAYERS` array:

```typescript
  { id: 'region', label: 'Region' },
  { id: 'policy_lab', label: 'Policy Lab' },
```

- [ ] **Step 3: Render PolicyLab in App**

In `dashboard/src/App.tsx`, import it (after the `RegionPanel` import):

```typescript
import PolicyLab from './components/PolicyLab';
```

Replace the sidebar block (the `<div className="w-[360px] ...">` containing `<RegionPanel ... />`) with a conditional:

```tsx
        <div className="w-[360px] shrink-0 border-l border-gray-200 overflow-y-auto">
          {activeLayer === 'policy_lab' ? (
            <PolicyLab nuts3Code={selectedNuts3} data={data} regionGroups={regionGroups} />
          ) : (
            <RegionPanel
              nuts3Code={selectedNuts3}
              data={data}
              activeLayer={activeLayer}
              regionGroups={regionGroups}
              onCountyHover={setHoveredNuts3}
            />
          )}
        </div>
```

- [ ] **Step 4: Verify it compiles**

Run: `cd dashboard && npx tsc --noEmit`
Expected: No errors.

- [ ] **Step 5: Commit**

```bash
git add dashboard/src/types.ts dashboard/src/components/LayerSwitcher.tsx dashboard/src/App.tsx
git commit -m "feat(RO-dashboard): add Policy Lab layer toggle and App wiring"
```

---

### Task 14: Full verification + final commit

**Files:** none (verification only)

- [ ] **Step 1: Run the full engine test suite**

Run: `cd dashboard && npm test`
Expected: all fiscal / hdi / cost / scenario / scenarioUrl tests pass.

- [ ] **Step 2: Type-check and build**

Run: `cd dashboard && npx tsc --noEmit && npm run build`
Expected: zero type errors; `dist/` builds successfully.

- [ ] **Step 3: Manual smoke test (dev server)**

Run: `cd dashboard && npm run dev`
In the browser at http://localhost:5173:
1. Click "Policy Lab" → sidebar shows the provisional-coefficients warning
2. Click a county → regime badge + overlay chart + cost readout render
3. Drag "Cohesion injection" → scenario line and programme cost update live
4. Drag "Redistribution share" → regime badge flips between convergence/agglomeration at some threshold
5. Click "Aggressive convergence" preset → sliders + chart jump
6. Confirm the URL gains `?rho=...&mu=...` query params; copy it to a new tab → scenario restores
7. Switch to "Reform cost"/"Region" layers → existing dashboard still works unchanged

- [ ] **Step 4: Final commit**

```bash
git add -A
git commit -m "feat(RO-engine): Plan 1 complete — Policy Lab scenario engine end-to-end"
```

---

## Self-Review

**Spec coverage (§-by-§ against the design spec):**
- §3 architecture (offline JSON → pure client engine): Tasks 7–9. ✅
- §4 lever taxonomy (9 levers, bounds, temporal profiles): Task 2 (`LeverVector`, `LEVER_BOUNDS`), Task 3 (`structuralRamp`, `perpetualInventory`). ✅
- §5.1 normalization (fraction-of-GVA): Task 3 `capitalFlows` + Task 7 stocks. ✅
- §5.2 productivity channel: Task 7 Channel 1. ✅
- §5.3 fiscal block + regime sign: Task 3 `capitalFlows`/`regimeSign`. ✅
- §5.4 demography + migration conservation: Task 7 Channel 2 (`hubMigDrain`). ✅
- §5.5 reform-cost mitigation (offset): represented via the `offset` lever in types/UI; **note:** the offset's effect on the gsynth reform-cost series is surfaced through the existing Region view's counterfactual, not recomputed here — documented limitation for Plan 1 (engine focuses on forward MG-VAR paths). 
- §5.6 interim HDI proxy: Task 4. ✅
- §5.7 consistency anchors (identity, offset, ι=1): identity + monotonicity tested in Task 7. **ι=1 ≡ innovation_hub** is approximated (the v0 Moretti reuse matches Stage 13 multipliers but the ramp/band handling differs); exact reproduction is a Plan 2 calibration acceptance test.
- §7 uncertainty bands: Task 7 delta-method bands. ✅
- §8 cost + presets: Task 5 + Task 10 presets. ✅ (budget *envelope* binding is deferred — cost *readout* is in; envelope is a Plan-2/Plan-1.1 enhancement, noted.)
- §9 dashboard (Policy Lab, regime badge, URL sharing, presets): Tasks 10–13. ✅
- §10 reproducibility/testing: Vitest suite Tasks 1–7; fixture builder seeded/idempotent Task 8. ✅
- §11 provenance (raw data READMEs): **Plan 2** (this plan uses derived v0 fixtures, no new raw sources). ✅ by deferral.

**Known deferrals (explicitly scoped to Plan 2 — calibration):** real β estimation (system-GMM, 500+ DiD, OOS gate); raw-data ingestion + READMEs; exact ι=1 ≡ innovation_hub acceptance test; binding budget envelope; plausibility/extrapolation flags beyond URL clamping.

**Placeholder scan:** No TBD/TODO; every code step shows complete code; all test steps include real assertions.

**Type consistency:** `LeverVector`, `Elasticities`, `CountyPrimitive`, `ScenarioResult` defined once in Task 2 and used unchanged in Tasks 3–13. `applyScenario` signature in Task 7 matches its call site in Task 12. `structuralRamp`/`perpetualInventory`/`capitalFlows`/`regimeSign` exported in Task 3 and imported in Task 7. `computeHDI` signature in Task 4 matches its Task-7 call. `DashboardData` extension in Task 9 matches PolicyLab's reads in Task 12.

---

## Follow-up: Plan 2 (to be written separately)

**Calibration pipeline** — replaces the v0 provisional fixtures with empirically-estimated coefficients:
- `scripts/calibration/A2_fert_did.R` (Rodzina 500+ DiD → β_fert)
- `scripts/calibration/A3_convergence_gmm.R` (system-GMM → β_K_hub, β_K_sat)
- `scripts/calibration/A1_estimate_elasticities.py` (orchestrate; β_gov, β_mig, β_edu, γ, λ; write calibrated `elasticities.json` with `provisional: false`)
- `scripts/calibration/A4_oos_validation.py` (PL pre/post-2010 RMSE gate)
- `data/raw/{qog_eqi,gus_500plus,espon_access,pl_minfin}/README.md` (provenance per CLAUDE.md)
- Calibration acceptance tests (sign, magnitude-vs-literature, OOS RMSE, exact ι=1 ≡ innovation_hub).
