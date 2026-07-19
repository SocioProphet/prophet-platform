// The data catalog — every source the cockpit reads, registered in one place with
// its live-adapter status. The #1 credibility gap is "fixtures vs. live feeds";
// this registry is the seam: each source declares the real upstream it stands in
// for, the surfaces it feeds, and whether the live adapter is wired yet.
export type AdapterStatus = 'live' | 'fixture' | 'planned';
export type SourceDomain = 'Civic' | 'Markets' | 'Real Estate' | 'Legal' | 'News' | 'Geospatial' | 'Graph' | 'Supply' | 'Economy' | 'Weather' | 'Identity';

export interface DataSource {
  id: string;
  name: string;
  domain: SourceDomain;
  upstream: string;        // the real-world feed this represents
  status: AdapterStatus;
  feeds: string[];         // surfaces / layers it powers
  cadence: string;         // refresh cadence
  license: string;
}

export const DATA_SOURCES: DataSource[] = [
  // Civic (map layers)
  { id: 'acs', name: 'Census ACS', domain: 'Civic', upstream: 'US Census American Community Survey', status: 'fixture', feeds: ['Map · People', 'Map · Economic', 'Map · Housing'], cadence: 'annual', license: 'public domain' },
  { id: 'cdc-places', name: 'CDC PLACES', domain: 'Civic', upstream: 'CDC PLACES health measures', status: 'fixture', feeds: ['Map · Health'], cadence: 'annual', license: 'public domain' },
  { id: 'doj-ucr', name: 'DOJ / FBI UCR', domain: 'Civic', upstream: 'FBI Uniform Crime Reporting', status: 'fixture', feeds: ['Map · Public Safety'], cadence: 'annual', license: 'public domain' },
  { id: 'nces', name: 'NCES / DOE', domain: 'Civic', upstream: 'Dept. of Education NCES', status: 'fixture', feeds: ['Map · Education'], cadence: 'annual', license: 'public domain' },
  { id: 'mobility', name: 'Mobility panel', domain: 'Civic', upstream: 'Placer / SafeGraph-class mobility', status: 'planned', feeds: ['Map · Foot Traffic', 'Site selection'], cadence: 'daily', license: 'commercial' },
  { id: 'epa-aqi', name: 'EPA AirNow', domain: 'Civic', upstream: 'EPA AirNow AQI', status: 'fixture', feeds: ['Map · Environment'], cadence: 'hourly', license: 'public domain' },
  { id: 'gtfs', name: 'Transit GTFS', domain: 'Civic', upstream: 'Agency GTFS feeds', status: 'planned', feeds: ['Map · Mobility'], cadence: 'live', license: 'open' },
  { id: 'civic-cal', name: 'Civic calendar', domain: 'Civic', upstream: 'Permits / civic event calendars', status: 'fixture', feeds: ['Map · Community events'], cadence: 'daily', license: 'open' },
  // Real estate
  { id: 'mls', name: 'MLS / property', domain: 'Real Estate', upstream: 'MLS + CoStar-class property data', status: 'planned', feeds: ['Map · Real Estate', 'Site selection'], cadence: 'daily', license: 'commercial' },
  // Markets / economy
  { id: 'markets', name: 'Market data', domain: 'Markets', upstream: 'Exchange / Bloomberg-class feed', status: 'fixture', feeds: ['Market Monitor', 'Portfolio', 'Algo'], cadence: 'realtime', license: 'commercial' },
  { id: 'fred', name: 'FRED / BLS', domain: 'Economy', upstream: 'St. Louis Fed FRED + BLS', status: 'fixture', feeds: ['Economy', 'Value Drivers'], cadence: 'monthly', license: 'public domain' },
  // Legal
  { id: 'fedreg', name: 'Federal Register', domain: 'Legal', upstream: 'federalregister.gov + Cornell LII', status: 'fixture', feeds: ['Law & Regulation'], cadence: 'daily', license: 'public domain' },
  { id: 'courts', name: 'Court dockets', domain: 'Legal', upstream: 'PACER / court docket feeds', status: 'planned', feeds: ['Law · Case law'], cadence: 'daily', license: 'mixed' },
  // News / social
  { id: 'rss', name: 'RSS / Atom', domain: 'News', upstream: 'Publisher RSS/Atom/JSON Feed', status: 'fixture', feeds: ['News'], cadence: 'live', license: 'open' },
  { id: 'bsky', name: 'Bluesky (ATProto)', domain: 'News', upstream: 'Bluesky AppView / PDS firehose', status: 'planned', feeds: ['News · Social'], cadence: 'live', license: 'open' },
  // Geospatial + graph
  { id: 'osm', name: 'OpenStreetMap', domain: 'Geospatial', upstream: 'OSM tiles + Overpass', status: 'live', feeds: ['Map basemap'], cadence: 'live', license: 'ODbL' },
  { id: 'gaia', name: 'GAIA world model', domain: 'Geospatial', upstream: 'GAIA OSM ingest / tile catalog', status: 'fixture', feeds: ['Map · GAIA layers'], cadence: 'batch', license: 'ODbL' },
  { id: 'hellgraph', name: 'HellGraph', domain: 'Graph', upstream: 'Sovereign federated hypergraph (Hypercore/Autobase)', status: 'live', feeds: ['Graph dock', 'PersonGraph', 'KnowledgeGraph'], cadence: 'live', license: 'sovereign' },
  // Supply / weather / identity
  { id: 'logistics', name: 'Logistics telemetry', domain: 'Supply', upstream: 'project44 / FourKites-class', status: 'planned', feeds: ['Supply Chain', 'Digital Twin'], cadence: 'live', license: 'commercial' },
  { id: 'nws', name: 'NWS / NOAA', domain: 'Weather', upstream: 'National Weather Service', status: 'fixture', feeds: ['Weather', 'Land & Resources'], cadence: 'hourly', license: 'public domain' },
  { id: 'holographme', name: 'HolographMe', domain: 'Identity', upstream: 'HolographMe reputation lattice', status: 'planned', feeds: ['People', 'News', 'Marketplace'], cadence: 'live', license: 'sovereign' },
];

export const sourcesByStatus = (s: AdapterStatus) => DATA_SOURCES.filter((d) => d.status === s);
