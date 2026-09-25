import { useState } from 'react';
import type { LeverVector } from '../types';
import { LEVER_BOUNDS, DEFAULT_LEVERS } from '../types';

interface LeverMeta { key: keyof LeverVector; label: string; unit: string; group: string; step: number; }

// Each lever carries its own slider step sized to its bound (LEVER_BOUNDS); a single
// heuristic over-stepped narrow-range levers (e.g. skills [0,5] snapping to endpoints).
const LEVERS: LeverMeta[] = [
  { key: 'rho',    label: 'Redistribution share',    unit: '',          group: 'Fiscal',       step: 0.05 },
  { key: 'kappa',  label: 'Cohesion injection',       unit: '€/cap/yr',  group: 'Fiscal',       step: 10 },
  { key: 'gov',    label: 'Gov-efficiency gain',       unit: '',          group: 'Productivity', step: 0.05 },
  { key: 'iota',   label: 'MegaCampus intensity',      unit: '×',         group: 'Productivity', step: 0.05 },
  { key: 'skills', label: 'Skills investment',         unit: '% GVA',     group: 'Productivity', step: 0.1 },
  { key: 'conn',   label: 'Connectivity',              unit: '',          group: 'Productivity', step: 0.05 },
  { key: 'mu',     label: 'Migration-retention',       unit: '€/cap/yr',  group: 'Demography',   step: 10 },
  { key: 'family', label: 'Family transfer',           unit: '€/cap/yr',  group: 'Demography',   step: 10 },
  { key: 'offset', label: 'Reform-transition offset',  unit: '',          group: 'Mitigation',   step: 0.05 },
];

const PRESETS: Record<string, Partial<LeverVector>> = {
  'Status quo': {},
  'Pure agglomeration': { iota: 1.5, gov: 0.6 },
  'Aggressive convergence': { rho: 0.5, mu: 200, conn: 0.8, skills: 3 },
  'EU cohesion-funded': { kappa: 250, conn: 0.6, skills: 2 },
};

const GROUPS = [...new Set(LEVERS.map((l) => l.group))];

interface Props {
  levers: LeverVector;
  onChange: (next: LeverVector) => void;
  provisional: boolean;
}

export default function LeverPanel({ levers, onChange, provisional }: Props) {
  const [collapsed, setCollapsed] = useState<Set<string>>(() => new Set(GROUPS));

  function toggle(g: string) {
    setCollapsed((prev) => {
      const next = new Set(prev);
      if (next.has(g)) next.delete(g); else next.add(g);
      return next;
    });
  }

  function set(key: keyof LeverVector, value: number) {
    onChange({ ...levers, [key]: value });
  }

  return (
    <div className="p-3 space-y-2 text-xs border-t border-gray-100">
      {provisional && (
        <div className="bg-amber-50 text-amber-800 rounded px-2 py-1">
          ⚠ Provisional coefficients (literature priors) — empirical calibration pending.
        </div>
      )}

      <div className="flex flex-wrap gap-1">
        {Object.keys(PRESETS).map((name) => (
          <button
            key={name}
            onClick={() => onChange({ ...DEFAULT_LEVERS, ...PRESETS[name] })}
            className="px-2 py-0.5 rounded border border-violet-300 text-violet-700 hover:bg-violet-50 text-[11px]"
          >
            {name}
          </button>
        ))}
      </div>

      {GROUPS.map((g) => (
        <div key={g} className="rounded border border-gray-100">
          <button
            onClick={() => toggle(g)}
            className="w-full flex items-center justify-between px-2 py-1.5 text-left text-gray-700 font-medium hover:bg-gray-50"
          >
            <span>{g}</span>
            <span className="text-gray-400 text-[10px]">{collapsed.has(g) ? '▶' : '▼'}</span>
          </button>
          {!collapsed.has(g) && (
            <div className="px-2 pb-2 space-y-1">
              {LEVERS.filter((l) => l.group === g).map((l) => {
                const [lo, hi] = LEVER_BOUNDS[l.key];
                return (
                  <label key={l.key} className="flex items-center gap-2">
                    <span className="w-36 text-gray-600 text-[11px]">{l.label}</span>
                    <input
                      type="range" min={lo} max={hi} step={l.step} value={levers[l.key]}
                      onChange={(e) => set(l.key, Number(e.target.value))}
                      className="flex-1"
                    />
                    <span className="w-16 text-right tabular-nums text-[11px]">
                      {levers[l.key]}{l.unit}
                    </span>
                  </label>
                );
              })}
            </div>
          )}
        </div>
      ))}
    </div>
  );
}
