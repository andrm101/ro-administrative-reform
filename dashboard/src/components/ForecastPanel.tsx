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

const ALL_PATHS: PathId[] = ['status_quo', 'counterfactual', 'innovation_hub'];
const ALL_OUTCOMES: OutcomeId[] = ['ln_population', 'ln_gva_per_empl', 'nat_change_rate', 'unemployment'];

interface Props {
  forecasts: Record<string, Record<string, ForecastPoint[]>>;
}

export default function ForecastPanel({ forecasts }: Props) {
  const availablePaths = ALL_PATHS.filter((p) =>
    ALL_OUTCOMES.some((v) => forecasts[v]?.[p] != null),
  );

  const [selectedPaths, setSelectedPaths] = useState<Set<PathId>>(
    new Set(ALL_PATHS),
  );
  const [outcome, setOutcome] = useState<OutcomeId>('ln_population');

  function togglePath(path: PathId) {
    setSelectedPaths((prev) => {
      const next = new Set(prev);
      if (next.has(path) && next.size > 1) {
        next.delete(path);
      } else {
        next.add(path);
      }
      return next;
    });
  }

  const pathData = forecasts[outcome] ?? {};
  const allYears = new Set<number>();
  for (const p of selectedPaths) {
    (pathData[p] ?? []).forEach((pt) => allYears.add(pt.year));
  }

  const chartData = Array.from(allYears)
    .sort((a, b) => a - b)
    .map((year) => {
      const row: Record<string, number | string | undefined> = { year };
      for (const p of selectedPaths) {
        const pt = (pathData[p] ?? []).find((x) => x.year === year);
        if (pt) {
          row[`${p}_value`] = pt.value ?? undefined;
          row[`${p}_lo80`]  = pt.lo80  ?? undefined;
          row[`${p}_hi80`]  = pt.hi80  ?? undefined;
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
          {ALL_OUTCOMES.map((id) => (
            <option key={id} value={id}>{OUTCOME_LABELS[id]}</option>
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

          {Array.from(selectedPaths).flatMap((p) => {
            const { stroke, fill } = PATH_COLORS[p];
            return [
              <Area
                key={`${p}_hi80`}
                type="monotone"
                dataKey={`${p}_hi80`}
                fill={fill}
                stroke="none"
                legendType="none"
                name=""
              />,
              <Area
                key={`${p}_lo80`}
                type="monotone"
                dataKey={`${p}_lo80`}
                fill="#ffffff"
                stroke="none"
                legendType="none"
                name=""
              />,
              <Line
                key={`${p}_value`}
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
