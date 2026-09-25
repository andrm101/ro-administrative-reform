import type { DivergenceFlag } from '../types';

interface Props {
  flag: DivergenceFlag;
}

const TYPE_META: Record<string, { label: string; colorClass: string; emoji: string }> = {
  structural_bottleneck: {
    label: 'High capacity · below-trend growth',
    colorClass: 'border-amber-200 bg-amber-50',
    emoji: '⚠',
  },
  latent_fragility: {
    label: 'Low capacity · above-trend growth',
    colorClass: 'border-orange-200 bg-orange-50',
    emoji: '📉',
  },
};

export default function DivergenceAlert({ flag }: Props) {
  const meta = TYPE_META[flag.type] ?? TYPE_META['structural_bottleneck'];

  return (
    <div className={`mx-3 mb-2 rounded border text-xs p-2 space-y-1.5 ${meta.colorClass}`}>
      {/* Tier 1 — Observation */}
      <div className="font-medium text-gray-800">
        {meta.emoji} Structural signal: {meta.label}
      </div>

      {/* Data confidence off-ramp — shown BEFORE the hypothesis */}
      {flag.data_caveat && (
        <div className="text-[10px] text-red-600 bg-red-50 rounded px-1.5 py-1 border border-red-200">
          {'⚠'} Coverage caveat: {flag.data_caveat}
        </div>
      )}

      {/* Tier 2 — Statistical strength */}
      <div className="text-gray-600 text-[10px] space-x-2">
        <span>
          <span className="text-gray-400">Residual t: </span>
          <span className="font-mono">{flag.resid_t.toFixed(2)}</span>
        </span>
        <span>·</span>
        <span>
          <span className="text-gray-400">LISA: </span>
          <span className="font-mono">{flag.lisa_quadrant}</span>
          {flag.lisa_quadrant === 'HL' && ' (isolated high-capacity outlier)'}
          {flag.lisa_quadrant === 'LH' && ' (isolated low-capacity outlier)'}
        </span>
      </div>

      {/* Tier 3 — Hypothesis */}
      <div className="text-gray-500 text-[10px] leading-snug border-t border-gray-200 pt-1">
        <span className="font-medium text-gray-600">Hypothesis for investigation: </span>
        {flag.structural_hypothesis}
      </div>

      <p className="text-[9px] text-gray-400">
        n {'≈'} 42 counties {'—'} {'∼'}2 flags expected by chance. Investigate with administrative
        data before drawing policy conclusions.
      </p>
    </div>
  );
}
