"""The compute registry — kind → backends, capabilities, warrant, entitlement.

This is the forge's adapter registry, generalized from "notebook adapters" to
"every kind of compute." Adding a compute type is a row here + an adapter. The
registry is discoverable (`/v1/registry`) so the surface renders itself and an
agent planner treats it as an action space.
"""
from __future__ import annotations

import os

from .contract import EpistemicStatus

# kind → definition. `executes_user_code` decides trust-boundary placement;
# `epistemic` is the default warrant of the kind's output.
KINDS: dict[str, dict] = {
    "notebook": {
        "backends": ["forge"], "default": "forge",
        "capabilities": ["python", "r", "julia", "stateful-kernel"],
        "epistemic": "derived", "executes_user_code": True, "status": "live",
    },
    "graph-query": {
        "backends": ["hellgraph"], "default": "hellgraph",
        "capabilities": ["label-query", "subgraph"],
        "epistemic": "observed", "executes_user_code": False, "status": "live",
    },
    "graph-stats": {
        "backends": ["hellgraph"], "default": "hellgraph",
        "capabilities": ["counts", "analytics"],
        "epistemic": "observed", "executes_user_code": False, "status": "live",
    },
    # sovereign Spark — the Databricks paradigm as ONE backend behind the uniform
    # contract, entitlement-gated + receipt-sealed. Real spark-runner /v1/submit.
    "spark": {
        "backends": ["spark-runner"], "default": "spark-runner",
        "capabilities": ["sql", "dataframe"],
        "epistemic": "derived", "executes_user_code": True, "status": "live",
    },
    # adapter wired (embed | chat); status held at declared until the model-server
    # endpoint contract is verified in-cluster — the adapter degrades honestly.
    "inference": {
        "backends": ["model-server"], "default": "model-server",
        "capabilities": ["chat", "embed"],
        "epistemic": "derived", "executes_user_code": False, "status": "declared",
    },
    # the COMPOSITE kind: a DAG of governed sub-computes, each sealing its own
    # receipt, bound by one composite receipt. Orchestrated by the engine itself
    # (backend "gateway") — no external runtime. Its warrant is the weakest step.
    "workflow": {
        "backends": ["gateway"], "default": "gateway",
        "capabilities": ["dag", "compose", "fan-in", "memoized-steps"],
        "epistemic": "derived", "executes_user_code": False, "status": "live",
    },
    # ── IFM: document → SQL, proof-carrying ──
    # Land the pack (stage 01): content-hash the raw bytes so identical packs are
    # comparable and re-runs are free (request memoization = the dedupe). In-process.
    "ingest": {
        "backends": ["gateway"], "default": "gateway",
        "capabilities": ["content-address", "pdf", "pptx", "dedupe"],
        "epistemic": "observed", "executes_user_code": False, "status": "live",
    },
    # Layout-aware parse (stage 02): document bytes → blocks[], each keeping its page
    # (+ shape bbox for PPTX, table cells pipe-joined; page/paragraph regions for PDF).
    "parse": {
        "backends": ["gateway"], "default": "gateway",
        "capabilities": ["pdf", "pptx", "text-blocks", "tables", "page-regions"],
        "epistemic": "observed", "executes_user_code": False, "status": "live",
    },
    # Extract a (graphics-heavy) document into typed rows against a target schema;
    # each fact carries its lineage + warrant. Backend = Holmes/Sherlock (Studio).
    "extraction": {
        "backends": ["holmes"], "default": "holmes",
        "capabilities": ["pdf", "pptx", "tables", "typed-rows", "source-spans"],
        "epistemic": "derived", "executes_user_code": False, "status": "live",
    },
    # Reconcile extracted facts against a structured reference. Jurisdiction-routed:
    # US = SEC EDGAR company-facts (open XBRL); AU = statutory Appendix 4E/4D previously
    # extracted through this same pipeline (cross-document — AU has no open-XBRL twin).
    # FactSet on a key later; the logic never changes. Agreement → verified; divergence
    # → flagged edge (the tradable signal).
    "reconcile": {
        "backends": ["open-data"], "default": "open-data",
        "capabilities": ["sec-edgar", "companyfacts", "asx-appendix", "jurisdiction-routing",
                         "tolerance-check", "warrant-promotion", "divergence-flag"],
        "epistemic": "verified", "executes_user_code": False, "status": "live",
    },
    # Load reconciled facts into the structured SQL layer (the doc→SQL sink), keyed by
    # (entity, period, field) + warrant. Sovereign SQLite now; Postgres DSN = prod swap.
    "load": {
        "backends": ["sql"], "default": "sql",
        "capabilities": ["upsert", "sqlite", "keyed-by-entity-period", "warrant-tagged"],
        "epistemic": "derived", "executes_user_code": False, "status": "live",
    },
}


class UnknownKind(KeyError):
    pass


class UnknownBackend(KeyError):
    pass


def resolve(kind: str, backend: str | None) -> tuple[str, dict, str]:
    """(kind, definition, backend). Raises on unknown kind/backend."""
    if kind not in KINDS:
        raise UnknownKind(kind)
    d = KINDS[kind]
    b = backend or d["default"]
    if b not in d["backends"]:
        raise UnknownBackend(f"{b} not a backend for {kind}")
    return kind, d, b


def epistemic_for(kind: str) -> EpistemicStatus:
    return KINDS.get(kind, {}).get("epistemic", "unknown")


# ── the uniform entitlement gate (generalizes STUDIO_COMPUTE_ENTITLEMENTS) ──
# Comma-sep tokens. A request is entitled if the set contains any of:
#   "*", kind, "kind:backend", project, "project:kind", "project:kind:backend",
# OR the caller presents an entitlement token that is itself in the set (paid tenants).
def _entitlements() -> set[str]:
    return {t.strip() for t in os.getenv("COMPUTE_ENTITLEMENTS", "").split(",") if t.strip()}


def entitled(project: str, kind: str, backend: str, presented: str | None) -> bool:
    ents = _entitlements()
    if "*" in ents:
        return True
    keys = {kind, f"{kind}:{backend}", project, f"{project}:{kind}", f"{project}:{kind}:{backend}"}
    if keys & ents:
        return True
    return bool(presented and presented in ents)


def kinds_providing(capability: str) -> list[str]:
    """The kinds whose capability set includes `capability`, live kinds first —
    the reverse index the planner treats as an action space over the registry."""
    hits = [k for k, d in KINDS.items() if capability in d["capabilities"]]
    return sorted(hits, key=lambda k: (KINDS[k]["status"] != "live", k))


def catalog(project: str, presented: str | None) -> list[dict]:
    """The registry as the surface/planner sees it: kinds + backends + entitlement."""
    out = []
    for kind, d in KINDS.items():
        out.append({
            "kind": kind, "backends": d["backends"], "default": d["default"],
            "capabilities": d["capabilities"], "epistemic": d["epistemic"],
            "executes_user_code": d["executes_user_code"], "status": d["status"],
            "entitled": entitled(project, kind, d["default"], presented),
        })
    return out
