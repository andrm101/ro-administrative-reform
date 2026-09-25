import {
  RadarChart, PolarGrid, PolarAngleAxis, Radar, ResponsiveContainer,
} from 'recharts';
import type { CountyCapacity, InfraLayer, PillarKey } from '../types';
import { peerCounties } from '../utils/capacity';

interface Props {
  county: CountyCapacity;
  countyCode: string;
  layer: InfraLayer;
}

const PILLAR_LABELS: Record<PillarKey, string> = {
  transport: 'Transport',
  education: 'Education',
  health: 'Health',
  economic: 'Economic',
};

const CONFIDENCE_STYLE: Record<string, string> = {
  high: 'text-green-600',
  medium: 'text-amber-600',
  low: 'text-red-500',
};

export default function CapacityCard({ county, countyCode, layer }: Props) {
  const peers = peerCounties(countyCode, layer);

  const radarData = (Object.keys(PILLAR_LABELS) as PillarKey[]).map((p) => ({
    pillar: PILLAR_LABELS[p],
    score: county.pillars[p].score,
    fullMark: 100,
  }));

  const [rankMin, rankMax] = county.rank_interval;
  const hasRankInterval = rankMin !== 0 || rankMax !== 0;

  return (
    <div className="px-3 py-2 border-t border-gray-100 text-xs space-y-2">
      {/* Header */}
      <div className="flex items-center justify-between">
        <span className="font-medium text-gray-700">Infrastructure capacity</span>
        <span className="text-gray-400 text-[10px]">
          {county.national_percentile}th pct nationally
          {hasRankInterval && ` · rank ${rankMin}–${rankMax}`}
        </span>
      </div>

      {/* Composite score */}
      <div className="flex items-center gap-2">
        <div className="text-2xl font-bold text-violet-700 tabular-nums">
          {county.capacity_index.toFixed(0)}
        </div>
        <div className="text-[10px] text-gray-500 leading-tight">
          <div>/ 100 composite</div>
          <div className="text-gray-400">
            arithmetic: {county.capacity_index_arithmetic.toFixed(0)}
            <span className="ml-1 text-gray-300">(gap = imbalance proxy)</span>
          </div>
        </div>
      </div>

      {/* Radar chart */}
      <ResponsiveContainer width="100%" height={130}>
        <RadarChart data={radarData} margin={{ top: 4, right: 16, bottom: 4, left: 16 }}>
          <PolarGrid stroke="#e5e7eb" />
          <PolarAngleAxis dataKey="pillar" tick={{ fontSize: 9, fill: '#6b7280' }} />
          <Radar
            name={county.name}
            dataKey="score"
            stroke="#7c3aed"
            fill="#7c3aed"
            fillOpacity={0.25}
            dot={{ r: 2, fill: '#7c3aed' }}
          />
        </RadarChart>
      </ResponsiveContainer>

      {/* Pillar breakdown */}
      <div className="grid grid-cols-2 gap-1">
        {(Object.keys(PILLAR_LABELS) as PillarKey[]).map((p) => {
          const ps = county.pillars[p];
          return (
            <div key={p} className="bg-gray-50 rounded px-1.5 py-1">
              <div className="text-gray-400 text-[9px] uppercase tracking-wide">{PILLAR_LABELS[p]}</div>
              <div className="font-medium text-gray-800">{ps.score.toFixed(0)}</div>
              <div className={`text-[9px] ${CONFIDENCE_STYLE[ps.confidence]}`}>
                {ps.confidence} · {ps.features} POIs
              </div>
            </div>
          );
        })}
      </div>

      {/* Peer comparison */}
      {peers.length > 0 && (
        <div>
          <div className="text-[9px] text-gray-400 uppercase tracking-wide mb-1">
            Similar-profile counties
          </div>
          <div className="space-y-0.5">
            {peers.map((peer, idx) => (
              <div key={idx} className="flex items-center justify-between bg-blue-50 rounded px-1.5 py-0.5">
                <span className="text-gray-700">{peer.name}</span>
                <span className="text-gray-500 tabular-nums">{peer.capacity_index.toFixed(0)}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      <p className="text-[9px] text-gray-400 leading-snug">
        Geometric-mean composite (partially non-compensatory). Rank interval across{' '}
        {layer._meta.ensemble_variants || 0} methodological variants.
        Cronbach &#945; = {layer._meta.cronbach_alpha.toFixed(2)}.
      </p>
    </div>
  );
}
