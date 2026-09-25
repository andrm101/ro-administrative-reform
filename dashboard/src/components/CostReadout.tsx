import type { ScenarioResult } from '../types';
import {
  formatEur, lnDeltaToPct,
  costPerCapita, costPctGva, costPerPpUplift,
} from '../utils/format';

interface Props {
  result: ScenarioResult;
  totalPop: number;
  totalGva: number;
}

export default function CostReadout({ result, totalPop, totalGva }: Props) {
  const lastPt = result.regionTotal.at(-1);
  const upliftPct = lastPt ? lnDeltaToPct(lastPt.scenario - lastPt.baseline) : 0;
  const perPp = costPerPpUplift(result.cost2040, upliftPct);

  const rows: { label: string; value: string }[] = [
    { label: 'NPV total', value: formatEur(result.cost2040) },
    { label: '€ / capita', value: formatEur(costPerCapita(result.cost2040, totalPop)) },
    {
      label: '% of regional GVA',
      value: `${costPctGva(result.cost2040, totalGva).toFixed(2)}%`,
    },
    {
      label: '€ / p.p. uplift',
      value: perPp !== null ? formatEur(perPp) : '—',
    },
  ];

  return (
    <div className="grid grid-cols-2 gap-1.5 p-3 text-xs">
      {rows.map(({ label, value }) => (
        <div key={label} className="bg-violet-50 rounded p-2">
          <div className="text-violet-500 text-[10px] leading-tight">{label}</div>
          <div className="font-bold text-violet-900 text-sm mt-0.5 tabular-nums">{value}</div>
        </div>
      ))}
    </div>
  );
}
