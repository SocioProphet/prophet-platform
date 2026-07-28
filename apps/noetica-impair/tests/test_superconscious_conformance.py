"""Emitted harness documents validate against superconscious's REAL schema files.

Not a copy of the schemas, not a hand-written stub -- the tests load
``~/dev/superconscious/schemas/interpretability/*.v0.json`` directly, so a schema bump
upstream fails here rather than silently producing invalid governance records. They
skip (not fail) when that repo is absent, so the rig stays standalone.
"""

from __future__ import annotations

import pytest

jsonschema = pytest.importorskip("jsonschema")

from noetica_impair.conformance import superconscious as sc
from noetica_impair.models import registry
from noetica_impair.provenance.features import FeatureArtifact
from noetica_impair.substances import presets as P
from noetica_impair.substances.schema import compile_preset

from noetica_impair.conformance import schema_source

SOURCE = schema_source.resolve()

pytestmark = pytest.mark.skipif(
    SOURCE is None,
    reason="no interpretability schemas found (Noetica vendored copy or superconscious checkout)",
)


def load_schema(name: str) -> dict:
    return SOURCE.load(name)


def validate(doc: dict, schema_name: str) -> None:
    jsonschema.validate(instance=doc, schema=load_schema(schema_name))


def test_schemas_resolve_from_noetica_vendored_copy():
    """Noetica is the integration surface: when its vendored copy is on disk, it wins.

    A live superconscious checkout is used to DETECT DRIFT, never to define truth --
    a half-rebased working tree next door must not change what Noetica considers
    valid evidence.

    The vendored copy currently lives on an unmerged branch (SocioProphet/Noetica#553),
    so a checkout on any other branch legitimately has no vendored schemas. That is a
    SKIP with a stated reason rather than a pass: falling back to upstream is a real
    weakening of the guarantee and must not be silent.
    """
    assert SOURCE is not None
    vendored = schema_source._candidate_dirs()[-2][1]   # the Noetica vendor path
    if not vendored.is_dir():
        pytest.skip(
            f"no vendored schemas at {vendored} (Noetica#553 unmerged, or the repo is "
            f"on another branch) -- resolver fell back to {SOURCE.origin!r}, which is "
            "correct behaviour but a weaker guarantee than the vendored path"
        )
    assert SOURCE.origin in {"noetica-vendored", "env-override"}, (
        f"vendored schemas exist at {vendored} but resolution picked "
        f"{SOURCE.origin!r} ({SOURCE.path}) -- precedence is broken"
    )


def test_vendored_schemas_match_their_manifest():
    """A stale schema validates happily and certifies against a moved contract."""
    rep = schema_source.verify_manifest(SOURCE)
    assert rep.ok, rep.detail


def test_vendored_schemas_have_not_drifted_from_upstream():
    rep = schema_source.drift_against_upstream(SOURCE)
    assert rep.ok, rep.detail


def test_provider_binding_validates():
    validate(sc.provider_binding(), "provider-binding")


def test_moe_routing_is_an_observable_gap_too():
    """MoE routing is missing from v0 on both axes -- one finding, not two."""
    assert "moe_router_distribution" in sc.UNREPRESENTABLE_OBSERVABLES
    assert "router_ops" in sc.UNREPRESENTABLE
    declared = sc.provider_binding()["supported_observables"]
    assert not any("router" in o or "moe" in o for o in declared)


def test_provider_binding_is_white_box_local():
    b = sc.provider_binding()
    assert b["access_mode"] == "white_box"
    assert b["governance_class"] == "local_offline"
    assert b["provider_surface"]["execution_location"] == "local_offline"


def test_source_locks_validate_for_the_sae_rig():
    meta = registry.get("gemma2-9b")
    locks = sc.source_locks(meta)
    assert len(locks) == 2, "the SAE rig must lock both the model and the SAE"
    for lock in locks:
        validate(lock, "artifact-source-lock")


def test_sae_lock_pins_the_estate_source_lock():
    """The pinned pair from superconscious's interpretability-harness doc."""
    meta = registry.get("gemma2-9b")
    assert meta.hf_id == "google/gemma-2-9b-it"
    sae = [l for l in sc.source_locks(meta) if l["artifact_kind"] == "sae"][0]
    ident = sae["artifact_identity"]
    assert ident["artifact_id"] == "google/gemma-scope-9b-it-res"
    assert ident["layer"] == 20
    assert ident["width"] == "131k"
    assert ident["average_l0"] == "average_l0_81"


def test_no_egress_declared():
    """Invariant 0.6 must be visible in the governance record, not just the code."""
    for lock in sc.source_locks(registry.get("gemma2-9b")):
        ab = lock["access_boundary"]
        assert ab["egress_required"] is False
        assert ab["download_required"] is False


def test_intervention_specs_validate():
    meta = registry.get("gemma2-9b")
    art = FeatureArtifact(version="v-test", model_key="gemma2-9b",
                          sae_release=meta.sae_release, contrast_sha="sha256:abc", top_n=4)
    art.add("hedging_caution", 20, [1, 2, 3], [0.9, 0.8, 0.7])
    art.add("consistency", 20, [4, 5], [0.6, 0.5])
    class _SAEStub:            # only needs .layer for the declaration
        layer = 20
    art.bind_sae(20, _SAEStub())

    compiled = compile_preset(P.get("ALCOHOL"), meta, seed=0, features=art)
    decl = sc.declare(compiled.interventions, meta, doses=(0.0, 0.2, 0.4, 0.6, 0.8))
    assert decl.intervention_specs, "expected at least one representable intervention"
    for spec in decl.intervention_specs:
        validate(spec, "intervention-spec")


def test_attention_and_router_ops_are_reported_as_gaps_not_misfiled():
    """v0 has no term for attention-score or router-gate edits.

    Coercing them into the nearest enum value would put a false claim into a
    governance record, so they must surface as explicit gaps.
    """
    meta = registry.get("mixtral-8x7b")
    compiled = compile_preset(P.get("ALCOHOL_MOE"), meta, seed=0, strict_limbs=False)
    decl = sc.declare(compiled.interventions, meta, doses=(0.0, 0.6))
    gap_kinds = {g.intervention_kind for g in decl.gaps}
    assert "attn_distance_decay" in gap_kinds
    assert "router_ops" in gap_kinds
    for spec in decl.intervention_specs:
        assert spec["intervention_kind"] in {
            "feature_steering", "logit_bias", "activation_addition",
        }


def test_strict_declaration_refuses_to_hide_gaps():
    meta = registry.get("mixtral-8x7b")
    compiled = compile_preset(P.get("ALCOHOL_MOE"), meta, seed=0, strict_limbs=False)
    with pytest.raises(ValueError, match="cannot express"):
        sc.declare(compiled.interventions, meta, doses=(0.0, 0.6), strict=True)


def test_dose_ladder_is_the_coefficient_schedule():
    meta = registry.get("gemma2-9b")
    compiled = compile_preset(P.get("COCAINE"), meta, seed=0, strict_limbs=False)
    decl = sc.declare(compiled.interventions, meta, doses=(0.0, 0.2, 0.4, 0.6, 0.8))
    sched = decl.intervention_specs[0]["coefficient_schedule"]
    assert sched["schedule_kind"] == "linear_sweep"
    assert sched["values"] == [0.0, 0.2, 0.4, 0.6, 0.8]


def test_feature_registry_entries_validate_and_do_not_overclaim():
    meta = registry.get("gemma2-9b")
    art = FeatureArtifact(version="v-test", model_key="gemma2-9b",
                          sae_release=meta.sae_release, contrast_sha="sha256:abc", top_n=4)
    art.add("hedging_caution", 20, [11, 12], [0.9, 0.8])
    entries = sc.feature_registry_entries(art, meta)
    assert entries
    for e in entries:
        validate(e, "feature-registry-entry")
        # Contrastive ranking yields candidates; only a causal test earns more.
        assert e["claim_status"] == "candidate_only"
        assert e["feature_identity"]["feature_kind"] == "sae_feature"
