#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from urllib.parse import quote

ROOT = Path(__file__).resolve().parents[1]
INPUT = ROOT / "contracts" / "repo-governance" / "examples" / "sociosphere-active-spine.observations.v0.json"
BUILD = ROOT / "build" / "repo-governance-mvp"
RDF_OUTPUT = BUILD / "repo-governance-observations.ttl"
MANIFEST_OUTPUT = BUILD / "repo-governance-replay-manifest.json"

BASE = "https://socioprophet.org/prophet-platform/repo-governance/"


def ttl_string(value: object) -> str:
    return json.dumps(str(value), ensure_ascii=False)


def iri(kind: str, value: str) -> str:
    return f"<{BASE}{kind}/{quote(value, safe='')}>"


def load_packet() -> dict:
    return json.loads(INPUT.read_text(encoding="utf-8"))


def observation_digest(observations: list[dict]) -> str:
    canonical = json.dumps(observations, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def render_turtle(packet: dict) -> str:
    observations = packet["observations"]
    lines = [
        "@prefix rg: <https://socioprophet.org/ns/repo-governance#> .",
        "@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .",
        "",
        f"{iri('replay', 'sociosphere-active-spine-v0')}",
        "  a rg:Replay ;",
        f"  rg:schemaVersion {ttl_string(packet['schema_version'])} ;",
        f"  rg:kind {ttl_string(packet['kind'])} ;",
        f"  rg:observationDigest {ttl_string(observation_digest(observations))} .",
        "",
    ]

    for obs in observations:
        obs_iri = iri("observation", obs["observation_id"])
        repo_iri = iri("repository", obs["subject_repository"])
        source_iri = iri("source", obs["source_path"])
        lines.extend([
            f"{obs_iri}",
            "  a rg:Observation ;",
            f"  rg:observationId {ttl_string(obs['observation_id'])} ;",
            f"  rg:subjectRepository {repo_iri} ;",
            f"  rg:surface {ttl_string(obs['surface'])} ;",
            f"  rg:predicate {ttl_string(obs['predicate'])} ;",
            f"  rg:value {ttl_string(obs['value'])} ;",
            f"  rg:source {source_iri} ;",
            f"  rg:sourcePath {ttl_string(obs['source_path'])} ;",
            f"  rg:sourceBlobSha {ttl_string(obs['source_blob_sha'])} ;",
            f"  rg:parserId {ttl_string(obs['parser_id'])} ;",
            f"  rg:extractionMethod {ttl_string(obs['extraction_method'])} ;",
            f"  rg:confidence {ttl_string(obs['confidence'])} ;",
            f"  rg:evidenceDigest {ttl_string(obs['evidence_digest'])} .",
            "",
            f"{repo_iri}",
            "  a rg:Repository ;",
            f"  rg:repositoryName {ttl_string(obs['subject_repository'])} .",
            "",
            f"{source_iri}",
            "  a rg:SourceArtifact ;",
            f"  rg:sourcePath {ttl_string(obs['source_path'])} ;",
            f"  rg:sourceBlobSha {ttl_string(obs['source_blob_sha'])} .",
            "",
        ])
    return "\n".join(lines)


def replay_manifest(packet: dict) -> dict:
    observations = packet["observations"]
    digest = observation_digest(observations)
    return {
        "schema_version": "0.1",
        "kind": "repo_governance_replay_manifest",
        "replay_id": f"replay:sociosphere-active-spine:{digest[:16]}",
        "input": str(INPUT.relative_to(ROOT)),
        "outputs": {
            "rdf": str(RDF_OUTPUT.relative_to(ROOT)),
            "manifest": str(MANIFEST_OUTPUT.relative_to(ROOT)),
        },
        "observation_count": len(observations),
        "observation_digest": digest,
        "mutation_authorized": False,
        "infrastructure_required": False,
    }


def main() -> int:
    packet = load_packet()
    BUILD.mkdir(parents=True, exist_ok=True)
    RDF_OUTPUT.write_text(render_turtle(packet), encoding="utf-8")
    MANIFEST_OUTPUT.write_text(json.dumps(replay_manifest(packet), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"OK: wrote {RDF_OUTPUT.relative_to(ROOT)}")
    print(f"OK: wrote {MANIFEST_OUTPUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
