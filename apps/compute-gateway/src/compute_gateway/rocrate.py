"""RO-Crate export — every governed run as a portable, signed research object.

A sealed receipt already carries heterogeneous-compute-as-homogeneous-evidence.
This renders it as an **RO-Crate 1.1** (https://w3id.org/ro/crate/1.1) metadata
document — the research-object packaging the science ecosystem already speaks
(Galaxy, WorkflowHub, Nextflow, Seek). The run becomes a citable `CreateAction`
whose inputs/outputs are content-addressed `File`s, whose provenance is W3C
PROV-O, and whose proof is the embedded in-toto Statement + Ed25519 signature.

So the moat — proof-carrying, epistemically-typed compute — leaves the platform
as a standards-compliant object anyone can verify, cite, and federate. No data
payloads are inlined (we hold only content hashes); the crate references them by
`sha256`, which is exactly content-addressed provenance.
"""
from __future__ import annotations

import time
from typing import Any

from .contract import Receipt

RO_CRATE_CONTEXT = "https://w3id.org/ro/crate/1.1/context"
RO_CRATE_SPEC = "https://w3id.org/ro/crate/1.1"


def _iso(ts: float) -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(ts))


def build(receipt: Receipt, *, publisher: str = "SocioProphet compute-gateway") -> dict[str, Any]:
    """Render a sealed receipt as an RO-Crate 1.1 metadata document (JSON-LD)."""
    run_id = "#run"
    in_id, out_id, rc_id, agent_id, tool_id = "#input", "#output", "#receipt", "#actor", "#kind"
    parts = [{"@id": in_id}, {"@id": out_id}, {"@id": rc_id}]

    graph: list[dict[str, Any]] = [
        # 1) the metadata descriptor (required root of every RO-Crate)
        {
            "@type": "CreativeWork",
            "@id": "ro-crate-metadata.json",
            "conformsTo": {"@id": RO_CRATE_SPEC},
            "about": {"@id": "./"},
        },
        # 2) the root data entity — the research object itself
        {
            "@id": "./",
            "@type": "Dataset",
            "name": f"Governed compute run · {receipt.kind}:{receipt.backend}",
            "description": (f"A {receipt.epistemic_status} compute run on the SocioProphet "
                            f"Universal Compute Plane, sealed as receipt {receipt.id}."),
            "datePublished": _iso(receipt.ts),
            "publisher": publisher,
            "license": {"@id": "https://spdx.org/licenses/CC-BY-4.0"},
            "mainEntity": {"@id": run_id},
            "hasPart": parts,
        },
        # 3) the run — a CreateAction dual-typed as a PROV Activity
        {
            "@id": run_id,
            "@type": ["CreateAction", "prov:Activity"],
            "name": f"compute:{receipt.kind}:{receipt.backend}",
            "startTime": _iso(receipt.ts),
            "endTime": _iso(receipt.ts),
            "agent": {"@id": agent_id},
            "instrument": {"@id": tool_id},
            "object": [{"@id": in_id}],
            "result": [{"@id": out_id}, {"@id": rc_id}],
            "actionStatus": {"@id": "http://schema.org/CompletedActionStatus"
                             if receipt.status == "ok" else "http://schema.org/FailedActionStatus"},
            "additionalProperty": [_pv("epistemic_status", receipt.epistemic_status),
                                   _pv("runtime", receipt.runtime),
                                   _pv("status", receipt.status)],
        },
        # 4) content-addressed input / output (no payloads inlined — hashes only)
        {"@id": in_id, "@type": ["File", "prov:Entity"], "name": "compute inputs",
         "encodingFormat": "application/json", "sha256": _hex(receipt.inputs_sha)},
        {"@id": out_id, "@type": ["File", "prov:Entity"], "name": "compute outputs",
         "encodingFormat": "application/json", "sha256": _hex(receipt.outputs_sha),
         "prov:wasGeneratedBy": {"@id": run_id}, "prov:wasDerivedFrom": {"@id": in_id}},
        # 5) the receipt as a first-class, identifiable entity
        {"@id": rc_id, "@type": ["File", "prov:Entity"], "name": "proof-carrying receipt",
         "identifier": receipt.id, "encodingFormat": "application/json",
         "prov:wasGeneratedBy": {"@id": run_id},
         "additionalProperty": [_pv("prev", receipt.prev or "genesis"),
                                _pv("hash_chain", "sha256")]},
        # 6) agent + the kind as a SoftwareApplication (the instrument)
        {"@id": agent_id, "@type": ["Person", "prov:Agent"], "name": receipt.actor},
        {"@id": tool_id, "@type": "SoftwareApplication",
         "name": f"compute.{receipt.kind}", "applicationCategory": "compute-kind",
         "operatingSystem": receipt.backend},
    ]

    # 7) the attestation — the in-toto Statement + Ed25519 signature, embedded so
    #    the research object is self-verifying (cosign-class).
    if receipt.signature and receipt.statement is not None:
        att_id = "#attestation"
        graph[1]["hasPart"].append({"@id": att_id})
        graph[2]["result"].append({"@id": att_id})
        graph.append({
            "@id": att_id,
            "@type": ["CreativeWork", "prov:Entity"],
            "name": "in-toto attestation (Ed25519)",
            "encodingFormat": "application/vnd.in-toto+json",
            "prov:wasGeneratedBy": {"@id": run_id},
            "additionalProperty": [
                _pv("predicateType", receipt.statement.get("predicateType", "")),
                _pv("signature", receipt.signature),
                _pv("public_key", receipt.public_key or ""),
                _pv("algorithm", "Ed25519"),
            ],
        })

    return {"@context": RO_CRATE_CONTEXT, "@graph": graph}


def _pv(name: str, value: Any) -> dict[str, Any]:
    return {"@type": "PropertyValue", "name": name, "value": value}


def _hex(sha: str) -> str:
    return sha.split(":", 1)[-1] if sha else ""
