import type { ScenarioResult } from '../types';

interface Props {
  result: ScenarioResult;
  regimePValue?: number;
}

const COPY: Record<ScenarioResult['regime'], { label: string; description: string; cls: string }> = {
  convergence: {
    label: 'CONVERGENCE',
    description: 'redistribution raises total regional output',
    cls: 'bg-emerald-50 text-emerald-800 border-emerald-200',
  },
  agglomeration: {
    label: 'AGGLOMERATION',
    description: 'redistribution reduces total regional output',
    cls: 'bg-rose-50 text-rose-800 border-rose-200',
  },
  neutral: {
    label: 'NEUTRAL',
    description: 'redistribution is output-neutral for this region',
    cls: 'bg-gray-50 text-gray-700 border-gray-200',
  },
};

export default function RegimeBadge({ result, regimePValue }: Props) {
  const c = COPY[result.regime];
  return (
    <div className={`text-xs rounded border px-2 py-1.5 ${c.cls}`}>
      <span className="font-semibold">{c.label}</span>
      {regimePValue !== undefined ? (
        <span className="ml-1"> · p={regimePValue.toFixed(2)}</span>
      ) : (
        <span className="ml-1 opacity-60">(margin {result.regimeMargin.toFixed(3)})</span>
      )}
      <span className="ml-1">— {c.description}</span>
    </div>
  );
}
