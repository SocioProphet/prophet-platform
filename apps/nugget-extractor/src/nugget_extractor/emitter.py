"""The emitter core — validate-then-write, one governed document per batch, resumable.

Write path (the point of W6.2 — the L2 content grain enters the platform log):

    document bytes → extract → build nuggets → VALIDATE EVERY ONE (fail-closed) →
        POST /api/graph/node  {id: <docRef>,      labels: [SourceDocument]}
        POST /api/graph/node  {id: <kkoTypeUri>,  labels: [KkoType]}          (per type)
        POST /api/graph/node  {id: <nuggetId>,    labels: [KnowledgeNugget, warrant:<t>]}
        POST /api/graph/edge  {label: fromDocument, from: nugget, to: document}
        POST /api/graph/edge  {label: kkoType,      from: nugget, to: <kkoTypeUri>}
        POST /api/graph/edge  {label: warrantedBy,  from: nugget, to: <cited nugget>}
    → POST /v1/compute kind=nugget-emit (compute-gateway)  ⇒ sealed receipt
    → only THEN is the batch counted as emitted.

hellgraph-service appends every write to its log; prophet-materializer-clickhouse tails
GET /api/graph/log and lands them in ClickHouse. This service never talks to ClickHouse —
the log is the only door.

The graph shape is the contract made walkable: `warrant:<type>` is a LABEL, so "give me
everything that is not model-generated" is a label query rather than a JSON scan, and the
normative visibility rule survives into every downstream surface. `warrantedBy` edges make
a derivation chain traversable from a computed value back to the quote it was computed
from, and `kkoType` edges are what make the nuggets KKO-typed IN THE GRAPH rather than
only in a JSON field.

FAIL-CLOSED RULES, in order of severity:
- VALIDATION failure ⇒ that nugget is NOT emitted, counted, and logged loudly. The rest of
  the document still emits (one bad span must not cost a whole filing), and the count on
  /healthz is the alarm — its steady-state MUST be 0. The sealed receipt carries the same
  count, so a silent drop in extraction quality is on the chain, not just in a gauge.
- HELLGRAPH failure ⇒ the batch stays PENDING with a per-WRITE cursor and resumes exactly
  where it stopped. Node writes are upserts and safe to repeat; an edge write is not (it
  would mint a second log event and a duplicate downstream row), so a half-written batch
  never re-sends the half that landed.
- GATEWAY failure ⇒ the graph writes have already landed (they cannot be un-written), so
  the batch stays pending AT THE RECEIPT STEP and retries the receipt only. Nothing is
  counted as emitted until it is both on the graph and attested — the same rule as the
  materializer's "no receipt ⇒ no checkpoint".
- The loop never dies: any error is recorded and retried on the next interval.

CONCURRENCY: two threads reach this object — the request path (POST /v1/extract) and the
background drain loop — so every mutation of the pending queue, the write cursor and the
logical clock is under one reentrant lock. Without it both threads drain the SAME batch:
the graph writes are replayed (duplicate `warrantedBy`/`kkoType` EDGES, each minting a
second log event and a duplicate downstream row), two receipts are minted for one
document, and the loser pops an already-empty queue. This was observed, not theorised —
it reproduced on the first end-to-end run when a request landed on a loop tick.

RESTART: identity is content-addressed (contract.local_id is a pure function of docRef +
source content hash + ordinal), so re-submitting the same document mints the same URNs and
the node writes upsert in place. In-memory pending batches do NOT survive a restart — the
recovery procedure is to re-POST the document, which is idempotent by construction. This
is stated rather than papered over with a queue this service has no store for.
"""
from __future__ import annotations

import logging
import os
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable

import jsonschema

from . import contract, nuggets as nugget_builder
from .clients import EmitError, GatewayError
from .extract import Extraction

log = logging.getLogger("nugget-extractor")

# Ceiling on _pending batches. A hellgraph outage stalls drain() at the FIRST failing
# op (batch.cursor never advances past it) while /v1/extract keeps admitting new
# documents — every call adds one batch to _pending and NUGGET_EXTRACTOR_MAX_PENDING
# batches later the pod is OOM'd. The cap makes that surface as a 503-shaped result
# (see BatchResult.status == 'degraded') that the caller can back-pressure on,
# instead of a pod bounce. Match the device-service `run_once` skip-with-reason
# pattern: no partial batch, no counted work, an explicit reason string.
#
# Copilot #1106: a bare `int(os.environ.get(...))` on a misconfigured value
# (e.g. NUGGET_EXTRACTOR_MAX_PENDING="off") would raise ValueError at IMPORT
# time and crash the pod on boot — an OOM guard that itself becomes a boot-
# time outage. Parse defensively: fall back to the 1000 default and log at
# WARN so the misconfiguration is loud rather than silent, and clamp to a
# non-negative floor (a negative cap would silently disable admission
# forever, which is the same shape defect).
def _parse_max_pending(raw: str | None, default: int = 1000) -> int:
    if raw is None or raw == "":
        return default
    try:
        value = int(raw)
    except (TypeError, ValueError):
        log.warning(
            "NUGGET_EXTRACTOR_MAX_PENDING=%r is not an int; falling back to %d",
            raw, default,
        )
        return default
    if value < 0:
        log.warning(
            "NUGGET_EXTRACTOR_MAX_PENDING=%d is negative; clamping to 0", value,
        )
        return 0
    return value


MAX_PENDING = _parse_max_pending(os.environ.get("NUGGET_EXTRACTOR_MAX_PENDING"))

NUGGET_LABEL = "KnowledgeNugget"
DOCUMENT_LABEL = "SourceDocument"
KKO_TYPE_LABEL = "KkoType"
EDGE_FROM_DOCUMENT = "fromDocument"
EDGE_KKO_TYPE = "kkoType"
EDGE_WARRANTED_BY = "warrantedBy"


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


@dataclass
class _Op:
    """One graph write. `node` ops are upserts; `edge` ops are not — hence the cursor."""
    kind: str                      # "node" | "edge"
    args: tuple


@dataclass
class _PendingBatch:
    """One document's remaining work: the graph writes not yet done, then the receipt."""
    doc_ref: str
    content_hash: str
    raw_sha256: str
    media_type: str
    nuggets: list[dict[str, Any]]
    warrant_counts: dict[str, int]
    validation_failures: int
    ops: list[_Op]
    cursor: int = 0                # ops[:cursor] have landed — never re-sent
    receipt_pending: bool = True


@dataclass
class BatchResult:
    documents: int = 0
    extracted: int = 0             # nuggets built from the document
    emitted: int = 0               # on the graph AND attested
    validation_failures: int = 0
    pending: int = 0               # nuggets in batches not yet fully sealed
    receipts: int = 0
    last_receipt_id: str | None = None
    warrant_counts: dict[str, int] = field(default_factory=dict)
    # `attempted` is not decoration: a drain with nothing pending contacts NOTHING, so
    # folding its default-true ok flags into /healthz would report both dependencies green
    # without ever having asked. False here means "no evidence either way", and the server
    # leaves the reported flags untouched — an unchecked dependency is never reported up.
    attempted: bool = False
    hellgraph_ok: bool = True
    gateway_ok: bool = True
    # Back-pressure signal: 'ok' | 'degraded'. Set when submit() refused to admit the
    # batch (because _pending is at MAX_PENDING) so the HTTP layer can translate to 503
    # instead of letting the pod balloon toward OOM. A `reason` explains which
    # dependency is stalled — the caller sees WHY it's being back-pressured.
    status: str = "ok"
    reason: str | None = None


@dataclass
class NuggetEmitter:
    writer: Any                    # HellGraphWriter | test fake
    gateway: Any                   # GatewayClient   | test fake
    clock: Callable[[], str] = field(default=_utc_now_iso)
    grain: str = "paragraph"
    _pending: list[_PendingBatch] = field(default_factory=list, repr=False)
    _logical: int = field(default=0, repr=False)
    _types_ensured: set[str] = field(default_factory=set, repr=False)
    # RLock, not Lock: submit() drains while already holding it. One writer at a time is
    # the whole point — see the CONCURRENCY note in the module docstring.
    _lock: threading.RLock = field(default_factory=threading.RLock, repr=False)

    # ── boot ──
    def startup_check(self) -> None:
        """Boot gate: the vendored-schema hash is asserted at import; here the schema must
        be a valid 2020-12 document, a probe nugget of EVERY warrant type built by this
        code must validate, and the laundering refusal must hold. Drift dies at boot."""
        contract.startup_check()

    # ── the door ──
    def submit(self, extraction: Extraction, *, doc_ref: str, run_ref: str,
               policy_labels: list[str] | None = None,
               extra_kko_type_refs: list[str] | None = None) -> BatchResult:
        """One extracted document → validated nuggets → a pending batch → drain.

        Returns the outcome for THIS call. A hellgraph or gateway outage leaves the batch
        pending (nothing counted as emitted) and the caller sees hellgraph_ok/gateway_ok
        false; the background loop retries it.

        Serialized against the drain loop and against other submits: concurrent writers
        would interleave graph writes for different documents and replay each other's
        edges. This service is single-writer by design (replicaCount 1, Recreate) and the
        lock is what makes that true inside the process too."""
        with self._lock:
            return self._submit(extraction, doc_ref=doc_ref, run_ref=run_ref,
                                policy_labels=policy_labels,
                                extra_kko_type_refs=extra_kko_type_refs)

    def _submit(self, extraction: Extraction, *, doc_ref: str, run_ref: str,
                policy_labels: list[str] | None = None,
                extra_kko_type_refs: list[str] | None = None) -> BatchResult:
        # BACK-PRESSURE gate — enforced BEFORE we build nuggets or advance the logical
        # clock, so a refused submit is a pure no-op the caller can safely retry. The
        # pending queue only fills when drain() is stalled (hellgraph or gateway is
        # down); admitting more work while both sides are wedged is what turns an
        # upstream outage into an OOM crash. Match device-service's skip-with-reason
        # posture — no partial batch, no counted work, an explicit reason string.
        if len(self._pending) >= MAX_PENDING:
            reason = (
                "nugget-extractor pending queue full "
                f"({len(self._pending)}/{MAX_PENDING}) — hellgraph downstream may be "
                "unavailable; retry after drain")
            log.warning("submit REFUSED — %s (doc=%s)", reason, doc_ref)
            return BatchResult(
                documents=0, extracted=0, emitted=0, validation_failures=0,
                pending=sum(len(b.nuggets) for b in self._pending),
                status="degraded", reason=reason,
                hellgraph_ok=False,   # the cap only trips when drain is stalled
                gateway_ok=False,
            )
        built = nugget_builder.build(
            extraction, doc_ref=doc_ref, run_ref=run_ref, clock=self.clock,
            logical_start=self._logical, policy_labels=policy_labels or [],
            extra_kko_type_refs=extra_kko_type_refs or [])
        self._logical += len(built)

        result = BatchResult(documents=1, extracted=len(built))
        valid: list[dict[str, Any]] = []
        for nugget in built:
            try:
                # THE fail-closed gate. `source_text` is passed so a direct-quote is
                # checked against what the document ACTUALLY says, not merely against its
                # own span arithmetic — a quote the source does not contain never enters
                # the graph, which is what makes laundering structurally impossible here.
                contract.validate_nugget(nugget, source_text=extraction.source_text)
            except (jsonschema.ValidationError, contract.NuggetError) as e:
                result.validation_failures += 1
                log.error("VALIDATION FAILURE — nugget NOT emitted (doc=%s id=%s): %s",
                          doc_ref, nugget.get("id"), getattr(e, "message", str(e)))
                continue
            valid.append(nugget)

        if valid:
            counts: dict[str, int] = {}
            for n in valid:
                counts[n["warrant"]["type"]] = counts.get(n["warrant"]["type"], 0) + 1
            result.warrant_counts = counts
            self._pending.append(_PendingBatch(
                doc_ref=doc_ref, content_hash=contract.content_hash(extraction.source_text),
                raw_sha256=extraction.raw_sha256, media_type=extraction.media_type,
                nuggets=valid, warrant_counts=counts,
                validation_failures=result.validation_failures,
                ops=self._plan(valid, doc_ref, extraction)))

        drained = self.drain()
        result.emitted = drained.emitted
        result.receipts = drained.receipts
        result.last_receipt_id = drained.last_receipt_id
        result.attempted = drained.attempted
        result.hellgraph_ok = drained.hellgraph_ok
        result.gateway_ok = drained.gateway_ok
        result.pending = drained.pending
        return result

    # ── plan ──
    def _plan(self, valid: list[dict[str, Any]], doc_ref: str,
              extraction: Extraction) -> list[_Op]:
        """The ordered write plan. Nodes before the edges that reference them, so an edge
        never points at a node the log has not seen yet."""
        ops: list[_Op] = [_Op("node", (doc_ref, [DOCUMENT_LABEL], {
            "docRef": doc_ref, "contentHash": contract.content_hash(extraction.source_text),
            "rawSha256": extraction.raw_sha256, "mediaType": extraction.media_type,
            "pages": extraction.pages, "sourceChars": len(extraction.source_text),
            "extractor": contract.CREATED_BY, "ocrBackend": "none"}))]

        types = sorted({t for n in valid for t in n.get("kkoTypeRefs", [])})
        for uri in types:
            if uri not in self._types_ensured:
                ops.append(_Op("node", (uri, [KKO_TYPE_LABEL], {"uri": uri, "vocab": "kko"})))

        ids = {n["id"] for n in valid}
        for n in valid:
            ops.append(_Op("node", (n["id"], [NUGGET_LABEL, f"warrant:{n['warrant']['type']}"],
                                    contract.flatten(n, ingest_time=self.clock()))))
            ops.append(_Op("edge", (EDGE_FROM_DOCUMENT, n["id"], doc_ref)))
            for uri in n.get("kkoTypeRefs", []):
                ops.append(_Op("edge", (EDGE_KKO_TYPE, n["id"], uri)))
            # Only nugget-to-nugget evidence becomes an edge: a run URN is not a graph node
            # this service owns, and inventing one would mint a dangling reference.
            for ref in n["warrant"]["evidence"]:
                if ref.startswith(contract.URN_PREFIX) and ref in ids:
                    ops.append(_Op("edge", (EDGE_WARRANTED_BY, n["id"], ref)))
        return ops

    # ── drain ──
    def drain(self) -> BatchResult:
        """Push pending batches: remaining graph writes, then the receipt. Resumable at
        the exact write that failed; nothing is counted emitted until it is attested.

        Single-writer: the background loop and the request path both call this."""
        with self._lock:
            return self._drain()

    def _drain(self) -> BatchResult:
        result = BatchResult()
        while self._pending:
            batch = self._pending[0]
            result.attempted = True
            try:
                while batch.cursor < len(batch.ops):
                    op = batch.ops[batch.cursor]
                    if op.kind == "node":
                        self.writer.post_node(*op.args)
                    else:
                        self.writer.post_edge(*op.args)
                    batch.cursor += 1        # advance ONLY after the write lands
            except EmitError as e:
                log.warning("hellgraph write failed at op %d/%d (doc=%s), batch stays "
                            "pending: %s", batch.cursor, len(batch.ops), batch.doc_ref, e)
                result.hellgraph_ok = False
                break

            try:
                receipt = self.gateway.mint(
                    doc_ref=batch.doc_ref, content_hash=batch.content_hash,
                    raw_sha256=batch.raw_sha256, media_type=batch.media_type,
                    nugget_count=len(batch.nuggets), warrant_counts=batch.warrant_counts,
                    validation_failures=batch.validation_failures,
                    batch_hash=contract.batch_hash(batch.nuggets))
            except GatewayError as e:
                log.warning("receipt refused for doc=%s — graph writes landed, batch stays "
                            "pending at the receipt step: %s", batch.doc_ref, e)
                result.gateway_ok = False
                break

            batch.receipt_pending = False
            result.emitted += len(batch.nuggets)
            result.receipts += 1
            result.last_receipt_id = receipt.get("receipt_id") or receipt.get("id")
            for k, v in batch.warrant_counts.items():
                result.warrant_counts[k] = result.warrant_counts.get(k, 0) + v
            self._types_ensured.update(t for n in batch.nuggets
                                       for t in n.get("kkoTypeRefs", []))
            self._pending.pop(0)

        result.pending = sum(len(b.nuggets) for b in self._pending)
        return result

    @property
    def pending_nuggets(self) -> int:
        with self._lock:
            return sum(len(b.nuggets) for b in self._pending)


__all__ = ["NuggetEmitter", "BatchResult", "NUGGET_LABEL", "DOCUMENT_LABEL",
           "KKO_TYPE_LABEL", "EDGE_FROM_DOCUMENT", "EDGE_KKO_TYPE", "EDGE_WARRANTED_BY"]
