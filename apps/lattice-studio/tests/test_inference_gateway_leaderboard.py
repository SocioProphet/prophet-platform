from lattice_studio.inference_gateway_leaderboard import score, leaderboard, notebook_fixture
from lattice_studio.inference_gateway_board import board_catalog_entries


def test_every_entry_is_scored_and_ranked():
    lb = leaderboard()
    assert len(lb) == len(board_catalog_entries())
    assert [r["rank"] for r in lb] == list(range(1, len(lb) + 1))
    # ranks are non-increasing by score
    scores = [r["score"] for r in lb]
    assert scores == sorted(scores, reverse=True)


def test_sovereign_outranks_vendor():
    lb = {r["model_id"]: r for r in leaderboard()}
    assert lb["gemma-2-9b-it"]["score"] > lb["claude-opus-4-8"]["score"]
    # the vendor-cloud model is not #1 — the thesis, encoded
    assert lb["claude-opus-4-8"]["rank"] != 1


def test_notebook_fixture_shape():
    nb = notebook_fixture()
    assert nb["kind"] == "ModelBoardNotebook"
    assert nb["entryCount"] == len(board_catalog_entries())
    assert sum(nb["sovereigntyMix"].values()) == nb["entryCount"]
    assert nb["leaderboard"][0]["rank"] == 1


def test_scoring_reads_only_catalog_fields():
    # a minimal valid-ish entry still scores without error
    assert isinstance(score({"privacy_profile": "vendor-cloud", "latency_band": "low", "cost_band": "high"}), float)
