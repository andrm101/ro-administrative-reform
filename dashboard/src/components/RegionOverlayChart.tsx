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
