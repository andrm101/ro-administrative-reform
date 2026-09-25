import { useState, useMemo, useEffect } from 'react';
import {
  ComposedChart, Area, XAxis, YAxis, CartesianGrid, Tooltip,
  ReferenceLine, ResponsiveContainer,
} from 'recharts';
import type { CountyPrimitive, DashboardData, LeverVector, RegionGroup } from '../types';
import type { InfraLayer } from '../types';
import { DEFAULT_LEVERS } from '../types';
import { applyScenario } from '../engine/scenario';
import { leversToQuery, queryToLevers } from '../utils/scenarioUrl';
import { lnDeltaToPct, formatPct, formatPp, formatEur } from '../utils/format';
import LeverPanel from './LeverPanel';
import RegimeBadge from './RegimeBadge';
import CostReadout from './CostReadout';
import MetricTooltip from './MetricTooltip';
import CapacityCard from './CapacityCard';
import DivergenceAlert from './DivergenceAlert';

interface Props {
  nuts3Code: string | null;
  data: DashboardData;
  regionGroups: Map<string, RegionGroup>;
  infraLayer: InfraLayer | null;   // ← add
}

export default function PolicyLab({ nuts3Code, data, regionGroups, infraLayer }: Props) {
  const [levers, setLevers] = useState<LeverVector>(() =>
    queryToLevers(new URLSearchParams(window.location.search)),
  );

  const [leversSeededFrom, setLeversSeededFrom] = useState<string | null>(null);

  useEffect(() => {
    const q = leversToQuery(levers);
    const url = q ? `${window.location.pathname}?${q}` : window.location.pathname;
    window.history.replaceState(null, '', url);
  }, [levers]);

  useEffect(() => {
    if (!nuts3Code || !infraLayer || leversSeededFrom === nuts3Code) return;
    const county = infraLayer.counties[nuts3Code];
    if (!county) return;
    setLevers((prev) => ({
      ...prev,
      skills: parseFloat((county.pillars.education.score / 100 * 5).toFixed(1)),
      conn:   parseFloat((county.pillars.transport.score / 100).toFixed(2)),
    }));
    setLeversSeededFrom(nuts3Code);
  }, [nuts3Code, infraLayer, leversSeededFrom]);

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

  const members = useMemo<CountyPrimitive[]>(() => {
    if (!group) return [];
    const codes = [group.hubNuts3, ...group.satellites].filter(Boolean) as string[];
    return codes.map((c) => primitives.get(c)).filter((m): m is CountyPrimitive => !!m);
  }, [group, primitives]);

  const totalPop = useMemo(() => members.reduce((s, m) => s + m.population, 0), [members]);
  const totalGva = useMemo(() => members.reduce((s, m) => s + m.gva_pc * m.population, 0), [members]);

  const popUpliftPct = useMemo(() => {
    if (!result || members.length === 0) return 0;
    return members.reduce((acc, m) => {
      const pts = result.perCountyPop[m.nuts3_code];
      const last = pts?.at(-1);
      if (!last) return acc;
      return acc + (m.population / (totalPop || 1)) * lnDeltaToPct(last.scenario - last.baseline);
    }, 0);
  }, [result, members, totalPop]);

  const hdiDeltaPp = useMemo(() => {
    if (!result || members.length === 0) return 0;
    const firstHDI = members.reduce((acc, m) => acc + (result.hdiProxy[m.nuts3_code]?.[0]?.value ?? 0) / members.length, 0);
    const lastHDI = members.reduce((acc, m) => acc + (result.hdiProxy[m.nuts3_code]?.at(-1)?.value ?? 0) / members.length, 0);
    return (lastHDI - firstHDI) * 100;
  }, [result, members]);

  function resetLeversToNeutral() {
    setLevers(DEFAULT_LEVERS);
    setLeversSeededFrom(null);
  }

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

  const lastPt = result.regionTotal.at(-1);
  const prodUpliftPct = lastPt ? lnDeltaToPct(lastPt.scenario - lastPt.baseline) : 0;

  const chartData = result.regionTotal.map((p) => ({
    year: p.year,
    upliftPct: lnDeltaToPct(p.scenario - p.baseline),
  }));

  const regimePValue = data.elasticities.regime_test?.p_value;

  const heroKpis = [
    { label: 'Region productivity @2040', value: formatPct(prodUpliftPct) },
    { label: 'Programme cost (NPV)', value: formatEur(result.cost2040) },
  ];

  return (
    <div className="flex flex-col h-full overflow-y-auto text-xs">
      <div className="px-4 py-2 bg-violet-50 border-b border-violet-100 shrink-0">
        <div className="font-bold text-violet-900 text-sm">Policy Lab — {group.nuts2Code}</div>
        <div className="text-violet-600 text-[11px]">{group.satellites.length} satellite counties</div>
      </div>

      <div className="p-3 space-y-2 shrink-0">
        <RegimeBadge result={result} regimePValue={regimePValue} />
        <div className="grid grid-cols-2 gap-2">
          {heroKpis.map(({ label, value }) => (
            <div key={label} className="bg-violet-50 rounded p-2">
              <div className="text-violet-500 text-[10px] leading-tight">{label}</div>
              <div className="font-bold text-violet-900 text-base tabular-nums">{value}</div>
            </div>
          ))}
        </div>
      </div>

      <ResponsiveContainer width="100%" height={180}>
        <ComposedChart data={chartData} margin={{ top: 4, right: 8, bottom: 4, left: 8 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
          <XAxis dataKey="year" tick={{ fontSize: 10 }} interval={2} />
          <YAxis
            tick={{ fontSize: 10 }}
            tickFormatter={(v: number) => `${v >= 0 ? '+' : ''}${v.toFixed(1)}%`}
            width={50}
          />
          <Tooltip
            contentStyle={{ fontSize: 11 }}
            formatter={(v: number) => [`${v >= 0 ? '+' : ''}${v.toFixed(2)}%`, 'Uplift']}
          />
          <ReferenceLine x={2025} stroke="#d97706" strokeDasharray="4 3" />
          <ReferenceLine y={0} stroke="#9ca3af" strokeWidth={1} />
          <Area
            type="monotone" dataKey="upliftPct"
            name="Scenario uplift %"
            stroke="#7c3aed" fill="#ede9fe" strokeWidth={2} dot={false}
          />
        </ComposedChart>
      </ResponsiveContainer>

      <CostReadout result={result} totalPop={totalPop} totalGva={totalGva} />

      {infraLayer && nuts3Code && infraLayer.counties[nuts3Code] && (
        <>
          {leversSeededFrom === nuts3Code && (
            <div className="mx-3 mb-1 text-[10px] text-blue-600 flex items-center justify-between">
              <span>Levers pre-seeded from infrastructure index</span>
              <button
                onClick={resetLeversToNeutral}
                className="underline hover:text-blue-800"
              >
                reset to neutral
              </button>
            </div>
          )}
          <CapacityCard
            county={infraLayer.counties[nuts3Code]}
            countyCode={nuts3Code}
            layer={infraLayer}
          />
        </>
      )}

      {infraLayer && nuts3Code && infraLayer.counties[nuts3Code]?.divergence && (
        <DivergenceAlert flag={infraLayer.counties[nuts3Code]!.divergence!} />
      )}

      <div className="grid grid-cols-2 gap-1.5 px-3 pb-2">
        {([
          {
            label: 'Productivity Δ',
            value: formatPct(prodUpliftPct),
            prov: data.elasticities.beta_K_sat?.provenance,
            gloss: 'ln-GVA/empl % uplift vs baseline at 2040. Driven by capital convergence speed (β_K_sat).',
          },
          {
            label: 'Population Δ',
            value: formatPct(popUpliftPct),
            prov: data.elasticities.beta_mig?.provenance,
            gloss: 'ln-population % uplift vs baseline at 2040. Driven by migration-retention elasticity (β_mig).',
          },
          {
            label: 'HDI proxy Δ',
            value: formatPp(hdiDeltaPp),
            prov: data.elasticities.beta_edu?.provenance,
            gloss: 'Interim HDI proxy change in percentage points (geometric mean of income, health, education indices).',
          },
          {
            label: 'Hub opportunity cost',
            value: formatPp(result.hubOpportunityCostPct),
            prov: data.elasticities.beta_K_hub?.provenance,
            gloss: 'Hub GVA growth change in p.p. — redistribution drains hub capital stock. Negative = hub cost.',
          },
        ] as const).map(({ label, value, prov, gloss }) => (
          <div key={label} className="bg-gray-50 rounded p-2">
            <div className="text-gray-500 text-[10px] leading-tight flex items-center gap-0.5">
              {label}
              <MetricTooltip provenance={prov} glossText={gloss} />
            </div>
            <div className="font-bold text-gray-900 mt-0.5 tabular-nums">{value}</div>
          </div>
        ))}
      </div>

      <LeverPanel levers={levers} onChange={setLevers} provisional={data.elasticities.provisional} />

      <div className="px-3 py-2 text-[10px] text-gray-400 border-t border-gray-100 shrink-0">
        Levels (productivity, population): % uplift = (e<sup>Δln</sup> − 1) × 100.
        Rates (HDI, opportunity cost): p.p. = percentage points.
      </div>
    </div>
  );
}
