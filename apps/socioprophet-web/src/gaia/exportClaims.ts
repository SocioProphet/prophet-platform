// Governed world-claim export — the moat made portable. Serialize the map's
// WorldClaims to a self-describing GeoJSON + manifest (schema, counts, sources,
// content fingerprint) that a skeptic can open, diff, and verify: every feature
// carries its GAIA policy status, ontogenesis Ω grade, uncertainty, and sourced
// evidence. No peer exports data this way — theirs is a value in a cell.
import type { WorldClaim } from './worldClaim';
import { omegaForClaim } from '../ontology/ontogenesis';

export interface ClaimFeature {
  type: 'Feature';
  geometry: unknown;
  properties: Record<string, unknown>;
}

export function claimToFeature(c: WorldClaim): ClaimFeature {
  return {
    type: 'Feature',
    geometry: c.geo_anchor.geometry ?? null,
    properties: {
      claim_id: c.claim_id,
      claim_type: c.claim_type,
      value: c.proposed_value,
      policy_status: c.policy_status.status,
      omega: omegaForClaim(c),
      confidence: c.uncertainty.confidence_score,
      uncertainty_class: c.uncertainty.uncertainty_class,
      sources: c.source_evidence.map((e) => `${e.source_type}:${e.attribution.source_name}`),
      as_of: c.temporal_validity.valid_from,
      h3: c.geo_anchor.h3_cells?.[0] ?? null,
    },
  };
}

// Non-cryptographic content fingerprint (FNV-1a). Honestly labelled — it's a change
// detector / diff key, not a cryptographic seal.
export function fnv1a(str: string): string {
  let h = 0x811c9dc5;
  for (let i = 0; i < str.length; i += 1) { h ^= str.charCodeAt(i); h = Math.imul(h, 0x01000193) >>> 0; }
  return h.toString(16).padStart(8, '0');
}

export interface ClaimBundle {
  schema: 'gaia.world_claim.v1+geojson';
  generated_at: string;
  count: number;
  admitted: number;
  sources: string[];
  type: 'FeatureCollection';
  features: ClaimFeature[];
  content_fingerprint: string;
}

export function claimBundle(claims: WorldClaim[], generatedAt = new Date().toISOString()): ClaimBundle {
  const features = claims.map(claimToFeature);
  const sources = [...new Set(claims.flatMap((c) => c.source_evidence.map((e) => e.attribution.source_name)))];
  const admitted = claims.filter((c) => c.policy_status.status === 'admitted').length;
  return {
    schema: 'gaia.world_claim.v1+geojson',
    generated_at: generatedAt,
    count: claims.length,
    admitted,
    sources,
    type: 'FeatureCollection',
    features,
    content_fingerprint: `fnv1a:${fnv1a(JSON.stringify(features))}`,
  };
}

// Browser download of the bundle as a .geojson file.
export function downloadClaimBundle(bundle: ClaimBundle, filename = 'gaia-world-claims.geojson'): void {
  const blob = new Blob([JSON.stringify(bundle, null, 2)], { type: 'application/geo+json' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url; a.download = filename; document.body.appendChild(a); a.click();
  a.remove(); URL.revokeObjectURL(url);
}
