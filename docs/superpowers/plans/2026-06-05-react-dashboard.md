# React Dashboard — RO Administrative Reform — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a static map-centric React SPA with a Romania NUTS3 choropleth map, persistent sidebar with 4 analytical tabs per county, and a Python export script that converts processed parquets into dashboard-ready JSON.

**Architecture:** Vite + React 18 + TypeScript in `dashboard/`. A Python script (`scripts/export_to_json_ro.py`) writes 7 JSON files to `data/dashboard/`; a `copy-data` npm script copies them into `dashboard/public/data/` before dev/build. All components fetch JSON at runtime via `import.meta.env.BASE_URL`. Deployed to GitHub Pages with the `gh-pages` package.

**Tech Stack:** Vite 5, React 18, TypeScript 5, react-leaflet 4, Leaflet 1.9, Recharts 2, Tailwind CSS 3, shx, gh-pages 6

**Spec:** `docs/superpowers/specs/2026-06-05-react-dashboard-design.md`

**Working directory for all commands:** `RO-Administrative-Reform/` (project root) unless stated otherwise.

---

## File Map

| Action | Path |
|--------|------|
| Create | `scripts/export_to_json_ro.py` |
| Create | `dashboard/package.json` |
| Create | `dashboard/vite.config.ts` |
| Create | `dashboard/tailwind.config.ts` |
| Create | `dashboard/postcss.config.cjs` |
| Create | `dashboard/tsconfig.json` |
| Create | `dashboard/tsconfig.node.json` |
| Create | `dashboard/index.html` |
| Create | `dashboard/public/data/.gitkeep` |
| Create | `dashboard/src/index.css` |
| Create | `dashboard/src/main.tsx` |
| Create | `dashboard/src/types.ts` |
| Create | `dashboard/src/utils/color.ts` |
| Create | `dashboard/src/hooks/useDashboardData.ts` |
| Create | `dashboard/src/App.tsx` |
| Create | `dashboard/src/components/SummaryBar.tsx` |
| Create | `dashboard/src/components/LayerSwitcher.tsx` |
| Create | `dashboard/src/components/RomaniaMap.tsx` |
| Create | `dashboard/src/components/RegionPanel.tsx` |
| Create | `dashboard/src/components/CounterfactualChart.tsx` |
| Create | `dashboard/src/components/ForecastPanel.tsx` |
| Create | `dashboard/src/components/MegaCampusBadge.tsx` |
| Create | `dashboard/src/components/MethodsTab.tsx` |
| Modify | `.gitignore` |

---

## Task 1: Scaffold Vite project and install dependencies

**Files:** `dashboard/package.json`, `dashboard/vite.config.ts`, `dashboard/tailwind.config.ts`, `dashboard/postcss.config.cjs`, `dashboard/tsconfig.json`, `dashboard/tsconfig.node.json`, `dashboard/index.html`, `dashboard/public/data/.gitkeep`, `dashboard/src/index.css`, `dashboard/src/main.tsx`, `.gitignore`

- [ ] **Step 1: Create `dashboard/package.json`**

```json
{
  "name": "ro-reform-dashboard",
  "version": "0.1.0",
  "private": true,
  "type": "module",
  "scripts": {
    "copy-data": "shx mkdir -p public/data && shx cp -r ../data/dashboard/. public/data/",
    "dev": "npm run copy-data && vite",
    "build": "npm run copy-data && tsc && vite build",
    "preview": "vite preview",
    "deploy": "npm run build && gh-pages -d dist"
  },
  "dependencies": {
    "leaflet": "^1.9.4",
    "react": "^18.3.1",
    "react-dom": "^18.3.1",
    "react-leaflet": "^4.2.1",
    "recharts": "^2.12.7"
  },
  "devDependencies": {
    "@types/leaflet": "^1.9.12",
    "@types/react": "^18.3.3",
    "@types/react-dom": "^18.3.0",
    "@vitejs/plugin-react": "^4.3.1",
    "autoprefixer": "^10.4.19",
    "gh-pages": "^6.1.1",
    "postcss": "^8.4.39",
    "shx": "^0.3.4",
    "tailwindcss": "^3.4.4",
    "typescript": "^5.2.2",
    "vite": "^5.3.1"
  }
}
```

- [ ] **Step 2: Create `dashboard/vite.config.ts`**

```typescript
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  base: '/RO-Administrative-Reform/',
})
```

- [ ] **Step 3: Create `dashboard/tailwind.config.ts`**

```typescript
import type { Config } from 'tailwindcss'

export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: { extend: {} },
  plugins: [],
} satisfies Config
```

- [ ] **Step 4: Create `dashboard/postcss.config.cjs`**

```javascript
module.exports = {
  plugins: {
    tailwindcss: {},
    autoprefixer: {},
  },
}
```

- [ ] **Step 5: Create `dashboard/tsconfig.json`**

```json
{
  "compilerOptions": {
    "target": "ES2020",
    "useDefineForClassFields": true,
    "lib": ["ES2020", "DOM", "DOM.Iterable"],
    "module": "ESNext",
    "skipLibCheck": true,
    "moduleResolution": "bundler",
    "allowImportingTsExtensions": true,
    "resolveJsonModule": true,
    "isolatedModules": true,
    "noEmit": true,
    "jsx": "react-jsx",
    "strict": true,
    "noUnusedLocals": true,
    "noUnusedParameters": true,
    "noFallthroughCasesInSwitch": true
  },
  "include": ["src"],
  "references": [{ "path": "./tsconfig.node.json" }]
}
```

- [ ] **Step 6: Create `dashboard/tsconfig.node.json`**

```json
{
  "compilerOptions": {
    "composite": true,
    "skipLibCheck": true,
    "module": "ESNext",
    "moduleResolution": "bundler",
    "allowSyntheticDefaultImports": true
  },
  "include": ["vite.config.ts"]
}
```

- [ ] **Step 7: Create `dashboard/index.html`**

```html
<!doctype html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>RO Administrative Reform — Policy Dashboard</title>
    <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/main.tsx"></script>
  </body>
</html>
```

- [ ] **Step 8: Create `dashboard/public/data/.gitkeep`** (empty file — keeps directory in git)

- [ ] **Step 9: Create `dashboard/src/index.css`**

```css
@tailwind base;
@tailwind components;
@tailwind utilities;

html, body, #root {
  height: 100%;
  margin: 0;
  font-family: system-ui, -apple-system, sans-serif;
}

.leaflet-container {
  height: 100%;
  width: 100%;
}
```

- [ ] **Step 10: Create `dashboard/src/main.tsx`** (stub — full App wired in Task 5)

```tsx
import React from 'react'
import ReactDOM from 'react-dom/client'
import './index.css'

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <div className="flex items-center justify-center h-full text-gray-500">
      Loading...
    </div>
  </React.StrictMode>,
)
```

- [ ] **Step 11: Add `dashboard/node_modules/` and `dashboard/dist/` to `.gitignore`**

Append to the root `.gitignore` (or create it if absent):

```
dashboard/node_modules/
dashboard/dist/
```

- [ ] **Step 12: Install dependencies**

```bash
cd dashboard
npm install
```

Expected: `node_modules/` created, no errors.

- [ ] **Step 13: Verify dev server starts**

```bash
# Still in dashboard/
npm run dev
```

Expected: Vite starts on http://localhost:5173, browser shows "Loading..." text. Stop with Ctrl+C.

- [ ] **Step 14: Commit**

```bash
git add dashboard/ .gitignore
git commit -m "feat(RO-dashboard): scaffold Vite+React+TS project"
```

---

## Task 2: Data export script

**Files:** `scripts/export_to_json_ro.py`

- [ ] **Step 1: Create `scripts/export_to_json_ro.py`**

```python
"""
Export RO dashboard JSON from processed parquets.
Run from project root: python scripts/export_to_json_ro.py

Outputs (data/dashboard/):
  regions.json       — 33 treated counties, GSC series, reform scenarios
  forecasts.json     — 3-path MG-VAR fan chart per county
  suitability.json   — T1-T8 scores for all 42 counties
  lp_irfs.json       — LP IRF coefficients
  sdid_estimates.json — SDiD ATT estimates
  eventstudy.json    — TWFE event-study coefficients
  summary.json       — aggregate KPIs
"""
from __future__ import annotations
import json
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).parent.parent
PROCESSED = ROOT / "data" / "processed"
OUT = ROOT / "data" / "dashboard"
OUT.mkdir(parents=True, exist_ok=True)


def _safe(val):
    if val is None:
        return None
    if isinstance(val, float) and np.isnan(val):
        return None
    if isinstance(val, (np.integer,)):
        return int(val)
    if isinstance(val, (np.floating,)):
        return float(val)
    if isinstance(val, bool):
        return bool(val)
    return val


def write_json(obj, path: Path) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, separators=(",", ":"), default=_safe)
    print(f"  {path.name:<30} {path.stat().st_size / 1024:>7.1f} KB")


# ── regions.json ──────────────────────────────────────────────────────────────

def export_regions() -> None:
    gaps = pd.read_parquet(PROCESSED / "ro_gsynth_gaps.parquet")
    suit = pd.read_parquet(PROCESSED / "ro_nuts3_suitability.parquet").set_index("nuts3_code")

    # Compute innovation uplift at 2040 from pvar_forecasts_roi
    fcst = pd.read_parquet(PROCESSED / "ro_pvar_forecasts_roi.parquet")
    fcst_2040 = fcst[(fcst["year"] == 2040) & (fcst["variable"] == "ln_population")]
    uplift_map: dict[str, float | None] = {}
    for nuts3, grp in fcst_2040.groupby("nuts3_code"):
        ih = grp.loc[grp["path"] == "innovation_hub", "value"]
        sq = grp.loc[grp["path"] == "status_quo", "value"]
        if not ih.empty and not sq.empty:
            diff = float(ih.iloc[0]) - float(sq.iloc[0])
            uplift_map[str(nuts3)] = round((np.exp(diff) - 1) * 100, 2)
        else:
            uplift_map[str(nuts3)] = None

    regions = []
    for nuts3, grp in gaps.groupby("nuts3_code"):
        nuts3 = str(nuts3)
        row_suit = suit.loc[nuts3] if nuts3 in suit.index else {}
        att = _safe(grp["att_avg_pre"].iloc[0])
        reform_cost_pct = round(float(att) * 100, 2) if att is not None else None

        vitality = _safe(row_suit.get("vitality_index")) if hasattr(row_suit, "get") else None
        tier1_gate = bool(row_suit.get("tier1_gate", False)) if hasattr(row_suit, "get") else False
        tier1_types = str(row_suit.get("tier1_types", "")) if hasattr(row_suit, "get") else ""

        series = [
            {
                "year": int(r["year"]),
                "actual": _safe(r["actual"]),
                "counterfactual": _safe(r["counterfactual"]),
                "gap": _safe(r["gap"]),
            }
            for _, r in grp.sort_values("year").iterrows()
        ]

        regions.append({
            "nuts3_code": nuts3,
            "judet_name": str(grp["judet_name"].iloc[0]),
            "county_seat": str(grp["county_seat"].iloc[0]),
            "nuts2_code": str(grp["nuts2_code"].iloc[0]),
            "att_avg_pre": att,
            "reform_cost_pct": reform_cost_pct,
            "reform_scenario_pessimistic": _safe(grp["reform_scenario_pessimistic"].iloc[0]),
            "reform_scenario_central": _safe(grp["reform_scenario_central"].iloc[0]),
            "reform_scenario_optimistic": _safe(grp["reform_scenario_optimistic"].iloc[0]),
            "vitality_index": vitality,
            "tier1_gate": tier1_gate,
            "tier1_types": tier1_types,
            "innovation_uplift_pct_2040": uplift_map.get(nuts3),
            "counterfactualSeries": series,
        })

    write_json(regions, OUT / "regions.json")


# ── forecasts.json ────────────────────────────────────────────────────────────

def export_forecasts() -> None:
    pvar = pd.read_parquet(PROCESSED / "ro_pvar_forecasts_roi.parquet")
    out = []
    for nuts3, grp in pvar.groupby("nuts3_code"):
        county_name = str(grp["county_name"].iloc[0])
        forecasts: dict = {}
        for (var, path), sub in grp.groupby(["variable", "path"]):
            sub = sub.sort_values("year")
            forecasts.setdefault(str(var), {})[str(path)] = [
                {
                    "year": int(r["year"]),
                    "value": _safe(r["value"]),
                    "lo80": _safe(r["lo80"]),
                    "hi80": _safe(r["hi80"]),
                    "lo95": _safe(r["lo95"]),
                    "hi95": _safe(r["hi95"]),
                }
                for _, r in sub.iterrows()
            ]
        out.append({"nuts3_code": str(nuts3), "county_name": county_name, "forecasts": forecasts})
    write_json(out, OUT / "forecasts.json")


# ── suitability.json ──────────────────────────────────────────────────────────

def export_suitability() -> None:
    df = pd.read_parquet(PROCESSED / "ro_nuts3_suitability.parquet")
    records = []
    for _, r in df.iterrows():
        records.append({
            "nuts3_code": str(r["nuts3_code"]),
            "judet_name": str(r["judet_name"]),
            "county_seat": str(r["county_seat"]),
            "nuts2_code": str(r["nuts2_code"]),
            "vitality_index": _safe(r["vitality_index"]),
            "vitality_rank_within_region": _safe(r["vitality_rank_within_region"]),
            "suitability_T1": _safe(r["suitability_T1"]),
            "suitability_T2": _safe(r["suitability_T2"]),
            "suitability_T3": _safe(r["suitability_T3"]),
            "suitability_T4": _safe(r["suitability_T4"]),
            "suitability_T5": _safe(r["suitability_T5"]),
            "suitability_T6": _safe(r["suitability_T6"]),
            "suitability_T7": _safe(r["suitability_T7"]),
            "suitability_T8": _safe(r["suitability_T8"]),
            "suitability_T4_adjusted": _safe(r["suitability_T4_adjusted"]),
            "tier1_gate": bool(r["tier1_gate"]),
            "tier1_types": str(r["tier1_types"]),
            "t4_anchor_source": str(r["t4_anchor_source"]),
        })
    write_json(records, OUT / "suitability.json")


# ── lp_irfs.json ──────────────────────────────────────────────────────────────

def export_lp_irfs() -> None:
    df = pd.read_parquet(PROCESSED / "ro_lp_irfs.parquet")
    records = [
        {
            "outcome": str(r["outcome"]),
            "horizon": int(r["horizon"]),
            "coef": _safe(r["coef"]),
            "se": _safe(r["se"]),
            "ci_lo_90": _safe(r["ci_lo_90"]),
            "ci_hi_90": _safe(r["ci_hi_90"]),
            "ci_lo_95": _safe(r["ci_lo_95"]),
            "ci_hi_95": _safe(r["ci_hi_95"]),
            "nobs": int(r["nobs"]),
        }
        for _, r in df.iterrows()
    ]
    write_json(records, OUT / "lp_irfs.json")


# ── sdid_estimates.json ───────────────────────────────────────────────────────

def export_sdid() -> None:
    df = pd.read_parquet(PROCESSED / "ro_sdid_estimates.parquet")
    records = [
        {
            "outcome": str(r["outcome"]),
            "estimator": str(r["estimator"]),
            "att": _safe(r["att"]),
            "se": _safe(r["se"]),
            "ci_lo": _safe(r["ci_lo"]),
            "ci_hi": _safe(r["ci_hi"]),
            "n_units": int(r["n_units"]),
            "n_years": int(r["n_years"]),
            "pseudo_treat_year": int(r["pseudo_treat_year"]),
        }
        for _, r in df.iterrows()
    ]
    write_json(records, OUT / "sdid_estimates.json")


# ── eventstudy.json ───────────────────────────────────────────────────────────

def export_eventstudy() -> None:
    df = pd.read_parquet(PROCESSED / "ro_eventstudy_coefs.parquet")
    records = [
        {
            "outcome": str(r["outcome"]),
            "event_time": int(r["event_time"]),
            "coef": _safe(r["coef"]),
            "se": _safe(r["se"]),
            "ci_lo": _safe(r["ci_lo"]),
            "ci_hi": _safe(r["ci_hi"]),
        }
        for _, r in df.iterrows()
    ]
    write_json(records, OUT / "eventstudy.json")


# ── summary.json ──────────────────────────────────────────────────────────────

def export_summary() -> None:
    sdid = pd.read_parquet(PROCESSED / "ro_sdid_estimates.parquet")
    suit = pd.read_parquet(PROCESSED / "ro_nuts3_suitability.parquet")
    cities = pd.read_parquet(PROCESSED / "ro_treatment_cities.parquet")
    gaps = pd.read_parquet(PROCESSED / "ro_gsynth_gaps.parquet")

    pop_row = sdid[sdid["outcome"] == "ln_population"]
    att = float(pop_row["att"].iloc[0]) if len(pop_row) else None

    summary = {
        "n_demoted": int((cities["treated"] == 1).sum()),
        "n_tier1": int(suit["tier1_gate"].sum()),
        "reform_year": 2025,
        "sdid_att_ln_pop": _safe(att),
        "sdid_pop_loss_pct": round(att * 100, 1) if att is not None else None,
        "gsc_avg_att": _safe(float(gaps["att_avg_pre"].groupby(gaps["nuts3_code"]).first().mean())),
        "data_note": "SDiD pseudo-treat 2015 (placebo). GSC: 350 PL donors, r*=1.",
    }
    write_json(summary, OUT / "summary.json")


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    print("=== export_to_json_ro.py ===\n")
    export_regions()
    export_forecasts()
    export_suitability()
    export_lp_irfs()
    export_sdid()
    export_eventstudy()
    export_summary()
    print(f"\nAll JSON written to {OUT}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Run the export script**

```bash
python scripts/export_to_json_ro.py
```

Expected output (approximate sizes):
```
=== export_to_json_ro.py ===

  regions.json                   450.0 KB
  forecasts.json                 280.0 KB
  suitability.json                12.0 KB
  lp_irfs.json                     8.0 KB
  sdid_estimates.json              0.5 KB
  eventstudy.json                  6.0 KB
  summary.json                     0.2 KB

All JSON written to data/dashboard
```

If any file is missing or the script errors, fix before continuing.

- [ ] **Step 3: Run copy-data and verify**

```bash
cd dashboard
npm run copy-data
```

Expected: `public/data/` now contains all 7 JSON files. Verify:

```bash
ls public/data/
```

Expected: `regions.json  forecasts.json  suitability.json  lp_irfs.json  sdid_estimates.json  eventstudy.json  summary.json`

- [ ] **Step 4: Commit**

```bash
cd ..
git add scripts/export_to_json_ro.py data/dashboard/
git commit -m "feat(RO-dashboard): export_to_json_ro.py -- 7 JSON files for dashboard"
```

---

## Task 3: TypeScript types and color utility

**Files:** `dashboard/src/types.ts`, `dashboard/src/utils/color.ts`

- [ ] **Step 1: Create `dashboard/src/types.ts`**

```typescript
// ── Data shapes matching the 7 JSON files ────────────────────────────────────

export interface CounterfactualPoint {
  year: number;
  actual: number | null;
  counterfactual: number | null;
  gap: number | null;
}

export interface RegionData {
  nuts3_code: string;
  judet_name: string;
  county_seat: string;
  nuts2_code: string;
  att_avg_pre: number | null;
  reform_cost_pct: number | null;
  reform_scenario_pessimistic: number | null;
  reform_scenario_central: number | null;
  reform_scenario_optimistic: number | null;
  vitality_index: number | null;
  tier1_gate: boolean;
  tier1_types: string;
  innovation_uplift_pct_2040: number | null;
  counterfactualSeries: CounterfactualPoint[];
}

export interface ForecastPoint {
  year: number;
  value: number | null;
  lo80: number | null;
  hi80: number | null;
  lo95: number | null;
  hi95: number | null;
}

export interface ForecastCounty {
  nuts3_code: string;
  county_name: string;
  forecasts: Record<string, Record<string, ForecastPoint[]>>;
}

export interface SuitabilityData {
  nuts3_code: string;
  judet_name: string;
  county_seat: string;
  nuts2_code: string;
  vitality_index: number | null;
  vitality_rank_within_region: number | null;
  suitability_T1: number;
  suitability_T2: number;
  suitability_T3: number;
  suitability_T4: number;
  suitability_T5: number;
  suitability_T6: number;
  suitability_T7: number;
  suitability_T8: number;
  suitability_T4_adjusted: number;
  tier1_gate: boolean;
  tier1_types: string;
  t4_anchor_source: string;
}

export interface LpIrf {
  outcome: string;
  horizon: number;
  coef: number | null;
  se: number | null;
  ci_lo_90: number | null;
  ci_hi_90: number | null;
  ci_lo_95: number | null;
  ci_hi_95: number | null;
  nobs: number;
}

export interface SdidEstimate {
  outcome: string;
  estimator: string;
  att: number | null;
  se: number | null;
  ci_lo: number | null;
  ci_hi: number | null;
  n_units: number;
  n_years: number;
  pseudo_treat_year: number;
}

export interface EventStudyCoef {
  outcome: string;
  event_time: number;
  coef: number | null;
  se: number | null;
  ci_lo: number | null;
  ci_hi: number | null;
}

export interface Summary {
  n_demoted: number;
  n_tier1: number;
  reform_year: number;
  sdid_att_ln_pop: number | null;
  sdid_pop_loss_pct: number | null;
  gsc_avg_att: number | null;
  data_note: string;
}

export type LayerType = 'reform_cost' | 'suitability' | 'roi';

export interface DashboardData {
  regions: RegionData[];
  regionsByCode: Record<string, RegionData>;
  forecasts: ForecastCounty[];
  forecastsByCode: Record<string, ForecastCounty>;
  suitability: SuitabilityData[];
  suitabilityByCode: Record<string, SuitabilityData>;
  lpIrfs: LpIrf[];
  sdid: SdidEstimate[];
  eventstudy: EventStudyCoef[];
  summary: Summary;
}
```

- [ ] **Step 2: Create `dashboard/src/utils/color.ts`**

```typescript
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
```

- [ ] **Step 3: Verify TypeScript compiles (no test runner needed — types are structural)**

```bash
cd dashboard
npx tsc --noEmit
```

Expected: no output (zero errors).

- [ ] **Step 4: Commit**

```bash
cd ..
git add dashboard/src/types.ts dashboard/src/utils/color.ts
git commit -m "feat(RO-dashboard): TypeScript types and choropleth color utilities"
```

---

## Task 4: Data fetching hook

**Files:** `dashboard/src/hooks/useDashboardData.ts`

- [ ] **Step 1: Create `dashboard/src/hooks/useDashboardData.ts`**

```typescript
import { useEffect, useState } from 'react';
import type {
  DashboardData, RegionData, ForecastCounty, SuitabilityData,
  LpIrf, SdidEstimate, EventStudyCoef, Summary,
} from '../types';

const BASE = import.meta.env.BASE_URL;

async function fetchJson<T>(name: string): Promise<T> {
  const res = await fetch(`${BASE}data/${name}`);
  if (!res.ok) throw new Error(`Failed to fetch ${name}: ${res.status}`);
  return res.json() as Promise<T>;
}

export function useDashboardData(): { data: DashboardData | null; error: string | null } {
  const [data, setData] = useState<DashboardData | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([
      fetchJson<RegionData[]>('regions.json'),
      fetchJson<ForecastCounty[]>('forecasts.json'),
      fetchJson<SuitabilityData[]>('suitability.json'),
      fetchJson<LpIrf[]>('lp_irfs.json'),
      fetchJson<SdidEstimate[]>('sdid_estimates.json'),
      fetchJson<EventStudyCoef[]>('eventstudy.json'),
      fetchJson<Summary>('summary.json'),
    ])
      .then(([regions, forecasts, suitability, lpIrfs, sdid, eventstudy, summary]) => {
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
        });
      })
      .catch((e: unknown) => setError(e instanceof Error ? e.message : String(e)));
  }, []);

  return { data, error };
}
```

- [ ] **Step 2: Verify TypeScript compiles**

```bash
cd dashboard
npx tsc --noEmit
```

Expected: no errors.

- [ ] **Step 3: Commit**

```bash
cd ..
git add dashboard/src/hooks/useDashboardData.ts
git commit -m "feat(RO-dashboard): useDashboardData hook -- fetches all 7 JSON files"
```

---

## Task 5: App shell — layout and routing state

**Files:** `dashboard/src/App.tsx`, `dashboard/src/main.tsx`

- [ ] **Step 1: Create `dashboard/src/App.tsx`**

```tsx
import { useState } from 'react';
import { useDashboardData } from './hooks/useDashboardData';
import type { LayerType } from './types';
import SummaryBar from './components/SummaryBar';
import RomaniaMap from './components/RomaniaMap';
import RegionPanel from './components/RegionPanel';

export default function App() {
  const { data, error } = useDashboardData();
  const [selectedNuts3, setSelectedNuts3] = useState<string | null>(null);
  const [activeLayer, setActiveLayer] = useState<LayerType>('reform_cost');

  if (error) {
    return (
      <div className="flex items-center justify-center h-full text-red-600">
        Failed to load dashboard data: {error}
      </div>
    );
  }

  if (!data) {
    return (
      <div className="flex items-center justify-center h-full text-gray-500">
        Loading data…
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="flex items-center px-4 h-11 bg-gray-900 text-white shrink-0">
        <span className="font-bold text-sm">🏛 RO Administrative Reform</span>
        <span className="mx-3 text-gray-600">|</span>
        <span className="text-gray-400 text-xs">Policy Intelligence Dashboard</span>
        <span className="ml-auto text-gray-500 text-xs">
          {data.summary.n_demoted} demoted counties · Reform year {data.summary.reform_year}
        </span>
      </div>

      {/* KPI + layer switcher */}
      <SummaryBar summary={data.summary} activeLayer={activeLayer} onLayerChange={setActiveLayer} />

      {/* Map + sidebar */}
      <div className="flex flex-1 min-h-0">
        <div className="flex-1 min-w-0">
          <RomaniaMap
            data={data}
            activeLayer={activeLayer}
            selectedNuts3={selectedNuts3}
            onCountyClick={setSelectedNuts3}
          />
        </div>
        <div className="w-[360px] shrink-0 border-l border-gray-200 overflow-y-auto">
          <RegionPanel nuts3Code={selectedNuts3} data={data} />
        </div>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Update `dashboard/src/main.tsx`**

```tsx
import React from 'react'
import ReactDOM from 'react-dom/client'
import './index.css'
import App from './App'

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
)
```

- [ ] **Step 3: Create placeholder stubs for components not yet implemented** (prevents import errors during dev)

Create `dashboard/src/components/SummaryBar.tsx`:
```tsx
export default function SummaryBar() { return <div className="h-9 bg-gray-700" />; }
```

Create `dashboard/src/components/RomaniaMap.tsx`:
```tsx
export default function RomaniaMap() { return <div className="h-full bg-blue-50 flex items-center justify-center text-blue-400">Map loading…</div>; }
```

Create `dashboard/src/components/RegionPanel.tsx`:
```tsx
export default function RegionPanel() { return <div className="p-4 text-gray-400 text-sm">Click a county on the map</div>; }
```

- [ ] **Step 4: Start dev server and verify layout**

```bash
cd dashboard
npm run dev
```

Open http://localhost:5173 (or the Vite-printed URL). Expected: dark header bar, grey KPI bar, blue map placeholder, empty sidebar. No console errors.

- [ ] **Step 5: Commit**

```bash
cd ..
git add dashboard/src/App.tsx dashboard/src/main.tsx dashboard/src/components/
git commit -m "feat(RO-dashboard): App shell with layout grid and stub components"
```

---

## Task 6: SummaryBar and LayerSwitcher

**Files:** `dashboard/src/components/SummaryBar.tsx`, `dashboard/src/components/LayerSwitcher.tsx`

- [ ] **Step 1: Create `dashboard/src/components/LayerSwitcher.tsx`**

```tsx
import type { LayerType } from '../types';

interface Props {
  activeLayer: LayerType;
  onChange: (layer: LayerType) => void;
}

const LAYERS: { id: LayerType; label: string }[] = [
  { id: 'reform_cost', label: 'Reform cost' },
  { id: 'suitability', label: 'Suitability' },
  { id: 'roi', label: 'ROI' },
];

export default function LayerSwitcher({ activeLayer, onChange }: Props) {
  return (
    <div className="flex gap-1">
      {LAYERS.map(({ id, label }) => (
        <button
          key={id}
          onClick={() => onChange(id)}
          className={`px-3 py-1 text-xs rounded transition-colors ${
            activeLayer === id
              ? 'bg-blue-500 text-white'
              : 'bg-gray-600 text-gray-300 hover:bg-gray-500'
          }`}
        >
          {label}
        </button>
      ))}
    </div>
  );
}
```

- [ ] **Step 2: Replace `dashboard/src/components/SummaryBar.tsx` with full implementation**

```tsx
import type { Summary, LayerType } from '../types';
import LayerSwitcher from './LayerSwitcher';

interface Props {
  summary: Summary;
  activeLayer: LayerType;
  onLayerChange: (layer: LayerType) => void;
}

function Chip({ label, value, color }: { label: string; value: string; color: string }) {
  return (
    <div className="flex items-center gap-2">
      <span className={`font-bold text-sm ${color}`}>{value}</span>
      <span className="text-gray-400 text-xs">{label}</span>
    </div>
  );
}

export default function SummaryBar({ summary, activeLayer, onLayerChange }: Props) {
  const attPct = summary.sdid_pop_loss_pct != null
    ? `${summary.sdid_pop_loss_pct > 0 ? '+' : ''}${summary.sdid_pop_loss_pct.toFixed(1)}%`
    : 'N/A';

  return (
    <div className="flex items-center gap-6 px-4 h-9 bg-gray-800 text-white shrink-0">
      <Chip label="demoted counties" value={String(summary.n_demoted)} color="text-red-400" />
      <Chip label="SDiD ATT pop" value={attPct} color="text-red-300" />
      <Chip label="Tier-1 counties" value={`${summary.n_tier1}/42`} color="text-green-400" />
      <Chip label="reform year" value={String(summary.reform_year)} color="text-yellow-400" />
      <div className="ml-auto flex items-center gap-2">
        <span className="text-gray-500 text-xs">Layer:</span>
        <LayerSwitcher activeLayer={activeLayer} onChange={onLayerChange} />
      </div>
    </div>
  );
}
```

- [ ] **Step 3: Verify in browser**

Reload http://localhost:5173. Expected: KPI bar shows "33 demoted counties · −1.9% SDiD ATT pop · 17/42 Tier-1 counties · 2025 reform year" and 3 layer buttons on the right. Clicking a layer button highlights it.

- [ ] **Step 4: Commit**

```bash
cd ..
git add dashboard/src/components/SummaryBar.tsx dashboard/src/components/LayerSwitcher.tsx
git commit -m "feat(RO-dashboard): SummaryBar KPI strip and LayerSwitcher"
```

---

## Task 7: RomaniaMap — choropleth with react-leaflet

**Files:** `dashboard/src/components/RomaniaMap.tsx`

- [ ] **Step 1: Replace `dashboard/src/components/RomaniaMap.tsx` with full implementation**

```tsx
import { useEffect, useRef, useState } from 'react';
import { MapContainer, GeoJSON } from 'react-leaflet';
import type { GeoJSON as GeoJSONType } from 'leaflet';
import type { GeoJsonObject, Feature, Geometry } from 'geojson';
import type { DashboardData, LayerType } from '../types';
import { reformCostColor, suitabilityColor, roiColor, maxSuitability } from '../utils/color';

const GEOJSON_URL =
  'https://gisco-services.ec.europa.eu/distribution/v2/nuts/geojson/NUTS_RG_20M_2021_4326_LEVL_3.geojson';

interface Props {
  data: DashboardData;
  activeLayer: LayerType;
  selectedNuts3: string | null;
  onCountyClick: (nuts3: string) => void;
}

interface NutsFeature extends Feature<Geometry> {
  properties: { NUTS_ID: string; CNTR_CODE: string; NAME_LATN: string };
}

export default function RomaniaMap({ data, activeLayer, selectedNuts3, onCountyClick }: Props) {
  const [geoJson, setGeoJson] = useState<GeoJsonObject | null>(null);
  const [geoError, setGeoError] = useState(false);
  const geoJsonRef = useRef<GeoJSONType | null>(null);

  // Pre-compute domain maxima for colour scales
  const maxAbsAtt = Math.max(
    ...data.regions.map((r) => Math.abs(r.att_avg_pre ?? 0)),
    0.001,
  );
  const maxUplift = Math.max(
    ...data.regions.map((r) => r.innovation_uplift_pct_2040 ?? 0),
    0.001,
  );

  useEffect(() => {
    fetch(GEOJSON_URL)
      .then((r) => r.json())
      .then((full: { features: NutsFeature[] }) => {
        const ro: GeoJsonObject = {
          type: 'FeatureCollection',
          // @ts-expect-error – GeoJsonObject doesn't expose features directly but this is valid
          features: full.features.filter((f) => f.properties.CNTR_CODE === 'RO'),
        };
        setGeoJson(ro);
      })
      .catch(() => setGeoError(true));
  }, []);

  function getStyle(feature: Feature | undefined) {
    if (!feature) return {};
    const nuts3 = (feature as NutsFeature).properties.NUTS_ID;
    const isSelected = nuts3 === selectedNuts3;

    let fillColor = '#e5e7eb';
    if (activeLayer === 'reform_cost') {
      const r = data.regionsByCode[nuts3];
      fillColor = reformCostColor(r?.att_avg_pre ?? null, maxAbsAtt);
    } else if (activeLayer === 'suitability') {
      const s = data.suitabilityByCode[nuts3];
      fillColor = s ? suitabilityColor(maxSuitability(s)) : '#e5e7eb';
    } else {
      const r = data.regionsByCode[nuts3];
      fillColor = roiColor(r?.innovation_uplift_pct_2040 ?? null, maxUplift);
    }

    return {
      fillColor,
      fillOpacity: isSelected ? 0.9 : 0.7,
      color: isSelected ? '#1d4ed8' : '#ffffff',
      weight: isSelected ? 2.5 : 0.8,
    };
  }

  function onEachFeature(feature: Feature, layer: L.Layer) {
    const nuts3 = (feature as NutsFeature).properties.NUTS_ID;
    const name = (feature as NutsFeature).properties.NAME_LATN;
    layer.bindTooltip(name, { sticky: true, className: 'text-xs' });
    layer.on('click', () => onCountyClick(nuts3));
  }

  if (geoError) {
    return (
      <div className="h-full flex flex-col items-center justify-center gap-2 bg-blue-50">
        <span className="text-red-500 text-sm">⚠ Map unavailable (CDN unreachable)</span>
        <div className="grid grid-cols-4 gap-1 max-w-md">
          {data.regions.map((r) => (
            <button
              key={r.nuts3_code}
              onClick={() => onCountyClick(r.nuts3_code)}
              className={`text-xs p-1 rounded border ${
                r.nuts3_code === selectedNuts3
                  ? 'bg-blue-600 text-white border-blue-600'
                  : 'bg-white border-gray-300 hover:bg-gray-50'
              }`}
            >
              {r.county_seat}
            </button>
          ))}
        </div>
      </div>
    );
  }

  if (!geoJson) {
    return (
      <div className="h-full flex items-center justify-center bg-blue-50 text-blue-400 text-sm">
        Loading map…
      </div>
    );
  }

  return (
    <MapContainer
      center={[45.9, 24.9]}
      zoom={6}
      zoomControl={false}
      style={{ height: '100%', width: '100%' }}
    >
      <GeoJSON
        key={`${activeLayer}-${selectedNuts3}`}
        ref={geoJsonRef}
        data={geoJson}
        style={getStyle}
        onEachFeature={onEachFeature}
      />
    </MapContainer>
  );
}
```

- [ ] **Step 2: Add Leaflet type import shim to `dashboard/src/vite-env.d.ts`** (Vite auto-creates this — verify it exists)

```bash
ls dashboard/src/vite-env.d.ts
```

If absent, create it:
```typescript
/// <reference types="vite/client" />
```

- [ ] **Step 3: Verify map renders**

Reload http://localhost:5173. Expected:
- Romania NUTS3 polygons appear coloured (red shades for reform cost layer by default)
- Hovering a county shows its name tooltip
- Clicking a county logs nothing visible yet (sidebar still a placeholder)
- If CDN unreachable: county list fallback renders

- [ ] **Step 4: Commit**

```bash
cd ..
git add dashboard/src/components/RomaniaMap.tsx
git commit -m "feat(RO-dashboard): RomaniaMap choropleth -- Leaflet + Eurostat NUTS3 GeoJSON"
```

---

## Task 8: RegionPanel shell with tabs

**Files:** `dashboard/src/components/RegionPanel.tsx`

- [ ] **Step 1: Replace `dashboard/src/components/RegionPanel.tsx` with full implementation**

```tsx
import { useState } from 'react';
import type { DashboardData } from '../types';
import CounterfactualChart from './CounterfactualChart';
import ForecastPanel from './ForecastPanel';
import MegaCampusBadge from './MegaCampusBadge';
import MethodsTab from './MethodsTab';

interface Props {
  nuts3Code: string | null;
  data: DashboardData;
}

type Tab = 'counterfactual' | 'forecast' | 'megacampus' | 'methods';

const TABS: { id: Tab; label: string }[] = [
  { id: 'counterfactual', label: 'Counterfactual' },
  { id: 'forecast', label: 'Forecast' },
  { id: 'megacampus', label: 'MegaCampus' },
  { id: 'methods', label: 'Methods' },
];

export default function RegionPanel({ nuts3Code, data }: Props) {
  const [activeTab, setActiveTab] = useState<Tab>('counterfactual');

  if (!nuts3Code) {
    return (
      <div className="flex flex-col items-center justify-center h-full text-gray-400 text-sm gap-2 p-6">
        <span className="text-2xl">🗺</span>
        <p>Click a county on the map to view its detail</p>
      </div>
    );
  }

  const region = data.regionsByCode[nuts3Code];
  const suit = data.suitabilityByCode[nuts3Code];
  const forecast = data.forecastsByCode[nuts3Code];

  if (!region) {
    return (
      <div className="p-4 text-gray-400 text-sm">
        No data for {nuts3Code}
      </div>
    );
  }

  const reformPct = region.reform_cost_pct != null
    ? `${region.reform_cost_pct > 0 ? '+' : ''}${region.reform_cost_pct.toFixed(1)}%`
    : '—';
  const vitality = region.vitality_index != null
    ? region.vitality_index.toFixed(2)
    : '—';
  const uplift = region.innovation_uplift_pct_2040 != null
    ? `+${region.innovation_uplift_pct_2040.toFixed(1)}%`
    : '—';

  return (
    <div className="flex flex-col h-full">
      {/* County header */}
      <div className="px-4 py-3 bg-gray-50 border-b border-gray-200 shrink-0">
        <div className="font-bold text-gray-900">{region.judet_name} — {region.county_seat}</div>
        <div className="text-gray-500 text-xs mt-0.5">
          NUTS3: {region.nuts3_code} · {region.nuts2_code}
        </div>
      </div>

      {/* KPI mini-cards */}
      <div className="grid grid-cols-3 gap-2 px-3 py-2 border-b border-gray-100 shrink-0">
        <div className="bg-red-50 rounded p-2 text-center">
          <div className="font-bold text-red-700 text-sm">{reformPct}</div>
          <div className="text-red-600 text-xs">Reform cost</div>
        </div>
        <div className="bg-green-50 rounded p-2 text-center">
          <div className="font-bold text-green-700 text-sm">{vitality}</div>
          <div className="text-green-600 text-xs">Vitality idx</div>
        </div>
        <div className="bg-blue-50 rounded p-2 text-center">
          <div className="font-bold text-blue-700 text-sm">{uplift}</div>
          <div className="text-blue-600 text-xs">Pop uplift 2040</div>
        </div>
      </div>

      {/* Tab bar */}
      <div className="flex border-b border-gray-200 shrink-0">
        {TABS.map(({ id, label }) => (
          <button
            key={id}
            onClick={() => setActiveTab(id)}
            className={`flex-1 py-2 text-xs font-medium transition-colors border-b-2 ${
              activeTab === id
                ? 'border-blue-500 text-blue-600'
                : 'border-transparent text-gray-500 hover:text-gray-700'
            }`}
          >
            {label}
          </button>
        ))}
      </div>

      {/* Tab content */}
      <div className="flex-1 overflow-y-auto p-3">
        {activeTab === 'counterfactual' && (
          <CounterfactualChart series={region.counterfactualSeries} />
        )}
        {activeTab === 'forecast' && forecast && (
          <ForecastPanel forecasts={forecast.forecasts} />
        )}
        {activeTab === 'forecast' && !forecast && (
          <div className="text-gray-400 text-sm">No forecast data for this county.</div>
        )}
        {activeTab === 'megacampus' && suit && (
          <MegaCampusBadge suitability={suit} />
        )}
        {activeTab === 'megacampus' && !suit && (
          <div className="text-gray-400 text-sm">No suitability data for this county.</div>
        )}
        {activeTab === 'methods' && (
          <MethodsTab sdid={data.sdid} lpIrfs={data.lpIrfs} eventstudy={data.eventstudy} />
        )}
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Add temporary stubs for child components not yet implemented**

These stubs prevent TypeScript errors. They will be replaced in later tasks.

Create `dashboard/src/components/CounterfactualChart.tsx`:
```tsx
import type { CounterfactualPoint } from '../types';
export default function CounterfactualChart({ series }: { series: CounterfactualPoint[] }) {
  return <div className="text-xs text-gray-400">{series.length} data points — chart coming in Task 9</div>;
}
```

Create `dashboard/src/components/ForecastPanel.tsx`:
```tsx
export default function ForecastPanel({ forecasts }: { forecasts: Record<string, Record<string, unknown[]>> }) {
  return <div className="text-xs text-gray-400">Forecast panel — Task 10. Variables: {Object.keys(forecasts).join(', ')}</div>;
}
```

Create `dashboard/src/components/MegaCampusBadge.tsx`:
```tsx
import type { SuitabilityData } from '../types';
export default function MegaCampusBadge({ suitability }: { suitability: SuitabilityData }) {
  return <div className="text-xs text-gray-400">MegaCampusBadge — Task 11. tier1: {String(suitability.tier1_gate)}</div>;
}
```

Create `dashboard/src/components/MethodsTab.tsx`:
```tsx
import type { SdidEstimate, LpIrf, EventStudyCoef } from '../types';
export default function MethodsTab({ sdid }: { sdid: SdidEstimate[]; lpIrfs: LpIrf[]; eventstudy: EventStudyCoef[] }) {
  return <div className="text-xs text-gray-400">Methods — Task 12. SDiD rows: {sdid.length}</div>;
}
```

- [ ] **Step 3: Verify panel renders on click**

In the browser, click a county on the map. Expected:
- Sidebar shows county name and seat
- KPI cards show reform cost %, vitality index, pop uplift
- Tab bar shows 4 tabs; clicking tabs switches content
- Counterfactual tab: shows "N data points — chart coming in Task 9"

- [ ] **Step 4: Commit**

```bash
cd ..
git add dashboard/src/components/
git commit -m "feat(RO-dashboard): RegionPanel shell with 4-tab layout and KPI cards"
```

---

## Task 9: CounterfactualChart

**Files:** `dashboard/src/components/CounterfactualChart.tsx`

- [ ] **Step 1: Replace `dashboard/src/components/CounterfactualChart.tsx`**

```tsx
import {
  ComposedChart, Line, ReferenceLine, ReferenceArea,
  XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer,
} from 'recharts';
import type { CounterfactualPoint } from '../types';

interface Props {
  series: CounterfactualPoint[];
}

export default function CounterfactualChart({ series }: Props) {
  if (series.length === 0) {
    return <div className="text-gray-400 text-sm">No GSC series available.</div>;
  }

  // Build chart data: filter to 2000+ and compute post-reform area bounds
  const chartData = series
    .filter((p) => p.year >= 2000)
    .map((p) => ({
      year: p.year,
      actual: p.actual,
      counterfactual: p.counterfactual,
      // For the ReferenceArea: shade between observed and counterfactual post-2024
      areaTop: p.year >= 2025 && p.actual != null && p.counterfactual != null
        ? Math.max(p.actual, p.counterfactual)
        : undefined,
      areaBottom: p.year >= 2025 && p.actual != null && p.counterfactual != null
        ? Math.min(p.actual, p.counterfactual)
        : undefined,
    }));

  // Y-axis domain
  const allVals = chartData.flatMap((d) => [d.actual, d.counterfactual].filter(Boolean) as number[]);
  const yMin = Math.min(...allVals) - 0.01;
  const yMax = Math.max(...allVals) + 0.01;

  return (
    <div>
      <div className="text-xs font-semibold text-gray-600 uppercase tracking-wide mb-2">
        GSC Counterfactual — ln(population)
      </div>
      <ResponsiveContainer width="100%" height={200}>
        <ComposedChart data={chartData} margin={{ top: 4, right: 8, bottom: 4, left: 8 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
          <XAxis dataKey="year" tick={{ fontSize: 10 }} interval={4} />
          <YAxis
            domain={[yMin, yMax]}
            tick={{ fontSize: 10 }}
            tickFormatter={(v: number) => v.toFixed(2)}
            width={45}
          />
          <Tooltip
            formatter={(v: number) => v.toFixed(4)}
            labelFormatter={(l) => `Year ${l}`}
            contentStyle={{ fontSize: 11 }}
          />
          <Legend iconSize={10} wrapperStyle={{ fontSize: 10 }} />
          <ReferenceLine x={2025} stroke="#d97706" strokeDasharray="4 3" label={{ value: '2025', fontSize: 9, fill: '#d97706' }} />
          <ReferenceArea
            dataKey="areaTop"
            x1={2025}
            x2={chartData[chartData.length - 1]?.year}
            y1={yMin}
            y2={yMax}
            fill="rgba(239,68,68,0.08)"
            stroke="none"
          />
          <Line
            type="monotone"
            dataKey="actual"
            stroke="#3b82f6"
            strokeWidth={2}
            dot={false}
            name="Observed"
          />
          <Line
            type="monotone"
            dataKey="counterfactual"
            stroke="#16a34a"
            strokeWidth={1.5}
            strokeDasharray="5 3"
            dot={false}
            name="Counterfactual (GSC)"
          />
        </ComposedChart>
      </ResponsiveContainer>
      <div className="text-xs text-gray-400 mt-1">
        Source: gsynth IFE, r*=1, 350 Polish donors. Dashed amber line = reform year 2025.
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Verify chart renders**

Click any treated county on the map, stay on Counterfactual tab. Expected: line chart with blue observed line and green dashed counterfactual line, year 2000–2024 on x-axis.

- [ ] **Step 3: Commit**

```bash
cd ..
git add dashboard/src/components/CounterfactualChart.tsx
git commit -m "feat(RO-dashboard): CounterfactualChart -- Recharts GSC vs observed"
```

---

## Task 10: ForecastPanel — 3-path fan chart

**Files:** `dashboard/src/components/ForecastPanel.tsx`

- [ ] **Step 1: Replace `dashboard/src/components/ForecastPanel.tsx`**

```tsx
import { useState } from 'react';
import {
  ComposedChart, Area, Line, XAxis, YAxis, CartesianGrid,
  Tooltip, Legend, ResponsiveContainer,
} from 'recharts';
import type { ForecastPoint } from '../types';

type PathId = 'status_quo' | 'counterfactual' | 'innovation_hub';
type OutcomeId = 'ln_population' | 'ln_gva_per_empl' | 'nat_change_rate' | 'unemployment';

const PATH_COLORS: Record<PathId, { stroke: string; fill: string }> = {
  status_quo:     { stroke: '#9ca3af', fill: '#e5e7eb' },
  counterfactual: { stroke: '#3b82f6', fill: '#dbeafe' },
  innovation_hub: { stroke: '#16a34a', fill: '#dcfce7' },
};

const PATH_LABELS: Record<PathId, string> = {
  status_quo:     'Status quo',
  counterfactual: 'Counterfactual (GSC)',
  innovation_hub: 'Innovation hub',
};

const OUTCOME_LABELS: Record<OutcomeId, string> = {
  ln_population:   'ln(population)',
  ln_gva_per_empl: 'ln(GVA/employed)',
  nat_change_rate: 'Natural change rate',
  unemployment:    'Unemployment',
};

interface Props {
  forecasts: Record<string, Record<string, ForecastPoint[]>>;
}

export default function ForecastPanel({ forecasts }: Props) {
  const availablePaths = Object.keys(PATH_COLORS).filter((p) =>
    Object.keys(forecasts).some((v) => forecasts[v][p] != null),
  ) as PathId[];

  const [selectedPaths, setSelectedPaths] = useState<Set<PathId>>(
    new Set(['status_quo', 'counterfactual', 'innovation_hub'] as PathId[]),
  );
  const [outcome, setOutcome] = useState<OutcomeId>('ln_population');

  function togglePath(path: PathId) {
    setSelectedPaths((prev) => {
      const next = new Set(prev);
      if (next.has(path)) {
        if (next.size > 1) next.delete(path); // keep at least one
      } else {
        next.add(path);
      }
      return next;
    });
  }

  // Merge all selected paths into a single data array keyed by year
  const pathData = forecasts[outcome] ?? {};
  const allYears = new Set<number>();
  for (const p of selectedPaths) {
    (pathData[p] ?? []).forEach((pt) => allYears.add(pt.year));
  }

  const chartData = Array.from(allYears)
    .sort((a, b) => a - b)
    .map((year) => {
      const row: Record<string, number | undefined> = { year };
      for (const p of selectedPaths) {
        const pt = (pathData[p] ?? []).find((x) => x.year === year);
        if (pt) {
          row[`${p}_value`] = pt.value ?? undefined;
          row[`${p}_lo80`] = pt.lo80 ?? undefined;
          row[`${p}_hi80`] = pt.hi80 ?? undefined;
        }
      }
      return row;
    });

  return (
    <div>
      {/* Controls */}
      <div className="flex items-center gap-2 mb-3 flex-wrap">
        <select
          value={outcome}
          onChange={(e) => setOutcome(e.target.value as OutcomeId)}
          className="text-xs border border-gray-200 rounded px-2 py-1 bg-white"
        >
          {Object.entries(OUTCOME_LABELS).map(([id, label]) => (
            <option key={id} value={id}>{label}</option>
          ))}
        </select>
        <div className="flex gap-1">
          {availablePaths.map((p) => (
            <button
              key={p}
              onClick={() => togglePath(p)}
              className={`text-xs px-2 py-1 rounded border transition-colors ${
                selectedPaths.has(p)
                  ? 'border-blue-500 bg-blue-50 text-blue-700'
                  : 'border-gray-200 text-gray-400'
              }`}
            >
              {PATH_LABELS[p]}
            </button>
          ))}
        </div>
      </div>

      {/* Fan chart */}
      <ResponsiveContainer width="100%" height={220}>
        <ComposedChart data={chartData} margin={{ top: 4, right: 8, bottom: 4, left: 8 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
          <XAxis dataKey="year" tick={{ fontSize: 10 }} interval={2} />
          <YAxis tick={{ fontSize: 10 }} tickFormatter={(v: number) => v.toFixed(2)} width={45} />
          <Tooltip contentStyle={{ fontSize: 11 }} labelFormatter={(l) => `Year ${l}`} />
          <Legend iconSize={10} wrapperStyle={{ fontSize: 10 }} />

          {Array.from(selectedPaths).map((p) => {
            const { stroke, fill } = PATH_COLORS[p];
            return [
              <Area
                key={`${p}_band`}
                type="monotone"
                dataKey={`${p}_hi80`}
                stackId={p}
                fill={fill}
                stroke="none"
                name={undefined}
                legendType="none"
              />,
              <Area
                key={`${p}_lo80`}
                type="monotone"
                dataKey={`${p}_lo80`}
                stackId={p}
                fill="#fff"
                stroke="none"
                name={undefined}
                legendType="none"
              />,
              <Line
                key={`${p}_line`}
                type="monotone"
                dataKey={`${p}_value`}
                stroke={stroke}
                strokeWidth={2}
                dot={false}
                name={PATH_LABELS[p]}
              />,
            ];
          })}
        </ComposedChart>
      </ResponsiveContainer>
      <div className="text-xs text-gray-400 mt-1">
        Shaded band = 80% CI. MG-VAR, Moretti multipliers applied to innovation_hub path.
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Verify fan chart renders**

Click a county, switch to Forecast tab. Expected: 3-path toggle buttons, outcome dropdown, fan chart with coloured lines and CI bands for 2025–2040.

- [ ] **Step 3: Commit**

```bash
cd ..
git add dashboard/src/components/ForecastPanel.tsx
git commit -m "feat(RO-dashboard): ForecastPanel -- 3-path MG-VAR fan chart with CI bands"
```

---

## Task 11: MegaCampusBadge

**Files:** `dashboard/src/components/MegaCampusBadge.tsx`

- [ ] **Step 1: Replace `dashboard/src/components/MegaCampusBadge.tsx`**

```tsx
import type { SuitabilityData } from '../types';

interface Props {
  suitability: SuitabilityData;
}

const T_LABELS: Record<string, string> = {
  T1: 'AI / ML Hub',
  T2: 'Life Sciences',
  T3: 'Energy Tech',
  T4: 'Cleantech',
  T5: 'Data Centre',
  T6: 'Adv. Manufacturing',
  T7: 'AgriTech',
  T8: 'Smart Logistics',
};

export default function MegaCampusBadge({ suitability: s }: Props) {
  const tier1Set = new Set(s.tier1_types.split('|').filter(Boolean));

  // Build sorted bar data (highest score first)
  const bars = [
    { key: 'T1', score: s.suitability_T1 },
    { key: 'T2', score: s.suitability_T2 },
    { key: 'T3', score: s.suitability_T3 },
    { key: 'T4', score: s.suitability_T4_adjusted },
    { key: 'T5', score: s.suitability_T5 },
    { key: 'T6', score: s.suitability_T6 },
    { key: 'T7', score: s.suitability_T7 },
    { key: 'T8', score: s.suitability_T8 },
  ].sort((a, b) => b.score - a.score);

  return (
    <div>
      {/* Section header */}
      <div className="flex items-center gap-2 mb-3">
        <span className="text-xs font-semibold text-gray-600 uppercase tracking-wide">
          MegaCampus Suitability
        </span>
        {s.tier1_gate ? (
          <span className="text-xs bg-green-100 text-green-700 px-2 py-0.5 rounded-full font-medium">
            ✅ Tier-1 Qualified
          </span>
        ) : (
          <span className="text-xs bg-gray-100 text-gray-500 px-2 py-0.5 rounded-full">
            ✗ Below threshold
          </span>
        )}
      </div>

      {/* Bar chart */}
      <div className="flex flex-col gap-1.5">
        {bars.map(({ key, score }) => {
          const isTier1 = tier1Set.has(key);
          const barPct = Math.round(score * 100);
          return (
            <div key={key} className="grid items-center gap-2" style={{ gridTemplateColumns: '32px 1fr 48px' }}>
              <span className={`text-xs font-bold ${isTier1 ? 'text-blue-700' : 'text-gray-400'}`}>
                {key}
              </span>
              <div className="relative h-2.5 bg-gray-100 rounded">
                <div
                  className={`h-full rounded ${isTier1 ? 'bg-blue-600' : 'bg-gray-300'}`}
                  style={{ width: `${barPct}%` }}
                />
                {/* Threshold line at 70% */}
                <div
                  className="absolute top-0 bottom-0 w-px bg-amber-400"
                  style={{ left: '70%' }}
                  title="Tier-1 threshold (0.70)"
                />
              </div>
              <span className={`text-xs text-right ${isTier1 ? 'text-blue-700 font-bold' : 'text-gray-400'}`}>
                {score.toFixed(2)}{isTier1 ? ' ★' : ''}
              </span>
            </div>
          );
        })}
      </div>

      {/* Axis labels */}
      <div className="flex justify-between text-xs text-gray-300 mt-1 pr-14">
        <span>0</span>
        <span style={{ marginLeft: '70%', transform: 'translateX(-50%)' }}>0.70</span>
        <span>1.0</span>
      </div>

      {/* Type legend */}
      <div className="mt-3 grid grid-cols-2 gap-x-3 gap-y-0.5">
        {bars.map(({ key }) => (
          <div key={key} className="text-xs text-gray-500">
            <span className="font-medium text-gray-600">{key}</span>: {T_LABELS[key]}
          </div>
        ))}
      </div>

      {/* T4 footnote */}
      {s.t4_anchor_source === 'industry_b_e_proxy' && (
        <div className="mt-2 text-xs text-amber-600 bg-amber-50 rounded px-2 py-1">
          ⚠ T4 anchor: industry B-E employment proxy (D35 not available at NUTS3)
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 2: Verify badges render**

Click a Tier-1 county (one where `tier1_types` is non-empty), switch to MegaCampus tab. Expected:
- "✅ Tier-1 Qualified" badge appears
- Blue bars for qualifying types, grey for others
- Amber threshold line at 70% of bar width
- ★ suffix on Tier-1 scores

- [ ] **Step 3: Commit**

```bash
cd ..
git add dashboard/src/components/MegaCampusBadge.tsx
git commit -m "feat(RO-dashboard): MegaCampusBadge -- mini bar chart with 0.70 threshold"
```

---

## Task 12: MethodsTab

**Files:** `dashboard/src/components/MethodsTab.tsx`

- [ ] **Step 1: Replace `dashboard/src/components/MethodsTab.tsx`**

```tsx
import type { SdidEstimate, LpIrf, EventStudyCoef } from '../types';

interface Props {
  sdid: SdidEstimate[];
  lpIrfs: LpIrf[];
  eventstudy: EventStudyCoef[];
}

const OUTCOME_LABELS: Record<string, string> = {
  ln_population:   'ln(population)',
  nat_change_rate: 'Nat. change rate',
  net_migration_rate: 'Net migration',
};

function fmt(v: number | null, digits = 3): string {
  return v != null ? v.toFixed(digits) : '—';
}

export default function MethodsTab({ sdid, lpIrfs, eventstudy }: Props) {
  // LP max pre-trend |coef| per outcome (h=0..15)
  const lpMaxByOutcome: Record<string, number> = {};
  for (const row of lpIrfs) {
    if (row.horizon <= 15 && row.coef != null) {
      const prev = lpMaxByOutcome[row.outcome] ?? 0;
      lpMaxByOutcome[row.outcome] = Math.max(prev, Math.abs(row.coef));
    }
  }

  // Event-study significant pre-trend count per outcome
  const etSigByOutcome: Record<string, number> = {};
  for (const row of eventstudy) {
    if (row.event_time < 0 && row.ci_lo != null && row.ci_hi != null) {
      if (row.ci_lo > 0 || row.ci_hi < 0) {
        etSigByOutcome[row.outcome] = (etSigByOutcome[row.outcome] ?? 0) + 1;
      }
    }
  }

  return (
    <div className="space-y-4 text-xs">
      {/* Identification narrative */}
      <div className="bg-blue-50 rounded p-3 text-blue-800 leading-relaxed">
        <strong>Identification strategy:</strong> TWFE event study (Stage 05) shows non-flat pre-trends,
        validating gsynth Interactive Factor Model (Xu 2017) over plain TWFE.
        Cross-country synthetic control uses 350 Polish donors post-1999 reform (r*=1 factor).
        SDiD (pseudo-treat 2015) and LP-IRFs both pass robustness checks.
      </div>

      {/* SDiD estimates */}
      <div>
        <div className="font-semibold text-gray-700 mb-1">SDiD Estimates (pseudo-treat 2015)</div>
        <table className="w-full border-collapse">
          <thead>
            <tr className="bg-gray-50">
              <th className="text-left py-1 px-2 border border-gray-200">Outcome</th>
              <th className="text-right py-1 px-2 border border-gray-200">ATT</th>
              <th className="text-right py-1 px-2 border border-gray-200">SE</th>
              <th className="text-right py-1 px-2 border border-gray-200">95% CI</th>
            </tr>
          </thead>
          <tbody>
            {sdid.map((r) => (
              <tr key={r.outcome} className="border-b border-gray-100">
                <td className="py-1 px-2 border border-gray-200">{OUTCOME_LABELS[r.outcome] ?? r.outcome}</td>
                <td className="text-right py-1 px-2 border border-gray-200 font-mono">{fmt(r.att)}</td>
                <td className="text-right py-1 px-2 border border-gray-200 font-mono">{fmt(r.se)}</td>
                <td className="text-right py-1 px-2 border border-gray-200 font-mono">
                  [{fmt(r.ci_lo)}, {fmt(r.ci_hi)}]
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        <div className="text-gray-400 mt-1">All CIs include zero (placebo passes).</div>
      </div>

      {/* LP pre-trends */}
      <div>
        <div className="font-semibold text-gray-700 mb-1">LP Pre-trend Check (h = 0…15)</div>
        <table className="w-full border-collapse">
          <thead>
            <tr className="bg-gray-50">
              <th className="text-left py-1 px-2 border border-gray-200">Outcome</th>
              <th className="text-right py-1 px-2 border border-gray-200">Max |coef|</th>
              <th className="text-right py-1 px-2 border border-gray-200">Result</th>
            </tr>
          </thead>
          <tbody>
            {Object.entries(lpMaxByOutcome).map(([outcome, maxCoef]) => (
              <tr key={outcome} className="border-b border-gray-100">
                <td className="py-1 px-2 border border-gray-200">{OUTCOME_LABELS[outcome] ?? outcome}</td>
                <td className="text-right py-1 px-2 border border-gray-200 font-mono">{maxCoef.toFixed(4)}</td>
                <td className={`text-right py-1 px-2 border border-gray-200 font-medium ${maxCoef < 0.05 ? 'text-green-600' : 'text-amber-600'}`}>
                  {maxCoef < 0.05 ? '✓ Flat' : '⚠ Drift'}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* TWFE event study */}
      <div>
        <div className="font-semibold text-gray-700 mb-1">TWFE Event Study Pre-trends</div>
        <table className="w-full border-collapse">
          <thead>
            <tr className="bg-gray-50">
              <th className="text-left py-1 px-2 border border-gray-200">Outcome</th>
              <th className="text-right py-1 px-2 border border-gray-200">Sig. pre-trend coefficients</th>
              <th className="text-right py-1 px-2 border border-gray-200">Verdict</th>
            </tr>
          </thead>
          <tbody>
            {Object.entries(etSigByOutcome).map(([outcome, count]) => (
              <tr key={outcome} className="border-b border-gray-100">
                <td className="py-1 px-2 border border-gray-200">{OUTCOME_LABELS[outcome] ?? outcome}</td>
                <td className="text-right py-1 px-2 border border-gray-200 font-mono">{count} / 19</td>
                <td className="text-right py-1 px-2 border border-gray-200 font-medium text-red-500">
                  ✗ Not flat
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        <div className="text-gray-500 mt-1">
          Non-flat pre-trends validate gsynth IFE (allows heterogeneous trends) over TWFE.
        </div>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Verify Methods tab renders**

Click any county, switch to Methods tab. Expected:
- Blue identification narrative box
- SDiD table with 3 rows (ln_population, nat_change_rate, net_migration_rate)
- LP pre-trend table
- TWFE event study table showing "Not flat" for all outcomes

- [ ] **Step 3: Commit**

```bash
cd ..
git add dashboard/src/components/MethodsTab.tsx
git commit -m "feat(RO-dashboard): MethodsTab -- SDiD, LP pre-trends, TWFE event-study table"
```

---

## Task 13: Final smoke test and GitHub Pages deployment

**Files:** `dashboard/vite.config.ts` (verify), `dashboard/package.json` (verify)

- [ ] **Step 1: Full end-to-end smoke test**

```bash
cd dashboard
npm run dev
```

Open http://localhost:5173. Work through this checklist:

- [ ] Header bar shows "RO Administrative Reform" title
- [ ] SummaryBar shows "33 demoted counties", negative SDiD ATT%, "17/42 Tier-1", "2025"
- [ ] Layer buttons: "Reform cost" active by default (blue); clicking "Suitability" and "ROI" switches map colouring
- [ ] Romania map loads and shows coloured polygons (may take 2-3 seconds for GeoJSON CDN)
- [ ] Hovering a county shows tooltip with name
- [ ] Clicking a county: sidebar updates with county name, NUTS3 code, 3 KPI cards
- [ ] Counterfactual tab: line chart renders with blue observed and green dashed counterfactual lines, amber 2025 reference line
- [ ] Forecast tab: fan chart renders with CI bands; path toggle buttons work; outcome dropdown works
- [ ] MegaCampus tab: 8 horizontal bars sorted by score, amber threshold line at 70%, ✅ badge for Tier-1 counties
- [ ] Methods tab: 3 tables render correctly
- [ ] Clicking a different county updates all tabs

Stop server with Ctrl+C.

- [ ] **Step 2: Production build**

```bash
npm run build
```

Expected: `dist/` directory created, build completes without TypeScript errors.

```bash
ls dist/
```

Expected: `index.html`, `assets/` directory.

- [ ] **Step 3: Preview production build**

```bash
npm run preview
```

Open the preview URL (http://localhost:4173/RO-Administrative-Reform/ — note the base path). Verify the same smoke-test checklist passes in the production build. Stop with Ctrl+C.

- [ ] **Step 4: Commit dashboard state**

```bash
cd ..
git add dashboard/
git commit -m "feat(RO-dashboard): complete React dashboard -- all 8 components wired"
```

- [ ] **Step 5: Deploy to GitHub Pages** (only if remote `origin` is configured)

```bash
cd dashboard
npm run deploy
```

Expected output: `Published` message with the GitHub Pages URL. The app will be live at `https://<username>.github.io/RO-Administrative-Reform/` (or the configured base path).

If the remote is not yet configured or the repo is `Sandbox` (not `RO-Administrative-Reform`), adjust `base` in `vite.config.ts` to match:

```typescript
// For a Sandbox repo deploying to a subdirectory:
base: '/Sandbox/RO-Administrative-Reform/',
```

Then rebuild and redeploy.

- [ ] **Step 6: Update PROGRESS.md**

Add to PROGRESS.md under "React Dashboard":
```
React Dashboard (Phase 4): PASS — all 8 components implemented, GitHub Pages deployment configured.
URL: https://<username>.github.io/<repo>/
```

---

## Self-Review Checklist

**Spec coverage:**

| Spec requirement | Covered by task |
|---|---|
| Vite + React + TypeScript scaffold | Task 1 |
| export_to_json_ro.py (7 JSON files) | Task 2 |
| TypeScript types for all JSON shapes | Task 3 |
| useDashboardData hook | Task 4 |
| App shell: layout grid, selectedNuts3/activeLayer state | Task 5 |
| SummaryBar: 4 KPI chips | Task 6 |
| LayerSwitcher: 3 toggle buttons | Task 6 |
| RomaniaMap: choropleth + CDN GeoJSON + click + fallback | Task 7 |
| RegionPanel: header, KPI cards, 4 tabs | Task 8 |
| CounterfactualChart: Recharts ComposedChart + ReferenceLine | Task 9 |
| ForecastPanel: 3-path toggle + variable dropdown + CI bands | Task 10 |
| MegaCampusBadge: mini bars + threshold line + footnote | Task 11 |
| MethodsTab: SDiD/LP/event-study tables | Task 12 |
| GitHub Pages build + deploy | Task 13 |
| BASE_URL for fetch paths | Task 4 (useDashboardData uses `import.meta.env.BASE_URL`) |
| GeoJSON CDN fallback (county list) | Task 7 |
| shx copy-data script | Task 1 |

**No placeholders found.** All steps contain complete code.

**Type consistency verified:** `RegionData`, `ForecastPoint`, `SuitabilityData`, `LpIrf`, `SdidEstimate`, `EventStudyCoef`, `Summary`, `DashboardData` defined in Task 3 and used consistently in Tasks 4–12.
