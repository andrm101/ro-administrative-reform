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
      <div className="flex text-xs text-gray-300 mt-1 pr-14 relative">
        <span>0</span>
        <span className="absolute" style={{ left: 'calc(32px + 70% * (100% - 32px - 48px) / 100% )' }}>0.70</span>
        <span className="ml-auto">1.0</span>
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
