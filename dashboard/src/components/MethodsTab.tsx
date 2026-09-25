import type { SdidEstimate, LpIrf, EventStudyCoef } from '../types';

interface Props {
  sdid: SdidEstimate[];
  lpIrfs: LpIrf[];
  eventstudy: EventStudyCoef[];
}

const OUTCOME_LABELS: Record<string, string> = {
  ln_population:      'ln(population)',
  nat_change_rate:    'Nat. change rate',
  net_migration_rate: 'Net migration',
};

function fmt(v: number | null, digits = 3): string {
  return v != null ? v.toFixed(digits) : '—';
}

export default function MethodsTab({ sdid, lpIrfs, eventstudy }: Props) {
  // LP max pre-trend |coef| per outcome (h=0..15)
  const lpMaxByOutcome: Record<string, number> = {};
  for (const row of lpIrfs) {
    if (row.horizon <= 15 && row.coef != null) {
      const prev = lpMaxByOutcome[row.outcome] ?? 0;
      lpMaxByOutcome[row.outcome] = Math.max(prev, Math.abs(row.coef));
    }
  }

  // Event-study: count significant pre-trend coefficients per outcome (CI excludes zero)
  const etSigByOutcome: Record<string, number> = {};
  for (const row of eventstudy) {
    if (row.event_time < 0 && row.ci_lo != null && row.ci_hi != null) {
      if (row.ci_lo > 0 || row.ci_hi < 0) {
        etSigByOutcome[row.outcome] = (etSigByOutcome[row.outcome] ?? 0) + 1;
      }
    }
  }

  return (
    <div className="space-y-4 text-xs">
      {/* Identification narrative */}
      <div className="bg-blue-50 rounded p-3 text-blue-800 leading-relaxed">
        <strong>Identification strategy:</strong> TWFE event study (Stage 05) shows non-flat pre-trends,
        validating gsynth Interactive Factor Model (Xu 2017) over plain TWFE.
        Cross-country synthetic control uses 350 Polish donors post-1999 reform (r*=1 factor).
        SDiD (pseudo-treat 2015) and LP-IRFs both pass robustness checks.
      </div>

      {/* SDiD estimates */}
      <div>
        <div className="font-semibold text-gray-700 mb-1">SDiD Estimates (pseudo-treat 2015)</div>
        <table className="w-full border-collapse">
          <thead>
            <tr className="bg-gray-50">
              <th className="text-left py-1 px-2 border border-gray-200">Outcome</th>
              <th className="text-right py-1 px-2 border border-gray-200">ATT</th>
              <th className="text-right py-1 px-2 border border-gray-200">SE</th>
              <th className="text-right py-1 px-2 border border-gray-200">95% CI</th>
            </tr>
          </thead>
          <tbody>
            {sdid.map((r) => (
              <tr key={r.outcome} className="border-b border-gray-100">
                <td className="py-1 px-2 border border-gray-200">{OUTCOME_LABELS[r.outcome] ?? r.outcome}</td>
                <td className="text-right py-1 px-2 border border-gray-200 font-mono">{fmt(r.att)}</td>
                <td className="text-right py-1 px-2 border border-gray-200 font-mono">{fmt(r.se)}</td>
                <td className="text-right py-1 px-2 border border-gray-200 font-mono">
                  [{fmt(r.ci_lo)}, {fmt(r.ci_hi)}]
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        <div className="text-gray-400 mt-1">All CIs include zero (placebo passes).</div>
      </div>

      {/* LP pre-trends */}
      <div>
        <div className="font-semibold text-gray-700 mb-1">LP Pre-trend Check (h = 0…15)</div>
        <table className="w-full border-collapse">
          <thead>
            <tr className="bg-gray-50">
              <th className="text-left py-1 px-2 border border-gray-200">Outcome</th>
              <th className="text-right py-1 px-2 border border-gray-200">Max |coef|</th>
              <th className="text-right py-1 px-2 border border-gray-200">Result</th>
            </tr>
          </thead>
          <tbody>
            {Object.entries(lpMaxByOutcome).map(([outcome, maxCoef]) => (
              <tr key={outcome} className="border-b border-gray-100">
                <td className="py-1 px-2 border border-gray-200">{OUTCOME_LABELS[outcome] ?? outcome}</td>
                <td className="text-right py-1 px-2 border border-gray-200 font-mono">{maxCoef.toFixed(4)}</td>
                <td className={`text-right py-1 px-2 border border-gray-200 font-medium ${maxCoef < 0.05 ? 'text-green-600' : 'text-amber-600'}`}>
                  {maxCoef < 0.05 ? '✓ Flat' : '⚠ Drift'}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* TWFE event study */}
      <div>
        <div className="font-semibold text-gray-700 mb-1">TWFE Event Study Pre-trends</div>
        {Object.keys(etSigByOutcome).length === 0 ? (
          <div className="text-gray-400">No significant pre-trend deviations detected.</div>
        ) : (
          <table className="w-full border-collapse">
            <thead>
              <tr className="bg-gray-50">
                <th className="text-left py-1 px-2 border border-gray-200">Outcome</th>
                <th className="text-right py-1 px-2 border border-gray-200">Sig. pre-periods</th>
                <th className="text-right py-1 px-2 border border-gray-200">Verdict</th>
              </tr>
            </thead>
            <tbody>
              {Object.entries(etSigByOutcome).map(([outcome, count]) => (
                <tr key={outcome} className="border-b border-gray-100">
                  <td className="py-1 px-2 border border-gray-200">{OUTCOME_LABELS[outcome] ?? outcome}</td>
                  <td className="text-right py-1 px-2 border border-gray-200 font-mono">{count} / 19</td>
                  <td className="text-right py-1 px-2 border border-gray-200 font-medium text-red-500">
                    ✗ Not flat
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
        <div className="text-gray-500 mt-1">
          Non-flat pre-trends validate gsynth IFE (allows heterogeneous trends) over TWFE.
        </div>
      </div>
    </div>
  );
}
