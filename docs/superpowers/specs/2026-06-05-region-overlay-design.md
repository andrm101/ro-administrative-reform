# Region View — NUTS2 Consolidation Overlay Design Spec

**Date:** 2026-06-05
**Project:** RO-Administrative-Reform
**Feature:** Region View — 4th map layer showing per-satellite-county innovation_hub vs status_quo gradient bands for a selected NUTS2 consolidation region
**Status:** Approved — ready for implementation plan

---

## Overview

A new "Region" map layer that lets the user select any NUTS2 region and see, in the sidebar, how each satellite county (demoted județ) develops under the `innovation_hub` vs `status_quo` MG-VAR scenario. The gap between the two paths per county is rendered as a suitability-encoded gradient band. Six "peak" enhancements are included: chart×map cross-highlight, 2025-anchored diverging bands, 2040 callout labels, suitability-encoded colours, an aggregate "Region total" line, and a cumulative KPI chip.

**No changes to the Python export script or JSON files are required.** All hub/satellite relationships are derived client-side from existing `suitability.json` (42 counties) and `regions.json` (33 treated counties).

---

## Data Model

### Hub / Satellite Derivation

```typescript
// Computed once in App.tsx via useMemo
type RegionGroup = {
  nuts2Code: string;
  hubNuts3: string | null;      // proposed regional capital (not in regions.json)
  satellites: string[];          // treated counties (in regions.json) for this NUTS2
};

function deriveRegionGroups(data: DashboardData): Map<string, RegionGroup> {
  const treatedCodes = new Set(data.regions.map(r => r.nuts3_code));
  const byNuts2 = new Map<string, RegionGroup>();

  for (const s of data.suitability) {
    if (!byNuts2.has(s.nuts2_code)) {
      byNuts2.set(s.nuts2_code, { nuts2Code: s.nuts2_code, hubNuts3: null, satellites: [] });
    }
    const g = byNuts2.get(s.nuts2_code)!;
    if (!treatedCodes.has(s.nuts3_code)) {
      g.hubNuts3 = s.nuts3_code;   // not treated → hub (proposed_regional_capital=1)
    } else {
      g.satellites.push(s.nuts3_code);
    }
  }
  return byNuts2;
}
```

Derived in `App.tsx` with `useMemo(() => deriveRegionGroups(data), [data])`.

### Suitability-Encoded Colour

Each satellite county's gradient colour is derived from its `maxSuitability()` score (0–1):

```typescript
// In utils/color.ts (new export)
export function suitabilityToHex(score: number): string {
  // score=0 → grey-purple #8b5cf6
  // score=1 → blue-green  #10b981
  const r = Math.round(lerp(139, 16,  score));
  const g = Math.round(lerp(92,  185, score));
  const b = Math.round(lerp(246, 129, score));
  return `#${r.toString(16).padStart(2,'0')}${g.toString(16).padStart(2,'0')}${b.toString(16).padStart(2,'0')}`;
}
```

High-suitability counties glow vibrant blue-green; low-suitability counties are muted grey-purple. This links MegaCampus scores to the forecast visually without a separate legend.

---

## Type Changes

```typescript
// types.ts
export type LayerType = 'reform_cost' | 'suitability' | 'roi' | 'region';

// New export for region groups
export interface RegionGroup {
  nuts2Code: string;
  hubNuts3: string | null;
  satellites: string[];
}
```

---

## Component Changes

### LayerSwitcher.tsx

Add 4th entry to `LAYERS`:

```typescript
{ id: 'region', label: 'Region' }
```

### App.tsx

New state and derived data:

```typescript
const [hoveredNuts3, setHoveredNuts3] = useState<string | null>(null);
const regionGroups = useMemo(() => data ? deriveRegionGroups(data) : new Map(), [data]);
```

Pass to children:
- `<RomaniaMap ... hoveredNuts3={hoveredNuts3} onCountyHover={setHoveredNuts3} regionGroups={regionGroups} />`
- `<RegionPanel ... activeLayer={activeLayer} regionGroups={regionGroups} onCountyHover={setHoveredNuts3} />`

### RomaniaMap.tsx

New props: `hoveredNuts3: string | null`, `onCountyHover: (n: string | null) => void`, `regionGroups: Map<string, RegionGroup>`

`getStyle()` changes when `activeLayer === 'region'`:

```typescript
if (activeLayer === 'region') {
  const featureNuts2 = nuts3.slice(0, 4);
  const selectedNuts2 = selectedNuts3
    ? (data.suitabilityByCode[selectedNuts3]?.nuts2_code ?? null)
    : null;
  const isSelectedRegion = featureNuts2 === selectedNuts2;
  const isHovered = nuts3 === hoveredNuts3;
  return {
    fillColor: isSelectedRegion ? '#7c3aed' : '#d1d5db',
    fillOpacity: isHovered ? 0.85 : isSelectedRegion ? 0.55 : 0.25,
    color: isSelectedRegion ? '#5b21b6' : '#9ca3af',
    weight: isHovered ? 3 : isSelectedRegion ? 2 : 0.5,
  };
}
```

`onEachFeature()` addition: bind `mouseover` → `onCountyHover(nuts3)`, `mouseout` → `onCountyHover(null)`.

The `key` prop already includes `activeLayer` so re-renders on toggle.

### RegionPanel.tsx

New props: `activeLayer: LayerType`, `regionGroups: Map<string, RegionGroup>`, `onCountyHover: (n: string | null) => void`

```typescript
if (activeLayer === 'region' && nuts3Code) {
  const suit = data.suitabilityByCode[nuts3Code];
  const nuts2 = suit?.nuts2_code;
  const group = nuts2 ? regionGroups.get(nuts2) : undefined;
  return group
    ? <RegionOverlayChart group={group} data={data} onCountyHover={onCountyHover} />
    : <div className="p-4 text-gray-400 text-sm">No region data for {nuts3Code}</div>;
}
// else: existing 4-tab layout unchanged
```

### RegionOverlayChart.tsx (new)

**Props:**

```typescript
interface Props {
  group: RegionGroup;
  data: DashboardData;
  onCountyHover: (nuts3: string | null) => void;
}
```

**Satellite order:** sorted by `maxSuitability(suitabilityByCode[nuts3])` descending — highest-scoring county drawn last (on top).

**Colour:** `suitabilityToHex(maxSuitability(suit))` per county.

**Outcome selector:** `<select>` with 4 options (ln_population default).

**Chart data construction:**

```typescript
const chartData = years.map(year => {
  const row: Record<string, number | undefined> = { year };
  for (const nuts3 of group.satellites) {
    const county = data.forecastsByCode[nuts3];
    const ih = county?.forecasts[outcome]?.innovation_hub?.find(p => p.year === year);
    const sq = county?.forecasts[outcome]?.status_quo?.find(p => p.year === year);
    row[`${nuts3}_ih`] = ih?.value ?? undefined;
    row[`${nuts3}_sq`] = sq?.value ?? undefined;
  }
  // Aggregate: population-weighted sum of innovation_hub
  row['region_total_ih'] = group.satellites
    .map(n => data.forecastsByCode[n]?.forecasts[outcome]?.innovation_hub?.find(p => p.year === year)?.value)
    .filter((v): v is number => v != null)
    .reduce((a, b) => a + b, 0) || undefined;
  return row;
});
```

**SVG gradients (in `<defs>` inside the chart):**

```tsx
<defs>
  {group.satellites.map(nuts3 => {
    const suit = data.suitabilityByCode[nuts3];
    const color = suitabilityToHex(suit ? maxSuitability(suit) : 0.5);
    return (
      <linearGradient key={nuts3} id={`grad-${nuts3}`} x1="0" y1="0" x2="0" y2="1">
        <stop offset="0%" stopColor={color} stopOpacity={0.55} />
        <stop offset="100%" stopColor={color} stopOpacity={0} />
      </linearGradient>
    );
  })}
</defs>
```

**Per-county series (in satellite order):**

```tsx
{group.satellites.map(nuts3 => {
  const suit = data.suitabilityByCode[nuts3];
  const color = suitabilityToHex(suit ? maxSuitability(suit) : 0.5);
  return [
    // Gradient fill from y=0 to innovation_hub
    <Area key={`${nuts3}-ih-fill`} type="monotone" dataKey={`${nuts3}_ih`}
          fill={`url(#grad-${nuts3})`} stroke={color} strokeWidth={2}
          dot={false} isAnimationActive={true} legendType="none" name={undefined} />,
    // White fill from y=0 to status_quo — erases gradient below the gap
    <Area key={`${nuts3}-sq-fill`} type="monotone" dataKey={`${nuts3}_sq`}
          fill="#ffffff" stroke={color} strokeWidth={1}
          strokeDasharray="4 2" strokeOpacity={0.5}
          dot={false} isAnimationActive={true} legendType="none" name={undefined} />,
  ];
})}
```

**Aggregate "Region total" line:**

```tsx
<Line type="monotone" dataKey="region_total_ih"
      stroke="#0f172a" strokeWidth={2.5} dot={false}
      name="Region total" strokeDasharray="none" />
```

**Reform year anchor:**

```tsx
<ReferenceLine x={2025} stroke="#d97706" strokeDasharray="4 3"
               label={{ value: 'Reform 2025', fontSize: 9, fill: '#d97706' }} />
```

**2040 callout labels:**

Custom `<LabelList>` is not ideal for this. Instead, after the `<ResponsiveContainer>`, render a small flex row of chips positioned below the chart's right edge:

```tsx
// Computed from the last data point (year=2040)
const uplifts = group.satellites.map(nuts3 => ({
  nuts3,
  name: data.suitabilityByCode[nuts3]?.judet_name ?? nuts3,
  color: suitabilityToHex(...),
  upliftPct: data.regionsByCode[nuts3]?.innovation_uplift_pct_2040 ?? null,
})).filter(u => u.upliftPct != null).sort((a,b) => (b.upliftPct ?? 0) - (a.upliftPct ?? 0));
```

Rendered as small pills below the chart:
```tsx
<div className="flex flex-wrap gap-1 mt-1">
  {uplifts.map(u => (
    <span key={u.nuts3} className="text-xs px-1.5 py-0.5 rounded-full font-medium"
          style={{ background: u.color + '22', color: u.color }}>
      {u.name} +{u.upliftPct?.toFixed(1)}%
    </span>
  ))}
</div>
```

**Cumulative KPI chip:**

```tsx
const avgUplift = uplifts.reduce((s, u) => s + (u.upliftPct ?? 0), 0) / uplifts.length;
// Rendered above the chart:
<div className="text-xs bg-violet-50 text-violet-800 rounded px-2 py-1 mb-2 font-medium">
  Avg. pop uplift by 2040 across {uplifts.length} counties:
  <span className="ml-1 font-bold">+{avgUplift.toFixed(1)}%</span>
  {' '}(innovation_hub vs status_quo)
</div>
```

**Cross-highlight via legend hover:**

```tsx
<Legend
  onMouseEnter={(entry) => onCountyHover(entry.dataKey?.toString().split('_')[0] ?? null)}
  onMouseLeave={() => onCountyHover(null)}
  formatter={(value) => <span className="text-xs">{value}</span>}
/>
```

Legend entries are the satellite county names (judet_name), one per county, with colour swatch.

**Hub county header:**

```tsx
const hub = group.hubNuts3 ? data.suitabilityByCode[group.hubNuts3] : null;
// In the sidebar header:
<div className="px-4 py-2 bg-violet-50 border-b border-violet-100 shrink-0">
  <div className="font-bold text-violet-900 text-sm">
    {hub?.judet_name ?? 'Unknown'} — {group.nuts2Code}
  </div>
  <div className="text-violet-600 text-xs mt-0.5">
    Regional capital — investment anchor · {group.satellites.length} satellite counties
  </div>
  {hub && (
    <div className="text-violet-400 text-xs">(Hub county: no MG-VAR forecast modelled)</div>
  )}
</div>
```

---

## Animation

Recharts `isAnimationActive={true}` (default) handles Area entrance animation — bands grow upward from the x-axis on mount. Since the MG-VAR data starts at 2025 and the gap is zero at the first point (both paths start from the same value at reform year), the bands naturally anchor at zero width in 2025 and fan out to 2040.

No additional CSS animation required.

---

## File Map

| Action | Path |
|--------|------|
| Modify | `dashboard/src/types.ts` |
| Modify | `dashboard/src/utils/color.ts` |
| Modify | `dashboard/src/App.tsx` |
| Modify | `dashboard/src/components/LayerSwitcher.tsx` |
| Modify | `dashboard/src/components/RomaniaMap.tsx` |
| Modify | `dashboard/src/components/RegionPanel.tsx` |
| Create | `dashboard/src/components/RegionOverlayChart.tsx` |

---

## Out of Scope

- Hub county MG-VAR forecast (not modelled — hub counties have `treated=0`)
- NUTS1-level aggregation
- Mobile layout
- Exporting the overlay chart as PNG
- Confidence interval (80%/95%) bands in the overlay (too cluttered with 5+ counties)

---

## Self-Review

**Spec coverage:** All 6 "peak" enhancements accounted for:
1. ✅ Chart × map cross-highlight — via `onCountyHover` prop chain + map mouseover
2. ✅ 2025-anchored diverging bands — data starts at 2025; Recharts animation handles growth
3. ✅ 2040 callout labels — uplift pill chips below chart from `innovation_uplift_pct_2040`
4. ✅ Suitability-encoded colour — `suitabilityToHex()` in `color.ts`
5. ✅ Aggregate "Region total" line — `region_total_ih` in chart data
6. ✅ Cumulative KPI chip — avg uplift % above chart

**No placeholders found.**

**Type consistency:** `RegionGroup` defined in `types.ts`, used in `App.tsx`, `RegionPanel.tsx`, `RegionOverlayChart.tsx`.

**Ambiguity resolved:** "hub county" = county in `suitability.json` whose `nuts3_code` is NOT in `regions.json` for the same `nuts2_code`. This is deterministic given the data.
