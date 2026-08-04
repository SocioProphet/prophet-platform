"""The workload-manifest gate: single-egress chokepoint + pinned verity, fail-closed."""
import importlib.util
import pathlib
import sys

_REPO = pathlib.Path(__file__).resolve().parents[4]
sys.path.insert(0, str(_REPO / "libs" / "python" / "mount-intent" / "src"))
_spec = importlib.util.spec_from_file_location(
    "vw", _REPO / "tools" / "validate_mount_intent_workload.py")
vw = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(vw)

A_MOUNTS = "mount-intent.socioprophet.io/mounts"
A_VERITY = "mount-intent.socioprophet.io/verity."


def _doc(anns):
    return {"kind": "Deployment", "metadata": {"name": "w", "annotations": anns}}


def test_valid_workload_passes():
    assert vw.validate_doc(_doc({
        A_MOUNTS: "out=canonical_data,corpus=curated_corpus,tmp=scratch",
        A_VERITY + "corpus": "a" * 64,
    }), "f") == []


def test_two_egress_rejected():
    e = vw.validate_doc(_doc({A_MOUNTS: "a=canonical_data,b=canonical_data"}), "f")
    assert any("at most one" in x for x in e)


def test_unpinned_curated_corpus_rejected():
    e = vw.validate_doc(_doc({A_MOUNTS: "c=curated_corpus"}), "f")
    assert any("root hash" in x for x in e)


def test_bad_verity_hash_rejected():
    e = vw.validate_doc(_doc({A_MOUNTS: "c=curated_corpus", A_VERITY + "c": "nothex"}), "f")
    assert any("64-hex" in x for x in e)


def test_unknown_intent_rejected():
    e = vw.validate_doc(_doc({A_MOUNTS: "x=bogus"}), "f")
    assert any("unknown intent" in x for x in e)


def test_unannotated_workload_skipped():
    assert vw.validate_doc(_doc({}), "f") == []
