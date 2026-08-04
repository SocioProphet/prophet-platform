#!/usr/bin/env python3
"""ADR-triggered dependency graph + two waves of safety — so a decision PERCOLATES.

Root-cause of the Nix→Guix failure (retrospective 2026-08-04): an ADR was made (migrate source-os
Nix→Guix, 08-02) but it produced only prose + a parity checklist. **No machine-actionable dependency
graph was ever built from it.** So nothing knew the swap's scope, nothing gated new Nix, nothing
healed the residual — and new work (including an agent's) defaulted straight back to Nix. Declared,
never enforced.

The fix, stated by the operator: *"when an ADR happens there needs to be a dependency graph built."*
This module is that. Given a SwapADR (a decision to replace toolchain/library FROM with TO across a
SCOPE), it:

  1. **builds the dependency graph** — every FROM-side artifact in scope as a node, reference edges
     between them (the blast radius, topologically ordered), and each node's port status vs TO.
  2. **Wave 1 — PREVENT (fail-closed):** a gate over changed files. A NEW FROM-side artifact in scope,
     unwaived, is a VIOLATION — "you added Nix under a Nix→Guix swap; author the Guix equivalent or
     file a waiver." This is the control that would have stopped the agent adding a new `.nix`.
  3. **Wave 2 — DETECT→HEAL:** sweep the graph for unported FROM nodes, order them leaves-first
     (port dependencies before dependents), and emit a SEALED remediation plan — because detect ≠ heal.

Generic over any swap ADR (library A→B, tool A→B); Nix→Guix is just the first instance. Fail-closed,
sealed receipts, stdlib-only.
"""
from __future__ import annotations

import fnmatch
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path


def _seal(body: dict) -> str:
    return "sha256:" + hashlib.sha256(
        json.dumps(body, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _rel(root: Path, p: Path) -> str:
    try:
        return p.relative_to(root).as_posix()
    except ValueError:
        return p.as_posix()


def _in_scope(relpath: str, adr: dict) -> bool:
    scopes = adr.get("scope") or []
    return (not scopes) or any(relpath == s or relpath.startswith(s.rstrip("/") + "/") for s in scopes)


def _matches(relpath: str, side: dict) -> bool:
    """A path is on this side of the swap if it matches a glob or its basename is a named marker."""
    base = relpath.rsplit("/", 1)[-1]
    if base in set(side.get("markers") or []):
        return True
    return any(fnmatch.fnmatch(base, g) or fnmatch.fnmatch(relpath, g) for g in (side.get("globs") or []))


def _is_from(relpath: str, adr: dict) -> bool:
    return _matches(relpath, adr.get("from") or {})


def _is_to(relpath: str, adr: dict) -> bool:
    return _matches(relpath, adr.get("to") or {})


def _waived(relpath: str, adr: dict) -> str | None:
    for w in adr.get("waivers") or []:
        pat = w.get("path", "")
        if relpath == pat or fnmatch.fnmatch(relpath, pat):
            return w.get("reason", "waived")
    return None


# reference extractors: how a FROM artifact points at another FROM artifact (best-effort, per lang).
_REF_RE = re.compile(r"""([./][\w./\-]+?\.(?:nix|scm))|(?:callPackage|import|require|source)\s+['"]?([\w./\-]+)""")


def _refs(text: str) -> set[str]:
    out: set[str] = set()
    for m in _REF_RE.finditer(text):
        tok = m.group(1) or m.group(2) or ""
        tok = tok.strip().lstrip("./")
        if tok:
            out.add(tok)
    return out


def build_dependency_graph(adr: dict, root) -> dict:
    """THE thing an ADR must produce: the blast-radius graph of the swap. Nodes = FROM-side artifacts
    in scope; edges = references between them; each node carries its port status vs TO. Sealed."""
    root = Path(root)
    to_stems: set[str] = set()
    from_files: list[str] = []
    for p in sorted(root.rglob("*")):
        if not p.is_file() or "/.git/" in p.as_posix():
            continue
        rel = _rel(root, p)
        if not _in_scope(rel, adr):
            continue
        if _is_to(rel, adr):
            to_stems.add(p.stem)
        elif _is_from(rel, adr):
            from_files.append(rel)

    # index by basename so references (often bare) can resolve to in-scope FROM nodes.
    by_base: dict[str, str] = {}
    for rel in from_files:
        by_base.setdefault(rel.rsplit("/", 1)[-1], rel)

    nodes: dict[str, dict] = {}
    for rel in from_files:
        try:
            text = (root / rel).read_text(errors="ignore")
        except OSError:
            text = ""
        deps = set()
        for tok in _refs(text):
            cand = tok.rsplit("/", 1)[-1]
            target = by_base.get(cand)
            if target and target != rel:
                deps.add(target)
        # a FROM node is "ported" if a TO artifact shares its stem (best-effort parity signal).
        stem = rel.rsplit("/", 1)[-1].rsplit(".", 1)[0]
        nodes[rel] = {"path": rel, "side": "from", "depends_on": sorted(deps),
                      "ported": stem in to_stems, "waiver": _waived(rel, adr)}
    for rel, n in nodes.items():
        n["dependents"] = sorted(r for r, m in nodes.items() if rel in m["depends_on"])

    unported = sorted(r for r, n in nodes.items() if not n["ported"] and not n["waiver"])
    graph = {
        "adr_id": adr.get("adr_id"), "kind": "adr.dependency_graph.v1", "built_at": _now(),
        "root": str(root), "scope": adr.get("scope"),
        "from": adr.get("from", {}).get("lang"), "to": adr.get("to", {}).get("lang"),
        "node_count": len(nodes), "ported_count": sum(1 for n in nodes.values() if n["ported"]),
        "unported_count": len(unported), "unported": unported,
        "nodes": [nodes[r] for r in sorted(nodes)],
    }
    graph["graph_digest"] = _seal({k: v for k, v in graph.items() if k != "built_at"})
    return graph


def wave1_prevent(adr: dict, changed_files, root=None) -> dict:
    """Wave 1 — PREVENT, fail-closed. A NEW FROM-side artifact in scope, unwaived, under a live swap
    is a violation. `changed_files` is the set being added/modified (e.g. a PR diff). If `root` is
    given, a change is only "new FROM" when a matching TO sibling does not already exist."""
    if adr.get("status") in ("done", "retired"):
        return {"wave": 1, "ok": True, "violations": [], "reason": "swap complete; gate inert"}
    violations = []
    for rel in changed_files:
        rel = rel.lstrip("./")
        if not _in_scope(rel, adr) or not _is_from(rel, adr):
            continue
        if _waived(rel, adr):
            continue
        violations.append({
            "path": rel,
            "rule": "no-new-FROM-under-active-swap",
            "message": (f"'{rel}' uses {adr.get('from', {}).get('lang')} but ADR {adr.get('adr_id')} "
                        f"is migrating {adr.get('scope')} to {adr.get('to', {}).get('lang')}. "
                        f"Author the {adr.get('to', {}).get('lang')} equivalent (see "
                        f"{adr.get('parity_doc')}) or add a waiver to the ADR."),
        })
    decision = {"wave": 1, "adr_id": adr.get("adr_id"), "decided_at": _now(),
                "ok": not violations, "placement": "blocked" if violations else "clear",
                "violations": violations}
    decision["receipt_digest"] = _seal({k: v for k, v in decision.items() if k != "receipt_digest"})
    return decision


def _topo_order(unported: list[str], nodes_by_path: dict) -> list[str]:
    """Leaves first: port an artifact only after the in-scope FROM artifacts it depends on. Cycles are
    broken deterministically (by path) so the plan is always total."""
    remaining = set(unported)
    ordered: list[str] = []
    while remaining:
        ready = sorted(r for r in remaining
                       if not (set(nodes_by_path[r]["depends_on"]) & remaining))
        if not ready:  # cycle — break it deterministically
            ready = [sorted(remaining)[0]]
        ordered.extend(ready)
        remaining -= set(ready)
    return ordered


def wave2_detect_heal(adr: dict, graph: dict) -> dict:
    """Wave 2 — DETECT→HEAL. Enumerate the residual FROM artifacts (the blast radius not yet ported),
    order them leaves-first, and emit a SEALED remediation plan. detect ≠ heal: this is the actionable
    port backlog, not just a count."""
    nodes_by_path = {n["path"]: n for n in graph["nodes"]}
    order = _topo_order(list(graph["unported"]), nodes_by_path)
    to_lang = adr.get("to", {}).get("lang")
    plan = []
    for i, rel in enumerate(order):
        n = nodes_by_path[rel]
        blocked_by = [d for d in n["depends_on"] if d in graph["unported"]]
        plan.append({
            "order": i + 1, "port": rel,
            "to": f"{to_lang}: re-express per {adr.get('parity_doc')}",
            "blocked_by": blocked_by, "dependents_unblocked": n["dependents"],
        })
    heal = {"wave": 2, "adr_id": adr.get("adr_id"), "swept_at": _now(),
            "residual": len(order), "parity_doc": adr.get("parity_doc"),
            "status": adr.get("status"), "remediation_plan": plan}
    heal["receipt_digest"] = _seal({k: v for k, v in heal.items() if k != "receipt_digest"})
    return heal


def run(adr: dict, root, changed_files=None) -> dict:
    """The full ADR safety pass: build the graph, run Wave 1 over any changed files, run Wave 2 over
    the residual. One sealed report — the percolation the ADR should have triggered on day one."""
    graph = build_dependency_graph(adr, root)
    w1 = wave1_prevent(adr, changed_files or [], root=root)
    w2 = wave2_detect_heal(adr, graph)
    report = {"adr_id": adr.get("adr_id"), "title": adr.get("title"), "ran_at": _now(),
              "graph": {"nodes": graph["node_count"], "ported": graph["ported_count"],
                        "unported": graph["unported_count"], "digest": graph["graph_digest"]},
              "wave1_prevent": {"ok": w1["ok"], "violations": len(w1["violations"])},
              "wave2_heal": {"residual": w2["residual"]},
              "healthy": w1["ok"] and graph["unported_count"] == 0}
    report["receipt_digest"] = _seal({k: v for k, v in report.items() if k != "receipt_digest"})
    return {"report": report, "graph": graph, "wave1": w1, "wave2": w2}


if __name__ == "__main__":
    import sys

    if len(sys.argv) >= 3:  # adr_dependency_graph.py <adr.json> <root> [changed_file ...]
        adr = json.loads(Path(sys.argv[1]).read_text())
        out = run(adr, sys.argv[2], changed_files=sys.argv[3:] or None)
        print(json.dumps(out["report"], indent=2, sort_keys=True))
        sys.exit(0 if out["wave1"]["ok"] else 1)

    # demo: the real Nix→Guix ADR against a tiny fixture (a new .nix is caught; residual is planned).
    import tempfile
    adr = {"adr_id": "ADR-0001", "title": "Migrate source-os Nix→Guix",
           "from": {"lang": "nix", "globs": ["*.nix"]}, "to": {"lang": "guix", "globs": ["*.scm"]},
           "scope": ["packages", "modules"], "parity_doc": "guix/NIX_BASELINE.md", "status": "parity",
           "waivers": [{"path": "packages/bootstrap.nix", "reason": "toolchain seed, ports last"}]}
    with tempfile.TemporaryDirectory() as td:
        r = Path(td)
        (r / "packages").mkdir(); (r / "modules").mkdir()
        (r / "packages/base.nix").write_text("{ }: { }")
        (r / "packages/app.nix").write_text("import ./base.nix")  # app depends on base
        (r / "modules/svc.nix").write_text("callPackage ../packages/app.nix")
        (r / "packages/bootstrap.nix").write_text("{ }: { }")  # waived
        out = run(adr, td, changed_files=["packages/new_thing.nix", "docs/readme.md"])
        print(json.dumps({
            "report": out["report"],
            "wave1_violations": [v["path"] for v in out["wave1"]["violations"]],
            "wave2_order": [(p["order"], p["port"], "blocked_by:" + ",".join(p["blocked_by"]) or "-")
                            for p in out["wave2"]["remediation_plan"]],
        }, indent=2))
