"""Read-path masking Policy Decision Point (PDP).

Mounts the masking moat on the one governed door: for read-effect compute kinds
(graph-query / graph-stats), the dispatched outputs are passed through a field-level
masking policy BEFORE they are sealed — so the Ed25519 receipt attests exactly what
the caller received, and the masking decision itself is emitted as a sealed output
(the property WKC-style dynamic masking does not produce).

Design:
  * OFF by default. No policy configured (GATEWAY_MASKING_POLICY unset) → outputs are
    returned unchanged. Adding this filter to a live gateway is therefore a no-op until
    a policy exists — safe rollout on a busy surface.
  * fail-closed WHEN configured: a forbidden identity mixture (e.g. no_health_adtech)
    withholds the records and returns only the deny decision.
  * the decision conforms to `identity-prime.masking-decision.v1` (the sociosphere
    contract) and is appended as a ComputeOutput so it is sealed + returned + attested.

This is the serving mount. The canonical desensitisation primitives live in the exodus
reference engine (exodus_tokenize / exodus_mask); the field schemes here are the compact
read-masking subset. Productionization (Chameleon algebraic re-keying, NIST FF1 FPE,
HSM-held keys) swaps the primitives behind `_transform` with no change to this PDP or
its callers.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import uuid
from datetime import datetime, timezone
from typing import Any

from .contract import ComputeOutput

READ_KINDS = frozenset({"graph-query", "graph-stats"})

_B32 = "0123456789ABCDEFGHIJKLMNOPQRSTUV"


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _key() -> bytes:
    # Dev default is clearly labelled; production supplies an HSM-backed key.
    return os.getenv("GATEWAY_MASKING_KEY", "reference-masking-key-not-for-prod").encode("utf-8")


def _read_json_source(raw: str | None) -> Any:
    """Parse a config value that is either inline JSON or a path to a JSON file.
    Returns the parsed value, or None on any error (fail closed to OFF: a policy that
    cannot be read must never silently expose raw data, but must not take down reads —
    it disables itself, and the absence is observable upstream)."""
    if not raw:
        return None
    try:
        if raw.strip().startswith(("{", "[")):
            return json.loads(raw)
        with open(raw, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return None


def load_policy(project: str = "default", entitlement: str | None = None) -> dict[str, Any] | None:
    """Resolve the masking policy for this request, or None (masking off).

    Per-tenant first: GATEWAY_MASKING_POLICIES is a table {selector: policy} (inline
    JSON or a file path), resolved by project, then entitlement, then a "*"/"default"
    fallback — so different tenants/entitlements carry different masking rules through
    the one gateway. Legacy single-policy GATEWAY_MASKING_POLICY still works as the
    global fallback when no table entry matches."""
    table = _read_json_source(os.getenv("GATEWAY_MASKING_POLICIES"))
    if isinstance(table, dict):
        for sel in (project, entitlement or "", "*", "default"):
            pol = table.get(sel)
            if isinstance(pol, dict):
                return pol
    single = _read_json_source(os.getenv("GATEWAY_MASKING_POLICY"))
    return single if isinstance(single, dict) else None


# ── field transforms (compact read-masking subset of tokenization-profile.v1) ──
def _transform(value: Any, scheme: str) -> Any:
    s = "" if value is None else str(value)
    if scheme == "redact":
        return "[REDACTED]"
    if scheme == "suppress":
        return None
    if scheme == "generalize":
        return (s[:1] + "*" * max(0, len(s) - 1)) if s else s
    if scheme == "one_way_hash":
        return "sha256:" + hashlib.sha256(s.encode("utf-8")).hexdigest()[:32]
    if scheme in ("hmac_pseudonym", "chameleon_token"):
        raw = hmac.new(_key(), s.encode("utf-8"), hashlib.sha256).digest()
        n = int.from_bytes(raw, "big")
        out = []
        for _ in range(16):
            out.append(_B32[n & 31]); n >>= 5
        return "tok_" + "".join(out)
    # unknown scheme → fail closed (redact) rather than pass raw through
    return "[REDACTED]"


def _mask_record(rec: dict[str, Any], mask_fields: dict[str, str]) -> list[str]:
    """Mask configured fields in-place at the record top level and in a nested
    `properties` dict (GraphNode shape). Returns the field paths actually masked."""
    touched: list[str] = []
    for field, scheme in mask_fields.items():
        if field in rec and rec[field] is not None:
            rec[field] = _transform(rec[field], scheme)
            touched.append(field)
        props = rec.get("properties")
        if isinstance(props, dict) and field in props and props[field] is not None:
            props[field] = _transform(props[field], scheme)
            touched.append(f"properties.{field}")
    return touched


def _record_topics(rec: dict[str, Any], fields: list[str]) -> set[str]:
    topics: set[str] = set()
    for f in fields:
        v = rec.get(f)
        if isinstance(v, str):
            topics.add(v)
        elif isinstance(v, list):
            topics.update(str(x) for x in v)
        props = rec.get("properties")
        if isinstance(props, dict) and isinstance(props.get(f), str):
            topics.add(props[f])
    return topics


def _requesting_topics(policy: dict[str, Any], actor: str, entitlement: str | None) -> set[str]:
    ident = f"{actor}|{entitlement or ''}".lower()
    return {t for sub, t in (policy.get("requesting_realm_topics") or {}).items() if sub.lower() in ident}


def _decision(policy: dict[str, Any], project: str, actor: str, verdict: str,
              *, reason_codes: list[str], forbidden: list[str] | None,
              applied: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "schema_version": "identity-prime.masking-decision.v1",
        "decision_id": "md_" + uuid.uuid4().hex[:16],
        "subject_ref": f"proj:{project}",
        "requested_op": "read",
        "audience": {"role": actor},
        "verdict": verdict,
        "reason_codes": reason_codes,
        "forbidden_mixture": forbidden,
        "applied_transforms": applied,
        "side_channel_mitigations": ["policy", "unlinkable_identifiers"],
        "policy_version": policy.get("policy_version", "unset"),
        "decided_by": "compute-gateway.masking",
        "created_at": _now_iso(),
    }


_MAX_WALK_DEPTH = 6


def _iter_records(output: ComputeOutput) -> list[dict[str, Any]]:
    """Every dict anywhere in the payload is a candidate record.

    This used to read `data["nodes"]` and nothing else, which meant a result shaped as
    `rows` / `table` / `edges` was returned UNMASKED while the policy reported itself
    active — and `rows` is a shape this estate actually emits, so it was a live hole, not a
    theoretical one. An allowlist of container keys just moves the hole to the next shape
    somebody adds.

    Walking every nested dict is safe because _mask_record only rewrites keys that appear
    in the policy's mask_fields: a dict with no configured field is returned untouched. So
    the failure mode of over-walking is "nothing happens", while the failure mode of
    under-walking is "personal data is served". Fail toward the former.
    """
    if not output.data:
        return []
    seen: list[dict[str, Any]] = []
    stack: list[tuple[Any, int]] = [(output.data, 0)]
    while stack:
        node, depth = stack.pop()
        if depth > _MAX_WALK_DEPTH:
            continue
        if isinstance(node, dict):
            seen.append(node)
            for v in node.values():
                if isinstance(v, (dict, list)):
                    stack.append((v, depth + 1))
        elif isinstance(node, list):
            for v in node:
                if isinstance(v, (dict, list)):
                    stack.append((v, depth + 1))
    # output.data itself is a container, not a record — masking its top level would rewrite
    # envelope keys that happen to collide with a field name.
    return seen[1:] if seen and seen[0] is output.data else seen


def apply(outputs: list[ComputeOutput], *, kind: str, project: str, actor: str,
          entitlement: str | None) -> list[ComputeOutput]:
    """Apply the read-path masking policy to `outputs`. No policy → unchanged.
    On a forbidden mixture the data outputs are withheld and only the deny decision
    is returned. Otherwise configured fields are masked and a masking-decision output
    is appended (so it is sealed + attested alongside the data)."""
    policy = load_policy(project, entitlement)
    if not policy:
        return outputs

    mask_fields: dict[str, str] = policy.get("mask_fields") or {}
    forbidden_sets = [set(m) for m in (policy.get("forbidden_mixtures") or [])]
    topic_fields = policy.get("record_topic_fields") or []

    # forbidden-mixture veto: requesting realm topics ∪ all record topics
    active = _requesting_topics(policy, actor, entitlement)
    if forbidden_sets and topic_fields:
        for out in outputs:
            for rec in _iter_records(out):
                active |= _record_topics(rec, topic_fields)
        for fset in forbidden_sets:
            if fset <= active:
                dec = _decision(policy, project, actor, "deny",
                                reason_codes=["FORBIDDEN_IDENTITY_MIXTURE"],
                                forbidden=sorted(fset), applied=[])
                return [ComputeOutput(type="masking-decision", data=dec)]

    if not mask_fields:
        return outputs  # policy present but no field rules → passthrough (still no deny)

    applied_summary: dict[str, str] = {}
    for out in outputs:
        for rec in _iter_records(out):
            for fp in _mask_record(rec, mask_fields):
                base = fp.split(".")[-1]
                applied_summary[fp] = mask_fields.get(base, "")
    applied = [{"field_path": fp, "scheme": sch} for fp, sch in sorted(applied_summary.items())]
    verdict = "allow_masked" if applied else "allow"
    dec = _decision(policy, project, actor, verdict,
                    reason_codes=["NO_FORBIDDEN_MIXTURE"], forbidden=None, applied=applied)
    return list(outputs) + [ComputeOutput(type="masking-decision", data=dec)]
