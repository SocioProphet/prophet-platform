"""Prove INV-DEP-15 (the ArgoCD source-sovereignty ratchet) both ways, offline.

Every ArgoCD Application should pull from a sovereign source (our own git or the sovereign
registry), never an unpinned public Helm CDN — a foundation chart fetched over a third-party
index is a supply-chain dependency the estate does not control. The gate is a SHRINK-ONLY
ratchet, so a gate that only ever passes proves nothing. This drives the pure seams through
every outcome with no filesystem scan:

  * our git / sovereign registry              => sovereign (recognized, allowed);
  * a public Helm CDN                         => NOT sovereign (the supply-chain risk);
  * a NEW external source not in KNOWN_BROKEN => FAILS (the ratchet forbids widening);
  * a KNOWN_BROKEN entry that no longer appears => FAILS (stale allowlist; ratchet only shrinks);
  * a KNOWN_BROKEN entry still present        => passes (tolerated while it migrates).

The final case runs the ratchet against the REAL repo tree this PR ships, so main stays
sovereign-or-shrinking at merge time.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

MODULE_PATH = Path(__file__).resolve().parents[1] / "verify_argocd_source_sovereignty.py"
sys.path.insert(0, str(MODULE_PATH.parent))
SPEC = importlib.util.spec_from_file_location("verify_argocd_source_sovereignty", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
MOD = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MOD
SPEC.loader.exec_module(MOD)


def test_sovereign_sources_recognized():
    assert MOD._is_sovereign("https://github.com/SocioProphet/prophet-platform")
    assert MOD._is_sovereign("https://github.com/SourceOS-Linux/sourceos")
    assert MOD._is_sovereign("https://registry.socioprophet.ai/charts")


def test_public_cdn_is_not_sovereign():
    assert not MOD._is_sovereign("https://kyverno.github.io/kyverno")
    assert not MOD._is_sovereign("https://grafana.github.io/helm-charts")


def test_new_external_source_fails():
    problems = MOD.evaluate({"https://evil.example.com/chart": ["x"]}, {})
    assert any("NEW external source" in p for p in problems), problems


def test_stale_allowlist_entry_fails():
    problems = MOD.evaluate({}, {"https://gone.github.io/x": "reason"})
    assert any("STALE allowlist entry" in p for p in problems), problems


def test_known_external_still_present_passes():
    url = "https://kyverno.github.io/kyverno"
    assert MOD.evaluate({url: ["kyverno"]}, {url: "reason"}) == []


def test_shipped_tree_is_sovereign_or_shrinking():
    # The canonical guarantee this PR ships: main's ArgoCD Applications are all sovereign
    # or tolerated-shrinking allowlist entries — no widening, no stale entries.
    assert MOD.evaluate(MOD.scan(MOD.ROOT), MOD.KNOWN_BROKEN) == []
