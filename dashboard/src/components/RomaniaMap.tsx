import { useEffect, useRef, useState, useCallback } from 'react';
import { MapContainer, GeoJSON, TileLayer, CircleMarker, Tooltip as LTooltip, useMapEvents } from 'react-leaflet';
import type { GeoJSON as LeafletGeoJSON, Layer } from 'leaflet';
import type { GeoJsonObject, Feature, Geometry, FeatureCollection } from 'geojson';
import type { DashboardData, LayerType, RegionGroup, PillarKey, InfraLayer } from '../types';
import { reformCostColor, suitabilityColor, roiColor, maxSuitability } from '../utils/color';
import InfraLayerPanel, { type BasemapType } from './InfraLayerPanel';
import { exportCapacityCsv } from '../utils/capacity';

const GISCO_URL =
  'https://gisco-services.ec.europa.eu/distribution/v2/nuts/geojson/NUTS_RG_20M_2021_4326_LEVL_3.geojson';

const BASEMAP_URLS: Record<BasemapType, string> = {
  positron: 'https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png',
  satellite: 'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
};

const PILLAR_COLORS: Record<PillarKey, string> = {
  transport: '#3b82f6',
  education: '#8b5cf6',
  health:    '#10b981',
  economic:  '#f59e0b',
};

interface Props {
  data: DashboardData;
  activeLayer: LayerType;
  selectedNuts3: string | null;
  onCountyClick: (nuts3: string) => void;
  hoveredNuts3: string | null;
  onCountyHover: (nuts3: string | null) => void;
  regionGroups: Map<string, RegionGroup>;
  infraLayer: InfraLayer | null;
}

interface NutsFeature extends Feature<Geometry> {
  properties: { NUTS_ID: string; CNTR_CODE: string; NAME_LATN: string };
}

interface PointFeature extends Feature {
  geometry: { type: 'Point'; coordinates: [number, number] };
  properties: Record<string, string>;
}

function ZoomWatcher({ onZoom }: { onZoom: (z: number) => void }) {
  useMapEvents({ zoom: (e) => onZoom(e.target.getZoom()) });
  return null;
}

export default function RomaniaMap({
  data, activeLayer, selectedNuts3, onCountyClick,
  hoveredNuts3, onCountyHover, infraLayer,
}: Props) {
  const [geoJson, setGeoJson] = useState<GeoJsonObject | null>(null);
  const [geoError, setGeoError] = useState(false);
  const [basemap, setBasemap] = useState<BasemapType>('positron');
  const [activePillars, setActivePillars] = useState<Set<PillarKey>>(new Set());
  const [poisByPillar, setPoisByPillar] = useState<Partial<Record<PillarKey, FeatureCollection>>>({});
  const [zoomLevel, setZoomLevel] = useState(6);
  const geoJsonRef = useRef<LeafletGeoJSON | null>(null);

  const showMarkers = zoomLevel >= 7;

  const maxAbsAtt = Math.max(...data.regions.map((r) => Math.abs(r.att_avg_pre ?? 0)), 0.001);
  const maxUplift = Math.max(...data.regions.map((r) => r.innovation_uplift_pct_2040 ?? 0), 0.001);

  useEffect(() => {
    fetch(GISCO_URL)
      .then((r) => r.json())
      .then((full: { features: NutsFeature[] }) => {
        const ro: GeoJsonObject = {
          type: 'FeatureCollection',
          // @ts-expect-error — valid GeoJSON but GeoJsonObject type doesn't expose features
          features: full.features.filter((f) => f.properties.CNTR_CODE === 'RO'),
        };
        setGeoJson(ro);
      })
      .catch(() => setGeoError(true));
  }, []);

  const handleTogglePillar = useCallback((p: PillarKey) => {
    setActivePillars((prev) => {
      const next = new Set(prev);
      if (next.has(p)) {
        next.delete(p);
      } else {
        next.add(p);
        if (!poisByPillar[p]) {
          fetch(`./data/osm/${p}.geojson`)
            .then((r) => r.json())
            .then((fc: FeatureCollection) =>
              setPoisByPillar((prev2) => ({ ...prev2, [p]: fc }))
            )
            .catch(() => console.warn(`POI load failed for: ${p}`));
        }
      }
      return next;
    });
  }, [poisByPillar]);

  const handleExportCsv = useCallback(() => {
    if (!infraLayer) return;
    const csv = exportCapacityCsv(infraLayer);
    const blob = new Blob([csv], { type: 'text/csv' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'ro_infrastructure_capacity.csv';
    a.click();
    URL.revokeObjectURL(url);
  }, [infraLayer]);

  function getStyle(feature: Feature | undefined) {
    if (!feature) return {};
    const nuts3 = (feature as NutsFeature).properties.NUTS_ID;
    const isSelected = nuts3 === selectedNuts3;
    const isDivergent = infraLayer?.counties[nuts3]?.divergence != null;

    if (activeLayer === 'region') {
      const selectedNuts2 = selectedNuts3
        ? (data.suitabilityByCode[selectedNuts3]?.nuts2_code ?? null)
        : null;
      const featureNuts2 = nuts3.slice(0, 4);
      const isSelectedRegion = featureNuts2 === selectedNuts2;
      const isHovered = nuts3 === hoveredNuts3;
      return {
        fillColor: isSelectedRegion ? '#7c3aed' : '#d1d5db',
        fillOpacity: isHovered ? 0.85 : isSelectedRegion ? 0.55 : 0.25,
        color: isSelectedRegion ? '#5b21b6' : '#9ca3af',
        weight: isHovered ? 3 : isSelectedRegion ? 2 : 0.5,
      };
    }

    let fillColor = '#e5e7eb';
    if (activeLayer === 'reform_cost') {
      fillColor = reformCostColor(data.regionsByCode[nuts3]?.att_avg_pre ?? null, maxAbsAtt);
    } else if (activeLayer === 'suitability') {
      const s = data.suitabilityByCode[nuts3];
      fillColor = s ? suitabilityColor(maxSuitability(s)) : '#e5e7eb';
    } else {
      fillColor = roiColor(data.regionsByCode[nuts3]?.innovation_uplift_pct_2040 ?? null, maxUplift);
    }

    return {
      fillColor,
      fillOpacity: isSelected ? 0.9 : 0.7,
      color: isDivergent ? '#f59e0b' : (isSelected ? '#1d4ed8' : '#ffffff'),
      weight: isDivergent ? 2.5 : (isSelected ? 2.5 : 0.8),
      dashArray: isDivergent && !isSelected ? '4 2' : undefined,
    };
  }

  function onEachFeature(feature: Feature, layer: Layer) {
    const nuts3 = (feature as NutsFeature).properties.NUTS_ID;
    const name = (feature as NutsFeature).properties.NAME_LATN;
    layer.bindTooltip(name, { sticky: true, className: 'text-xs' });
    layer.on('click', () => onCountyClick(nuts3));
    layer.on('mouseover', () => onCountyHover(nuts3));
    layer.on('mouseout', () => onCountyHover(null));
  }

  if (geoError) {
    return (
      <div className="h-full flex flex-col items-center justify-center gap-2 bg-blue-50">
        <span className="text-red-500 text-sm">Map unavailable (CDN unreachable)</span>
        <div className="grid grid-cols-4 gap-1 max-w-md">
          {data.regions.map((r) => (
            <button
              key={r.nuts3_code}
              onClick={() => onCountyClick(r.nuts3_code)}
              className={`text-xs p-1 rounded border ${
                r.nuts3_code === selectedNuts3
                  ? 'bg-blue-600 text-white border-blue-600'
                  : 'bg-white border-gray-300 hover:bg-gray-50'
              }`}
            >
              {r.county_seat}
            </button>
          ))}
        </div>
      </div>
    );
  }

  if (!geoJson) {
    return (
      <div className="h-full flex items-center justify-center bg-blue-50 text-blue-400 text-sm">
        Loading map&hellip;
      </div>
    );
  }

  return (
    <div className="relative h-full w-full">
      <MapContainer center={[45.9, 24.9]} zoom={6} zoomControl={false} style={{ height: '100%', width: '100%' }}>
        <TileLayer
          url={BASEMAP_URLS[basemap]}
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/">CARTO</a>'
          subdomains={basemap === 'positron' ? 'abcd' : undefined}
        />
        <ZoomWatcher onZoom={setZoomLevel} />
        <GeoJSON
          key={`${activeLayer}-${selectedNuts3}-${hoveredNuts3}`}
          ref={geoJsonRef}
          data={geoJson}
          style={getStyle}
          onEachFeature={onEachFeature}
        />
        {showMarkers &&
          (Object.keys(PILLAR_COLORS) as PillarKey[])
            .filter((p) => activePillars.has(p) && poisByPillar[p])
            .flatMap((p) =>
              (poisByPillar[p]!.features as PointFeature[])
                .filter((f) => f.geometry?.type === 'Point')
                .map((f, i) => {
                  const [lng, lat] = f.geometry.coordinates;
                  const name = f.properties?.name ?? '';
                  return (
                    <CircleMarker
                      key={`${p}-${i}`}
                      center={[lat, lng]}
                      radius={4}
                      pathOptions={{ color: PILLAR_COLORS[p], fillColor: PILLAR_COLORS[p], fillOpacity: 0.7, weight: 1 }}
                    >
                      {name && <LTooltip>{name}</LTooltip>}
                    </CircleMarker>
                  );
                })
            )}
      </MapContainer>

      <InfraLayerPanel
        activePillars={activePillars}
        onTogglePillar={handleTogglePillar}
        basemap={basemap}
        onBasemapChange={setBasemap}
        onExportCsv={handleExportCsv}
      />
    </div>
  );
}
