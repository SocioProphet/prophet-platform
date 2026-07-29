"""Seal-the-Walls W1.3 — receipt unification: the HellGraph ENGINE's sealed()
receipts on THE estate receipt spine, verifiable end-to-end by ONE walk.

The engine (vendored @socioprophet/hellgraph) seals every enrich/explore result:
`hash = "sha256:" + sha256(JSON.stringify(rec))` over the receipt WITHOUT its
`hash` field, where `rec` is built with a fixed key order and serialized by V8's
JSON.stringify (insertion order, no whitespace, ECMAScript number formatting).
For the gateway to attest that seal it must RECOMPUTE it byte-exactly — so this
module carries a JS-faithful serializer (`js_stringify`) plus the engine's exact
receipt shapes (key order pinned from the vendored dist, engine 0.4.40):

  enrich  (AttributeRecommendation): {label, method, peers, snapshot, recommendations}
      recommendation item: {key, kind, fusedScore, rank, peerCoverage, ownCoverage, signals}
      signals: {consistency, trust, probabilistic[, coherence]}   (coherence LAST when present)
  explore (Exploration):             {seeds, method, snapshot, suggestions}
      suggestion item: {id, labels, score, rank}
  snapshot (both): {seq, nodes, edges} — seq = the store's monotonic logical
      clock, THE receipt binding to graph state (counts alone collide).

Canonicalization is SCHEMA-DRIVEN, not trust-the-wire: key order is rebuilt from
the pinned shapes, so recomputation survives any transport that reorders keys
(the durable blob store re-serializes with sort_keys). Unknown keys are REFUSED
loudly — a receipt this module can't order byte-exactly is a receipt it must not
attest (an engine shape change lands here as a fail-loud diff, never a silent
mis-hash).

The verify walk (`verify_walk`) is the ONE end-to-end check the wall demands:
  1. gateway-signature    — the receipt is on the project chain, its id-hash
                            recomputes, and the Ed25519 signature over the
                            in-toto statement verifies (spine authenticity).
  2. engine-seal-hash     — the stored engine receipt's sealed sha256 recomputes
                            byte-exactly (engine-output integrity).
  3. snapshot-seq-binding — the stored envelope matches the SIGNED outputs_sha
                            and the engine receipt's snapshot.seq equals the seq
                            the gateway bound at seal time (graph-state binding;
                            catches tamper-and-reseal, which step 2 cannot).
Each step is typed in the returned trace; a failure stops the walk and marks the
remaining steps skipped — so tampering fails at the step that OWNS the guarantee.
"""
from __future__ import annotations

import hashlib
import json
import math
from decimal import Decimal
from typing import Any

from . import artifacts, receipts, signing

ENGINE_KINDS = ("enrich", "explore")

# ── the engine's receipt shapes, key order pinned from the vendored dist ──
_SNAPSHOT_KEYS = ("seq", "nodes", "edges")
_SIGNAL_KEYS = ("consistency", "trust", "probabilistic", "coherence")   # coherence optional, LAST
_RECOMMENDATION_KEYS = ("key", "kind", "fusedScore", "rank", "peerCoverage", "ownCoverage", "signals")
_SUGGESTION_KEYS = ("id", "labels", "score", "rank")
_TOP_KEYS = {
    "enrich": ("label", "method", "peers", "snapshot", "recommendations"),
    "explore": ("seeds", "method", "snapshot", "suggestions"),
}
_OUTPUT_FIELD = {"enrich": "recommendations", "explore": "suggestions"}


class EngineReceiptError(ValueError):
    """A receipt this module cannot canonicalize byte-exactly (never attest it)."""


# ── JS-faithful serialization: byte-identical to V8 JSON.stringify ──
def _js_number(x: float) -> str:
    """ECMAScript Number::toString(x, 10) for a finite double — V8's shortest
    round-trip digits (Python's repr produces the same digit string) re-rendered
    with JS placement rules: plain decimal for 1e-6 ≤ |x| < 1e21, exponent form
    (`e+21`, `e-7` — sign always, no zero-pad) outside, integral doubles without
    a trailing `.0`."""
    if math.isnan(x) or math.isinf(x):
        raise EngineReceiptError("non-finite number in engine receipt")
    if x == 0:
        return "0"                                   # JSON.stringify(-0) === "0"
    sign, digits, exponent = Decimal(repr(x)).as_tuple()
    ds = "".join(map(str, digits)).rstrip("0") or "0"
    exponent += len(digits) - len(ds)                # shortest digits, adjusted exponent
    k = len(ds)
    n = k + int(exponent)                            # value = 0.<ds> × 10^n
    if k <= n <= 21:
        body = ds + "0" * (n - k)
    elif 0 < n <= 21:
        body = ds[:n] + "." + ds[n:]
    elif -6 < n <= 0:
        body = "0." + "0" * (-n) + ds
    else:
        e = n - 1
        mantissa = ds if k == 1 else ds[0] + "." + ds[1:]
        body = f"{mantissa}e{'+' if e >= 0 else '-'}{abs(e)}"
    return ("-" if sign else "") + body


def js_stringify(value: Any) -> str:
    """V8 JSON.stringify for the JSON value domain (dict insertion order kept).
    Python's json string escaping already matches V8 (`\\b \\t \\n \\f \\r`,
    `\\u00xx` control chars, raw non-ASCII); numbers need `_js_number`."""
    if value is None:
        return "null"
    if isinstance(value, bool):                      # before int — bool subclasses int
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        return _js_number(value)
    if isinstance(value, str):
        return json.dumps(value, ensure_ascii=False)
    if isinstance(value, list):
        return "[" + ",".join(js_stringify(v) for v in value) + "]"
    if isinstance(value, dict):
        parts = []
        for k, v in value.items():
            if not isinstance(k, str):
                raise EngineReceiptError(f"non-string object key: {k!r}")
            parts.append(json.dumps(k, ensure_ascii=False) + ":" + js_stringify(v))
        return "{" + ",".join(parts) + "}"
    raise EngineReceiptError(f"unserializable value of type {type(value).__name__}")


# ── shape validation + schema-driven canonical ordering ──
def _is_count(v: Any) -> bool:
    return isinstance(v, int) and not isinstance(v, bool) and v >= 0


def _is_num(v: Any) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def _check_exact_keys(obj: dict, allowed: tuple[str, ...], required: tuple[str, ...],
                      where: str, errors: list[str]) -> None:
    unknown = [k for k in obj if k not in allowed]
    missing = [k for k in required if k not in obj]
    if unknown:
        errors.append(f"{where} has unknown key(s) {unknown} (engine 0.4.x shape pinned — refuse, never mis-hash)")
    if missing:
        errors.append(f"{where} missing {missing}")


def validate(kind: str, receipt: Any) -> list[str]:
    """Errors making `receipt` NOT a sealable engine receipt of `kind`. Empty ⇒
    the shape is exactly the engine's sealed() output: hash + snapshot
    {seq,nodes,edges} + the ranked output — everything sealed_hash() can order."""
    if kind not in ENGINE_KINDS:
        return [f"kind must be one of {list(ENGINE_KINDS)}, got {kind!r}"]
    if not isinstance(receipt, dict):
        return ["engineReceipt must be a JSON object"]
    errors: list[str] = []
    top = _TOP_KEYS[kind]
    _check_exact_keys(receipt, top + ("hash",), top + ("hash",), "engineReceipt", errors)
    if errors:
        return errors

    h = receipt["hash"]
    if not (isinstance(h, str) and h.startswith("sha256:") and len(h) == 71):
        errors.append("hash must be 'sha256:<64 hex>'")
    if not isinstance(receipt["method"], str):
        errors.append("method must be a string")

    snap = receipt["snapshot"]
    if not isinstance(snap, dict):
        errors.append("snapshot must be an object {seq, nodes, edges}")
    else:
        _check_exact_keys(snap, _SNAPSHOT_KEYS, _SNAPSHOT_KEYS, "snapshot", errors)
        for k in _SNAPSHOT_KEYS:
            if k in snap and not _is_count(snap[k]):
                errors.append(f"snapshot.{k} must be a non-negative integer")

    if kind == "enrich":
        if not isinstance(receipt["label"], str):
            errors.append("label must be a string")
        if not _is_count(receipt["peers"]):
            errors.append("peers must be a non-negative integer")
        recs = receipt["recommendations"]
        if not isinstance(recs, list):
            errors.append("recommendations must be a list")
        else:
            for i, item in enumerate(recs):
                where = f"recommendations[{i}]"
                if not isinstance(item, dict):
                    errors.append(f"{where} must be an object")
                    continue
                _check_exact_keys(item, _RECOMMENDATION_KEYS, _RECOMMENDATION_KEYS, where, errors)
                for k in ("key", "kind"):
                    if not isinstance(item.get(k, ""), str):
                        errors.append(f"{where}.{k} must be a string")
                for k in ("fusedScore", "peerCoverage", "ownCoverage"):
                    if k in item and not _is_num(item[k]):
                        errors.append(f"{where}.{k} must be a number")
                if "rank" in item and not _is_count(item["rank"]):
                    errors.append(f"{where}.rank must be a non-negative integer")
                sig = item.get("signals")
                if not isinstance(sig, dict):
                    errors.append(f"{where}.signals must be an object")
                else:
                    _check_exact_keys(sig, _SIGNAL_KEYS, _SIGNAL_KEYS[:3], f"{where}.signals", errors)
                    for k in _SIGNAL_KEYS:
                        if k in sig and not _is_num(sig[k]):
                            errors.append(f"{where}.signals.{k} must be a number")
    else:
        seeds = receipt["seeds"]
        if not (isinstance(seeds, list) and all(isinstance(s, str) for s in seeds)):
            errors.append("seeds must be a list of strings")
        sugs = receipt["suggestions"]
        if not isinstance(sugs, list):
            errors.append("suggestions must be a list")
        else:
            for i, item in enumerate(sugs):
                where = f"suggestions[{i}]"
                if not isinstance(item, dict):
                    errors.append(f"{where} must be an object")
                    continue
                _check_exact_keys(item, _SUGGESTION_KEYS, _SUGGESTION_KEYS, where, errors)
                if not isinstance(item.get("id", ""), str):
                    errors.append(f"{where}.id must be a string")
                labels = item.get("labels", [])
                if not (isinstance(labels, list) and all(isinstance(x, str) for x in labels)):
                    errors.append(f"{where}.labels must be a list of strings")
                if "score" in item and not _is_num(item["score"]):
                    errors.append(f"{where}.score must be a number")
                if "rank" in item and not _is_count(item["rank"]):
                    errors.append(f"{where}.rank must be a non-negative integer")
    return errors


def _ordered(obj: dict, keys: tuple[str, ...]) -> dict:
    """The object with its keys in the ENGINE's construction order (optional keys
    — signals.coherence — simply absent). Validation already refused unknowns."""
    return {k: obj[k] for k in keys if k in obj}


def canonicalize(kind: str, rec: dict) -> dict:
    """Rebuild the exact object the engine hashed (receipt WITHOUT `hash`), key
    order restored from the pinned shapes — trust the schema, not the wire."""
    out = _ordered(rec, _TOP_KEYS[kind])
    out["snapshot"] = _ordered(rec["snapshot"], _SNAPSHOT_KEYS)
    if kind == "enrich":
        out["recommendations"] = [
            {**_ordered(r, _RECOMMENDATION_KEYS), "signals": _ordered(r["signals"], _SIGNAL_KEYS)}
            for r in rec["recommendations"]]
    else:
        out["suggestions"] = [_ordered(s, _SUGGESTION_KEYS) for s in rec["suggestions"]]
    return out


def sealed_hash(kind: str, receipt: dict) -> str:
    """Recompute the engine's sealed sha256 byte-exactly: canonical key order,
    V8 serialization, hash field excluded."""
    rec = canonicalize(kind, {k: v for k, v in receipt.items() if k != "hash"})
    return "sha256:" + hashlib.sha256(js_stringify(rec).encode()).hexdigest()


# ── the ONE verify walk ──
_WALK = ("gateway-signature", "engine-seal-hash", "snapshot-seq-binding")


def _receipt_body_hash_ok(r: Any) -> bool:
    body = {k: getattr(r, k) for k in (
        "project", "kind", "backend", "runtime", "inputs_sha", "outputs_sha",
        "status", "actor", "epistemic_status", "prev", "ts")}
    return receipts.sha(body) == r.id


def verify_walk(project: str, receipt_id: str) -> dict[str, Any]:
    """Walk an engine-seal receipt end-to-end: gateway signature → engine sealed
    hash recomputation → snapshot.seq binding. Returns {valid, receipt_id,
    project, steps:[{step, status: ok|fail|skipped, detail}]}; the walk stops at
    the first failure so tampering is attributed to the step that owns it."""
    steps: list[dict[str, Any]] = []

    def fail(step: str, detail: str) -> dict[str, Any]:
        steps.append({"step": step, "status": "fail", "detail": detail})
        for later in _WALK[len(steps):]:
            steps.append({"step": later, "status": "skipped", "detail": "prior step failed"})
        return {"valid": False, "receipt_id": receipt_id, "project": project, "steps": steps}

    def ok(step: str, detail: str | None = None) -> None:
        steps.append({"step": step, "status": "ok", "detail": detail})

    # 1 — gateway-signature: on the chain, id-hash intact, Ed25519 verifies.
    r = next((x for x in receipts.chain(project) if x.id == receipt_id), None)
    if r is None:
        return fail("gateway-signature", f"no receipt {receipt_id} in project {project}")
    if r.kind != "engine-seal":
        return fail("gateway-signature", f"receipt kind {r.kind!r} is not engine-seal")
    if not _receipt_body_hash_ok(r):
        return fail("gateway-signature", "receipt id-hash does not recompute (chain tampered)")
    if r.signature is None:
        return fail("gateway-signature",
                    "receipt is unsigned (no GATEWAY_SIGNING_KEY at seal time) — spine authenticity unprovable")
    if r.statement is None or not signing.verify_signature(r.statement, r.signature, r.public_key):
        return fail("gateway-signature", "gateway Ed25519 signature does not verify over the in-toto statement")
    ok("gateway-signature", "chained + Ed25519 over in-toto statement verified")

    # 2 — engine-seal-hash: the stored engine receipt's sealed sha256 recomputes.
    digests = artifacts.for_receipt(receipt_id)
    blob = next((b for b in (artifacts.get(d) for d in digests)
                 if isinstance(b, dict) and isinstance(b.get("data"), dict)
                 and "engine_receipt" in b["data"]), None)
    if blob is None:
        return fail("engine-seal-hash", "stored engine receipt not found in the artifact store")
    ekind = blob["data"].get("kind")
    er = blob["data"]["engine_receipt"]
    errors = validate(ekind, er)
    if errors:
        return fail("engine-seal-hash", f"stored engine receipt shape invalid: {'; '.join(errors)}")
    try:
        recomputed = sealed_hash(ekind, er)
    except EngineReceiptError as e:
        return fail("engine-seal-hash", f"engine receipt not canonicalizable: {e}")
    if recomputed != er["hash"]:
        return fail("engine-seal-hash",
                    f"engine sealed hash does not recompute: sealed {er['hash']}, recomputed {recomputed}")
    ok("engine-seal-hash", f"sealed sha256 recomputed byte-exactly ({recomputed})")

    # 3 — snapshot-seq-binding: the receipt's snapshot.seq equals the seq bound at
    # seal time, AND the SIGNED outputs_sha still covers the stored envelope. This
    # is what catches tamper-AND-reseal: a self-consistently re-hashed engine
    # receipt passes step 2, but it cannot move the signed binding. The seq
    # comparison runs first so a seq divergence is named as such; the outputs_sha
    # pin then closes the remaining move (rewriting the binding copy itself).
    bound = blob["data"].get("snapshot")
    claimed = er["snapshot"]
    if not (isinstance(bound, dict) and _is_count(bound.get("seq")) and _is_count(claimed.get("seq"))):
        return fail("snapshot-seq-binding", "snapshot.seq missing or not a non-negative integer")
    if bound["seq"] != claimed["seq"]:
        return fail("snapshot-seq-binding",
                    f"engine receipt snapshot.seq {claimed['seq']} does not match the sealed binding seq {bound['seq']}")
    stored_outputs = [artifacts.get(d) for d in digests]
    if receipts.sha(stored_outputs) != r.outputs_sha:
        return fail("snapshot-seq-binding",
                    "stored envelope does not match the signed outputs_sha (binding broken)")
    ok("snapshot-seq-binding", f"graph-state binding intact (seq {bound['seq']})")

    return {"valid": True, "receipt_id": receipt_id, "project": project, "steps": steps}
