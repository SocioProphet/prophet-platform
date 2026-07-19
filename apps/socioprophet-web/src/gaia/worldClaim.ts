// GAIA governed WorldClaim contract, adopted into the cockpit.
// Mirrors gaia-world-model/schemas/geospatial/world_claim.v1 (+ geo_anchor,
// source_evidence). The GAIA admissibility invariant:
//   Observation/Evidence → ProposedClaim → Explanation + Uncertainty
//   → PolicyDecision → Admitted / Provisional / Review
// A map datum is not treated as truth until it carries an anchor, ≥1 source
// evidence ref, temporal validity, uncertainty, and a policy status. This is how
// the map's honesty ("real" vs "illustrative") becomes a CONFORMANT instance of
// our own open, hashed, policy-gated world model — not a bespoke badge.
import { prov, type Provenance } from '../features/provenance/types';

export type AnchorType = 'point' | 'linestring' | 'polygon' | 'bbox' | 'h3_cell' | 'tile_region' | 'document_span' | 'time_window';

export interface GeoAnchor {
  anchor_id: string;
  anchor_type: AnchorType;
  geometry?: { type: string; coordinates: unknown };
  bbox?: [number, number, number, number];
  h3_cells?: string[];
  crs: string; // e.g. 'EPSG:4326'
  temporal: { observed_at: string; valid_from?: string; valid_to?: string; time_basis?: string };
}

// GAIA canonical source types. 'census_acs' is a LOCAL extension pending an
// upstream addition — GAIA's v1 enum has no statistical-tabulation type, so we
// flag rather than mis-map real ACS data onto 'field_report'/'sensor_observation'.
export type GaiaSourceType =
  | 'osm' | 'eo_stac' | 'dem_lidar' | 'weather_reanalysis' | 'field_report'
  | 'generated_manifest' | 'sensor_observation' | 'synthetic_fixture'
  | 'census_acs' | 'fema_nfhl'; // last two are LOCAL extensions pending upstream (no gov-dataset type in v1)
export const GAIA_V1_SOURCE_TYPES: readonly GaiaSourceType[] = [
  'osm', 'eo_stac', 'dem_lidar', 'weather_reanalysis', 'field_report', 'generated_manifest', 'sensor_observation', 'synthetic_fixture',
];

export interface SourceEvidence {
  evidence_id: string;
  source_type: GaiaSourceType;
  source_ref?: string;
  attribution: { source_name: string; license_ref: string; attribution_text: string };
  temporal: { observed_at: string };
  quality?: { score: number };
  content_hash?: string;
}

export type PolicyStatusValue = 'proposed' | 'provisional' | 'admitted' | 'review' | 'rejected';
export type UncertaintyClass = 'low' | 'moderate' | 'high' | 'very_high' | 'unknown';
export type StalenessClass = 'realtime' | 'recent' | 'historical' | 'archive' | 'unknown';
export type ClaimType = 'feature_classification' | 'risk' | 'coverage' | 'source_attribution' | 'fusion_result' | 'observation_passthrough';

export interface WorldClaim {
  claim_version: 'v1';
  claim_id: string;
  claim_type: ClaimType;
  geo_anchor: GeoAnchor;
  source_evidence_refs: string[]; // ≥1 required by the contract
  source_evidence: SourceEvidence[]; // inline copies for display (schema keeps refs; we carry both)
  proposed_value: Record<string, unknown>;
  temporal_validity: { valid_from: string; valid_to?: string; staleness_class?: StalenessClass };
  uncertainty: { confidence_score: number; uncertainty_class: UncertaintyClass; uncertainty_notes?: string };
  policy_status: { status: PolicyStatusValue; review_reason?: string; constraints?: string[] };
  attribution: { primary_source_name: string; license_refs: string[]; attribution_texts?: string[] };
  provenance: { chain: string[]; runtime_ref: string; created_at: string; content_hash?: string };
  classification?: { data_class: 'public' | 'internal' | 'restricted' | 'sensitive'; handling_tags?: string[] };
  map_display?: { display_layer: 'admitted_world_state' | 'provisional_overlay' | 'proposed_candidate' | 'review_flagged'; advisory_label?: string };
}

// Is this claim admissible as a truth layer? (the contract's gate for /map)
export const isAdmitted = (c: WorldClaim): boolean => c.policy_status.status === 'admitted';

// Project a governed WorldClaim onto the cockpit's ProvenanceBadge verdict, so the
// two vocabularies stay unified: admitted+real-source → grounded/verified;
// synthetic or un-reviewed → unassayed; rejected → unverified.
export function claimToProvenance(c: WorldClaim): Provenance {
  const realSource = c.source_evidence.some((e) => e.source_type !== 'synthetic_fixture');
  const method =
    c.policy_status.status === 'rejected' ? 'generated'
    : !realSource ? 'fixture'
    : c.policy_status.status === 'admitted' ? 'retrieved'
    : 'fixture';
  return prov(method, {
    verifier: 'GAIA world-claim',
    sources: c.source_evidence.map((e) => `${e.source_type}: ${e.attribution.source_name}`),
    receipt: c.provenance.content_hash,
    asOf: c.temporal_validity.valid_from.slice(0, 10),
    note: `Governed WorldClaim · policy ${c.policy_status.status} · uncertainty ${c.uncertainty.uncertainty_class}${c.policy_status.constraints?.length ? ` · ${c.policy_status.constraints.join(', ')}` : ''}`,
  });
}

// ── Builders ──────────────────────────────────────────────────────────────────
function h3Anchor(cellId: string, lon: number, lat: number, observedAt: string): GeoAnchor {
  return {
    anchor_id: `anchor:${cellId}`,
    anchor_type: 'h3_cell',
    h3_cells: [cellId],
    geometry: { type: 'Point', coordinates: [lon, lat] },
    crs: 'EPSG:4326',
    temporal: { observed_at: observedAt },
  };
}

// A real, admitted claim: e.g. ACS median income joined to a census tract.
// `confidence`/`uncertaintyClass`/`uncertaintyNotes` default to a direct-measurement
// profile; pass them to reflect e.g. a spatially-interpolated field.
export function realWorldClaim(opts: {
  cellId: string; lon: number; lat: number; claimType: ClaimType;
  value: Record<string, unknown>; source: SourceEvidence; staleness?: StalenessClass;
  confidence?: number; uncertaintyClass?: UncertaintyClass; uncertaintyNotes?: string;
}): WorldClaim {
  const now = new Date().toISOString();
  const ev = opts.source;
  return {
    claim_version: 'v1', claim_id: `wc:${opts.cellId}:${opts.claimType}`, claim_type: opts.claimType,
    geo_anchor: h3Anchor(opts.cellId, opts.lon, opts.lat, ev.temporal.observed_at),
    source_evidence_refs: [ev.evidence_id], source_evidence: [ev],
    proposed_value: opts.value,
    temporal_validity: { valid_from: ev.temporal.observed_at, staleness_class: opts.staleness ?? 'recent' },
    uncertainty: { confidence_score: opts.confidence ?? 0.9, uncertainty_class: opts.uncertaintyClass ?? 'low', uncertainty_notes: opts.uncertaintyNotes ?? 'Direct measurement from an official/open source.' },
    policy_status: { status: 'admitted' },
    attribution: { primary_source_name: ev.attribution.source_name, license_refs: [ev.attribution.license_ref], attribution_texts: [ev.attribution.attribution_text] },
    provenance: { chain: [ev.source_type, 'gaia:world_claim_ingest'], runtime_ref: 'cockpit/map', created_at: now, content_hash: ev.content_hash },
    classification: { data_class: 'public' },
    map_display: { display_layer: 'admitted_world_state' },
  };
}

// A synthetic/illustrative claim: proposed, not admissible as truth, high uncertainty,
// carries a display-advisory-only constraint. This is how the map stays honest.
export function syntheticWorldClaim(opts: {
  cellId: string; lon: number; lat: number; claimType: ClaimType; value: Record<string, unknown>; metricLabel: string;
}): WorldClaim {
  const now = new Date().toISOString();
  const ev: SourceEvidence = {
    evidence_id: `ev:synth:${opts.cellId}:${opts.claimType}`,
    source_type: 'synthetic_fixture',
    attribution: { source_name: 'Illustrative model (demo)', license_ref: 'internal:demo', attribution_text: `Synthetic ${opts.metricLabel} — sample data, not a live feed.` },
    temporal: { observed_at: now },
    quality: { score: 0.2 },
  };
  return {
    claim_version: 'v1', claim_id: `wc:${opts.cellId}:${opts.claimType}`, claim_type: opts.claimType,
    geo_anchor: h3Anchor(opts.cellId, opts.lon, opts.lat, now),
    source_evidence_refs: [ev.evidence_id], source_evidence: [ev],
    proposed_value: opts.value,
    temporal_validity: { valid_from: now, staleness_class: 'unknown' },
    uncertainty: { confidence_score: 0.2, uncertainty_class: 'high', uncertainty_notes: 'Deterministic synthetic field — illustrative only.' },
    policy_status: { status: 'proposed', review_reason: 'synthetic source', constraints: ['display-advisory-only'] },
    attribution: { primary_source_name: 'Illustrative model (demo)', license_refs: ['internal:demo'] },
    provenance: { chain: ['synthetic_fixture'], runtime_ref: 'cockpit/map', created_at: now },
    classification: { data_class: 'public', handling_tags: ['illustrative'] },
    map_display: { display_layer: 'proposed_candidate', advisory_label: 'Illustrative — not governed world state' },
  };
}

// SourceEvidence for real municipal reported incidents (Socrata open data). Reported
// incidents from an authority map onto GAIA's 'field_report' source type.
export function crimeEvidence(cellId: string, count: number, city = 'Municipal Open Data'): SourceEvidence {
  return {
    evidence_id: `ev:crime:${cellId}`,
    source_type: 'field_report',
    source_ref: 'socrata://municipal-crime',
    attribution: { source_name: `${city} — reported incidents (open data)`, license_ref: 'gov:open-data-terms', attribution_text: `${city} open data, reported incidents. ${count} in this area.` },
    temporal: { observed_at: new Date().toISOString() },
    quality: { score: 0.85 },
  };
}

// SourceEvidence for OSM public-transit stops — a canonical GAIA 'osm' source.
export function osmTransitEvidence(cellId: string, count: number): SourceEvidence {
  return {
    evidence_id: `ev:osmtransit:${cellId}`,
    source_type: 'osm',
    source_ref: 'osm://overpass/public_transport',
    attribution: { source_name: 'OpenStreetMap (Overpass)', license_ref: 'osm:odbl', attribution_text: `${count} OSM public-transit stops. © OpenStreetMap contributors.` },
    temporal: { observed_at: new Date().toISOString() },
    quality: { score: 0.8 },
  };
}

// SourceEvidence for FEMA National Flood Hazard Layer designations.
export function femaFloodEvidence(cellId: string, zone: string): SourceEvidence {
  return {
    evidence_id: `ev:fema:${cellId}`,
    source_type: 'fema_nfhl',
    source_ref: 'fema-nfhl://flood-hazard-zones',
    attribution: { source_name: 'FEMA National Flood Hazard Layer', license_ref: 'us-gov:public-domain', attribution_text: `FEMA NFHL flood-hazard zone ${zone || 'n/a'}.` },
    temporal: { observed_at: new Date().toISOString() },
    quality: { score: 0.88 },
  };
}

// SourceEvidence for Open-Meteo air quality (CAMS reanalysis → GAIA 'weather_reanalysis').
export function openMeteoAirEvidence(cellId: string): SourceEvidence {
  return {
    evidence_id: `ev:air:${cellId}`,
    source_type: 'weather_reanalysis',
    source_ref: 'open-meteo://air-quality/us_aqi',
    attribution: { source_name: 'Open-Meteo Air Quality (CAMS)', license_ref: 'open-meteo:cc-by-4.0', attribution_text: 'Air quality (US AQI) from Open-Meteo, based on the CAMS reanalysis.' },
    temporal: { observed_at: new Date().toISOString() },
    quality: { score: 0.75 },
  };
}

// Convenience: SourceEvidence for the real ACS × TIGER census income join.
export function acsIncomeEvidence(cellId: string, observedAt = '2023-01-01T00:00:00Z'): SourceEvidence {
  return {
    evidence_id: `ev:acs:${cellId}`,
    source_type: 'census_acs',
    source_ref: 'census-acs://B19013_001E + tigerweb/tracts',
    attribution: { source_name: 'US Census Bureau ACS 5-year + TIGERweb', license_ref: 'us-gov:public-domain', attribution_text: 'U.S. Census Bureau, American Community Survey 5-year estimates; TIGER/Line tract geometry.' },
    temporal: { observed_at: observedAt },
    quality: { score: 0.92 },
  };
}

// SourceEvidence for the real ACS × TIGER census population join (B01003).
export function acsPopulationEvidence(cellId: string, observedAt = '2023-01-01T00:00:00Z'): SourceEvidence {
  return {
    evidence_id: `ev:acspop:${cellId}`,
    source_type: 'census_acs',
    source_ref: 'census-acs://B01003_001E + tigerweb/tracts',
    attribution: { source_name: 'US Census Bureau ACS 5-year + TIGERweb', license_ref: 'us-gov:public-domain', attribution_text: 'U.S. Census Bureau, American Community Survey 5-year total population; TIGER/Line tract geometry.' },
    temporal: { observed_at: observedAt },
    quality: { score: 0.92 },
  };
}
