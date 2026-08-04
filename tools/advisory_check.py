#!/usr/bin/env python3
"""Don't re-vendor blind: gate a package@version on open vulnerability data (OSV) before vendoring.

The re-vendor loop pins digests and proves the marker, but had no notion of whether the version it
moves TO is known-vulnerable or malicious — the competitive research called this out (we detect
staleness, not malice). This adds a fail-closed advisory gate over OSV.dev — the open, aggregated
vulnerability database (GitHub Advisory, PyPI, npm, Go, crates.io, ...). Sovereign by design: we
CONSUME the open data over a plain query, we do not depend on a SaaS scanner.

Fail-closed: if a version has known advisories it is BLOCKED; and if the advisory service cannot be
reached at all, it is also BLOCKED — you do not re-vendor into the unknown. An explicit override
(--allow-unverified) exists for air-gapped runs, and is recorded as such.
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.request
from pathlib import Path

OSV_QUERY_URL = "https://api.osv.dev/v1/query"


def _http_post(url: str, body: dict) -> dict:
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _severity(vuln: dict) -> str:
    # OSV puts a CVSS vector under severity[]; the human label often rides in database_specific.
    ds = vuln.get("database_specific") or {}
    return ds.get("severity") or (vuln.get("severity") or [{}])[0].get("type") or "unknown"


def assess(name: str, ecosystem: str, version: str, *, http_post=None) -> dict:
    """Query OSV for name@version in ecosystem; return advisories + a fail-closed recommendation."""
    http_post = http_post or _http_post  # resolved at call time so the default is patchable
    result = {"package": name, "ecosystem": ecosystem, "version": version}
    try:
        resp = http_post(OSV_QUERY_URL, {"version": version, "package": {"name": name, "ecosystem": ecosystem}})
    except Exception as exc:  # network / parse / timeout — cannot verify safety
        result.update({"checked": False, "recommendation": "block",
                       "reason": f"advisory service unreachable ({type(exc).__name__}); fail-closed",
                       "advisories": []})
        return result

    vulns = resp.get("vulns") or []
    advisories = [{"id": v.get("id"), "summary": (v.get("summary") or "")[:200], "severity": _severity(v),
                   "aliases": v.get("aliases", [])} for v in vulns]
    vulnerable = bool(advisories)
    result.update({
        "checked": True,
        "vulnerable": vulnerable,
        "advisories": advisories,
        "recommendation": "block" if vulnerable else "allow",
        "reason": (f"{len(advisories)} known advisor{'y' if len(advisories) == 1 else 'ies'} for "
                   f"{name}@{version}" if vulnerable else f"no known advisories for {name}@{version}"),
    })
    return result


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Fail-closed OSV advisory gate for a package@version.")
    ap.add_argument("--package", required=True)
    ap.add_argument("--ecosystem", required=True, help="OSV ecosystem, e.g. npm, PyPI, Go, crates.io")
    ap.add_argument("--version", required=True)
    ap.add_argument("--allow-unverified", action="store_true",
                    help="permit promotion when the advisory service is unreachable (air-gapped); recorded as such")
    ap.add_argument("--out", type=Path, help="write the assessment JSON here")
    args = ap.parse_args(argv)

    r = assess(args.package, args.ecosystem, args.version)
    if r["recommendation"] == "block" and not r.get("checked") and args.allow_unverified:
        r["recommendation"] = "allow-unverified"
        r["reason"] += " — overridden by --allow-unverified"
    text = json.dumps(r, indent=2, sort_keys=True)
    (args.out.write_text(text + "\n") if args.out else print(text))
    if r["recommendation"] == "block":
        print(f"BLOCK: {r['reason']}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
