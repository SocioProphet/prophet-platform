/**
 * Generated from contracts/chronos-evidence-loop/customer-readout.v0.json
 *
 * DO NOT EDIT — regenerate by running the generation script.
 * Source authority: SocioProphet/sociosphere
 * Contract kind: chronos_evidence_loop_platform_readout v0.1
 *
 * This module is a read-only product consumption surface.
 * No runtime execution, provider calls, or external effects are performed.
 * No downstream carrier ownership moves into Prophet Platform.
 */

export interface CarrierPlane {
  plane: string;
  repo: string;
  merged_ref: string;
  carrier: string;
}

export interface PlatformBoundary {
  read_only: boolean;
  consumes_sociosphere_proof_package: boolean;
  owns_downstream_carriers: boolean;
  executes_runtime_actions: boolean;
}

export interface ChronosEvidenceLoopReadout {
  schema_version: string;
  kind: string;
  source_authority: string;
  source_artifact: string;
  title: string;
  summary: string;
  proof_points: string[];
  carrier_planes: CarrierPlane[];
  non_claims: string[];
  platform_boundary: PlatformBoundary;
}

const readout: ChronosEvidenceLoopReadout = {
  schema_version: "0.1",
  kind: "chronos_evidence_loop_platform_readout",
  source_authority: "SocioProphet/sociosphere",
  source_artifact: "reports/corpus-loop-customer-readout.json",
  title: "CHRONOS Evidence Loop",
  summary:
    "A read-only product view of the governed Watson/Cyc/Semantic-Web/CHRONOS evidence loop. The platform displays the validated carrier chain and customer-safe proof points while SocioSphere remains the workspace coordination authority.",
  proof_points: [
    "Source corpus captured in SocioProphet/sociosphere#334.",
    "Five downstream carrier planes are represented.",
    "All carrier commits are pinned upstream in the SocioSphere manifest.",
    "All declared carrier artifacts are found in the SocioSphere resolution report.",
    "The readout is safe for architecture review and product demonstration.",
  ],
  carrier_planes: [
    {
      plane: "Evidence",
      repo: "SocioProphet/sherlock-search",
      merged_ref: "#58",
      carrier: "source-quality answer trace",
    },
    {
      plane: "Ontology",
      repo: "SocioProphet/ontogenesis",
      merged_ref: "#103",
      carrier: "corpus event semantics",
    },
    {
      plane: "Policy",
      repo: "SocioProphet/policy-fabric",
      merged_ref: "#85",
      carrier: "governed policy decision",
    },
    {
      plane: "Agent carrier",
      repo: "SocioProphet/agentplane",
      merged_ref: "#184",
      carrier: "bounded action loop carrier",
    },
    {
      plane: "Ledger",
      repo: "SocioProphet/model-governance-ledger",
      merged_ref: "#20",
      carrier: "governance record checks",
    },
  ],
  non_claims: [
    "No runtime execution is performed by this product view.",
    "No provider calls are performed by this product view.",
    "No external effects are performed by this product view.",
    "No production storage integration is claimed by this product view.",
    "No patent or license clearance is claimed by this product view.",
    "No downstream carrier ownership moves into Prophet Platform.",
  ],
  platform_boundary: {
    read_only: true,
    consumes_sociosphere_proof_package: true,
    owns_downstream_carriers: false,
    executes_runtime_actions: false,
  },
};

export default readout;
