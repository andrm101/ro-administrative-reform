# OSM Infrastructure Extracts — Romania

Source: OpenStreetMap contributors, ODbL licence (https://www.openstreetmap.org/copyright)
Extraction tool: Overpass API (https://overpass-api.de)
Download date: 2026-06-06
Projection: WGS84 (EPSG:4326)
Coverage: Romania (bounding box or administrative boundary)

## NUTS3 county boundaries
File: nuts3_romania_bounds.geojson
Source: Eurostat GISCO — NUTS 2021, 1:20M scale
URL: https://gisco-services.ec.europa.eu/distribution/v2/nuts/geojson/NUTS_RG_20M_2021_4326_LEVL_3.geojson
Filter: CNTR_CODE == 'RO'

## transport.geojson — motorways, trunk roads, rail stations, airports
Overpass QL:
  [out:json][timeout:120];
  area["ISO3166-1"="RO"]->.ro;
  (
    way["highway"~"^(motorway|trunk|primary)$"](area.ro);
    node["railway"~"^(station|halt)$"](area.ro);
    node["aeroway"="aerodrome"](area.ro);
  );
  out center;

## education.geojson — universities, colleges, research institutes
Overpass QL:
  [out:json][timeout:60];
  area["ISO3166-1"="RO"]->.ro;
  (
    node["amenity"~"^(university|college)$"](area.ro);
    way["amenity"~"^(university|college)$"](area.ro);
    node["office"="research"](area.ro);
  );
  out center;

## health.geojson — hospitals and clinics
Overpass QL:
  [out:json][timeout:60];
  area["ISO3166-1"="RO"]->.ro;
  (
    node["amenity"~"^(hospital|clinic)$"](area.ro);
    way["amenity"~"^(hospital|clinic)$"](area.ro);
  );
  out center tags;

## economic_zones.geojson — industrial zones, SEZs
Overpass QL:
  [out:json][timeout:60];
  area["ISO3166-1"="RO"]->.ro;
  (
    way["landuse"="industrial"](area.ro);
    way["industrial"](area.ro);
  );
  out center;

## Variable definitions
- transport: count of motorway/trunk/primary road ways (proxy for road network density),
  rail stations, airports within county
- education: count of university/college amenities and research offices within county
- health: count of hospital/clinic amenities within county; beds=* tag captured where present
- economic: count of industrial landuse polygons (centroids used for spatial join)
