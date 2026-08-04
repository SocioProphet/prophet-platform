#!/usr/bin/env python3
"""Referential-integrity gate for prophet-platform's JSON Schemas.

The same declared-not-enforced defect the sourceos-spec ref-gate (SourceOS-Linux/sourceos-spec
#277) closes exists here: contracts/ + schemas/ hold ~288 real schemas with cross-file $refs, and
nothing checks that a $ref to a moved/renamed/typo'd target still resolves. A schema promising a
contract ("this field conforms to Other.json#/$defs/x") that points at a hole is a paper contract.

This is the sourceos-spec gate generalized to a MIXED tree: contracts/ and schemas/ also hold
data/examples, so — unlike the single-purpose sourceos-spec schemas/ dir — this only treats a file
as a schema when it declares `$schema` or `$id`; data/example JSON is skipped, not metaschema-
checked. $refs resolve path-relative (referring file's dir first), then by basename, then by $id.

For every schema it asserts: valid JSON Schema (Draft 2020-12 metaschema) + every $ref resolves to
a real schema AND a real pointer target. Self-excluding (lives in tools/, never scanned). Teeth
proven every run by an inline synthetic negative control that never touches the real tree.

  validate_schema_references.py                 # scan contracts/ + schemas/
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

try:
    from jsonschema import Draft202012Validator
    from jsonschema.exceptions import SchemaError
except ImportError:  # pragma: no cover
    sys.stderr.write("needs jsonschema (pip install --user jsonschema)\n")
    raise

ROOT = Path(__file__).resolve().parents[1]
SCAN_DIRS = ["contracts", "schemas"]


def _is_schema(doc) -> bool:
    """A JSON file is a schema (vs data/example) if it declares $schema or $id."""
    return isinstance(doc, dict) and ("$schema" in doc or "$id" in doc)


def iter_refs(node):
    if isinstance(node, dict):
        for k, v in node.items():
            if k == "$ref" and isinstance(v, str):
                yield v
            else:
                yield from iter_refs(v)
    elif isinstance(node, list):
        for it in node:
            yield from iter_refs(it)


def resolve_pointer(doc, fragment: str) -> bool:
    parts = [p.replace("~1", "/").replace("~0", "~")
             for p in fragment.lstrip("/").split("/") if p != ""]
    node = doc
    for part in parts:
        if isinstance(node, dict):
            if part not in node:
                return False
            node = node[part]
        elif isinstance(node, list):
            try:
                idx = int(part)
            except ValueError:
                return False
            if not (0 <= idx < len(node)):
                return False
            node = node[idx]
        else:
            return False
    return True


# Standard external meta-schemas: a $ref to these is legitimate and out of scope for LOCAL
# referential integrity (we neither can nor need to resolve them here). Any OTHER external URL
# is still flagged — it should be vendored, or it is a typo.
EXTERNAL_OK_HOSTS = ("json-schema.org",)


def resolve_ref(ref: str, *, from_path: Path, by_path, by_name, by_id) -> tuple[bool, str]:
    file_part, _, fragment = ref.partition("#")
    if file_part == "":
        target = by_path.get(from_path.resolve())
    elif file_part.startswith(("http://", "https://")) and any(h in file_part for h in EXTERNAL_OK_HOSTS):
        return True, ""   # standard external meta-schema — legitimately unresolvable locally
    else:
        # path-relative to the referring file first (most correct in a multi-dir tree)
        cand = (from_path.parent / file_part).resolve()
        target = by_path.get(cand) or by_name.get(Path(file_part).name) or by_id.get(file_part)
    if target is None:
        return False, f"$ref to missing schema: {ref!r}"
    if fragment.strip("/") == "":
        return True, ""
    return (True, "") if resolve_pointer(target, fragment) else (False, f"$ref pointer unresolved: {ref!r}")


def load_all(root: Path):
    by_path, by_name, by_id = {}, {}, {}
    for rel in SCAN_DIRS:
        for path in sorted((root / rel).rglob("*.json")) if (root / rel).is_dir() else []:
            try:
                doc = json.loads(path.read_text())
            except (json.JSONDecodeError, OSError):
                continue
            if not _is_schema(doc):
                continue
            rp = path.resolve()
            by_path[rp] = doc
            by_name.setdefault(path.name, doc)   # first wins on basename collision
            if isinstance(doc.get("$id"), str):
                by_id[doc["$id"]] = doc
    return by_path, by_name, by_id


def check_all(root: Path):
    by_path, by_name, by_id = load_all(root)
    findings, ref_count = [], 0
    for rp, doc in by_path.items():
        name = str(rp.relative_to(root)) if rp.is_relative_to(root) else rp.name
        try:
            Draft202012Validator.check_schema(doc)
        except SchemaError as e:
            findings.append((name, f"not a valid JSON Schema: {e.message}"))
        for ref in iter_refs(doc):
            ref_count += 1
            ok, why = resolve_ref(ref, from_path=rp, by_path=by_path, by_name=by_name, by_id=by_id)
            if not ok:
                findings.append((name, why))
    return findings, len(by_path), ref_count


def _negative_control() -> bool:
    good = {"$id": "https://x/_NC.json", "type": "object", "$defs": {"a": {"type": "string"}}}
    p = Path("/tmp/_nc.json").resolve()   # resolve so keys match resolve_ref's from_path.resolve()
    by_path, by_name, by_id = {p: good}, {"_NC.json": good}, {good["$id"]: good}
    checks = [
        ("dangling internal pointer caught",
         resolve_ref("#/$defs/missing", from_path=p, by_path=by_path, by_name=by_name, by_id=by_id)[0] is False),
        ("dangling file ref caught",
         resolve_ref("Nope.json", from_path=p, by_path=by_path, by_name=by_name, by_id=by_id)[0] is False),
        ("valid internal pointer resolves",
         resolve_ref("#/$defs/a", from_path=p, by_path=by_path, by_name=by_name, by_id=by_id)[0] is True),
        ("valid $id ref resolves",
         resolve_ref(good["$id"], from_path=p, by_path=by_path, by_name=by_name, by_id=by_id)[0] is True),
        ("data file is not a schema", not _is_schema({"foo": "bar"})),
        ("schema is a schema", _is_schema(good)),
    ]
    ok = all(v for _, v in checks)
    for n, v in checks:
        print(f"    {'OK  ' if v else 'FAIL'} negative control: {n}")
    return ok


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Referential-integrity gate for contracts/ + schemas/.")
    ap.add_argument("--self-test", action="store_true")
    args = ap.parse_args(argv)
    if not _negative_control():
        print("FAIL: negative control did not trip — no teeth; refusing to certify")
        return 2
    if args.self_test:
        return 0
    findings, n, refs = check_all(ROOT)
    if n == 0:
        print("FAIL: no schemas found — refusing to green a scan of nothing")
        return 2
    if findings:
        print(f"FAIL: {len(findings)} referential-integrity defect(s) across {n} schemas:")
        for name, why in sorted(findings):
            print(f"  {name}: {why}")
        return 1
    print(f"OK: {n} schemas valid; all {refs} $refs resolve to a real target")
    return 0


if __name__ == "__main__":
    sys.exit(main())
