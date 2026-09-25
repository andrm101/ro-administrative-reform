# Region View — NUTS2 Consolidation Overlay Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a 4th "Region" map layer that highlights an entire NUTS2 consolidation region on the map and renders a gradient-band overlay chart in the sidebar showing per-satellite-county innovation_hub vs status_quo MG-VAR paths, suitability-encoded by colour.

**Architecture:** All hub/satellite grouping is derived client-side from existing JSON (`suitability.json` has 42 counties; `regions.json` has 33 treated counties — the difference per NUTS2 is the hub). A new `RegionOverlayChart` component renders one gradient-filled band per satellite county using Recharts `<Area>` stacking. State flows down: App.tsx holds `hoveredNuts3` and `regionGroups`; RomaniaMap and RegionPanel receive them as props.

**Tech Stack:** React 18 + TypeScript, Recharts (ComposedChart, Area, Line, ReferenceLine, Legend), react-leaflet, Tailwind CSS, Vite

**Spec:** `docs/superpowers/specs/2026-06-05-region-overlay-design.md`

---

## File Map

| Action | File | Responsibility |
|--------|------|----------------|
| Modify | `dashboard/src/types.ts` | Add `'region'` to `LayerType`; export `RegionGroup` interface |
| Modify | `dashboard/src/utils/color.ts` | Add `suitabilityToHex()` export |
| Modify | `dashboard/src/App.tsx` | Add `hoveredNuts3` state, `regionGroups` useMemo, `deriveRegionGroups()`, pass new props |
| Modify | `dashboard/src/components/LayerSwitcher.tsx` | Add 4th "Region" button |
| Modify | `dashboard/src/components/RomaniaMap.tsx` | NUTS2 region highlight style; `onCountyHover` binding |
| Modify | `dashboard/src/components/RegionPanel.tsx` | Branch on `activeLayer === 'region'` to render `RegionOverlayChart` |
| Create | `dashboard/src/components/RegionOverlayChart.tsx` | Gradient overlay chart with all 6 peak enhancements |

---

### Task 1: Extend types.ts

**Files:**
- Modify: `dashboard/src/types.ts:106`

- [ ] **Step 1: Add `'region'` to LayerType and add RegionGroup interface**

Replace line 106 in `dashboard/src/types.ts`:

```typescript
// Before:
export type LayerType = 'reform_cost' | 'suitability' | 'roi';

// After:
export type LayerType = 'reform_cost' | 'suitability' | 'roi' | 'region';

export interface RegionGroup {
  nuts2Code: string;
  hubNuts3: string | null;
  satellites: string[];
}
```

- [ ] **Step 2: Verify TypeScript still compiles**

Run: `cd dashboard && npx tsc --noEmit`
Expected: No errors (LayerSwitcher will warn about unknown id until Task 4 — skip that file for now).

- [ ] **Step 3: Commit**

```bash
git add dashboard/src/types.ts
git commit -m "feat(RO-dashboard): add region LayerType and RegionGroup interface"
```

---

### Task 2: Add `suitabilityToHex()` to color.ts

**Files:**
- Modify: `dashboard/src/utils/color.ts`

- [ ] **Step 1: Add the new export at the end of the file**

Append to `dashboard/src/utils/color.ts` after the `maxSuitability` function:

```typescript
/** Suitability score (0–1) → hex colour. score=0 → #8b5cf6 (grey-purple), score=1 → #10b981 (blue-green). */
export function suitabilityToHex(score: number): string {
  const r = lerp(139, 16,  score);
  const g = lerp(92,  185, score);
  const b = lerp(246, 129, score);
  return `#${r.toString(16).padStart(2, '0')}${g.toString(16).padStart(2, '0')}${b.toString(16).padStart(2, '0')}`;
}
```

Note: `lerp()` already rounds internally — no extra `Math.round` needed.

- [ ] **Step 2: Verify TypeScript compiles**

Run: `cd dashboard && npx tsc --noEmit`
Expected: No errors.

- [ ] **Step 3: Commit**

```bash
git add dashboard/src/utils/color.ts
git commit -m "feat(RO-dashboard): add suitabilityToHex colour utility"
```

---

### Task 3: Update App.tsx — state, useMemo, deriveRegionGroups, props

**Files:**
- Modify: `dashboard/src/App.tsx`

Context: Current App.tsx imports `useState` only, has `selectedNuts3` and `activeLayer` state. `DashboardData` has `suitability: SuitabilityData[]` and `regions: RegionData[]`.

- [ ] **Step 1: Rewrite App.tsx with new imports, state, and prop pass-through**

Replace the full contents of `dashboard/src/App.tsx` with:

```typescript
import { useState, useMemo } from 'react';
import { useDashboardData } from './hooks/useDashboardData';
import type { LayerType, RegionGroup } from './types';
import type { DashboardData } from './types';
import SummaryBar from './components/SummaryBar';
import RomaniaMap from './components/RomaniaMap';
import RegionPanel from './components/RegionPanel';

function deriveRegionGroups(data: DashboardData): Map<string, RegionGroup> {
  const treatedCodes = new Set(data.regions.map((r) => r.nuts3_code));
  const byNuts2 = new Map<string, RegionGroup>();

  for (const s of data.suitability) {
    if (!byNuts2.has(s.nuts2_code)) {
      byNuts2.set(s.nuts2_code, { nuts2Code: s.nuts2_code, hubNuts3: null, satellites: [] });
    }
    const g = byNuts2.get(s.nuts2_code)!;
    if (!treatedCodes.has(s.nuts3_code)) {
      g.hubNuts3 = s.nuts3_code;
    } else {
      g.satellites.push(s.nuts3_code);
    }
  }
  return byNuts2;
}

export default function App() {
  const { data, error } = useDashboardData();
  const [selectedNuts3, setSelectedNuts3] = useState<string | null>(null);
  const [activeLayer, setActiveLayer] = useState<LayerType>('reform_cost');
  const [hoveredNuts3, setHoveredNuts3] = useState<string | null>(null);

  const regionGroups = useMemo(
    () => (data ? deriveRegionGroups(data) : new Map<string, RegionGroup>()),
    [data],
  );

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
            hoveredNuts3={hoveredNuts3}
            onCountyHover={setHoveredNuts3}
            regionGroups={regionGroups}
          />
        </div>
        <div className="w-[360px] shrink-0 border-l border-gray-200 overflow-y-auto">
          <RegionPanel
            nuts3Code={selectedNuts3}
            data={data}
            activeLayer={activeLayer}
            regionGroups={regionGroups}
            onCountyHover={setHoveredNuts3}
          />
        </div>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Verify TypeScript compiles**

Run: `cd dashboard && npx tsc --noEmit`
Expected: Errors in RomaniaMap.tsx and RegionPanel.tsx about unknown props — acceptable until Tasks 5 and 6 are done. No errors in App.tsx itself.

- [ ] **Step 3: Commit**

```bash
git add dashboard/src/App.tsx
git commit -m "feat(RO-dashboard): add hoveredNuts3, regionGroups state and deriveRegionGroups"
```

---

### Task 4: Update LayerSwitcher.tsx — add Region button

**Files:**
- Modify: `dashboard/src/components/LayerSwitcher.tsx`

- [ ] **Step 1: Add 4th LAYERS entry**

Replace the LAYERS array in `dashboard/src/components/LayerSwitcher.tsx`:

```typescript
const LAYERS: { id: LayerType; label: string }[] = [
  { id: 'reform_cost', label: 'Reform cost' },
  { id: 'suitability', label: 'Suitability' },
  { id: 'roi', label: 'ROI' },
  { id: 'region', label: 'Region' },
];
```

- [ ] **Step 2: Verify TypeScript compiles**

Run: `cd dashboard && npx tsc --noEmit`
Expected: No errors in LayerSwitcher.tsx.

- [ ] **Step 3: Commit**

```bash
git add dashboard/src/components/LayerSwitcher.tsx
git commit -m "feat(RO-dashboard): add Region layer button to LayerSwitcher"
```

---

### Task 5: Update RomaniaMap.tsx — new props, NUTS2 highlight, hover bindings

**Files:**
- Modify: `dashboard/src/components/RomaniaMap.tsx`

Context: Current file has `Props` interface with 4 props. `getStyle()` has three branches. `onEachFeature()` binds tooltip and click. `RegionGroup` must be imported from types.

- [ ] **Step 1: Rewrite RomaniaMap.tsx with new props and logic**

Replace the full contents of `dashboard/src/components/RomaniaMap.tsx` with:

```typescript
import { useEffect, useRef, useState } from 'react';
import { MapContainer, GeoJSON } from 'react-leaflet';
import type { GeoJSON as LeafletGeoJSON, Layer } from 'leaflet';
import type { GeoJsonObject, Feature, Geometry } from 'geojson';
import type { DashboardData, LayerType, RegionGroup } from '../types';
import { reformCostColor, suitabilityColor, roiColor, maxSuitability } from '../utils/color';

const GEOJSON_URL =
  'https://gisco-services.ec.europa.eu/distribution/v2/nuts/geojson/NUTS_RG_20M_2021_4326_LEVL_3.geojson';

interface Props {
  data: DashboardData;
  activeLayer: LayerType;
  selectedNuts3: string | null;
  onCountyClick: (nuts3: string) => void;
  hoveredNuts3: string | null;
  onCountyHover: (nuts3: string | null) => void;
  regionGroups: Map<string, RegionGroup>;
}

interface NutsFeature extends Feature<Geometry> {
  properties: { NUTS_ID: string; CNTR_CODE: string; NAME_LATN: string };
}

export default function RomaniaMap({
  data, activeLayer, selectedNuts3, onCountyClick,
  hoveredNuts3, onCountyHover,
}: Props) {
  const [geoJson, setGeoJson] = useState<GeoJsonObject | null>(null);
  const [geoError, setGeoError] = useState(false);
  const geoJsonRef = useRef<LeafletGeoJSON | null>(null);

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
          // @ts-expect-error – valid GeoJSON but GeoJsonObject type doesn't expose features
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

    if (activeLayer === 'region') {
      const selectedNuts2 = selectedNuts3
        ? (data.suitabilityByCode[selectedNuts3]?.nuts2_code ?? null)
        : null;
      const featureNuts2 = nuts3.slice(0, 4);
      const isSelectedRegion = featureNuts2 === selectedNuts2;
      const isHovered = nuts3 === hoveredNuts3;
      return {
        fillColor: isSelectedRegion ? '#7c3aed' : '#d1d5db',
        fillOpacity: isHovered ? 0.85 : isSelectedRegion ? 0.55 : 0.25,
        color: isSelectedRegion ? '#5b21b6' : '#9ca3af',
        weight: isHovered ? 3 : isSelectedRegion ? 2 : 0.5,
      };
    }

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

  function onEachFeature(feature: Feature, layer: Layer) {
    const nuts3 = (feature as NutsFeature).properties.NUTS_ID;
    const name = (feature as NutsFeature).properties.NAME_LATN;
    layer.bindTooltip(name, { sticky: true, className: 'text-xs' });
    layer.on('click', () => onCountyClick(nuts3));
    layer.on('mouseover', () => onCountyHover(nuts3));
    layer.on('mouseout', () => onCountyHover(null));
  }

  if (geoError) {
    return (
      <div className="h-full flex flex-col items-center justify-center gap-2 bg-blue-50">
        <span className="text-red-500 text-sm">&#9888; Map unavailable (CDN unreachable)</span>
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
        Loading map&hellip;
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
        key={`${activeLayer}-${selectedNuts3}-${hoveredNuts3}`}
        ref={geoJsonRef}
        data={geoJson}
        style={getStyle}
        onEachFeature={onEachFeature}
      />
    </MapContainer>
  );
}
```

Note: `regionGroups` is accepted in Props but not used directly in RomaniaMap — the NUTS2 derivation uses `suitabilityByCode` which is already in `data`. The prop is kept in the interface for forward compatibility but destructured away (just not used).

Actually, remove `regionGroups` from the destructuring since it's unused:

The Props interface includes it for type-checking from App.tsx, but it doesn't need to be destructured. The component can just ignore it. TypeScript will complain if it's declared in Props but NOT passed — so keep it in Props, just don't destructure it. The code above already handles this correctly.

- [ ] **Step 2: Verify TypeScript compiles**

Run: `cd dashboard && npx tsc --noEmit`
Expected: Errors only in RegionPanel.tsx (until Task 6). No errors in RomaniaMap.tsx.

- [ ] **Step 3: Commit**

```bash
git add dashboard/src/components/RomaniaMap.tsx
git commit -m "feat(RO-dashboard): NUTS2 region highlight and county hover in RomaniaMap"
```

---

### Task 6: Update RegionPanel.tsx — branch on region layer

**Files:**
- Modify: `dashboard/src/components/RegionPanel.tsx`

Context: Current RegionPanel has Props with `nuts3Code` and `data`. Needs 3 new props: `activeLayer`, `regionGroups`, `onCountyHover`. When `activeLayer === 'region'`, it renders `RegionOverlayChart` instead of the 4-tab layout.

- [ ] **Step 1: Rewrite RegionPanel.tsx with new props and region branch**

Replace the full contents of `dashboard/src/components/RegionPanel.tsx` with:

```typescript
import { useState } from 'react';
import type { DashboardData, LayerType, RegionGroup } from '../types';
import CounterfactualChart from './CounterfactualChart';
import ForecastPanel from './ForecastPanel';
import MegaCampusBadge from './MegaCampusBadge';
import MethodsTab from './MethodsTab';
import RegionOverlayChart from './RegionOverlayChart';

interface Props {
  nuts3Code: string | null;
  data: DashboardData;
  activeLayer: LayerType;
  regionGroups: Map<string, RegionGroup>;
  onCountyHover: (nuts3: string | null) => void;
}

type Tab = 'counterfactual' | 'forecast' | 'megacampus' | 'methods';

const TABS: { id: Tab; label: string }[] = [
  { id: 'counterfactual', label: 'Counterfactual' },
  { id: 'forecast', label: 'Forecast' },
  { id: 'megacampus', label: 'MegaCampus' },
  { id: 'methods', label: 'Methods' },
];

export default function RegionPanel({ nuts3Code, data, activeLayer, regionGroups, onCountyHover }: Props) {
  const [activeTab, setActiveTab] = useState<Tab>('counterfactual');

  if (!nuts3Code) {
    return (
      <div className="flex flex-col items-center justify-center h-full text-gray-400 text-sm gap-2 p-6">
        <span className="text-2xl">🗺</span>
        <p>Click a county on the map to view its detail</p>
      </div>
    );
  }

  // Region layer: show NUTS2 consolidation overlay
  if (activeLayer === 'region') {
    const suit = data.suitabilityByCode[nuts3Code];
    const nuts2 = suit?.nuts2_code;
    const group = nuts2 ? regionGroups.get(nuts2) : undefined;
    if (!group) {
      return (
        <div className="p-4 text-gray-400 text-sm">
          No region data for {nuts3Code}
        </div>
      );
    }
    return <RegionOverlayChart group={group} data={data} onCountyHover={onCountyHover} />;
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

- [ ] **Step 2: Verify TypeScript compiles**

Run: `cd dashboard && npx tsc --noEmit`
Expected: Error about `RegionOverlayChart` not found — acceptable until Task 7.

- [ ] **Step 3: Commit**

```bash
git add dashboard/src/components/RegionPanel.tsx
git commit -m "feat(RO-dashboard): RegionPanel branches to RegionOverlayChart on region layer"
```

---

### Task 7: Create RegionOverlayChart.tsx — gradient overlay chart

**Files:**
- Create: `dashboard/src/components/RegionOverlayChart.tsx`

Context:
- `ForecastCounty.forecasts` is `Record<string, Record<string, ForecastPoint[]>>` — access as `forecasts[outcome]['innovation_hub']` for an array of `{ year, value, lo80, hi80, lo95, hi95 }`.
- Satellite counties sorted by `maxSuitability()` descending (highest on top in the chart).
- All 6 peak enhancements: (1) cross-highlight, (2) 2025 anchor, (3) 2040 pills, (4) suitability colour, (5) region total line, (6) KPI chip.

- [ ] **Step 1: Create the file**

Create `dashboard/src/components/RegionOverlayChart.tsx` with the following content:

```typescript
import { useState, useMemo } from 'react';
import {
  ComposedChart, Area, Line, XAxis, YAxis, CartesianGrid,
  Tooltip, Legend, ReferenceLine, ResponsiveContainer,
} from 'recharts';
import type { DashboardData, RegionGroup } from '../types';
import { suitabilityToHex, maxSuitability } from '../utils/color';

type OutcomeId = 'ln_population' | 'ln_gva_per_empl' | 'nat_change_rate' | 'unemployment';

const OUTCOME_LABELS: Record<OutcomeId, string> = {
  ln_population:   'ln(population)',
  ln_gva_per_empl: 'ln(GVA/employed)',
  nat_change_rate: 'Natural change rate',
  unemployment:    'Unemployment',
};

const ALL_OUTCOMES: OutcomeId[] = ['ln_population', 'ln_gva_per_empl', 'nat_change_rate', 'unemployment'];

interface Props {
  group: RegionGroup;
  data: DashboardData;
  onCountyHover: (nuts3: string | null) => void;
}

export default function RegionOverlayChart({ group, data, onCountyHover }: Props) {
  const [outcome, setOutcome] = useState<OutcomeId>('ln_population');

  // Sort satellites by suitability descending (highest drawn last = on top)
  const sortedSatellites = useMemo(() => {
    return [...group.satellites].sort((a, b) => {
      const sa = data.suitabilityByCode[a];
      const sb = data.suitabilityByCode[b];
      return (sb ? maxSuitability(sb) : 0) - (sa ? maxSuitability(sa) : 0);
    });
  }, [group.satellites, data.suitabilityByCode]);

  // Colour per satellite
  const countyColor = useMemo(() => {
    const m = new Map<string, string>();
    for (const nuts3 of group.satellites) {
      const suit = data.suitabilityByCode[nuts3];
      m.set(nuts3, suitabilityToHex(suit ? maxSuitability(suit) : 0.5));
    }
    return m;
  }, [group.satellites, data.suitabilityByCode]);

  // Years from any satellite's innovation_hub path
  const years = useMemo(() => {
    const ys = new Set<number>();
    for (const nuts3 of group.satellites) {
      const fc = data.forecastsByCode[nuts3];
      (fc?.forecasts[outcome]?.['innovation_hub'] ?? []).forEach((p) => ys.add(p.year));
    }
    return Array.from(ys).sort((a, b) => a - b);
  }, [group.satellites, data.forecastsByCode, outcome]);

  // Chart data: one row per year
  const chartData = useMemo(() => {
    return years.map((year) => {
      const row: Record<string, number | undefined> = { year };
      for (const nuts3 of group.satellites) {
        const fc = data.forecastsByCode[nuts3];
        const ih = fc?.forecasts[outcome]?.['innovation_hub']?.find((p) => p.year === year);
        const sq = fc?.forecasts[outcome]?.['status_quo']?.find((p) => p.year === year);
        row[`${nuts3}_ih`] = ih?.value ?? undefined;
        row[`${nuts3}_sq`] = sq?.value ?? undefined;
      }
      // Region aggregate: sum of innovation_hub values across satellites
      const ihValues = group.satellites
        .map((n) => {
          const fc = data.forecastsByCode[n];
          return fc?.forecasts[outcome]?.['innovation_hub']?.find((p) => p.year === year)?.value;
        })
        .filter((v): v is number => v != null);
      row['region_total_ih'] = ihValues.length > 0 ? ihValues.reduce((a, b) => a + b, 0) : undefined;
      return row;
    });
  }, [years, group.satellites, data.forecastsByCode, outcome]);

  // 2040 uplift pills
  const uplifts = useMemo(() => {
    return group.satellites
      .map((nuts3) => ({
        nuts3,
        name: data.suitabilityByCode[nuts3]?.judet_name ?? nuts3,
        color: countyColor.get(nuts3) ?? '#8b5cf6',
        upliftPct: data.regionsByCode[nuts3]?.innovation_uplift_pct_2040 ?? null,
      }))
      .filter((u) => u.upliftPct != null)
      .sort((a, b) => (b.upliftPct ?? 0) - (a.upliftPct ?? 0));
  }, [group.satellites, data, countyColor]);

  const avgUplift =
    uplifts.length > 0
      ? uplifts.reduce((s, u) => s + (u.upliftPct ?? 0), 0) / uplifts.length
      : null;

  const hub = group.hubNuts3 ? data.suitabilityByCode[group.hubNuts3] : null;

  return (
    <div className="flex flex-col h-full overflow-y-auto">
      {/* Hub header */}
      <div className="px-4 py-2 bg-violet-50 border-b border-violet-100 shrink-0">
        <div className="font-bold text-violet-900 text-sm">
          {hub?.judet_name ?? group.nuts2Code} — {group.nuts2Code}
        </div>
        <div className="text-violet-600 text-xs mt-0.5">
          Regional capital — investment anchor · {group.satellites.length} satellite counties
        </div>
        {hub && (
          <div className="text-violet-400 text-xs">(Hub county: no MG-VAR forecast modelled)</div>
        )}
      </div>

      <div className="p-3 flex flex-col gap-2">
        {/* KPI chip */}
        {avgUplift != null && (
          <div className="text-xs bg-violet-50 text-violet-800 rounded px-2 py-1 font-medium">
            Avg. pop uplift by 2040 across {uplifts.length} counties:
            <span className="ml-1 font-bold">+{avgUplift.toFixed(1)}%</span>
            {' '}(innovation_hub vs status_quo)
          </div>
        )}

        {/* Outcome selector */}
        <select
          value={outcome}
          onChange={(e) => setOutcome(e.target.value as OutcomeId)}
          className="text-xs border border-gray-200 rounded px-2 py-1 bg-white self-start"
        >
          {ALL_OUTCOMES.map((id) => (
            <option key={id} value={id}>{OUTCOME_LABELS[id]}</option>
          ))}
        </select>

        {years.length === 0 ? (
          <div className="text-gray-400 text-sm">No forecast data for this region.</div>
        ) : (
          <>
            {/* Gradient overlay chart */}
            <ResponsiveContainer width="100%" height={260}>
              <ComposedChart data={chartData} margin={{ top: 4, right: 8, bottom: 4, left: 8 }}>
                <defs>
                  {sortedSatellites.map((nuts3) => {
                    const color = countyColor.get(nuts3) ?? '#8b5cf6';
                    return (
                      <linearGradient key={nuts3} id={`grad-${nuts3}`} x1="0" y1="0" x2="0" y2="1">
                        <stop offset="0%" stopColor={color} stopOpacity={0.55} />
                        <stop offset="100%" stopColor={color} stopOpacity={0} />
                      </linearGradient>
                    );
                  })}
                </defs>

                <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                <XAxis dataKey="year" tick={{ fontSize: 10 }} interval={2} />
                <YAxis tick={{ fontSize: 10 }} tickFormatter={(v: number) => v.toFixed(2)} width={45} />
                <Tooltip contentStyle={{ fontSize: 11 }} labelFormatter={(l) => `Year ${l}`} />

                <ReferenceLine
                  x={2025}
                  stroke="#d97706"
                  strokeDasharray="4 3"
                  label={{ value: 'Reform 2025', fontSize: 9, fill: '#d97706', position: 'insideTopLeft' }}
                />

                {/* Per-county gradient bands: sorted lowest-suitability first so highest renders on top */}
                {sortedSatellites.map((nuts3) => {
                  const color = countyColor.get(nuts3) ?? '#8b5cf6';
                  const name = data.suitabilityByCode[nuts3]?.judet_name ?? nuts3;
                  return [
                    // Gradient fill from 0 to innovation_hub
                    <Area
                      key={`${nuts3}-ih`}
                      type="monotone"
                      dataKey={`${nuts3}_ih`}
                      fill={`url(#grad-${nuts3})`}
                      stroke={color}
                      strokeWidth={2}
                      dot={false}
                      legendType="line"
                      name={name}
                      isAnimationActive={true}
                    />,
                    // White fill from 0 to status_quo — erases gradient below the scenario gap
                    <Area
                      key={`${nuts3}-sq`}
                      type="monotone"
                      dataKey={`${nuts3}_sq`}
                      fill="#ffffff"
                      stroke={color}
                      strokeWidth={1}
                      strokeDasharray="4 2"
                      strokeOpacity={0.5}
                      dot={false}
                      legendType="none"
                      name=""
                      isAnimationActive={true}
                    />,
                  ];
                })}

                {/* Aggregate region total */}
                <Line
                  type="monotone"
                  dataKey="region_total_ih"
                  stroke="#0f172a"
                  strokeWidth={2.5}
                  dot={false}
                  name="Region total"
                  legendType="line"
                />

                <Legend
                  iconSize={10}
                  wrapperStyle={{ fontSize: 10 }}
                  onMouseEnter={(entry) => {
                    // entry.dataKey is the Area/Line dataKey
                    const dk = (entry as { dataKey?: string }).dataKey ?? '';
                    const nuts3 = dk.replace('_ih', '');
                    if (group.satellites.includes(nuts3)) onCountyHover(nuts3);
                  }}
                  onMouseLeave={() => onCountyHover(null)}
                />
              </ComposedChart>
            </ResponsiveContainer>

            <div className="text-xs text-gray-400">
              Solid = innovation_hub · Dashed = status_quo · Gradient band = scenario gap · Colour = MegaCampus suitability
            </div>

            {/* 2040 uplift pills */}
            {uplifts.length > 0 && (
              <div className="flex flex-wrap gap-1 mt-1">
                {uplifts.map((u) => (
                  <span
                    key={u.nuts3}
                    className="text-xs px-1.5 py-0.5 rounded-full font-medium"
                    style={{ background: u.color + '22', color: u.color, border: `1px solid ${u.color}44` }}
                    onMouseEnter={() => onCountyHover(u.nuts3)}
                    onMouseLeave={() => onCountyHover(null)}
                  >
                    {u.name} +{u.upliftPct?.toFixed(1)}%
                  </span>
                ))}
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Verify TypeScript compiles clean**

Run: `cd dashboard && npx tsc --noEmit`
Expected: Zero errors across all files.

- [ ] **Step 3: Commit**

```bash
git add dashboard/src/components/RegionOverlayChart.tsx
git commit -m "feat(RO-dashboard): RegionOverlayChart with gradient bands and 6 peak enhancements"
```

---

### Task 8: Integration smoke-test and final commit

**Files:**
- No new files

- [ ] **Step 1: Start the dev server and verify the app loads**

Run: `cd dashboard && npm run dev`
Expected: Vite outputs `Local: http://localhost:5173` with no build errors.

- [ ] **Step 2: Manually verify each piece works**

In the browser at http://localhost:5173:
1. Click "Region" in the layer switcher → map turns grey/light purple
2. Click any county on the map → the entire NUTS2 region it belongs to lights up violet
3. Sidebar shows RegionOverlayChart (violet header with hub name, satellite count)
4. KPI chip shows average uplift %
5. Outcome selector changes the chart data
6. Lines and gradient bands render per satellite county
7. "Region total" dark thick line is visible
8. Dashed yellow vertical line at x=2025
9. 2040 uplift pills appear below the chart with county names and %
10. Hovering a legend item highlights the corresponding polygon on the map
11. Hovering an uplift pill also highlights the county on the map
12. Switching back to "Reform cost", "Suitability", or "ROI" layer restores normal county-level choropleth

- [ ] **Step 3: Verify TypeScript one final time**

Run: `cd dashboard && npx tsc --noEmit`
Expected: Zero errors.

- [ ] **Step 4: Final commit**

```bash
git add -A
git commit -m "feat(RO-dashboard): Region View complete — NUTS2 overlay with gradient bands"
```

---

## Self-Review

**Spec coverage:**
1. ✅ Chart × map cross-highlight — `onCountyHover` on legend entry and uplift pills → map `hoveredNuts3`
2. ✅ 2025-anchored diverging bands — `<ReferenceLine x={2025}>` + data starts at 2025
3. ✅ 2040 callout labels — uplift pill chips from `innovation_uplift_pct_2040`
4. ✅ Suitability-encoded colour — `suitabilityToHex(maxSuitability(suit))` per county
5. ✅ Aggregate "Region total" line — `region_total_ih` computed as sum of satellite ih values
6. ✅ Cumulative KPI chip — `avgUplift` across all satellites with forecast data

**Placeholder scan:** No TBD, TODO, or vague steps found.

**Type consistency:**
- `RegionGroup` defined in Task 1, imported in Tasks 3, 6, 7 — consistent
- `suitabilityToHex` defined in Task 2, imported in Task 7 — consistent
- `hoveredNuts3: string | null` flows App → RomaniaMap (Task 5) and App → RegionPanel → RegionOverlayChart (Tasks 6, 7) — consistent
- `ForecastCounty.forecasts[outcome]['innovation_hub']` access matches `Record<string, Record<string, ForecastPoint[]>>` type from types.ts — consistent
- `maxSuitability()` signature in color.ts requires the full suitability object — Task 7 passes `data.suitabilityByCode[nuts3]` which is `SuitabilityData` — consistent

**Note on RomaniaMap key prop:** Changed from `${activeLayer}-${selectedNuts3}` to `${activeLayer}-${selectedNuts3}-${hoveredNuts3}` so hover state changes trigger GeoJSON re-render. This is necessary for the region layer where hover opacity changes require a full style recalculation. For other layers this adds slight re-renders on hover but is functionally correct.
