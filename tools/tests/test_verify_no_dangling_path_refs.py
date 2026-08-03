"""Teeth for the blast-radius-on-refactor gate (INV-DEP-12).

Proven both ways, and against the exact incident that motivated it: a moved file whose OLD
path is still hard-coded somewhere must FLAG; a move whose references were all updated must be
CLEAN; a bare shared basename (two `kustomization.yaml`) must NOT be a false positive; and a
rename whose consumers point at the NEW path must be CLEAN. A gate that has only ever passed
proves nothing.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import verify_no_dangling_path_refs as chk  # noqa: E402


# (a) A removed path still referenced by another file -> flagged, with file:line + missing path.
def test_removed_path_still_referenced_is_flagged():
    removed = ["infra/k8s/search-orchestrator/base/configmap.yaml"]
    tree = {
        "tools/validate_search_orchestrator_academy_deploy.py": (
            "REQUIRED = [\n"
            '    "infra/k8s/search-orchestrator/base/configmap.yaml",\n'
            "]\n"
        ),
    }
    violations = chk.scan(removed, tree)
    assert len(violations) == 1, violations
    v = violations[0]
    assert "tools/validate_search_orchestrator_academy_deploy.py:2" in v
    assert "infra/k8s/search-orchestrator/base/configmap.yaml" in v


# The real 2026-08-02 incident: the file was MOVED to base-support/, but a consumer kept the
# old base/ path. That is a rename-away whose old path survives as a hard-coded ref.
def test_academy_deploy_incident_shape_is_flagged():
    removed = ["infra/k8s/search-orchestrator/base/configmap.yaml"]
    tree = {
        "tools/validate_search_orchestrator_academy_deploy.py": (
            '"infra/k8s/search-orchestrator/base/configmap.yaml": ["expected-key"],\n'
        ),
        # the new location exists and is referenced correctly elsewhere — irrelevant to the flag
        "infra/k8s/search-orchestrator/base-support/kustomization.yaml": (
            "resources:\n  - configmap.yaml\n"
        ),
    }
    violations = chk.scan(removed, tree)
    assert any("base/configmap.yaml" in v for v in violations), violations


# (b) A removed path with all references updated to the new path -> clean.
def test_all_references_updated_is_clean():
    removed = ["infra/k8s/search-orchestrator/base/configmap.yaml"]
    tree = {
        "tools/validate_search_orchestrator_academy_deploy.py": (
            '"infra/k8s/search-orchestrator/base-support/configmap.yaml": ["expected-key"],\n'
        ),
    }
    assert chk.scan(removed, tree) == []


# (c) A bare-basename collision (two files named kustomization.yaml) -> NOT flagged.
def test_bare_basename_collision_is_not_flagged():
    removed = ["infra/k8s/search-orchestrator/base/kustomization.yaml"]
    tree = {
        # a DIFFERENT kustomization.yaml, referenced by its own distinct path
        "infra/k8s/rollouts/base/kustomization.yaml": "resources:\n  - rollout.yaml\n",
        # a file that references the surviving one by a distinct 2-segment suffix
        "infra/k8s/rollouts/overlays/prod/kustomization.yaml": (
            "resources:\n  - ../../base\n"
        ),
        # and a doc that mentions the bare basename in prose
        "docs/DEPLOY.md": "each overlay has its own kustomization.yaml file\n",
    }
    assert chk.scan(removed, tree) == []


# The bare basename alone must never match, even when it is the removed file's basename.
def test_bare_basename_alone_never_matches():
    removed = ["a/b/kustomization.yaml"]
    tree = {"x/y/z.md": "see kustomization.yaml for details\n"}
    assert chk.scan(removed, tree) == []


# (d) A rename where the NEW path is referenced -> clean (only the OLD path is in `removed`).
def test_rename_with_new_path_referenced_is_clean():
    removed = ["infra/k8s/foo/old/deployment.yaml"]  # the rename-away old path
    tree = {
        "tools/consumer.py": '"infra/k8s/foo/new/deployment.yaml"\n',
    }
    assert chk.scan(removed, tree) == []


# A >=2-segment suffix reference (not the full path) is still caught.
def test_two_segment_suffix_is_matched():
    removed = ["infra/k8s/search-orchestrator/base/pvc.yaml"]
    tree = {"scripts/deploy.sh": "kubectl apply -f base/pvc.yaml\n"}
    violations = chk.scan(removed, tree)
    assert any("base/pvc.yaml" in v for v in violations) or any("pvc.yaml" in v for v in violations)
    assert violations, "a distinctive >=2-segment suffix must be caught"


# Path boundaries: a needle must not match inside a longer segment or a different extension.
def test_no_partial_segment_false_positive():
    removed = ["k8s/base/configmap.yaml"]
    tree = {
        "a.txt": "xk8s/base/configmap.yaml\n",          # left-glued
        "b.txt": "k8s/base/configmap.yaml.bak\n",         # right-glued (different file)
        "c.txt": "k8s/base/configmap.yamlish\n",          # right-glued word
    }
    assert chk.scan(removed, tree) == []


def test_binary_text_none_is_skipped():
    removed = ["a/b/c.yaml"]
    # a tuple-iterable tree with a None (binary) entry that "contains" the path bytes-wise
    tree = [("bin/blob", None), ("ok.md", "a/b/c.yaml\n")]
    violations = chk.scan(removed, tree)
    assert len(violations) == 1 and "ok.md:1" in violations[0]


def test_removed_file_does_not_flag_itself():
    removed = ["a/b/c.yaml"]
    # if the removed file is (wrongly) passed in the tree, it must not self-flag
    tree = {"a/b/c.yaml": "self reference a/b/c.yaml\n"}
    assert chk.scan(removed, tree) == []


def test_empty_removed_is_clean():
    assert chk.scan([], {"any.py": "infra/k8s/x/y.yaml\n"}) == []


def test_iterable_of_pairs_tree_supported():
    removed = ["a/b/c.yaml"]
    tree = iter([("f.py", "ref a/b/c.yaml here\n")])
    violations = chk.scan(removed, tree)
    assert len(violations) == 1


# Fail-closed plumbing: a bogus base ref cannot be diffed, so main() must NOT return 0.
def test_main_fails_closed_on_unresolvable_base(capsys):
    rc = chk.main(["--base-ref", "definitely/not/a/ref/zzz"])
    assert rc != 0
    err = capsys.readouterr().err
    assert "INV-DEP-12" in err


# _parse_name_status_z parses D and R records from `git diff --name-status -z` output.
def test_parse_name_status_z_handles_delete_and_rename():
    # D old1 ; R100 old2 -> new2 ; D old3
    payload = "D\0old/one.yaml\0R100\0old/two.yaml\0new/two.yaml\0D\0old/three.yaml\0"
    removed = chk._parse_name_status_z(payload)
    assert removed == ["old/one.yaml", "old/two.yaml", "old/three.yaml"]
