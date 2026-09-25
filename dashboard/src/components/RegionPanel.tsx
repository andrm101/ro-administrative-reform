import { useState } from 'react';
import type { DashboardData, LayerType, RegionGroup } from '../types';
import CounterfactualChart from './CounterfactualChart';
import ForecastPanel from './ForecastPanel';
import MegaCampusBadge from './MegaCampusBadge';
import MethodsTab from './MethodsTab';
import RegionOverlayChart from './RegionOverlayChart';

interface Props {
  nuts3Code: string | null;
  data: DashboardData;
  activeLayer: LayerType;
  regionGroups: Map<string, RegionGroup>;
  onCountyHover: (nuts3: string | null) => void;
}

type Tab = 'counterfactual' | 'forecast' | 'megacampus' | 'methods';

const TABS: { id: Tab; label: string }[] = [
  { id: 'counterfactual', label: 'Counterfactual' },
  { id: 'forecast', label: 'Forecast' },
  { id: 'megacampus', label: 'MegaCampus' },
  { id: 'methods', label: 'Methods' },
];

export default function RegionPanel({ nuts3Code, data, activeLayer, regionGroups, onCountyHover }: Props) {
  const [activeTab, setActiveTab] = useState<Tab>('counterfactual');

  if (!nuts3Code) {
    return (
      <div className="flex flex-col items-center justify-center h-full text-gray-400 text-sm gap-2 p-6">
        <span className="text-2xl">🗺</span>
        <p>Click a county on the map to view its detail</p>
      </div>
    );
  }

  // Region layer: show NUTS2 consolidation overlay
  if (activeLayer === 'region') {
    const suit = data.suitabilityByCode[nuts3Code];
    const nuts2 = suit?.nuts2_code;
    const group = nuts2 ? regionGroups.get(nuts2) : undefined;
    if (!group) {
      return (
        <div className="p-4 text-gray-400 text-sm">
          No region data for {nuts3Code}
        </div>
      );
    }
    return <RegionOverlayChart group={group} data={data} onCountyHover={onCountyHover} />;
  }

  const region = data.regionsByCode[nuts3Code];
  const suit = data.suitabilityByCode[nuts3Code];
  const forecast = data.forecastsByCode[nuts3Code];

  if (!region) {
    return (
      <div className="p-4 text-gray-400 text-sm">
        No data for {nuts3Code}
      </div>
    );
  }

  const reformPct = region.reform_cost_pct != null
    ? `${region.reform_cost_pct > 0 ? '+' : ''}${region.reform_cost_pct.toFixed(1)}%`
    : '—';
  const vitality = region.vitality_index != null
    ? region.vitality_index.toFixed(2)
    : '—';
  const uplift = region.innovation_uplift_pct_2040 != null
    ? `+${region.innovation_uplift_pct_2040.toFixed(1)}%`
    : '—';

  return (
    <div className="flex flex-col h-full">
      {/* County header */}
      <div className="px-4 py-3 bg-gray-50 border-b border-gray-200 shrink-0">
        <div className="font-bold text-gray-900">{region.judet_name} — {region.county_seat}</div>
        <div className="text-gray-500 text-xs mt-0.5">
          NUTS3: {region.nuts3_code} · {region.nuts2_code}
        </div>
      </div>

      {/* KPI mini-cards */}
      <div className="grid grid-cols-3 gap-2 px-3 py-2 border-b border-gray-100 shrink-0">
        <div className="bg-red-50 rounded p-2 text-center">
          <div className="font-bold text-red-700 text-sm">{reformPct}</div>
          <div className="text-red-600 text-xs">Reform cost</div>
        </div>
        <div className="bg-green-50 rounded p-2 text-center">
          <div className="font-bold text-green-700 text-sm">{vitality}</div>
          <div className="text-green-600 text-xs">Vitality idx</div>
        </div>
        <div className="bg-blue-50 rounded p-2 text-center">
          <div className="font-bold text-blue-700 text-sm">{uplift}</div>
          <div className="text-blue-600 text-xs">Pop uplift 2040</div>
        </div>
      </div>

      {/* Tab bar */}
      <div className="flex border-b border-gray-200 shrink-0">
        {TABS.map(({ id, label }) => (
          <button
            key={id}
            onClick={() => setActiveTab(id)}
            className={`flex-1 py-2 text-xs font-medium transition-colors border-b-2 ${
              activeTab === id
                ? 'border-blue-500 text-blue-600'
                : 'border-transparent text-gray-500 hover:text-gray-700'
            }`}
          >
            {label}
          </button>
        ))}
      </div>

      {/* Tab content */}
      <div className="flex-1 overflow-y-auto p-3">
        {activeTab === 'counterfactual' && (
          <CounterfactualChart series={region.counterfactualSeries} />
        )}
        {activeTab === 'forecast' && forecast && (
          <ForecastPanel forecasts={forecast.forecasts} />
        )}
        {activeTab === 'forecast' && !forecast && (
          <div className="text-gray-400 text-sm">No forecast data for this county.</div>
        )}
        {activeTab === 'megacampus' && suit && (
          <MegaCampusBadge suitability={suit} />
        )}
        {activeTab === 'megacampus' && !suit && (
          <div className="text-gray-400 text-sm">No suitability data for this county.</div>
        )}
        {activeTab === 'methods' && (
          <MethodsTab sdid={data.sdid} lpIrfs={data.lpIrfs} eventstudy={data.eventstudy} />
        )}
      </div>
    </div>
  );
}
