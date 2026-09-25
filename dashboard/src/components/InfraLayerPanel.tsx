import { useState } from 'react';
import type { PillarKey } from '../types';

type BasemapType = 'positron' | 'satellite';

interface Props {
  activePillars: Set<PillarKey>;
  onTogglePillar: (p: PillarKey) => void;
  basemap: BasemapType;
  onBasemapChange: (b: BasemapType) => void;
  onExportCsv: () => void;
}

const PILLAR_LABELS: Record<PillarKey, string> = {
  transport: 'Transport',
  education: 'Education',
  health:    'Health',
  economic:  'Economic zones',
};

const PILLAR_COLORS: Record<PillarKey, string> = {
  transport: '#3b82f6',
  education: '#8b5cf6',
  health:    '#10b981',
  economic:  '#f59e0b',
};

export type { BasemapType };

export default function InfraLayerPanel({
  activePillars, onTogglePillar, basemap, onBasemapChange, onExportCsv,
}: Props) {
  const [open, setOpen] = useState(true);

  return (
    <div className="absolute top-2 right-2 z-[1000] bg-white rounded-lg shadow-md border border-gray-200 text-xs w-48">
      <button
        onClick={() => setOpen((o) => !o)}
        className="w-full flex items-center justify-between px-2.5 py-2 font-medium text-gray-700 hover:bg-gray-50 rounded-lg"
      >
        <span>Infrastructure</span>
        <span className="text-gray-400 text-[10px]">{open ? '▲' : '▼'}</span>
      </button>

      {open && (
        <div className="px-2.5 pb-2.5 border-t border-gray-100 space-y-1.5">
          <p className="text-[9px] text-gray-400 uppercase tracking-wide pt-1.5">Layers</p>
          {(Object.keys(PILLAR_LABELS) as PillarKey[]).map((p) => (
            <label key={p} className="flex items-center gap-2 cursor-pointer">
              <input
                type="checkbox"
                checked={activePillars.has(p)}
                onChange={() => onTogglePillar(p)}
                className="rounded"
                style={{ accentColor: PILLAR_COLORS[p] }}
              />
              <span className="text-gray-700">{PILLAR_LABELS[p]}</span>
            </label>
          ))}

          <p className="text-[9px] text-gray-400 uppercase tracking-wide pt-1">Basemap</p>
          {(['positron', 'satellite'] as BasemapType[]).map((b) => (
            <label key={b} className="flex items-center gap-2 cursor-pointer">
              <input
                type="radio"
                name="infra-basemap"
                checked={basemap === b}
                onChange={() => onBasemapChange(b)}
                className="accent-violet-600"
              />
              <span className="text-gray-700">
                {b === 'positron' ? 'Positron (default)' : 'Satellite'}
              </span>
            </label>
          ))}

          <button
            onClick={onExportCsv}
            className="mt-1.5 w-full text-center text-violet-600 hover:text-violet-800 text-[10px] py-0.5 border border-violet-200 rounded"
          >
            Export capacity CSV
          </button>
        </div>
      )}
    </div>
  );
}
