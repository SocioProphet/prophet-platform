"""oais-deposition — the OAIS preservation/curation vault contract check.

Enforces the OAIS information-package chain for an accepted benchmark
submission (#1263 feature 9, follow-up #1272):

    SIP (submitted bytes) -> AIP (preserved: fixity + preservation metadata
    + harvestable OAI-PMH record) -> DIP (disseminated: fixity == AIP fixity).

Fixity is SHA-256 (FIPS 180-4 algorithm via stdlib ``hashlib``; NOT a claim of
a FIPS 140-validated module). The AIP is DOI-ready: its fixity digest is the
content address a DataCite version DOI binds to (#1267).

TEETH — a deposition is ACCEPTED iff:
  1. the AIP fixity is SHA-256 with a 64-hex digest (missing/other -> REJECTED);
  2. a PATH-shaped SIP content_locator MUST resolve and the AIP fixity digest
     MATCHES the SHA-256 of those bytes (tampered content -> REJECTED, and a path
     locator that does not resolve -> REJECTED — fixity is verified, not merely
     present; an opaque "(inline:…)" SIP has no in-tree bytes to re-hash and is
     trusted on its ingest-time fixity);
  3. the AIP carries the required preservation-metadata keys (missing -> REJECTED);
  4. the AIP carries an OAI-PMH-shaped record (missing/wrong prefix -> REJECTED);
  5. if a DIP is present, its fixity MATCHES the AIP fixity exactly
     (mismatch -> REJECTED — an unfaithful dissemination is not archival).

Usage:
    python tools/oais_deposition.py verify <deposition.json> [--root DIR]
    python tools/oais_deposition.py ingest <content-file> --aip-id ID [--out FILE]
    # verify: exit 0 = ACCEPTED, 1 = REJECTED, 2 = malformed
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]

FIXITY_ALGORITHM = "SHA-256"  # FIPS 180-4 algorithm (hashlib.sha256); NOT a FIPS 140 module.
REQUIRED_PRESERVATION_KEYS = (
    "preservation_level", "retention_tier", "fixity_check_schedule", "format", "created_at",
)


def sha256_hex(data: bytes) -> str:
    """SHA-256 content address (FIPS 180-4 algorithm via stdlib hashlib)."""
    return hashlib.sha256(data).hexdigest()


@dataclass
class DepositionVerdict:
    deposition_id: str
    accepted: bool
    reasons: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {"deposition_id": self.deposition_id, "accepted": self.accepted, "reasons": self.reasons}


def _check_fixity_shape(fixity: dict | None, where: str, reasons: list[str]) -> bool:
    if not fixity:
        reasons.append(f"{where}: no fixity (an unfixed package is not archival)")
        return False
    if fixity.get("algorithm") != FIXITY_ALGORITHM:
        reasons.append(f"{where}: fixity algorithm {fixity.get('algorithm')!r} != {FIXITY_ALGORITHM!r}")
        return False
    digest = fixity.get("digest") or ""
    if len(digest) != 64 or any(c not in "0123456789abcdef" for c in digest):
        reasons.append(f"{where}: fixity digest is not 64-hex SHA-256")
        return False
    return True


def verify_deposition(dep: dict, root: Path | None = None) -> DepositionVerdict:
    """Verify the OAIS chain. See module docstring for the accept conditions."""
    root = root or ROOT
    reasons: list[str] = []
    v = DepositionVerdict(deposition_id=dep.get("deposition_id", "?"), accepted=False)

    aip = dep.get("aip") or {}
    aip_fixity = aip.get("fixity")

    # 1. AIP fixity shape
    aip_fixity_ok = _check_fixity_shape(aip_fixity, "AIP", reasons)

    # 2. fixity actually verifies the SIP bytes. A PATH-shaped content_locator is an
    #    in-tree object reference and MUST resolve: an asserted-but-absent object
    #    leaves the fixity unverifiable and fails closed ("no bytes" != "faithful
    #    fixity"). An opaque/inline SIP (the "(inline:Nb)" sentinel from ingest_sip,
    #    or any parenthesized handle) carries no in-tree path to re-hash — its fixity
    #    was computed from the bytes at ingest — so the byte re-check is skipped.
    sip = dep.get("sip") or {}
    locator = sip.get("content_locator")
    if aip_fixity_ok and locator and not locator.startswith("("):
        candidate = (root / locator) if not Path(locator).is_absolute() else Path(locator)
        if candidate.is_file():
            actual = sha256_hex(candidate.read_bytes())
            if actual != aip_fixity["digest"]:
                reasons.append(
                    f"AIP: fixity digest does not match SIP content bytes "
                    f"(declared {aip_fixity['digest'][:12]}..., actual {actual[:12]}...) — content tampered or wrong")
        else:
            reasons.append(
                f"AIP: SIP content_locator {locator!r} does not resolve to a file "
                "— fixity is unverifiable (fail-closed)")

    # 3. preservation metadata
    pm = aip.get("preservation_metadata") or {}
    missing_pm = [k for k in REQUIRED_PRESERVATION_KEYS if not pm.get(k)]
    if missing_pm:
        reasons.append(f"AIP: preservation_metadata missing required keys {missing_pm}")

    # 4. OAI-PMH record shape
    rec = aip.get("oai_pmh_record") or {}
    if not rec:
        reasons.append("AIP: no oai_pmh_record (not harvestable)")
    else:
        if rec.get("metadata_prefix") != "oai_dc":
            reasons.append(f"AIP: oai_pmh_record.metadata_prefix {rec.get('metadata_prefix')!r} != 'oai_dc'")
        for k in ("identifier", "datestamp"):
            if not rec.get(k):
                reasons.append(f"AIP: oai_pmh_record missing {k}")
        dc = rec.get("dc") or {}
        for k in ("title", "identifier"):
            if not dc.get(k):
                reasons.append(f"AIP: oai_pmh_record.dc missing {k}")

    # 5. DIP fixity must match AIP fixity exactly
    dip = dep.get("dip")
    if dip:
        dip_fixity = dip.get("fixity")
        if _check_fixity_shape(dip_fixity, "DIP", reasons) and aip_fixity_ok:
            if dip_fixity["algorithm"] != aip_fixity["algorithm"] or dip_fixity["digest"] != aip_fixity["digest"]:
                reasons.append("DIP: fixity does not match the AIP fixity (unfaithful dissemination)")

    v.reasons = reasons
    v.accepted = not reasons
    return v


def ingest_sip(content: bytes, *, aip_id: str, title: str, media_type: str = "application/octet-stream",
               storage: str = "zot", retention_tier: str = "permanent",
               preservation_level: str = "full", fixity_check_schedule: str = "P30D",
               creators: list[str] | None = None, content_locator: str = "") -> dict:
    """Ingest raw SIP bytes -> a schema-valid, self-consistent AIP deposition.

    The AIP fixity is COMPUTED from the actual bytes, and both AIP and (mirror)
    DIP carry that digest — so an accepted submission produces a citable AIP
    (the fixity digest is the DataCite content address, #1267).
    """
    digest = sha256_hex(content)
    now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    fixity = {"algorithm": FIXITY_ALGORITHM, "digest": digest}
    return {
        "deposition_id": f"dep-{aip_id}",
        "sip": {
            "content_locator": content_locator or f"(inline:{len(content)}b)",
            "media_type": media_type, "size_bytes": len(content), "submitted_at": now,
        },
        "aip": {
            "aip_id": aip_id, "storage": storage, "fixity": fixity,
            "preservation_metadata": {
                "preservation_level": preservation_level, "retention_tier": retention_tier,
                "fixity_check_schedule": fixity_check_schedule, "format": media_type,
                "created_at": now, "provenance": "tools/oais_deposition.py ingest",
            },
            "oai_pmh_record": {
                "identifier": f"oai:commons.socioprophet.ai:{aip_id}",
                "datestamp": now, "metadata_prefix": "oai_dc",
                "dc": {
                    "title": title, "creator": creators or ["SocioProphet Knowledge Commons"],
                    "date": now, "identifier": f"sha256:{digest}", "format": media_type,
                },
            },
        },
        "dip": {
            "dip_id": f"dip-{aip_id}", "fixity": fixity,
            "access_url": f"https://commons.socioprophet.ai/oai?verb=GetRecord&identifier=oai:commons.socioprophet.ai:{aip_id}",
            "disseminated_at": now,
        },
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="OAIS preservation deposition — verify / ingest")
    sub = ap.add_subparsers(dest="cmd", required=True)

    pv = sub.add_parser("verify", help="verify an OAIS deposition (fixity + preservation + OAI-PMH + DIP match)")
    pv.add_argument("deposition", type=Path)
    pv.add_argument("--root", type=Path, default=ROOT, help="root for resolving relative content_locator")

    pi = sub.add_parser("ingest", help="ingest content bytes into a schema-valid AIP deposition")
    pi.add_argument("content", type=Path)
    pi.add_argument("--aip-id", required=True)
    pi.add_argument("--title", default="benchmark deposition")
    pi.add_argument("--media-type", default="application/octet-stream")
    pi.add_argument("--out", type=Path, default=None)

    args = ap.parse_args(argv)

    if args.cmd == "ingest":
        try:
            content = args.content.read_bytes()
        except OSError as exc:
            print(f"cannot read content: {exc}", file=sys.stderr)
            return 2
        dep = ingest_sip(content, aip_id=args.aip_id, title=args.title, media_type=args.media_type,
                         content_locator=str(args.content))
        out = json.dumps(dep, indent=2)
        if args.out:
            args.out.write_text(out)
        else:
            print(out)
        return 0

    # verify
    try:
        dep = json.loads(args.deposition.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        print(f"malformed deposition: {exc}", file=sys.stderr)
        return 2
    verdict = verify_deposition(dep, root=args.root)
    print(json.dumps(verdict.to_dict(), indent=2))
    status = "ACCEPTED" if verdict.accepted else "REJECTED"
    tail = "" if verdict.accepted else " — " + "; ".join(verdict.reasons)
    print(f"\n{status}: {verdict.deposition_id}{tail}", file=sys.stderr)
    return 0 if verdict.accepted else 1


if __name__ == "__main__":
    raise SystemExit(main())
