"""Enrol the gateway's content-addressed artifacts into L5 governance.

The lifecycle-warden was live and sealing receipts, but `GET /v1/objects` returned
`[]` -- it governed an empty set (issue #1048). The `POST /v1/objects` enrolment
endpoint had no caller outside its own tests. This module is that caller.

It reads the gateway's own artifact store (the 3,000+ content-addressed blobs that
back materialize/graph receipts), classifies each by the EPISTEMIC CLASS of the
receipt that produced it, and enrols it under the Sovereign Retention Doctrine
(contracts/governance/retention-policy.v0.json):

    derived   -> ttl 14d, hard-delete 90d   (reproducible cache; the receipt is the asset)
    observed  -> ttl 30d, hard-delete 365d
    asserted  -> legal hold; manual delete only
    (unknown) -> observed (bounded, sensitive) -- doubt keeps longer, never deletes faster

Two-lever, like the warden's own enforcement: DRY-RUN by default (prints exactly
what WOULD be enrolled); `apply=True` performs it. Enrolment is idempotent -- the
warden rejects a re-ingest of an already-governed id (409), which we count as
'already governed', not an error, so re-running never double-enrols or errors.

Enrolment does NOT delete anything. With the warden in its default dry-run mode it
merely starts SCANNING real objects and sealing audited plans of what retention
would do -- the second lever (WARDEN_ENFORCE=on) remains a separate, deliberate act.
"""
from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from . import persistence

_POLICY_REL = Path("contracts") / "governance" / "retention-policy.v0.json"

DAY_MS = 86_400_000


def _find_policy() -> Path:
    """Locate the doctrine by walking up from this file until we find it. Robust
    to where the module is run from -- computing a fixed parents[N] at import time
    IndexErrors the moment the file is copied elsewhere (e.g. into a pod)."""
    here = Path(__file__).resolve()
    for base in (here, *here.parents):
        candidate = base / _POLICY_REL
        if candidate.exists():
            return candidate
    # Fall back to the in-repo location so load_policy() raises a clear
    # FileNotFoundError naming the expected path, not an IndexError.
    return here.parents[min(4, len(here.parents) - 1)] / _POLICY_REL

# Poster contract: (url, json_body) -> (http_status, response_dict). Injectable so
# tests never touch the network and never depend on a live warden.
Poster = Callable[[str, dict], "tuple[int, dict]"]


def load_policy(path: Path | None = None) -> dict:
    path = path or _find_policy()
    return json.loads(path.read_text(encoding="utf-8"))


def classify(epistemic_status: str | None, policy: dict) -> str:
    classes = policy["classes"]
    if epistemic_status in classes:
        return epistemic_status
    return policy["fallback"]["unknown_epistemic_status"]


@dataclass
class EnrolmentPlan:
    digest: str
    receipt_id: str
    epistemic_status: str | None
    klass: str
    body: dict


@dataclass
class EnrolmentSummary:
    planned: int = 0
    enrolled: int = 0
    already_governed: int = 0
    failed: int = 0
    by_class: dict = field(default_factory=dict)
    errors: list = field(default_factory=list)

    def as_dict(self) -> dict:
        return {"planned": self.planned, "enrolled": self.enrolled,
                "already_governed": self.already_governed, "failed": self.failed,
                "by_class": self.by_class, "errors": self.errors[:20]}


def _blob_mime(blob) -> str:
    if isinstance(blob, dict) and isinstance(blob.get("mime"), str) and blob["mime"]:
        return blob["mime"]
    return "application/json"


def build_plan(policy: dict, *, now_ms: int | None = None,
               limit: int | None = None) -> list[EnrolmentPlan]:
    """Derive the enrolment requests from the gateway's real store. Pure: reads
    the store, touches nothing, contacts no network."""
    now = now_ms if now_ms is not None else int(time.time() * 1000)

    # receipt_id -> epistemic_status, from the receipts already on the chain.
    epistemic: dict[str, str | None] = {}
    for receipts in persistence.load_receipts().values():
        for r in receipts:
            epistemic[r.get("id")] = r.get("epistemic_status")

    plans: list[EnrolmentPlan] = []
    seen: set[str] = set()
    for receipt_id, digests in persistence.load_index().items():
        status = epistemic.get(receipt_id)
        klass = classify(status, policy)
        spec = policy["classes"][klass]
        for digest in digests:
            if digest in seen:
                continue  # one blob, one governed object, even if many receipts cite it
            seen.add(digest)
            blob = persistence.get_blob(digest)
            if blob is None:
                continue
            content = blob if isinstance(blob, str) else json.dumps(blob, sort_keys=True)
            body: dict = {
                "id": digest,
                "content": content,
                "mime": _blob_mime(blob),
                "residency": policy["universal_invariants"]["residency"],
                "vendorOptIn": policy["universal_invariants"]["vendor_opt_in"],
            }
            if spec["disposition"] == "auto":
                body["ttlAt"] = now + spec["ttl_days"] * DAY_MS
                body["retentionDeleteAt"] = now + spec["retention_delete_days"] * DAY_MS
            if spec.get("sensitive_by_default"):
                body["sensitiveFields"] = ["payload"]
            plans.append(EnrolmentPlan(digest, receipt_id, status, klass, body))
            if limit is not None and len(plans) >= limit:
                return plans
    return plans


def _default_poster(warden_url: str, token: str | None) -> Poster:
    def post(path: str, body: dict) -> tuple[int, dict]:
        req = urllib.request.Request(
            warden_url.rstrip("/") + path,
            data=json.dumps(body).encode(),
            headers={"content-type": "application/json",
                     **({"authorization": f"Bearer {token}"} if token else {})},
            method="POST")
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                return resp.status, json.loads(resp.read() or b"{}")
        except urllib.error.HTTPError as e:
            try:
                return e.code, json.loads(e.read() or b"{}")
            except Exception:
                return e.code, {}
    return post


def enrol(policy: dict, poster: Poster, *, apply: bool = False,
          now_ms: int | None = None, limit: int | None = None) -> EnrolmentSummary:
    plans = build_plan(policy, now_ms=now_ms, limit=limit)
    s = EnrolmentSummary(planned=len(plans))
    for p in plans:
        s.by_class[p.klass] = s.by_class.get(p.klass, 0) + 1
        if not apply:
            continue
        try:
            status, resp = poster("/v1/objects", p.body)
        except Exception as e:  # network etc. -- one bad object must not abort the sweep
            s.failed += 1
            s.errors.append(f"{p.digest[:16]}: {type(e).__name__}: {e}")
            continue
        if status in (200, 201):
            s.enrolled += 1
        elif status == 409:  # warden: "object already governed" -- idempotent, expected on re-run
            s.already_governed += 1
        else:
            s.failed += 1
            s.errors.append(f"{p.digest[:16]}: HTTP {status} {resp.get('error', '')}")
    return s


def main(argv: list[str] | None = None) -> int:
    import argparse
    import os

    ap = argparse.ArgumentParser(description="Enrol gateway artifacts into L5 governance")
    ap.add_argument("--warden-url", default=os.getenv("COMPUTE_WARDEN_URL", "http://lifecycle-warden:8095"))
    ap.add_argument("--token", default=os.getenv("WARDEN_TOKEN") or None)
    ap.add_argument("--apply", action="store_true",
                    help="perform enrolment (default: dry-run plan only)")
    ap.add_argument("--limit", type=int, default=None, help="cap the number of objects")
    args = ap.parse_args(argv)

    if not persistence.enabled():
        print("GATEWAY_STORE_DIR unset -- no durable store to read. Nothing to enrol.")
        return 1

    policy = load_policy()
    poster = _default_poster(args.warden_url, args.token) if args.apply else (lambda *_: (0, {}))
    s = enrol(policy, poster, apply=args.apply, limit=args.limit)
    mode = "APPLIED" if args.apply else "DRY-RUN (pass --apply to enrol)"
    print(f"[{mode}] " + json.dumps(s.as_dict(), indent=2))
    return 1 if s.failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
