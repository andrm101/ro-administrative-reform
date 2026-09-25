import type { Summary, LayerType } from '../types';
import LayerSwitcher from './LayerSwitcher';

interface Props {
  summary: Summary;
  activeLayer: LayerType;
  onLayerChange: (layer: LayerType) => void;
}

function Chip({ label, value, color }: { label: string; value: string; color: string }) {
  return (
    <div className="flex items-center gap-2">
      <span className={`font-bold text-sm ${color}`}>{value}</span>
      <span className="text-gray-400 text-xs">{label}</span>
    </div>
  );
}

export default function SummaryBar({ summary, activeLayer, onLayerChange }: Props) {
  const attPct = summary.sdid_pop_loss_pct != null
    ? `${summary.sdid_pop_loss_pct > 0 ? '+' : ''}${summary.sdid_pop_loss_pct.toFixed(1)}%`
    : 'N/A';

  return (
    <div className="flex items-center gap-6 px-4 h-9 bg-gray-800 text-white shrink-0">
      <Chip label="demoted counties" value={String(summary.n_demoted)} color="text-red-400" />
      <Chip label="SDiD ATT pop" value={attPct} color="text-red-300" />
      <Chip label="Tier-1 counties" value={`${summary.n_tier1}/42`} color="text-green-400" />
      <Chip label="reform year" value={String(summary.reform_year)} color="text-yellow-400" />
      <div className="ml-auto flex items-center gap-2">
        <span className="text-gray-500 text-xs">Layer:</span>
        <LayerSwitcher activeLayer={activeLayer} onChange={onLayerChange} />
      </div>
    </div>
  );
}
