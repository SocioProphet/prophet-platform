// Digital Health Twin client (walking skeleton) → the health-twin engine (/svc/health). Reads the
// person's FHIR-lite record bundle (keyed to organ systems, so the anatomical diagram is the index)
// and drives governed consent grants — a designated agent gets a scoped, time-boxed, receipted,
// revocable read grant, and every access is a receipt or a block. In production the engine runs
// LOCAL-FIRST on the person's own node; this skeleton reads a synthetic subject. Non-diagnostic.
import { resolveBase } from '../config/cockpitRuntime';

const BASE = resolveBase('health', 'VITE_HEALTH_BASE', '/svc/health');

export type EpistemicMode = 'observed' | 'derived' | 'verified' | 'attested' | 'hypothesis';
// organ = the anatomical structure a record localises to (health:localizedTo); classIri/organIri = the
// HDT ontology class + organ IRIs the fact carries, so it types into HellGraph + reasons in Ontogenesis.
export interface Observation { id: string; system: string; organ?: string; classIri?: string; organIri?: string | null; code: string; codeSystem: string; display: string; value: number; unit: string; refLow?: number; refHigh?: number; effective: string; trend?: number[]; epistemic: EpistemicMode }
export interface Condition { id: string; system: string; organ?: string; classIri?: string; organIri?: string | null; code: string; codeSystem: string; display: string; onset: string; clinicalStatus: string; epistemic: EpistemicMode }
export interface Encounter { id: string; system: string; type: string; date: string; provider: string; note: string }
export interface ImagingStudy { id: string; system: string; modality: string; bodySite: string; date: string; description: string; epistemic: EpistemicMode }
export interface SystemBundle { id: string; label: string; organs: string[]; iri?: string; compartment?: string; observations: Observation[]; conditions: Condition[]; encounters: Encounter[]; imaging: ImagingStudy[] }
export interface Grant { id: string; agent: string; scope: string; granted_at: string; expires_at: string; revoked: boolean; reads: number; receipt: string; active?: boolean }
export interface TwinBundle {
  subject: { id: string; label: string; note: string };
  systems: SystemBundle[];
  timeline: Encounter[];
  counts: { observations: number; conditions: number; encounters: number; imaging: number };
  grants: Grant[];
  ontology?: { health: string; hdt: string; subjectClass: string; note: string };
  disclaimer: string;
}

export async function loadTwin(): Promise<TwinBundle> {
  const res = await fetch(`${BASE}/api/health/twin`, { headers: { accept: 'application/json' } });
  if (!res.ok) throw new Error(`health twin unreachable (${res.status})`);
  return (await res.json()) as TwinBundle;
}
export async function grantAccess(agent: string, scope: string, ttlDays: number): Promise<{ grant: Grant }> {
  const res = await fetch(`${BASE}/api/health/grant`, { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify({ agent, scope, ttlDays }) });
  if (!res.ok) throw new Error(`grant failed (${res.status})`);
  return await res.json();
}
export async function revokeAccess(grant: string): Promise<unknown> {
  const res = await fetch(`${BASE}/api/health/revoke`, { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify({ grant }) });
  if (!res.ok) throw new Error(`revoke failed (${res.status})`);
  return await res.json();
}
export async function agentRead(grant: string): Promise<{ blocked?: boolean; reason?: string; reads?: number; receipt?: { id: string } }> {
  const res = await fetch(`${BASE}/api/health/agent-read`, { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify({ grant }) });
  return await res.json();
}

// ── ingestion + reconciliation surface (the connector plane + the estate services it orchestrates) ──
export interface ConnectorMeta { id: string; name: string; kind: string; authModel: string; sourceShape: string; uscdiClasses: string[]; modes: string[] }
export interface IngestSummary { counts: { total: number } & Record<string, number>; sources: { source: string; connector: string; mode: string; count: number }[]; uscdiCoverage: string[] }
export interface ServiceHealth { service: string; up: boolean; url: string }
export interface GoldenRecord { entity_id: string; name: string; size: number; members: string[]; contributingSources: string[] }
export interface ReconcileReport { service: string; reason?: string; before: number; after: number; merged: number; golden: GoldenRecord[]; receipt?: { id: string } }

export async function listConnectors(): Promise<{ connectors: ConnectorMeta[]; summary: IngestSummary }> {
  const res = await fetch(`${BASE}/api/health/connectors`, { headers: { accept: 'application/json' } });
  if (!res.ok) throw new Error(`connectors unreachable (${res.status})`);
  return await res.json();
}
export async function ingestConnector(connector: string, mode = 'fixture'): Promise<{ added: { total: number }; summary: IngestSummary; receipt: { id: string } }> {
  const res = await fetch(`${BASE}/api/health/ingest`, { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify({ connector, mode }) });
  if (!res.ok) throw new Error(`ingest failed (${res.status})`);
  return await res.json();
}
export async function reconcile(): Promise<ReconcileReport> {
  const res = await fetch(`${BASE}/api/health/reconcile`, { method: 'POST', headers: { 'content-type': 'application/json' }, body: '{}' });
  if (!res.ok) throw new Error(`reconcile failed (${res.status})`);
  return await res.json();
}
export async function serviceHealth(): Promise<{ services: ServiceHealth[] }> {
  const res = await fetch(`${BASE}/api/health/services`, { headers: { accept: 'application/json' } });
  if (!res.ok) throw new Error(`services unreachable (${res.status})`);
  return await res.json();
}
