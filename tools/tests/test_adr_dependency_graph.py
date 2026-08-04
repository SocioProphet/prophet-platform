#!/usr/bin/env python3
"""Tests for the ADR dependency graph + two waves of safety (the Nix→Guix percolation fix)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import adr_dependency_graph as adg  # noqa: E402

ADR = {
    "adr_id": "ADR-0001", "title": "Migrate source-os Nix→Guix",
    "from": {"lang": "nix", "globs": ["*.nix"]}, "to": {"lang": "guix", "globs": ["*.scm"]},
    "scope": ["packages", "modules"], "parity_doc": "guix/NIX_BASELINE.md", "status": "parity",
    "waivers": [{"path": "packages/bootstrap.nix", "reason": "toolchain seed"}],
}


def _tree(tmp_path):
    (tmp_path / "packages").mkdir()
    (tmp_path / "modules").mkdir()
    (tmp_path / "docs").mkdir()
    (tmp_path / "packages/base.nix").write_text("{ }: { }")
    (tmp_path / "packages/app.nix").write_text("import ./base.nix\n")          # app -> base
    (tmp_path / "modules/svc.nix").write_text("callPackage ../packages/app.nix")  # svc -> app
    (tmp_path / "packages/bootstrap.nix").write_text("{ }")                     # waived
    (tmp_path / "packages/ported.nix").write_text("{ }")                        # has a .scm sibling
    (tmp_path / "packages/ported.scm").write_text(";; guix")                    # TO side -> ported
    (tmp_path / "docs/readme.md").write_text("# not in the swap")
    return tmp_path


def test_the_adr_builds_a_dependency_graph_with_edges_and_port_status(tmp_path):
    g = adg.build_dependency_graph(ADR, _tree(tmp_path))
    nodes = {n["path"]: n for n in g["nodes"]}
    # docs/readme.md is out of scope; ported.scm is TO not a node; the 5 .nix in scope are nodes.
    assert set(nodes) == {"packages/base.nix", "packages/app.nix", "modules/svc.nix",
                          "packages/bootstrap.nix", "packages/ported.nix"}
    assert nodes["packages/app.nix"]["depends_on"] == ["packages/base.nix"]
    assert nodes["packages/base.nix"]["dependents"] == ["packages/app.nix"]
    assert nodes["modules/svc.nix"]["depends_on"] == ["packages/app.nix"]
    assert nodes["packages/ported.nix"]["ported"] is True          # .scm sibling exists
    assert nodes["packages/bootstrap.nix"]["waiver"] is not None
    assert g["graph_digest"].startswith("sha256:")


def test_unported_excludes_ported_and_waived(tmp_path):
    g = adg.build_dependency_graph(ADR, _tree(tmp_path))
    # residual = the 3 real unported nix; ported.nix (has .scm) and bootstrap.nix (waived) excluded.
    assert set(g["unported"]) == {"packages/base.nix", "packages/app.nix", "modules/svc.nix"}
    assert g["unported_count"] == 3


def test_wave1_blocks_a_new_nix_under_the_swap_failclosed():
    # THE regression: an agent adds a new .nix while Nix→Guix is live. Must be blocked.
    d = adg.wave1_prevent(ADR, ["packages/sourceos_shell.nix", "docs/readme.md"])
    assert d["ok"] is False and d["placement"] == "blocked"
    assert [v["path"] for v in d["violations"]] == ["packages/sourceos_shell.nix"]
    assert "waiver" in d["violations"][0]["message"] or "equivalent" in d["violations"][0]["message"]
    assert d["receipt_digest"].startswith("sha256:")


def test_wave1_allows_waived_out_of_scope_and_TO_side():
    d = adg.wave1_prevent(ADR, ["packages/bootstrap.nix",   # waived
                                "tools/thing.nix",           # out of scope
                                "packages/newmod.scm"])      # TO side, fine
    assert d["ok"] is True and d["violations"] == []


def test_wave1_is_inert_once_the_swap_is_done():
    done = {**ADR, "status": "done"}
    d = adg.wave1_prevent(done, ["packages/anything.nix"])
    assert d["ok"] is True  # gate lifts after cutover


def test_wave2_emits_a_leaves_first_sealed_remediation_plan(tmp_path):
    g = adg.build_dependency_graph(ADR, _tree(tmp_path))
    heal = adg.wave2_detect_heal(ADR, g)
    order = [p["port"] for p in heal["remediation_plan"]]
    # base has no in-scope deps → first; app depends on base → after it; svc depends on app → last.
    assert order.index("packages/base.nix") < order.index("packages/app.nix") < order.index("modules/svc.nix")
    assert heal["residual"] == 3 and heal["receipt_digest"].startswith("sha256:")
    svc = next(p for p in heal["remediation_plan"] if p["port"] == "modules/svc.nix")
    assert svc["blocked_by"] == ["packages/app.nix"]


def test_run_is_unhealthy_while_residual_or_violations_exist(tmp_path):
    out = adg.run(ADR, _tree(tmp_path), changed_files=["packages/new.nix"])
    assert out["report"]["healthy"] is False
    assert out["report"]["wave1_prevent"]["violations"] == 1
    assert out["report"]["wave2_heal"]["residual"] == 3
    assert out["report"]["receipt_digest"].startswith("sha256:")


def test_generalizes_to_any_swap_library_a_to_b(tmp_path):
    # not Nix-specific: e.g. replace requests -> httpx across a python package.
    adr = {"adr_id": "ADR-0002", "title": "requests→httpx",
           "from": {"lang": "requests", "globs": ["*.uses-requests"]},
           "to": {"lang": "httpx", "globs": ["*.uses-httpx"]},
           "scope": ["svc"], "parity_doc": "MIGRATION.md", "status": "parity", "waivers": []}
    (tmp_path / "svc").mkdir()
    (tmp_path / "svc" / "a.uses-requests").write_text("x")
    g = adg.build_dependency_graph(adr, tmp_path)
    assert g["unported_count"] == 1
    assert adg.wave1_prevent(adr, ["svc/b.uses-requests"])["ok"] is False


if __name__ == "__main__":
    import tempfile
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    passed = 0
    for fn in fns:
        import inspect
        if "tmp_path" in inspect.signature(fn).parameters:
            with tempfile.TemporaryDirectory() as td:
                fn(Path(td))
        else:
            fn()
        passed += 1
    print(f"ok: {passed} adr-dependency-graph tests passed")
    sys.exit(0)
