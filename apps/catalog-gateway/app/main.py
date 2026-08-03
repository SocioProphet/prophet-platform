"""Catalog Gateway — the unified read/resolve/lineage + interop seam over the
Crystal Atlas catalog families.

First increment (read-only), composing existing pieces rather than reinventing them:
  * GET /v1/catalog/{kind}/{id}          — resolve a source|asset|model|workflow entry
  * GET /v1/catalog/{kind}/{id}/lineage  — upstream refs (source_refs), best-effort resolved
  * GET /v1/catalog/asset/{id}.dcat.json — the first real DCAT/schema.org emitter

The GMS-equivalent seam the design brief calls for (docs/strategy/PROPHET_DATA_CATALOG_DESIGN.md).
Registration (write path), search/faceting, and the masking-PDP mount land in later increments.
"""
from __future__ import annotations

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse

from . import ops, readout, slo
from .dcat import asset_to_dcat
from .store import KINDS, SERVICE, get_entry, is_valid_id

app = FastAPI(title="Prophet Platform Catalog Gateway", version="0.1.0")


@app.get("/healthz")
def healthz() -> dict:
    return {"status": "ok", "service": SERVICE, "kinds": list(KINDS)}


def _resolve_or_404(kind: str, entry_id: str) -> dict:
    if kind not in KINDS:
        raise HTTPException(status_code=404, detail=f"unknown catalog kind: {kind}")
    if not is_valid_id(entry_id):
        raise HTTPException(status_code=400, detail="invalid catalog id")
    entry = get_entry(kind, entry_id)
    if entry is None:
        raise HTTPException(status_code=404, detail=f"{kind} '{entry_id}' not found")
    return entry


# NOTE: the `.dcat.json` route is declared BEFORE the generic `/{kind}/{entry_id}`
# resolver. Starlette matches routes in declaration order and `{entry_id}` is `[^/]+`
# (dots included), so the generic resolver would otherwise swallow "<id>.dcat.json".
@app.get("/v1/catalog/asset/{entry_id}.dcat.json")
def asset_dcat(entry_id: str) -> JSONResponse:
    entry = _resolve_or_404("asset", entry_id)
    doc = asset_to_dcat(entry)
    # Log the entry's OWN asset_id (what the DCAT doc is identified by), falling
    # back to the request path — so the ops event can never disagree with the
    # emitted document when the stored asset_id differs from the path.
    ops.record_dcat_emitted(entry.get("asset_id") or entry_id, doc.get("dct:accessRights", ""),
                            distribution_class=entry.get("distribution_class"))
    return JSONResponse(content=doc, media_type="application/ld+json")


# NOTE: the ops-readout routes are declared BEFORE the generic `/{kind}/{entry_id}`
# resolver for the same reason as `.dcat.json`: `/v1/catalog/ops/readout` would
# otherwise bind kind="ops", entry_id="readout" and 404. `ops` is not a catalog kind.
@app.get("/v1/catalog/ops/readout")
def ops_readout(top_n: int = readout.DEFAULT_TOP_N) -> dict:
    """Compute the catalog KPIs by folding the captured operational events. Read-only:
    does not crystallize a new event (use POST for that)."""
    return readout.compute_readout(top_n=max(1, min(top_n, 100)))


@app.post("/v1/catalog/ops/readout")
def ops_readout_emit(top_n: int = readout.DEFAULT_TOP_N) -> dict:
    """Compute AND crystallize the readout as a catalog.ops.readout.v0 event (the
    scheduled readout job's endpoint). Returns the readout with the emitted event_id."""
    doc, event_id = readout.emit_readout(top_n=max(1, min(top_n, 100)))
    return {"readout": doc, "event_id": event_id}


@app.get("/v1/catalog/ops/slo")
def ops_slo() -> dict:
    """Grade the current readout against the SLO → the Assay verdict (ok/sad/bad).
    Read-only: does not crystallize an event (use POST)."""
    return slo.evaluate()


@app.post("/v1/catalog/ops/slo")
def ops_slo_emit() -> dict:
    """Evaluate AND crystallize the verdict as a catalog.ops.slo.v0 event."""
    doc, event_id = slo.emit_slo()
    return {"slo": doc, "event_id": event_id}


@app.get("/v1/catalog/{kind}/{entry_id}/lineage")
def lineage(kind: str, entry_id: str) -> dict:
    entry = _resolve_or_404(kind, entry_id)
    # source_refs are the lineage seed. Best-effort resolve any that are catalog ids.
    upstream = []
    for ref in entry.get("source_refs") or []:
        as_source = get_entry("source", ref)
        as_asset = get_entry("asset", ref)
        upstream.append({"ref": ref, "resolved": bool(as_source or as_asset),
                         "kind": "source" if as_source else ("asset" if as_asset else None)})
    return {"node": entry_id, "kind": kind, "upstream": upstream}


@app.get("/v1/catalog/{kind}/{entry_id}")
def resolve(kind: str, entry_id: str) -> dict:
    try:
        entry = _resolve_or_404(kind, entry_id)
    except HTTPException as exc:
        if exc.status_code == 404 and kind in KINDS:
            ops.record_resolved(kind, entry_id, hit=False)  # capture misses too
        raise
    ops.record_resolved(kind, entry_id, hit=True)
    return {"kind": kind, "entry": entry}
