"""THEOREM: go-live is a deliberate flip, not a side effect of merging the manifest.

The platform-services ApplicationSet (deploy/argocd/platform-services.yaml) is
automated{prune,selfHeal}: once deploy/values/hellgraph-percolator.yaml lands on main,
ArgoCD ships the Deployment (replicaCount 1, no enabled/disabled Application-level knob)
regardless of what the PR description promises. The ONLY real lever is the
PERCOLATOR_LOOP env var this chart writes into config: (see server.py, which defaults
the background poll loop to "on" when the var is unset or anything other than "off").

If this file ever ships without that key — or with it set to "on" — the loop starts
polling hellgraph-service and minting compute-gateway receipts against the live cluster
the moment ArgoCD syncs, silently, with no human "go-live" decision in the loop. That is
exactly the class of gap this whole review pass exists to catch: a manifest that reads as
gated in prose but isn't gated in the object the cluster actually reconciles.
"""
from __future__ import annotations

from pathlib import Path

import yaml

VALUES = Path(__file__).resolve().parents[3] / "deploy" / "values" / "hellgraph-percolator.yaml"


def _deployed_config() -> dict:
    return yaml.safe_load(VALUES.read_text(encoding="utf-8"))["config"]


def test_percolator_loop_is_off_by_default_in_the_deployed_manifest():
    cfg = _deployed_config()
    assert cfg.get("PERCOLATOR_LOOP") == "off", (
        "PERCOLATOR_LOOP is not pinned to 'off' in deploy/values/hellgraph-percolator.yaml — "
        "the automated ApplicationSet will start the live poll loop on merge, not on a "
        "deliberate go-live decision. Flip this only when go-live is actually decided."
    )


def test_replica_count_alone_is_not_treated_as_the_gate():
    """Documents the actual mechanism so a future editor doesn't 'fix' this by zeroing
    replicaCount instead — that would also kill /healthz and drop the service from
    ArgoCD's health rollup, which PERCOLATOR_LOOP=off does not."""
    raw = yaml.safe_load(VALUES.read_text(encoding="utf-8"))
    assert raw["replicaCount"] == 1
    assert raw["config"]["PERCOLATOR_LOOP"] == "off"
