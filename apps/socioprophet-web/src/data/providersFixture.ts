// Provider directory for supply-chain ORCHESTRATION — materials, processing,
// warehousing, freight, customs, last-mile, and services. Each provider is a
// governed marketplace participant: capabilities, a location (on the map),
// capacity, lead time, unit cost, rating, and reputation. UI-only; a real provider
// registry + HolographMe reputation swap in behind the same shape.
export type Stage = 'source' | 'process' | 'warehouse' | 'freight' | 'customs' | 'lastmile' | 'service';

export interface Provider {
  id: string;
  name: string;
  stage: Stage;
  kind: string;
  capabilities: string[];
  geo: { lon: number; lat: number; place: string };
  capacityPct: number;   // available capacity
  leadDays: number;
  unitCost: number;      // $ per unit for this stage
  rating: number;        // 1..5
  reputation: 'verified' | 'unrated';
  provenanceHash: string;
}

export const STAGES: Array<{ id: Stage; label: string; verb: string }> = [
  { id: 'source', label: 'Source', verb: 'sources' },
  { id: 'process', label: 'Process', verb: 'processes' },
  { id: 'warehouse', label: 'Warehouse', verb: 'stores' },
  { id: 'freight', label: 'Freight', verb: 'ships' },
  { id: 'customs', label: 'Customs', verb: 'clears' },
  { id: 'lastmile', label: 'Last-mile', verb: 'delivers' },
];

export const PROVIDERS: Provider[] = [
  // Source
  { id: 'p-escondida', name: 'Escondida Mine', stage: 'source', kind: 'copper mine', capabilities: ['copper concentrate', 'bulk'], geo: { lon: -69.07, lat: -24.27, place: 'Antofagasta, CL' }, capacityPct: 72, leadDays: 14, unitCost: 820, rating: 4.5, reputation: 'verified', provenanceHash: 'sha256:esc…a1' },
  { id: 'p-foundry', name: 'Leading-Edge Foundry', stage: 'source', kind: 'semiconductor fab', capabilities: ['wafers', '5nm'], geo: { lon: 120.97, lat: 24.78, place: 'Hsinchu, TW' }, capacityPct: 41, leadDays: 60, unitCost: 4200, rating: 4.8, reputation: 'verified', provenanceHash: 'sha256:fab…b2' },
  { id: 'p-mill', name: 'Regional Metals Mill', stage: 'source', kind: 'recycled metals', capabilities: ['scrap copper', 'local'], geo: { lon: -74.10, lat: 40.72, place: 'Newark, NJ' }, capacityPct: 88, leadDays: 5, unitCost: 910, rating: 3.9, reputation: 'unrated', provenanceHash: 'sha256:mil…c3' },
  // Process
  { id: 'p-smelter', name: 'Chuquicamata Smelter', stage: 'process', kind: 'smelter', capabilities: ['refine', 'cathode'], geo: { lon: -68.90, lat: -22.32, place: 'Calama, CL' }, capacityPct: 63, leadDays: 10, unitCost: 340, rating: 4.3, reputation: 'verified', provenanceHash: 'sha256:smt…d4' },
  { id: 'p-assembly', name: 'Shenzhen Assembly', stage: 'process', kind: 'assembler', capabilities: ['SMT', 'test'], geo: { lon: 114.06, lat: 22.54, place: 'Shenzhen, CN' }, capacityPct: 55, leadDays: 18, unitCost: 260, rating: 4.1, reputation: 'verified', provenanceHash: 'sha256:asm…e5' },
  // Warehouse
  { id: 'p-newark-wh', name: 'Newark Bonded Warehouse', stage: 'warehouse', kind: 'bonded FTZ', capabilities: ['bonded', 'cold-chain'], geo: { lon: -74.17, lat: 40.69, place: 'Newark, NJ' }, capacityPct: 60, leadDays: 2, unitCost: 45, rating: 4.4, reputation: 'verified', provenanceHash: 'sha256:nwk…f6' },
  { id: 'p-bk-dc', name: 'Brooklyn Distribution Center', stage: 'warehouse', kind: 'urban DC', capabilities: ['cross-dock', 'urban'], geo: { lon: -73.98, lat: 40.68, place: 'Brooklyn, NY' }, capacityPct: 34, leadDays: 1, unitCost: 62, rating: 4.0, reputation: 'unrated', provenanceHash: 'sha256:bkd…07' },
  // Freight
  { id: 'p-ocean', name: 'Trans-Pacific Ocean Line', stage: 'freight', kind: 'ocean', capabilities: ['FCL', 'reefer'], geo: { lon: -118.26, lat: 33.74, place: 'via LA/LB' }, capacityPct: 48, leadDays: 22, unitCost: 180, rating: 3.8, reputation: 'verified', provenanceHash: 'sha256:ocn…18' },
  { id: 'p-air', name: 'AirCargo Express', stage: 'freight', kind: 'air', capabilities: ['expedited', 'AOG'], geo: { lon: -73.78, lat: 40.64, place: 'via JFK' }, capacityPct: 70, leadDays: 3, unitCost: 640, rating: 4.6, reputation: 'verified', provenanceHash: 'sha256:air…29' },
  { id: 'p-truck', name: 'Northeast Trucking', stage: 'freight', kind: 'trucking', capabilities: ['LTL', 'regional'], geo: { lon: -74.05, lat: 40.73, place: 'NJ/NY' }, capacityPct: 82, leadDays: 2, unitCost: 90, rating: 4.2, reputation: 'unrated', provenanceHash: 'sha256:trk…3a' },
  // Customs
  { id: 'p-broker', name: 'Port Authority Customs Broker', stage: 'customs', kind: 'broker', capabilities: ['entry filing', 'FTZ'], geo: { lon: -74.15, lat: 40.68, place: 'Port NY/NJ' }, capacityPct: 90, leadDays: 1, unitCost: 120, rating: 4.5, reputation: 'verified', provenanceHash: 'sha256:brk…4b' },
  // Last-mile
  { id: 'p-metro', name: 'Metro Last-Mile Co.', stage: 'lastmile', kind: 'van', capabilities: ['same-day', 'signature'], geo: { lon: -73.97, lat: 40.72, place: 'Manhattan, NY' }, capacityPct: 55, leadDays: 1, unitCost: 38, rating: 4.1, reputation: 'verified', provenanceHash: 'sha256:met…5c' },
  { id: 'p-bike', name: 'Cargo Bike Collective', stage: 'lastmile', kind: 'cargo-bike', capabilities: ['zero-emission', 'dense-urban'], geo: { lon: -73.99, lat: 40.73, place: 'Lower Manhattan' }, capacityPct: 40, leadDays: 1, unitCost: 22, rating: 3.7, reputation: 'unrated', provenanceHash: 'sha256:bik…6d' },
  // Service
  { id: 'p-qa', name: 'QA Inspection Services', stage: 'service', kind: 'inspection', capabilities: ['pre-shipment', 'compliance'], geo: { lon: -74.00, lat: 40.71, place: 'NYC' }, capacityPct: 75, leadDays: 2, unitCost: 150, rating: 4.4, reputation: 'verified', provenanceHash: 'sha256:qa…7e' },
];

export const providersForStage = (s: Stage) => PROVIDERS.filter((p) => p.stage === s);
