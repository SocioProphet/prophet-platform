"""HTTP shell: POST /v1/extract (the door) + /healthz (honest counters) + a drain loop.

/healthz always answers 200 with the truth. Liveness is "the process and the drain loop
are up", not "every dependency is green" — restarting this pod cannot fix a down
hellgraph, and killing it would only lose the pending batches it is holding.

THE COUNTERS, and what a nonzero value means:
  extracted           nuggets built from submitted documents.
  emitted             nuggets on the graph AND covered by a sealed receipt. Nothing is
                      counted here until both are true.
  validation_failures MUST BE 0. Any other value means this service built a nugget that
                      does not conform to the vendored contract — it was refused, never
                      emitted, logged loudly, and the count is also bound into the sealed
                      receipt for the document it came from.
  pending             nuggets in batches not yet fully written + sealed (a hellgraph or
                      gateway outage). Retried by the loop; lost on restart, in which case
                      the recovery is to re-POST the document (identity is content-
                      addressed, so re-submission is idempotent).
  gateway_ok          did the last receipt attempt succeed. False ⇒ nothing is being
                      counted as emitted, by design.
  ocr_required        documents REJECTED because they are scans. This service ships no
                      OCR (extract.py) — this counter is that gap's honest meter, not a
                      silent zero from a stub.

Config (env):
  HELLGRAPH_URL          the graph/log surface     (default http://hellgraph-service:8090)
  COMPUTE_GATEWAY_URL    the receipt spine         (default http://compute-gateway:8080)
  GATEWAY_TOKEN          via secretEnv — the OUTBOUND credential for the receipt door
  NUGGET_INGEST_TOKEN    via secretEnv — the INBOUND bearer for /v1/extract. Unset ⇒ the
                         endpoint fails closed with 503 (compute-gateway precedent);
                         /healthz stays open so the probe still works.
  NUGGET_PROJECT         receipt chain/project     (default "default")
  NUGGET_GRAIN           paragraph | sentence      (default paragraph)
  NUGGET_MAX_BYTES       largest accepted document (default 16777216)
  DRAIN_INTERVAL_SECONDS (default 5)
  NUGGET_LOOP=off        disables the drain loop (tests / one-shot debugging)
  OCR_BACKEND            only "none" is registered; anything else aborts at import
"""
from __future__ import annotations

import base64
import binascii
import logging
import os
import threading
import time
import uuid
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Header, HTTPException
from pydantic import BaseModel, Field

from . import contract, extract as extract_mod
from .clients import GatewayClient, HellGraphWriter
from .emitter import NuggetEmitter

logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))

DRAIN_INTERVAL = float(os.getenv("DRAIN_INTERVAL_SECONDS", "5"))
LOOP_ENABLED = os.getenv("NUGGET_LOOP", "on").lower() != "off"
GRAIN = os.getenv("NUGGET_GRAIN", "paragraph")
MAX_BYTES = int(os.getenv("NUGGET_MAX_BYTES", str(16 * 1024 * 1024)))
INGEST_TOKEN = os.getenv("NUGGET_INGEST_TOKEN", "")

STATE: dict = {
    "documents": 0, "extracted": 0, "emitted": 0,
    "validation_failures": 0,       # steady-state MUST be 0 — nonzero is the alarm
    "pending": 0, "receipts": 0, "last_receipt_id": None,
    "warrant_counts": {}, "hellgraph_ok": None, "gateway_ok": None,
    "ocr_backend": extract_mod.OCR_BACKEND, "ocr_required": 0,
    "unsupported_media": 0, "extract_errors": 0,
    "grain": GRAIN, "loop_running": False,
    "last_emit_at": None, "last_error": None, "last_error_at": None,
}
_LOCK = threading.Lock()
_EMITTER: NuggetEmitter | None = None


def build_emitter() -> NuggetEmitter:
    return NuggetEmitter(
        writer=HellGraphWriter(os.getenv("HELLGRAPH_URL", "http://hellgraph-service:8090")),
        gateway=GatewayClient(
            os.getenv("COMPUTE_GATEWAY_URL", "http://compute-gateway:8080"),
            token=os.getenv("GATEWAY_TOKEN", ""),
            project=os.getenv("NUGGET_PROJECT", "default")),
        grain=GRAIN)


def emitter() -> NuggetEmitter:
    global _EMITTER
    if _EMITTER is None:
        _EMITTER = build_emitter()
    return _EMITTER


def _drain_step() -> None:
    """One loop step: push whatever is pending, fold the outcome into STATE."""
    try:
        result = emitter().drain()
        with _LOCK:
            STATE["emitted"] += result.emitted
            STATE["receipts"] += result.receipts
            STATE["pending"] = result.pending
            if result.attempted:
                # An idle drain contacts nothing. Reporting its default-green flags would
                # claim both dependencies are healthy without ever having asked — so an
                # unattempted pass leaves the last real observation (or None) standing.
                STATE["hellgraph_ok"] = result.hellgraph_ok
                STATE["gateway_ok"] = result.gateway_ok
            if result.last_receipt_id:
                STATE["last_receipt_id"] = result.last_receipt_id
            for k, v in result.warrant_counts.items():
                STATE["warrant_counts"][k] = STATE["warrant_counts"].get(k, 0) + v
            if result.emitted:
                STATE["last_emit_at"] = time.time()
            STATE["last_error"] = None
    except Exception as e:  # noqa: BLE001 — the loop must survive any dependency outage
        with _LOCK:
            STATE["last_error"] = f"{type(e).__name__}: {e}"
            STATE["last_error_at"] = time.time()


def _loop() -> None:
    with _LOCK:
        STATE["loop_running"] = True
    while True:
        _drain_step()
        time.sleep(DRAIN_INTERVAL)


@asynccontextmanager
async def _lifespan(_app: FastAPI):
    # Fail-closed boot gate IN THE MAIN THREAD: the vendored schema hash is asserted at
    # import; this validates a probe nugget of every warrant type AND the laundering
    # refusal. Contract drift aborts uvicorn startup — a visible crash, never a silently
    # broken producer behind a green pod.
    emitter().startup_check()
    if LOOP_ENABLED:
        threading.Thread(target=_loop, name="nugget-drain", daemon=True).start()
    yield


app = FastAPI(title="nugget-extractor", version="0.1.0", lifespan=_lifespan)


def require_token(authorization: str = Header(default="")) -> None:
    if not INGEST_TOKEN:
        raise HTTPException(status_code=503,
                            detail="ingest token not configured (fail-closed)")
    if authorization.removeprefix("Bearer ").strip() != INGEST_TOKEN:
        raise HTTPException(status_code=401, detail="unauthorized")


class ExtractRequest(BaseModel):
    document_b64: str
    filename: str = ""
    media_type: str | None = None
    # Optional: defaults to urn:srcos:document:<raw sha256>, i.e. the document IS its
    # content address unless the caller has a governed URN for it.
    doc_ref: str | None = None
    policy_labels: list[str] = Field(default_factory=list)
    kko_type_refs: list[str] = Field(default_factory=list)
    grain: str | None = None
    # Build + validate, return the nuggets, write NOTHING. For conformance checking a
    # document before it enters the graph.
    dry_run: bool = False


@app.post("/v1/extract")
def extract_endpoint(req: ExtractRequest, _: None = Depends(require_token)) -> dict:
    """Document → warranted nuggets → the graph → a sealed receipt.

    422 for anything this service cannot honestly extract (bad base64, unsupported media,
    a scan needing OCR). 503 when the nuggets are built and valid but hellgraph or the
    gateway refused — the batch is pending and the loop retries it; the caller may also
    simply re-POST, which is idempotent."""
    try:
        raw = base64.b64decode(req.document_b64, validate=True)
    except (binascii.Error, ValueError):
        raise HTTPException(status_code=422, detail="document_b64 must be valid base64")
    if len(raw) > MAX_BYTES:
        raise HTTPException(status_code=413,
                            detail=f"document is {len(raw)} bytes; limit is {MAX_BYTES}")

    try:
        extraction = extract_mod.extract(raw, filename=req.filename,
                                         media_type=req.media_type,
                                         grain=req.grain or GRAIN)
    except extract_mod.OcrRequired as e:
        with _LOCK:
            STATE["ocr_required"] += 1
        raise HTTPException(status_code=422, detail=str(e))
    except extract_mod.UnsupportedMedia as e:
        with _LOCK:
            STATE["unsupported_media"] += 1
        raise HTTPException(status_code=422, detail=str(e))
    except extract_mod.ExtractError as e:
        with _LOCK:
            STATE["extract_errors"] += 1
        raise HTTPException(status_code=422, detail=str(e))

    doc_ref = req.doc_ref or contract.doc_urn("document", extraction.raw_sha256)
    run_ref = f"urn:srcos:run:nugget-extract-{uuid.uuid4().hex[:16]}"

    if req.dry_run:
        from . import nuggets as builder
        built = builder.build(extraction, doc_ref=doc_ref, run_ref=run_ref,
                              clock=emitter().clock, logical_start=0,
                              policy_labels=req.policy_labels,
                              extra_kko_type_refs=req.kko_type_refs)
        failures = 0
        ok = []
        for n in built:
            try:
                contract.validate_nugget(n, source_text=extraction.source_text)
                ok.append(n)
            except Exception:  # noqa: BLE001 — a preview reports, it does not raise
                failures += 1
        return {"ok": True, "dry_run": True, "doc_ref": doc_ref,
                "content_hash": contract.content_hash(extraction.source_text),
                "raw_sha256": extraction.raw_sha256, "pages": extraction.pages,
                "extracted": len(built), "validation_failures": failures,
                "nuggets": ok}

    try:
        result = emitter().submit(extraction, doc_ref=doc_ref, run_ref=run_ref,
                                  policy_labels=req.policy_labels,
                                  extra_kko_type_refs=req.kko_type_refs)
    except Exception as e:  # noqa: BLE001 — never leak a stack trace as a 500 body
        with _LOCK:
            STATE["last_error"] = f"{type(e).__name__}: {e}"
            STATE["last_error_at"] = time.time()
        raise HTTPException(status_code=500, detail=f"{type(e).__name__}: {e}")

    with _LOCK:
        STATE["documents"] += result.documents
        STATE["extracted"] += result.extracted
        STATE["emitted"] += result.emitted
        STATE["validation_failures"] += result.validation_failures
        STATE["receipts"] += result.receipts
        STATE["pending"] = result.pending
        if result.attempted:            # same rule as the loop: never report an unchecked
            STATE["hellgraph_ok"] = result.hellgraph_ok   # dependency as green
            STATE["gateway_ok"] = result.gateway_ok
        if result.last_receipt_id:
            STATE["last_receipt_id"] = result.last_receipt_id
        for k, v in result.warrant_counts.items():
            STATE["warrant_counts"][k] = STATE["warrant_counts"].get(k, 0) + v
        if result.emitted:
            STATE["last_emit_at"] = time.time()

    body = {"ok": result.emitted > 0, "doc_ref": doc_ref, "run_ref": run_ref,
            "content_hash": contract.content_hash(extraction.source_text),
            "raw_sha256": extraction.raw_sha256, "pages": extraction.pages,
            "extracted": result.extracted, "emitted": result.emitted,
            "validation_failures": result.validation_failures,
            "pending": result.pending, "warrant_counts": result.warrant_counts,
            "receipt_id": result.last_receipt_id,
            "hellgraph_ok": result.hellgraph_ok, "gateway_ok": result.gateway_ok}
    if result.emitted == 0 and result.extracted > result.validation_failures:
        # Valid nuggets exist but are not attested yet — say so with a retryable status
        # rather than a 200 that would read as "landed".
        raise HTTPException(status_code=503, detail=body)
    return body


@app.get("/healthz")
def healthz() -> dict:
    with _LOCK:
        snapshot = dict(STATE)
    snapshot["pending"] = emitter().pending_nuggets
    return {"ok": True, "service": "nugget-extractor",
            "schema_sha256": contract.SCHEMA_SHA256,
            "spec_version": contract.SPEC_VERSION, **snapshot}
