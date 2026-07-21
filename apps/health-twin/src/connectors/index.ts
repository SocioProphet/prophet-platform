// Connector registry — the modular integration surface. Adding a source is adding one file here; each
// proves out on a real-schema fixture now and flips to live with a credential (no downstream change).
import type { Connector, IngestMode, IngestResult, SourceId } from '../ingest.js';
import { appleHealth } from './apple-health.js';
import { oura } from './oura.js';
import { epicSmartFhir } from './epic-smart-fhir.js';
import { cmsBlueButton } from './cms-blue-button.js';
import { dicomweb } from './dicomweb.js';

export const CONNECTORS: Connector[] = [epicSmartFhir, cmsBlueButton, appleHealth, oura, dicomweb];

export const getConnector = (id: string): Connector | undefined => CONNECTORS.find((c) => c.id === id);

// public catalogue (no fixtures/logic) — what the surface lists as "connect a source".
export const connectorCatalogue = () => CONNECTORS.map((c) => ({
  id: c.id, name: c.name, kind: c.kind, authModel: c.authModel,
  sourceShape: c.sourceShape, uscdiClasses: c.uscdiClasses, modes: c.modes,
}));

// run one connector end-to-end: fetch(mode) → normalize(). fixture proves the live path (normalize is
// mode-invariant). Throws if the requested mode isn't wired (live needs a credential).
export async function runConnector(id: SourceId, mode: IngestMode = 'fixture'): Promise<IngestResult> {
  const c = getConnector(id);
  if (!c) throw new Error(`unknown connector: ${id}`);
  if (!c.modes.includes(mode)) throw new Error(`connector ${id} has no '${mode}' transport wired`);
  const raw = await c.fetch(mode);
  return c.normalize(raw, mode);
}
