import type { ElasticityProvenance } from '../types';

interface Props {
  provenance?: ElasticityProvenance;
  glossText: string;
}

export default function MetricTooltip({ provenance, glossText }: Props) {
  if (!provenance) return null;
  return (
    <span className="relative group inline-block align-middle ml-0.5 cursor-help select-none">
      <span className="text-violet-400 text-[10px]">ⓘ</span>
      <div className="absolute bottom-full left-1/2 -translate-x-1/2 mb-1 hidden group-hover:block z-50
                      w-64 bg-white border border-gray-200 rounded shadow-lg p-2 text-xs text-gray-700 space-y-1
                      pointer-events-none">
        <p className="font-semibold text-gray-900 leading-snug">{glossText}</p>
        <p><span className="text-gray-400">Method:</span> {provenance.method}</p>
        {provenance.n_obs != null && (
          <p><span className="text-gray-400">N:</span> {provenance.n_obs.toLocaleString()} obs</p>
        )}
        {provenance.boot_ci_90 && (
          <p>
            <span className="text-gray-400">90% CI:</span>{' '}
            [{provenance.boot_ci_90[0].toFixed(3)}, {provenance.boot_ci_90[1].toFixed(3)}]
          </p>
        )}
        {provenance.half_life_years != null && (
          <p>
            <span className="text-gray-400">Half-life:</span>{' '}
            {provenance.half_life_years.toFixed(1)} yrs
          </p>
        )}
        {provenance.citation && (
          <p className="text-gray-400 text-[10px] leading-snug">{provenance.citation}</p>
        )}
      </div>
    </span>
  );
}
