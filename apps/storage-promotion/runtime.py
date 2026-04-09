#!/usr/bin/env python3
from __future__ import annotations

import datetime as dt
import hashlib
import json
from typing import Any


def canonical_json(payload: Any) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))


def sha256_hex(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()


def build_observation(
    payload: dict[str, Any],
    *,
    observation_id: str = "obs:demo:1:v1",
    source_system: str = "storage-promotion",
    source_record_id: str = "demo-1",
    trust_class: str = "demo",
) -> dict[str, Any]:
    payload_str = canonical_json(payload)
    now = utc_now()
    return {
        "version": "0.1",
        "observation_id": observation_id,
        "source_system": source_system,
        "source_record_id": source_record_id,
        "observed_at": now,
        "normalized_payload": payload,
        "trust_class": trust_class,
        "content_hash": f"sha256:{sha256_hex(payload_str)}",
        "identity_hash": f"sha256:{sha256_hex(observation_id)}",
        "lineage_hash": f"sha256:{sha256_hex(source_system + ':' + source_record_id)}",
        "state": "active",
        "created_at": now,
    }


def promote_observation(observation: dict[str, Any]) -> dict[str, Any]:
    payload = observation["normalized_payload"]
    subject = str(payload["subject"])
    relation = str(payload["action"])
    obj = str(payload["object"])

    entities = [
        {
            "id": f"ent:user:{subject}",
            "kind": "user",
            "name": subject,
        },
        {
            "id": f"ent:role:{obj}",
            "kind": "role",
            "name": obj,
        },
    ]

    claim = {
        "id": f"clm:{subject}-{relation}-{obj}",
        "type": relation,
        "subject": subject,
        "object": obj,
        "source_observation_id": observation["observation_id"],
    }

    return {
        "promotion_run_id": f"run:promotion:{subject}:{obj}:v1",
        "entities": entities,
        "claim": claim,
        "status": "succeeded",
    }


def project_promoted(promoted: dict[str, Any]) -> dict[str, Any]:
    nodes = [{"id": entity["id"], "kind": entity["kind"], "name": entity["name"]} for entity in promoted["entities"]]
    claim = promoted["claim"]
    edges = [
        {
            "from": f"ent:user:{claim['subject']}",
            "to": f"ent:role:{claim['object']}",
            "type": claim["type"],
            "claim_id": claim["id"],
        }
    ]
    manifest = {
        "version": "0.1",
        "projection_manifest_id": f"pmf:neo4j:{claim['id']}",
        "projection_kind": "neo4j-shaped-graph",
        "generated_at": utc_now(),
        "source_observation_id": claim["source_observation_id"],
        "source_claim_id": claim["id"],
        "object_count": len(nodes) + len(edges),
        "hash_rollup": f"sha256:{sha256_hex(canonical_json({'nodes': nodes, 'edges': edges}))}",
        "target_store": "neo4j",
    }
    return {
        "nodes": nodes,
        "edges": edges,
        "projection_manifest": manifest,
    }
