import { useEffect, useState } from 'react';
import type {
  DashboardData, RegionData, ForecastCounty, SuitabilityData,
  LpIrf, SdidEstimate, EventStudyCoef, Summary, Elasticities, FiscalPrimitives, CountyPrimitive,
} from '../types';

const BASE = import.meta.env.BASE_URL;

async function fetchJson<T>(name: string): Promise<T> {
  const res = await fetch(`${BASE}data/${name}`);
  if (!res.ok) throw new Error(`Failed to fetch ${name}: ${res.status}`);
  return res.json() as Promise<T>;
}

export function useDashboardData(): { data: DashboardData | null; error: string | null } {
  const [data, setData] = useState<DashboardData | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([
      fetchJson<RegionData[]>('regions.json'),
      fetchJson<ForecastCounty[]>('forecasts.json'),
      fetchJson<SuitabilityData[]>('suitability.json'),
      fetchJson<LpIrf[]>('lp_irfs.json'),
      fetchJson<SdidEstimate[]>('sdid_estimates.json'),
      fetchJson<EventStudyCoef[]>('eventstudy.json'),
      fetchJson<Summary>('summary.json'),
      fetchJson<Elasticities>('elasticities.json'),
      fetchJson<FiscalPrimitives>('fiscal_primitives.json'),
    ])
      .then(([regions, forecasts, suitability, lpIrfs, sdid, eventstudy, summary, elasticities, fiscalPrimitives]) => {
        setData({
          regions,
          regionsByCode: Object.fromEntries(regions.map((r) => [r.nuts3_code, r])),
          forecasts,
          forecastsByCode: Object.fromEntries(forecasts.map((f) => [f.nuts3_code, f])),
          suitability,
          suitabilityByCode: Object.fromEntries(suitability.map((s) => [s.nuts3_code, s])),
          lpIrfs,
          sdid,
          eventstudy,
          summary,
          elasticities,
          primitivesByCode: Object.fromEntries(
            (fiscalPrimitives as FiscalPrimitives).counties.map((c: CountyPrimitive) => [c.nuts3_code, c]),
          ),
        });
      })
      .catch((e: unknown) => setError(e instanceof Error ? e.message : String(e)));
  }, []);

  return { data, error };
}
