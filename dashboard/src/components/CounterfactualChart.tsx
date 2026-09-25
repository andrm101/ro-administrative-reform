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

  const chartData = series
    .filter((p) => p.year >= 2000)
    .map((p) => ({
      year: p.year,
      actual: p.actual,
      counterfactual: p.counterfactual,
    }));

  const allVals = chartData.flatMap((d) => [d.actual, d.counterfactual].filter((v): v is number => v != null));
  const yMin = allVals.length > 0 ? Math.min(...allVals) - 0.01 : 0;
  const yMax = allVals.length > 0 ? Math.max(...allVals) + 0.01 : 1;
  const lastYear = chartData[chartData.length - 1]?.year ?? 2024;

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
            formatter={(v) => (typeof v === 'number' ? v.toFixed(4) : String(v))}
            labelFormatter={(l) => `Year ${l}`}
            contentStyle={{ fontSize: 11 }}
          />
          <Legend iconSize={10} wrapperStyle={{ fontSize: 10 }} />
          <ReferenceLine
            x={2025}
            stroke="#d97706"
            strokeDasharray="4 3"
            label={{ value: '2025', fontSize: 9, fill: '#d97706' } as any}
          />
          <ReferenceArea
            x1={2025}
            x2={lastYear}
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
