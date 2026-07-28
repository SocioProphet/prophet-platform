"""Conformance to superconscious's auditable/attested layer — the northstar.

Two things are pinned here: what the rig may ASSERT (claim ledger tag discipline) and
what it may TOUCH (forbidden circuits), plus the 14-fragment release bundle that
superconscious binds by opaque hash.
"""

from __future__ import annotations

import json

import pytest

from noetica_impair.conformance.bundle import (
    BOUND_MODES, BundleDraft, FRAGMENT_KINDS, NON_CLAIMS, draft_from_run, sha256_of,
)
from noetica_impair.conformance.lawful import (
    ForbiddenCircuit, LawfulError, analogy_claim, check_forbidden, circuit_entry,
    circuit_id, claim_entry, claim_id, invariant_claim, measurement_claim,
    preset_concepts,
)
from noetica_impair.substances import presets as P


# ── claim ledger: tag discipline ─────────────────────────────────────────────

def test_a_measurement_is_tagged_E_and_anchored_to_a_receipt():
    e = measurement_claim(claim_id_=claim_id("c1-alcohol"), claim="ALCOHOL@0.6 retains 0.54 competence",
                          receipt_ref="sha256:" + "a" * 64)
    assert e["tag"] == "E" and e["empirical_measurement_ref"].startswith("sha256:")
    assert e["status"] == "captured"
    assert "this model, seed and battery" in e["claim_demarcation"]


def test_the_pharmacology_mapping_is_a_T_claim_not_a_measurement():
    """Tagging the analogy E would dress a metaphor as a result."""
    e = analogy_claim(claim_id_=claim_id("c2-gaba"),
                      claim="GABA-A potentiation resembles self-monitor ablation",
                      receptor="GABA-A positive allosteric modulation")
    assert e["tag"] == "T"
    assert e["typological_parallel_target"]
    assert "not a claim about brains" in e["claim_demarcation"]


def test_an_invariant_is_a_G_claim():
    e = invariant_claim(claim_id_=claim_id("c3-inert"), claim="dose=0 is bit-for-bit sober",
                        invariant_ref="invariant-0.3")
    assert e["tag"] == "G" and e["governance_invariant_ref"] == "invariant-0.3"


def test_a_tag_without_its_evidence_is_refused():
    with pytest.raises(LawfulError, match="empirical_measurement_ref"):
        claim_entry(claim_id_=claim_id("x"), claim="a claim long enough to state itself", tag="E")
    with pytest.raises(LawfulError, match="typological_parallel_target"):
        claim_entry(claim_id_=claim_id("x"), claim="a claim long enough to state itself", tag="T")


def test_compound_tags_require_every_referenced_evidence():
    with pytest.raises(LawfulError, match="governance_invariant_ref"):
        claim_entry(claim_id_=claim_id("x"), claim="a claim long enough to state itself", tag="E|G",
                    empirical_measurement_ref="sha256:" + "b" * 64)
    ok = claim_entry(claim_id_=claim_id("x"), claim="a claim long enough to state itself", tag="E|G",
                     empirical_measurement_ref="sha256:" + "b" * 64,
                     governance_invariant_ref="invariant-0.3")
    assert ok["tag"] == "E|G"


def test_invalid_tag_shape_is_refused():
    with pytest.raises(LawfulError, match="invalid tag"):
        claim_entry(claim_id_=claim_id("x"), claim="a claim long enough to state itself", tag="Z")


def test_the_rig_may_not_promote_its_own_claims():
    """The tier-2 binding declares no_public_claim_promotion."""
    with pytest.raises(LawfulError, match="no_public_claim_promotion"):
        claim_entry(claim_id_=claim_id("x"), claim="a claim long enough to state itself", tag="E",
                    empirical_measurement_ref="sha256:" + "c" * 64,
                    status="promoted")


# ── circuit registry ─────────────────────────────────────────────────────────

def test_a_circuit_needs_both_discovery_and_ablation_evidence():
    with pytest.raises(LawfulError, match="BOTH discovery and ablation"):
        circuit_entry(circuit_id_=circuit_id("k1"), circuit_name="caution", model_ref="gemma2-9b",
                      discovery_evidence_ref="sha256:" + "d" * 64,
                      ablation_evidence_ref="")


def test_a_well_formed_circuit_entry_carries_its_allocation_caveat():
    e = circuit_entry(circuit_id_=circuit_id("k1"), circuit_name="hedging_caution",
                      model_ref="gemma2-9b",
                      discovery_evidence_ref="sha256:" + "d" * 64,
                      ablation_evidence_ref="sha256:" + "e" * 64,
                      layer_range=[20, 20])
    assert e["allocation_type"] == "unknown"
    assert "superposition not ruled out" in e["allocation_basis"]
    assert e["registry_status"] == "candidate"


def test_invalid_registry_status_is_refused():
    with pytest.raises(LawfulError, match="registry_status"):
        circuit_entry(circuit_id_=circuit_id("k"), circuit_name="n", model_ref="m",
                      discovery_evidence_ref="a", ablation_evidence_ref="b",
                      registry_status="blessed")


# ── forbidden circuits ───────────────────────────────────────────────────────

REFUSAL_GATE = ForbiddenCircuit(
    forbidden_circuit_id="fc-refusal-001",
    circuit_pattern=r"refusal|guard",
    prohibition_basis="ablating trained refusal behaviour is gated for deployment",
    enforcement_mode="deployment_gate",
    detection_method="concept name match against steered feature sets",
)
THREAT_AUDIT = ForbiddenCircuit(
    forbidden_circuit_id="fc-threat-002",
    circuit_pattern=r"threat",
    prohibition_basis="threat-appraisal steering requires post-hoc audit",
    enforcement_mode="post_training_audit",
    detection_method="concept name match",
)


def test_mdma_trips_the_refusal_gate():
    """MDMA suppresses refusal_guard — exactly what a deployment gate is for."""
    chk = check_forbidden(preset_concepts(P.MDMA), [REFUSAL_GATE, THREAT_AUDIT])
    assert not chk.allowed
    assert any("refusal_guard" in b for b in chk.blocking)
    assert "BLOCKING" in chk.report()


def test_an_advisory_mode_does_not_block_but_is_recorded():
    chk = check_forbidden(preset_concepts(P.CANNABIS), [THREAT_AUDIT])
    assert chk.allowed, "post_training_audit is advisory, not a gate"
    assert chk.advisory


def test_a_preset_touching_nothing_declared_is_clean():
    chk = check_forbidden(preset_concepts(P.COCAINE), [REFUSAL_GATE])
    assert chk.allowed and not chk.hits


def test_invalid_enforcement_mode_is_refused():
    with pytest.raises(LawfulError, match="enforcement_mode"):
        ForbiddenCircuit(forbidden_circuit_id="x", circuit_pattern="y",
                         prohibition_basis="z", enforcement_mode="vibes",
                         detection_method="d")


# ── the 14-fragment bundle ───────────────────────────────────────────────────

def test_fragment_vocabulary_matches_the_binding_schema():
    assert len(FRAGMENT_KINDS) == 14
    assert len(NON_CLAIMS) == 10 and len(set(NON_CLAIMS)) == 10


def test_the_doctrine_that_keeps_the_rig_out_of_superconscious():
    """The binding layer declares it does NOT execute steering. This rig does."""
    assert "no_live_steering_execution" in NON_CLAIMS
    assert "no_runtime_provider_access" in NON_CLAIMS
    assert "no_public_claim_promotion" in NON_CLAIMS


def test_hashes_are_stable_and_schema_shaped():
    h = sha256_of({"b": 2, "a": 1})
    assert h == sha256_of({"a": 1, "b": 2}), "dict ordering must not change the hash"
    import re
    assert re.match(r"^sha256:[0-9a-f]{64}$", h)


def test_an_incomplete_bundle_refuses_to_bind():
    """Padding would attest to fragments that do not exist."""
    d = BundleDraft()
    d.add("ModelArtifact", "weights://x")
    with pytest.raises(ValueError, match="cannot bind an incomplete bundle"):
        d.to_binding()


def test_the_gap_report_separates_not_yet_from_cannot():
    d = BundleDraft()
    r = d.gap_report()
    assert "NOT PRODUCIBLE by this rig" in r
    assert "CausalTriad" in r and "AttributionGraph" in r
    assert "PublicInterpretabilityNote" in r


def test_a_complete_bundle_binds_and_is_json_safe():
    d = BundleDraft()
    for k in FRAGMENT_KINDS:
        d.add(k, {"kind": k})
    b = d.to_binding()
    assert b["composition_kind"] == "certificate_fragment_composition"
    assert len(b["fragment_refs"]) == 14
    assert b["bound_modes"] == BOUND_MODES
    assert len(b["non_claims"]) == 10
    json.dumps(b)


def test_draft_from_run_maps_real_evidence_onto_fragments():
    class Rec:
        weights_ref = "weights://gemma2-9b@abc"
        receipt = {"id": "sha256:" + "f" * 64, "outputs_sha": "sha256:" + "0" * 64}
    d = draft_from_run(run_record=Rec(),
                       dose_response={"0.6": {"competence": 0.5}},
                       dissociation={"min_pairwise": 0.31})
    present = set(d.fragments)
    assert {"ModelArtifact", "BenchmarkResult", "ImplementabilityCurve",
            "OffTargetAudit"} <= present
    assert not d.complete
    assert "SAEArtifact" in d.missing


# ── validated against the REAL vendored schemas ──────────────────────────────

def _schema(family, name):
    from noetica_impair.conformance import schema_source
    return schema_source.family_schema(family, name)


needs_vendored = pytest.mark.skipif(
    _schema("lawful-learning", "claim-ledger-entry.v1") is None,
    reason="lawful-learning schemas not vendored in this checkout",
)


@needs_vendored
def test_emitted_claims_validate_against_the_real_schema():
    import jsonschema
    sch = _schema("lawful-learning", "claim-ledger-entry.v1")
    for e in (
        measurement_claim(claim_id_=claim_id("c1-alcohol"), claim="a claim long enough to state itself", receipt_ref="sha256:" + "a" * 64),
        analogy_claim(claim_id_=claim_id("c2-gaba"), claim="another claim of adequate length", receptor="GABA-A"),
        invariant_claim(claim_id_=claim_id("c3-inert"), claim="dose zero is bit for bit sober", invariant_ref="inv-0.3"),
    ):
        jsonschema.validate(instance=e, schema=sch)


@needs_vendored
def test_emitted_circuit_entries_validate_against_the_real_schema():
    import jsonschema
    sch = _schema("lawful-learning", "circuit-registry.v1")
    e = circuit_entry(circuit_id_=circuit_id("k1"), circuit_name="hedging_caution",
                      model_ref="gemma2-9b",
                      discovery_evidence_ref="sha256:" + "d" * 64,
                      ablation_evidence_ref="sha256:" + "e" * 64)
    jsonschema.validate(instance=e, schema=sch)


@needs_vendored
def test_the_release_bundle_validates_against_the_tier2_binding_schema():
    """The whole northstar in one assertion: our bundle is bindable."""
    import jsonschema
    sch = _schema("composition", "interpretability-harness-tier2-binding.v1")
    d = BundleDraft()
    for k in FRAGMENT_KINDS:
        d.add(k, {"kind": k})
    jsonschema.validate(instance=d.to_binding(), schema=sch)


def test_free_form_ids_are_refused_with_a_pointer_to_the_helper():
    """The schemas namespace ids; a caller must not discover that at validation time."""
    with pytest.raises(LawfulError, match="use claim_id"):
        measurement_claim(claim_id_="c1", claim="a long enough claim here",
                          receipt_ref="sha256:" + "a" * 64)
    with pytest.raises(LawfulError, match="use circuit_id"):
        circuit_entry(circuit_id_="k1", circuit_name="n", model_ref="m",
                      discovery_evidence_ref="a", ablation_evidence_ref="b")


def test_a_claim_too_short_to_state_itself_is_refused():
    with pytest.raises(LawfulError, match="at least 10"):
        measurement_claim(claim_id_=claim_id("t"), claim="short",
                          receipt_ref="sha256:" + "a" * 64)


def test_composition_id_is_a_const_not_a_per_run_identifier():
    from noetica_impair.conformance.bundle import COMPOSITION_ID
    d = BundleDraft(composition_id="urn:made:up")
    for k in FRAGMENT_KINDS:
        d.add(k, {"kind": k})
    with pytest.raises(ValueError, match="schema const"):
        d.to_binding()
    assert BundleDraft().composition_id == COMPOSITION_ID
