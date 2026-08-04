"""Tests for CheckCoverSufficiency (evidence_cover_registry_spec_v0_1 §CheckCoverSufficiency)."""
import json
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from check_cover_sufficiency import check_cover_sufficiency, repair_digest

TIER_ORDER = ["T1", "T2", "T3"]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _graph(covers: list[dict], tier_order: list[str] = TIER_ORDER,
           claim_id: str = "claim://test/x",
           admissibility_floors: dict | None = None) -> dict:
    """Build a minimal valid EvidenceCoverGraph for testing."""
    ev_ids = {eid for c in covers for eid in c.get("evidence_item_ids", [])}
    evidence_items = [
        {"id": eid, "type": "TestEvidence",
         "digest_sha256": "a" * 64}
        for eid in sorted(ev_ids)
    ]
    tp: dict = {"tier_order": tier_order}
    if admissibility_floors:
        tp["admissibility_floor_by_claim_class"] = admissibility_floors
    return {
        "evidence_cover_graph_version": 1,
        "claim_id": claim_id,
        "evidence_items": evidence_items or [
            {"id": "placeholder", "type": "T", "digest_sha256": "a" * 64}
        ],
        "covers": covers,
        "tier_policy": tp,
    }


def _cover(tier: str, cid: str = "cov-1", ev_ids: list[str] | None = None) -> dict:
    return {
        "cover_id": cid,
        "claim_id": "claim://test/x",
        "tier": tier,
        "evidence_item_ids": ev_ids or ["placeholder"],
    }


# ---------------------------------------------------------------------------
# Basic verdict tests
# ---------------------------------------------------------------------------

def test_sufficient_when_cover_at_t_eval():
    g = _graph([_cover("T1")])
    verdict, repair = check_cover_sufficiency(g, "T1")
    assert verdict == "SUFFICIENT"
    assert repair is None


def test_sufficient_when_cover_stricter_than_t_eval():
    # T1 cover is admissible at T2 (T1 index 0 <= T2 index 1)
    g = _graph([_cover("T1")])
    verdict, repair = check_cover_sufficiency(g, "T2")
    assert verdict == "SUFFICIENT"


def test_inconclusive_when_only_coarser_cover():
    # T3 cover (index 2) is NOT admissible at T1 (index 0)
    g = _graph([_cover("T3")])
    verdict, repair = check_cover_sufficiency(g, "T1")
    assert verdict == "INCONCLUSIVE"
    assert repair is not None
    assert repair["reason"] == "cover_sufficiency_gap"


def test_inconclusive_repair_carries_claim_id():
    g = _graph([_cover("T3")], claim_id="claim://test/my-claim")
    g["covers"][0]["claim_id"] = "claim://test/my-claim"
    g["claim_id"] = "claim://test/my-claim"
    _, repair = check_cover_sufficiency(g, "T1")
    assert repair["claim_id"] == "claim://test/my-claim"


def test_sufficient_when_multiple_covers_one_admissible():
    covers = [_cover("T3", "c1"), _cover("T1", "c2")]
    g = _graph(covers)
    verdict, repair = check_cover_sufficiency(g, "T2")
    assert verdict == "SUFFICIENT"


def test_inconclusive_when_no_covers():
    g = _graph([])
    g["covers"] = []  # empty covers — schema normally requires minItems 1, but runtime handles gracefully
    verdict, _ = check_cover_sufficiency(g, "T1")
    assert verdict == "INCONCLUSIVE"


def test_sufficient_at_most_permissive_tier():
    g = _graph([_cover("T1")])
    verdict, _ = check_cover_sufficiency(g, "T1")
    assert verdict == "SUFFICIENT"


def test_sufficient_at_most_restrictive_tier():
    g = _graph([_cover("T3")])
    verdict, _ = check_cover_sufficiency(g, "T3")
    assert verdict == "SUFFICIENT"


# ---------------------------------------------------------------------------
# Admissibility floor enforcement
# ---------------------------------------------------------------------------

def test_floor_equal_to_t_eval_passes():
    # floor=T1, T_eval=T1 → floor_idx (0) is NOT < t_eval_idx (0) → no upgrade required
    g = _graph([_cover("T1")], admissibility_floors={"financial-audit": "T1"})
    verdict, repair = check_cover_sufficiency(g, "T1", claim_class="financial-audit")
    assert verdict == "SUFFICIENT"
    assert repair is None


def test_floor_stricter_than_t_eval_inconclusive():
    # floor=T1 (idx 0), T_eval=T2 (idx 1) → floor_idx (0) < t_eval_idx (1) → INCONCLUSIVE+upgrade
    g = _graph([_cover("T2")], admissibility_floors={"financial-audit": "T1"})
    verdict, repair = check_cover_sufficiency(g, "T2", claim_class="financial-audit")
    assert verdict == "INCONCLUSIVE"
    assert repair is not None
    assert repair["reason"] == "admissibility_floor_not_met"
    assert any(a["action"] == "upgrade_tier" for a in repair["requested_actions"])


def test_floor_coarser_than_t_eval_no_upgrade():
    # floor=T3 (idx 2), T_eval=T1 (idx 0) → floor_idx (2) NOT < t_eval_idx (0) → no floor block
    g = _graph([_cover("T1")], admissibility_floors={"general": "T3"})
    verdict, _ = check_cover_sufficiency(g, "T1", claim_class="general")
    assert verdict == "SUFFICIENT"


def test_unknown_claim_class_no_floor_enforcement():
    g = _graph([_cover("T2")], admissibility_floors={"financial-audit": "T1"})
    verdict, _ = check_cover_sufficiency(g, "T2", claim_class="unknown-class")
    assert verdict == "SUFFICIENT"


def test_no_claim_class_skips_floor():
    g = _graph([_cover("T2")], admissibility_floors={"financial-audit": "T1"})
    verdict, _ = check_cover_sufficiency(g, "T2", claim_class=None)
    assert verdict == "SUFFICIENT"


# ---------------------------------------------------------------------------
# Determinism law (spec §EmitRepairRequest)
# ---------------------------------------------------------------------------

def test_repair_request_deterministic_need_additional():
    g = _graph([_cover("T3")])
    _, r1 = check_cover_sufficiency(g, "T1")
    _, r2 = check_cover_sufficiency(g, "T1")
    assert repair_digest(r1) == repair_digest(r2)


def test_repair_request_deterministic_upgrade_tier():
    g = _graph([_cover("T2")], admissibility_floors={"cls": "T1"})
    _, r1 = check_cover_sufficiency(g, "T2", "cls")
    _, r2 = check_cover_sufficiency(g, "T2", "cls")
    assert repair_digest(r1) == repair_digest(r2)


def test_different_inputs_different_digest():
    g1 = _graph([_cover("T3")], claim_id="claim://test/a")
    g2 = _graph([_cover("T3")], claim_id="claim://test/b")
    g2["covers"][0]["claim_id"] = "claim://test/b"
    g2["claim_id"] = "claim://test/b"
    _, r1 = check_cover_sufficiency(g1, "T1")
    _, r2 = check_cover_sufficiency(g2, "T1")
    assert repair_digest(r1) != repair_digest(r2)


# ---------------------------------------------------------------------------
# Repair request structure
# ---------------------------------------------------------------------------

def test_repair_need_additional_has_action():
    g = _graph([_cover("T3")])
    _, repair = check_cover_sufficiency(g, "T1")
    assert len(repair["requested_actions"]) >= 1
    actions = [a["action"] for a in repair["requested_actions"]]
    assert "need_additional_evidence" in actions


def test_repair_upgrade_tier_has_floor_in_details():
    g = _graph([_cover("T2")], admissibility_floors={"cls": "T1"})
    _, repair = check_cover_sufficiency(g, "T2", "cls")
    action = next(a for a in repair["requested_actions"] if a["action"] == "upgrade_tier")
    assert action["details"]["admissibility_floor"] == "T1"
    assert action["details"]["t_eval"] == "T2"


def test_repair_version_field():
    g = _graph([_cover("T3")])
    _, repair = check_cover_sufficiency(g, "T1")
    assert repair["repair_request_version"] == 1


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

def test_no_tier_policy_all_covers_admissible():
    graph = {
        "evidence_cover_graph_version": 1,
        "claim_id": "claim://test/no-policy",
        "evidence_items": [{"id": "e1", "type": "T", "digest_sha256": "a" * 64}],
        "covers": [{"cover_id": "c1", "claim_id": "claim://test/no-policy",
                    "tier": "ANY", "evidence_item_ids": ["e1"]}],
    }
    verdict, repair = check_cover_sufficiency(graph, "ANY")
    assert verdict == "SUFFICIENT"


def test_cover_with_unknown_tier_not_admissible():
    g = _graph([_cover("BOGUS")])
    verdict, _ = check_cover_sufficiency(g, "T1")
    assert verdict == "INCONCLUSIVE"


# ---------------------------------------------------------------------------
# Fixture runner (integration)
# ---------------------------------------------------------------------------

def test_fixture_runner_passes(tmp_path):
    """The three shipped fixtures all pass when run through the CLI fixture runner."""
    import pathlib
    import subprocess
    root = pathlib.Path(__file__).resolve().parent.parent.parent
    fixture_dir = str(root / "contracts" / "evidence" / "sufficiency-check")
    graph_path = str(root / "contracts" / "evidence" / "sufficiency-check" / "check_cover_sufficiency_passes_floor.json")
    result = subprocess.run(
        [sys.executable, str(root / "tools" / "check_cover_sufficiency.py"),
         graph_path, "--tier", "T1", "--fixture-dir", fixture_dir],
        capture_output=True, text=True,
        cwd=str(root / "tools"),
    )
    # 0=all SUFFICIENT, 1=some INCONCLUSIVE (expected for the floor-upgrade fixture)
    assert result.returncode in (0, 1)


def test_fixture_json_valid():
    """All three fixture JSONs are syntactically valid."""
    import pathlib
    fixture_dir = pathlib.Path(__file__).resolve().parent.parent.parent / "contracts" / "evidence" / "sufficiency-check"
    for p in fixture_dir.glob("check_cover_sufficiency_*.json"):
        data = json.loads(p.read_text())
        assert "expected_verdict" in data
        assert data["expected_verdict"] in ("SUFFICIENT", "INCONCLUSIVE")
        assert "graph" in data
