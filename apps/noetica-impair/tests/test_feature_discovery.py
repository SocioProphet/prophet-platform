"""The §5 discovery pass and its three gates.

A feature artifact is the most dangerous output this repo produces: a list of integers
that looks authoritative, is perfectly reproducible, and carries no visible sign of
being wrong. These tests pin the gates that stand between a run and one of those.
"""

from __future__ import annotations

import json
import subprocess
import sys

import pytest
import torch

from noetica_impair.hooks.sae import SyntheticSAE
from noetica_impair.models import loaders
from noetica_impair.provenance import contrasts as C
from noetica_impair.provenance.features import (
    CONCEPTS, discover, reliability_report, residual_encoder, split_half_reliability,
)


# ── gate 1: the contrast sets ────────────────────────────────────────────────

def test_every_concept_has_a_contrast_set():
    for c in CONCEPTS:
        assert c in C.CONTRASTS, f"{c} has no contrast set, so it cannot be discovered"


@pytest.mark.parametrize("concept", sorted(C.CONTRASTS))
def test_shipped_contrast_sets_pass_the_audit(concept):
    a = C.audit(C.get(concept))
    assert a.ok, f"{concept}: " + "; ".join(a.warnings)


@pytest.mark.parametrize("concept", sorted(C.CONTRASTS))
def test_pairs_are_index_aligned_and_distinct(concept):
    cs = C.get(concept)
    assert len(cs.present) == len(cs.absent)
    for p, a in cs.pairs:
        assert p != a, "a minimal pair must actually differ"
        assert p.strip() and a.strip()


def test_audit_catches_a_length_confound():
    """The real failure this caught: long hedged sentences vs short flat ones."""
    bad = C.ContrastSet("x", "", tuple(
        (f"It might possibly be the case that item {i} is somewhat relevant here today",
         f"Item {i} is relevant") for i in range(8)))
    a = C.audit(bad)
    assert not a.ok
    assert any("length skew" in w for w in a.warnings)


def test_audit_catches_a_topic_confound():
    """Present about one domain, absent about another — the classic silent failure."""
    bad = C.ContrastSet("x", "", tuple(
        (f"The surgeon prepared the sterile operating theatre number {i}",
         f"The chef seasoned the simmering tomato sauce batch {i}") for i in range(8)))
    a = C.audit(bad)
    assert not a.ok
    assert any("lexical overlap" in w for w in a.warnings)


def test_audit_catches_too_few_pairs():
    tiny = C.ContrastSet("x", "", (("a cat sat here", "a cat ran here"),))
    assert not C.audit(tiny).ok


def test_lexical_separability_is_recorded_not_gated():
    """Natural-language concepts are lexically marked; that is a caveat, not a failure."""
    a = C.audit(C.get("self_reference"))
    assert a.ok, "a lexically-marked concept must still pass the audit"
    assert a.lexical_separability > 0.5
    assert a.marker_tokens


# ── gate 2: reliability ──────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def toy():
    return loaders.load("toy-dense", seed=3, device="cpu")


@pytest.fixture(scope="module")
def toy_sae(toy):
    d = getattr(toy.model.config, "hidden_size", None) or toy.meta.d_model
    return SyntheticSAE(d_model=d, d_sae=d * 4, layer=1, seed=3)


def test_residual_encoder_returns_one_tensor_per_prompt(toy):
    enc = residual_encoder(toy, 1)
    out = enc(["hello there", "a longer prompt with more tokens in it"])
    assert len(out) == 2
    assert all(h.dim() == 2 for h in out)
    assert out[1].shape[0] > out[0].shape[0], "no padding — real token counts differ"


def test_encoder_reads_the_layer_it_was_asked_for(toy):
    a = residual_encoder(toy, 0)(["same text"])[0]
    b = residual_encoder(toy, 2)(["same text"])[0]
    assert not torch.allclose(a, b), "different layers must give different residuals"


def test_encoder_rejects_an_out_of_range_layer(toy):
    with pytest.raises(ValueError, match="out of range"):
        residual_encoder(toy, 999)


def test_split_half_reliability_is_high_for_a_perfectly_consistent_contrast(toy, toy_sae):
    """Identical text on each side of every pair => the halves must agree."""
    enc = residual_encoder(toy, 1)
    pres = ["zzz marker text"] * 8
    absent = ["ordinary neutral text"] * 8
    r = split_half_reliability(encode_residuals=enc, sae=toy_sae, present=pres,
                               absent=absent, top_n=8, seed=0)
    assert r["checkable"]
    assert r["overlap"] == pytest.approx(1.0), "a noiseless contrast must be perfectly stable"


def test_split_half_reliability_is_low_for_noise(toy, toy_sae):
    """Random unrelated text on both sides => nothing stable to find."""
    import random
    rng = random.Random(0)
    def junk(n): return ["".join(rng.choice("abcdefg ") for _ in range(30)) for _ in range(n)]
    enc = residual_encoder(toy, 1)
    r = split_half_reliability(encode_residuals=enc, sae=toy_sae, present=junk(10),
                               absent=junk(10), top_n=16, seed=0)
    assert r["overlap"] < 0.6, f"noise scored {r['overlap']:.2f} — the gate would not fire"


def test_reliability_report_flags_unstable_concepts(toy, toy_sae):
    enc = residual_encoder(toy, 1)
    art = discover(encode_residuals=enc, sae=toy_sae, layer=1,
                   pairs=C.as_pairs(("hedging_caution",)), model_key="toy-dense",
                   sae_release=None, top_n=8)
    ok, problems = reliability_report(art, min_overlap=0.99)   # unreachable bar
    assert not ok and problems


def test_discovery_records_reliability_in_the_artifact(toy, toy_sae):
    enc = residual_encoder(toy, 1)
    art = discover(encode_residuals=enc, sae=toy_sae, layer=1,
                   pairs=C.as_pairs(("salience",)), model_key="toy-dense",
                   sae_release=None, top_n=8)
    rel = art.concepts["salience"]["reliability"]
    assert rel["checkable"] and "overlap" in rel and "rank_correlation" in rel


def test_artifact_round_trips(toy, toy_sae, tmp_path):
    enc = residual_encoder(toy, 1)
    art = discover(encode_residuals=enc, sae=toy_sae, layer=1,
                   pairs=C.as_pairs(("salience",)), model_key="toy-dense",
                   sae_release=None, top_n=8)
    p = art.save(tmp_path / "a.json")
    from noetica_impair.provenance.features import FeatureArtifact
    back = FeatureArtifact.load(p)
    assert back.version == art.version and back.contrast_sha == art.contrast_sha
    assert back.concepts["salience"]["feature_ids"] == art.concepts["salience"]["feature_ids"]


# ── the CLI gates ────────────────────────────────────────────────────────────

def run_cli(*argv: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m", "noetica_impair.experiments.discover_features", *argv],
        capture_output=True, text=True, timeout=600,
    )


def test_cli_refuses_to_write_an_unstable_artifact(tmp_path):
    """The whole point: no artifact on disk when the ranking is noise."""
    out = tmp_path / "art.json"
    r = run_cli("--model", "toy-dense", "--layer", "2", "--synthetic-sae",
                "--out", str(out), "--top-n", "8", "--seed", "1")
    assert r.returncode == 3, r.stderr[-400:]
    assert not out.exists(), "a refused run must leave nothing behind"


def test_cli_force_writes_but_records_the_failure(tmp_path):
    out = tmp_path / "art.json"
    r = run_cli("--model", "toy-dense", "--layer", "2", "--synthetic-sae",
                "--out", str(out), "--top-n", "8", "--seed", "1", "--force")
    assert r.returncode == 0, r.stderr[-400:]
    d = json.loads(out.read_text())
    assert d["gates"]["forced"] is True
    assert d["gates"]["synthetic_sae"] is True
    assert d["gates"]["reliability_ok"] is False
    assert d["gates"]["reliability_problems"], "the failure must be recorded, not dropped"


def test_lexical_control_flags_marker_token_concepts(tmp_path):
    """Concepts reliable on UNTRAINED weights are carried by their marker tokens.

    Observed for self_reference (i/my/me vs he/she/their) — reliability proves the
    ranking is consistent, not that the concept was found.
    """
    out = tmp_path / "art.json"
    r = run_cli("--model", "toy-dense", "--layer", "2", "--synthetic-sae",
                "--lexical-control", "--out", str(out), "--top-n", "8",
                "--seed", "1", "--force")
    assert r.returncode == 0, r.stderr[-400:]
    d = json.loads(out.read_text())
    ctl = d["gates"]["lexical_control"]
    assert ctl and "self_reference" in ctl
    assert d["gates"]["lexical_suspects"], "the control found nothing — it is not working"
