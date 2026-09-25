# React Dashboard Design Spec — RO Administrative Reform

**Date:** 2026-06-05
**Project:** RO-Administrative-Reform
**Phase:** Phase 4 (VISION.md)
**Status:** Approved — ready for implementation plan

---

## Overview

A policy-facing React SPA that visualises the full RO Administrative Reform analytical pipeline. Deployable as a static site (GitHub Pages) or run locally (`npm run dev`). No backend server required.

---

## Tech Stack

| Layer | Choice | Reason |
|---|---|---|
| Build | Vite + React 18 | Fast dev server, clean `dist/` output |
| Language | TypeScript | Component contracts, data type safety |
| Map | react-leaflet + Leaflet | Choropleth NUTS3, CDN GeoJSON |
| Charts | Recharts | Lightweight, composable, good for fan charts |
| Styling | Tailwind CSS | Utility-first, no custom CSS files to manage |
| Deploy | `gh-pages` npm package | One-command push to GitHub Pages |

---

## GeoJSON Strategy

Romanian NUTS3 boundaries fetched at runtime from the Eurostat NUTS 2021 GeoJSON CDN:
```
https://gisco-services.ec.europa.eu/distribution/v2/nuts/geojson/NUTS_RG_20M_2021_4326_LEVL_3.geojson
```
Filter client-side to features where `properties.CNTR_CODE === "RO"` (41 features — NUTS3 for Romania). No file to host or version.

Fallback: if the CDN fetch fails, display a county list in place of the map with a banner noting the map is unavailable.

---

## File Structure

```
dashboard/
├── index.html
├── package.json
├── vite.config.ts            # base: '/RO-Administrative-Reform/' for GitHub Pages
├── tailwind.config.ts
├── tsconfig.json
├── public/
│   └── data/                 # Symlink or copy of data/dashboard/*.json at build
├── src/
│   ├── main.tsx
│   ├── App.tsx               # Root: map + sidebar layout, selected-county state
│   ├── types.ts              # TypeScript interfaces for all JSON shapes
│   ├── hooks/
│   │   └── useDashboardData.ts   # Fetches all JSON files, returns typed objects
│   └── components/
│       ├── SummaryBar.tsx        # Top KPI strip (4 aggregate stats + LayerSwitcher)
│       ├── RomaniaMap.tsx        # react-leaflet MapContainer, choropleth layer
│       ├── LayerSwitcher.tsx     # Inline buttons: Reform cost | Suitability | ROI
│       ├── RegionPanel.tsx       # Sidebar shell: county header + KPI cards + tabs
│       ├── CounterfactualChart.tsx  # Recharts LineChart: observed vs GSC
│       ├── ForecastPanel.tsx     # Recharts AreaChart: 3-path fan chart + toggle
│       ├── MegaCampusBadge.tsx   # SVG mini bars for T1–T8 suitability
│       └── MethodsTab.tsx        # SDiD/LP/event-study summary table
```

---

## Data Pipeline

### Step 1: Export JSON

New script `scripts/export_to_json_ro.py` (modelled on PL `export_to_json.py`):

| Output file | Source parquet | Content |
|---|---|---|
| `regions.json` | `ro_gsynth_gaps.parquet` + `ro_treatment_cities.parquet` | Per-county metadata, GSC series, reform scenarios |
| `forecasts.json` | `ro_pvar_forecasts_roi.parquet` | 3-path fan chart data per county (status_quo / counterfactual / innovation_hub) |
| `suitability.json` | `ro_nuts3_suitability.parquet` | T1–T8 scores, vitality index, tier1_gate, tier1_types |
| `lp_irfs.json` | `ro_lp_irfs.parquet` | LP IRF coefficients per outcome |
| `sdid_estimates.json` | `ro_sdid_estimates.parquet` | SDiD ATT estimates |
| `eventstudy.json` | `ro_eventstudy_coefs.parquet` | Event-study coefficients per outcome |
| `summary.json` | Computed | Aggregate KPIs for SummaryBar |

### Step 2: Build integration

`package.json` defines a `"copy-data"` script using `shx cp -r ../data/dashboard/* public/data/` that must be run before `npm run dev` or `npm run build`. The `"dev"` and `"build"` scripts in `package.json` call `copy-data` first via `npm run copy-data && vite` so `fetch('/data/regions.json')` resolves in both dev and the GitHub Pages build. `shx` is a cross-platform shell utility that avoids Windows/Unix path differences.

---

## Component Specifications

### App.tsx
- State: `selectedNuts3: string | null` (county code), `activeLayer: 'reform_cost' | 'suitability' | 'roi'`
- Layout: CSS grid `[44px header] [36px KPI bar] [1fr main]`; main = `[1fr map] [360px sidebar]`
- On mount: fetch all JSON via `useDashboardData()`

### SummaryBar.tsx
- 4 KPI chips from `summary.json`: demoted counties, SDiD ATT pop, Tier-1 counties, reform year
- `LayerSwitcher` inline on the right: 3 toggle buttons update `activeLayer` state
- Dark background (`#2d3748`)

### RomaniaMap.tsx
Props: `data`, `activeLayer`, `selectedNuts3`, `onCountyClick`
- `MapContainer` centered on Romania (~46.0, 25.0), zoom 6, no zoom controls visible
- Fetch GeoJSON on mount from Eurostat CDN, filter `CNTR_CODE === "RO"`
- `GeoJSON` layer with `style` function: colour counties by `activeLayer` metric using a sequential scale
  - `reform_cost`: white → red (higher reform cost = darker red)
  - `suitability`: white → blue (highest T-max suitability score)
  - `roi`: white → green (ROI central estimate)
- Selected county: blue fill + thicker border
- `onEachFeature`: click handler calls `onCountyClick(nuts3_code)`
- Tooltip on hover: county name + active metric value

### LayerSwitcher.tsx
Props: `activeLayer`, `onChange`
- 3 `<button>` elements, active button highlighted
- Labels: "Reform cost" / "Suitability" / "ROI"

### RegionPanel.tsx
Props: `nuts3Code`, `data`
- If `nuts3Code` is null: placeholder card ("Click a county on the map")
- County header: `judet_name` — `county_seat`, NUTS3/NUTS2 codes
- 3 KPI mini-cards: reform cost (%), vitality index, ROI central (€M)
- Tab bar: Counterfactual | Forecast | MegaCampus | Methods
- Tab state: `activeTab`, renders one child component

### CounterfactualChart.tsx
Props: `nuts3Code`, `gaps` (GSC series for this county)
- Recharts `ComposedChart`: `Line` for observed, `Line` dashed for counterfactual
- `ReferenceArea` shading between observed and counterfactual post-reform
- `ReferenceLine` at x=2025 (reform year, dashed amber)
- Legend: Observed / Counterfactual (GSC) / Reform cost area
- Y-axis: ln(population), labelled
- X-axis: year 2000–2024

### ForecastPanel.tsx
Props: `nuts3Code`, `forecasts` (3-path fan chart data)
- Toggle buttons: `status_quo` / `counterfactual` / `innovation_hub` — can show multiple simultaneously
- For each selected path: Recharts `AreaChart` with 80% CI band + central line
- Path colours: status_quo=grey, counterfactual=blue, innovation_hub=green
- `<select>` dropdown to switch outcome: `ln_population` (default) / `ln_gva_per_empl` / `nat_change_rate` / `unemployment`
- X-axis: 2025–2040

### MegaCampusBadge.tsx
Props: `suitability` (one row from suitability.json)
- Section header: "MegaCampus Suitability" + tier1_gate badge (✅ Qualified / ✗ Below threshold)
- 8 horizontal bars (T1–T8), sorted by score descending
- Bar colour: blue if score ≥ 0.70, grey otherwise
- Threshold line rendered at 70% of bar width via CSS `::after` or inline style
- Score label right-aligned; Tier-1 types get ★ suffix
- `t4_anchor_source` footnote: "T4 anchor: industry B-E proxy (D35 not available at NUTS3)"

### MethodsTab.tsx
Props: `sdid`, `lp_irfs`, `eventstudy`
- SDiD table: outcome | ATT | SE | 95% CI | note (pseudo-treat 2015)
- LP pre-trend summary: max |coef| over h=0..15 per outcome, flag if > 0.05
- Event-study verdict: "Pre-trends NOT flat → validates gsynth IFE over TWFE"
- Static text block explaining identification narrative

---

## Choropleth Colour Scales

| Layer | Scale | Domain |
|---|---|---|
| `reform_cost` | `interpolateReds` (d3-scale-chromatic via CDN) | [0, max(|att_avg_pre|)] |
| `suitability` | `interpolateBlues` | [0, 1] |
| `roi` | `interpolateGreens` | [0, max(roi_central)] |

Counties with no data (non-treated, suitability only covers 42 counties): grey fill.

---

## Deployment

### Local dev
```bash
cd dashboard
npm install
npm run dev   # http://localhost:5173
```

### GitHub Pages
```bash
npm run build   # outputs dist/
npm run deploy  # gh-pages -d dist
```

`vite.config.ts`:
```ts
export default defineConfig({
  base: '/RO-Administrative-Reform/',
  ...
})
```

`.gitignore` additions: `dashboard/node_modules/`, `dashboard/dist/`

---

## Out of Scope

- No authentication, no server-side rendering
- No real-time data updates (all data is static JSON)
- No mobile-first breakpoints (designed for 1280px+ desktop viewport)
- No county-to-county comparison view (single county detail at a time)

---

## Inputs Required

All parquets already on disk in `data/processed/`. Running `scripts/export_to_json_ro.py` produces the 7 JSON files before `npm run dev`.
