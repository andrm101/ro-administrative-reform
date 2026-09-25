import type { LayerType } from '../types';

interface Props {
  activeLayer: LayerType;
  onChange: (layer: LayerType) => void;
}

const LAYERS: { id: LayerType; label: string }[] = [
  { id: 'reform_cost', label: 'Reform cost' },
  { id: 'suitability', label: 'Suitability' },
  { id: 'roi', label: 'ROI' },
  { id: 'region', label: 'Region' },
  { id: 'policy_lab', label: 'Policy Lab' },
];

export default function LayerSwitcher({ activeLayer, onChange }: Props) {
  return (
    <div className="flex gap-1">
      {LAYERS.map(({ id, label }) => (
        <button
          key={id}
          onClick={() => onChange(id)}
          className={`px-3 py-1 text-xs rounded transition-colors ${
            activeLayer === id
              ? 'bg-blue-500 text-white'
              : 'bg-gray-600 text-gray-300 hover:bg-gray-500'
          }`}
        >
          {label}
        </button>
      ))}
    </div>
  );
}
