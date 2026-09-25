import { useState, useMemo, useEffect } from 'react';
import { useDashboardData } from './hooks/useDashboardData';
import type { LayerType, RegionGroup } from './types';
import type { DashboardData } from './types';
import { loadInfraLayer } from './utils/capacity';
import type { InfraLayer } from './types';
import SummaryBar from './components/SummaryBar';
import RomaniaMap from './components/RomaniaMap';
import RegionPanel from './components/RegionPanel';
import PolicyLab from './components/PolicyLab';

function deriveRegionGroups(data: DashboardData): Map<string, RegionGroup> {
  const treatedCodes = new Set(data.regions.map((r) => r.nuts3_code));
  const byNuts2 = new Map<string, RegionGroup>();

  for (const s of data.suitability) {
    if (!byNuts2.has(s.nuts2_code)) {
      byNuts2.set(s.nuts2_code, { nuts2Code: s.nuts2_code, hubNuts3: null, satellites: [] });
    }
    const g = byNuts2.get(s.nuts2_code)!;
    if (!treatedCodes.has(s.nuts3_code)) {
      g.hubNuts3 = s.nuts3_code;
    } else {
      g.satellites.push(s.nuts3_code);
    }
  }
  return byNuts2;
}

export default function App() {
  const { data, error } = useDashboardData();
  const [selectedNuts3, setSelectedNuts3] = useState<string | null>(null);
  const [activeLayer, setActiveLayer] = useState<LayerType>('reform_cost');
  const [hoveredNuts3, setHoveredNuts3] = useState<string | null>(null);
  const [infraLayer, setInfraLayer] = useState<InfraLayer | null>(null);

  const regionGroups = useMemo(
    () => (data ? deriveRegionGroups(data) : new Map<string, RegionGroup>()),
    [data],
  );

  useEffect(() => {
    loadInfraLayer()
      .then(setInfraLayer)
      .catch((e) => console.warn('infra_layer.json not available:', e));
  }, []);

  if (error) {
    return (
      <div className="flex items-center justify-center h-full text-red-600">
        Failed to load dashboard data: {error}
      </div>
    );
  }

  if (!data) {
    return (
      <div className="flex items-center justify-center h-full text-gray-500">
        Loading data…
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="flex items-center px-4 h-11 bg-gray-900 text-white shrink-0">
        <span className="font-bold text-sm">🏛 RO Administrative Reform</span>
        <span className="mx-3 text-gray-600">|</span>
        <span className="text-gray-400 text-xs">Policy Intelligence Dashboard</span>
        <span className="ml-auto text-gray-500 text-xs">
          {data.summary.n_demoted} demoted counties · Reform year {data.summary.reform_year}
        </span>
      </div>

      {/* KPI + layer switcher */}
      <SummaryBar summary={data.summary} activeLayer={activeLayer} onLayerChange={setActiveLayer} />

      {/* Map + sidebar */}
      <div className="flex flex-1 min-h-0">
        <div className="flex-1 min-w-0">
          <RomaniaMap
            data={data}
            activeLayer={activeLayer}
            selectedNuts3={selectedNuts3}
            onCountyClick={setSelectedNuts3}
            hoveredNuts3={hoveredNuts3}
            onCountyHover={setHoveredNuts3}
            regionGroups={regionGroups}
            infraLayer={infraLayer}
          />
        </div>
        <div className="w-[360px] shrink-0 border-l border-gray-200 overflow-y-auto">
          {activeLayer === 'policy_lab' ? (
            <PolicyLab nuts3Code={selectedNuts3} data={data} regionGroups={regionGroups} infraLayer={infraLayer} />
          ) : (
            <RegionPanel
              nuts3Code={selectedNuts3}
              data={data}
              activeLayer={activeLayer}
              regionGroups={regionGroups}
              onCountyHover={setHoveredNuts3}
            />
          )}
        </div>
      </div>
    </div>
  );
}
