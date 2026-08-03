#!/usr/bin/env python3
"""Enforce FIPS algorithm conformance inside the declared crypto boundary.

The federal tier declares `require_fips_validated_crypto: true`
(apps/cloudshell-fog/deployment-inventory.federal*.yaml) — and, before this check,
NOTHING read that flag: a FIPS requirement enforced by no code (a control that cannot
fail). This turns it into a real gate:

  1. ALGORITHM conformance — no banned (non-FIPS) algorithm CALL may appear in the
     paths under `scope` of security/fips-boundary.yaml (BLAKE2/BLAKE3/MD5/SHA-1).
  2. DECLARED-FLAG enforcement — if ANY deployment declares
     `require_fips_validated_crypto: true`, then security/fips-boundary.yaml must
     exist with a non-empty scope AND this checker must be wired into the required
     CI gate. So the flag can never again be true while enforced by nothing, and the
     check cannot be quietly deleted while the flag stays true (self-validating —
     a scanner must include itself, feedback_self_validating_checker).

Module CMVP validation (OpenSSL FIPS provider, Go BoringCrypto, Rust ring->aws-lc-rs)
is a separate dimension tracked as Build 2; it is reported, not enforced here.

Runs in the validate-target-diagnostics gate (`make fips-conformance-check`) and is
proven able to go red by tools/tests/test_check_fips_conformance.py.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]
BOUNDARY = "security/fips-boundary.yaml"
CI_GATE = ".github/workflows/validate-target-diagnostics.yml"
CHECK_TARGET = "fips-conformance-check"

_SOURCE_SUFFIXES = {".py", ".ts", ".js", ".mjs", ".go", ".rs"}


def load_boundary(root: Path) -> dict[str, Any] | None:
    """The boundary mapping, or None when the file is absent — main() then treats a
    missing boundary as a violation only if a deployment actually requires FIPS
    (fail-closed there, no-op otherwise). Malformed YAML is always fail-closed."""
    path = root / BOUNDARY
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return None
    try:
        data = yaml.safe_load(text)
    except yaml.YAMLError as e:
        raise SystemExit(f"fips-conformance-check: FAIL — {BOUNDARY} is not valid YAML ({type(e).__name__})")
    if not isinstance(data, dict):
        raise SystemExit(f"fips-conformance-check: FAIL — {BOUNDARY} is not a mapping")
    return data


def _iter_source_files(root: Path, scope_entry: str):
    p = root / scope_entry
    if p.is_file():
        yield p
    elif p.is_dir():
        for f in sorted(p.rglob("*")):
            if f.suffix in _SOURCE_SUFFIXES and "/node_modules/" not in str(f):
                yield f


def scan_scope(root: Path, boundary: dict[str, Any]) -> list[str]:
    scope = boundary.get("scope") or []
    banned = boundary.get("banned_algorithms") or []
    allow = {(a.get("path"), a.get("id")) for a in (boundary.get("allowlist") or [])}
    compiled = [(b["id"], re.compile(b["pattern"]), b.get("why", "")) for b in banned]
    out: list[str] = []
    for entry in scope:
        for f in _iter_source_files(root, entry):
            rel = str(f.relative_to(root))
            try:
                lines = f.read_text(encoding="utf-8").splitlines()
            except (UnicodeDecodeError, OSError):
                out.append(f"{rel}: unreadable file inside the FIPS boundary — cannot certify")
                continue
            for n, line in enumerate(lines, 1):
                # Drop inline AND full-line comments — a banned-algorithm name mentioned
                # in a comment (e.g. "# was hashlib.sha1(...)") is not a call.
                code = line.split("#", 1)[0].split("//", 1)[0]
                if not code.strip():
                    continue
                for bid, rx, why in compiled:
                    if rx.search(code) and (rel, bid) not in allow:
                        out.append(f"{rel}:{n}: non-FIPS algorithm '{bid}' in the FIPS boundary — {why}")
    return out


def _ci_wires_check(root: Path) -> bool:
    try:
        return CHECK_TARGET in (root / CI_GATE).read_text(encoding="utf-8")
    except OSError:
        return False


def _key_is_true(obj: Any, key: str) -> bool:
    """Recursively: does `key` appear anywhere with the boolean value true? (Parsing
    the YAML and checking the real key beats a raw-text regex, which would match the
    key inside a comment or a string.)"""
    if isinstance(obj, dict):
        if obj.get(key) is True:
            return True
        return any(_key_is_true(v, key) for v in obj.values())
    if isinstance(obj, list):
        return any(_key_is_true(v, key) for v in obj)
    return False


def deployments_requiring_fips(root: Path) -> list[str]:
    out: list[str] = []
    for p in sorted(root.rglob("deployment-inventory*.y*ml")):
        try:
            data = yaml.safe_load(p.read_text(encoding="utf-8"))
        except (OSError, yaml.YAMLError):
            continue
        if _key_is_true(data, "require_fips_validated_crypto"):
            out.append(str(p.relative_to(root)))
    return out


def check_flag_enforced(root: Path, boundary: dict[str, Any]) -> list[str]:
    requiring = deployments_requiring_fips(root)
    if not requiring:
        return []
    out: list[str] = []
    if not (boundary.get("scope") or []):
        out.append(
            f"{', '.join(requiring)} declare require_fips_validated_crypto: true but "
            f"{BOUNDARY} has an empty scope — the flag would enforce nothing"
        )
    if not _ci_wires_check(root):
        out.append(
            f"{', '.join(requiring)} require FIPS but '{CHECK_TARGET}' is not wired into "
            f"{CI_GATE} — a FIPS flag enforced by no gate is a control that cannot fail"
        )
    return out


def _find_value(obj: Any, key: str) -> Any:
    """The first value found for `key` anywhere in a nested mapping/list, or None."""
    if isinstance(obj, dict):
        if key in obj:
            return obj[key]
        for v in obj.values():
            r = _find_value(v, key)
            if r is not None:
                return r
    elif isinstance(obj, list):
        for v in obj:
            r = _find_value(v, key)
            if r is not None:
                return r
    return None


def check_module_warrant(root: Path, boundary: dict[str, Any]) -> list[str]:
    """Build 2 — module CMVP warrant. A deployment with require_fips_validated_crypto: true must
    NAME its FIPS-validated crypto module per runtime (fips_crypto_modules), chosen from the
    boundary's `fips_modules` allowlist. An approved algorithm (Build 1) on an unvalidated module
    is not FIPS; a flag with no named validated module is a claim without a warrant. Placeholders
    (e.g. REPLACE_ME) are not on the allowlist and therefore fail."""
    allow = boundary.get("fips_modules") or {}
    out: list[str] = []
    for p in sorted(root.rglob("deployment-inventory*.y*ml")):
        try:
            data = yaml.safe_load(p.read_text(encoding="utf-8"))
        except (OSError, yaml.YAMLError):
            continue
        if not _key_is_true(data, "require_fips_validated_crypto"):
            continue
        rel = str(p.relative_to(root))
        modules = _find_value(data, "fips_crypto_modules")
        if not isinstance(modules, dict) or not modules:
            out.append(
                f"{rel}: require_fips_validated_crypto: true but names no fips_crypto_modules — "
                f"a FIPS flag without a named validated module is a claim without a warrant"
            )
            continue
        for runtime, chosen in modules.items():
            allowed = allow.get(runtime)
            if allowed is None:
                out.append(f"{rel}: fips_crypto_modules names runtime '{runtime}' with no FIPS-validated allowlist in {BOUNDARY}")
            elif chosen not in allowed:
                out.append(f"{rel}: fips_crypto_modules.{runtime}={chosen!r} is not a FIPS-validated module (allowed: {allowed})")
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Enforce FIPS algorithm conformance in the crypto boundary")
    ap.add_argument("--root", default=str(ROOT), type=Path)
    args = ap.parse_args(argv)
    root = Path(args.root)
    boundary = load_boundary(root)
    if boundary is None:
        # No boundary file. Fail-closed only if something actually requires FIPS.
        requiring = deployments_requiring_fips(root)
        if requiring:
            print(f"fips-conformance-check: FAIL — {BOUNDARY} is missing but these require FIPS: {', '.join(requiring)}")
            return 1
        print("fips-conformance-check: OK — no FIPS boundary declared and nothing requires one.")
        return 0
    violations = check_flag_enforced(root, boundary) + scan_scope(root, boundary) + check_module_warrant(root, boundary)
    if violations:
        print("fips-conformance-check: FAIL — FIPS boundary is not conformant:")
        for v in violations:
            print(f"  - {v}")
        return 1
    print("fips-conformance-check: OK — no non-FIPS algorithms in the boundary; the federal flag is "
          "enforced and its FIPS-validated crypto modules are named (Build 1 algorithm + Build 2 module warrant).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
