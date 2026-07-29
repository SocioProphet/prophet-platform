"""The sovereign flag plane's server half — and the property that distinguishes it from
every commercial flag service: a flag change is SEALED, so it is provable rather than
merely logged."""
import contextlib
import importlib
import os
import tempfile

os.environ["GATEWAY_TOKEN"] = "t"
os.environ["COMPUTE_ENTITLEMENTS"] = "demo"
os.environ["GATEWAY_WRITE_PROVENANCE"] = "false"

from fastapi.testclient import TestClient  # noqa: E402

from compute_gateway import config_plane, engine, persistence, receipts, server, zerotrust  # noqa: E402

importlib.reload(zerotrust)
importlib.reload(engine)
importlib.reload(server)
client = TestClient(server.app)
AUTH = {"Authorization": "Bearer t"}


@contextlib.contextmanager
def durable():
    prev = os.environ.get("GATEWAY_STORE_DIR")
    with tempfile.TemporaryDirectory() as d:
        os.environ["GATEWAY_STORE_DIR"] = d
        persistence._reset_connection()
        receipts._CHAINS.clear()
        try:
            yield d
        finally:
            if prev is None:
                os.environ.pop("GATEWAY_STORE_DIR", None)
            else:
                os.environ["GATEWAY_STORE_DIR"] = prev
            persistence._reset_connection()
            receipts._CHAINS.clear()


def test_reads_are_open_so_an_outage_cannot_be_made_worse():
    # No token: a client that cannot READ would be pushed onto a stale cache for no gain.
    assert client.get("/v1/config").status_code == 200


def test_mutation_requires_a_token():
    assert client.post("/v1/config/set", json={"name": "memory.banded", "value": True}).status_code == 401


def test_a_flag_change_is_sealed_and_the_receipt_verifies():
    with durable():
        r = client.post("/v1/config/set", headers=AUTH,
                        json={"name": "memory.banded", "value": True, "actor": "michael"}).json()
        assert r["value"] is True and r["previous"] is None
        assert r["receipt"].startswith("sha256:"), "the change IS a receipt, not a log line"

        chain = client.get("/v1/receipts", params={"project": "config-plane"}, headers=AUTH).json()
        sealed = [c for c in chain["receipts"] if c["kind"] == "config-change"]
        assert len(sealed) == 1
        assert sealed[0]["actor"] == "michael"
        assert sealed[0]["epistemic_status"] == "attested", "a human flipped it — that is attested"
        assert client.get("/v1/receipts/verify", params={"project": "config-plane"},
                          headers=AUTH).json()["valid"]


def test_the_receipt_records_what_it_changed_FROM():
    with durable():
        client.post("/v1/config/set", headers=AUTH, json={"name": "memory.banded", "value": True})
        second = client.post("/v1/config/set", headers=AUTH,
                             json={"name": "memory.banded", "value": False}).json()
        assert second["previous"] is True, "the prior value is carried, so a flip is reconstructable"


def test_the_snapshot_serves_what_was_set():
    with durable():
        client.post("/v1/config/set", headers=AUTH, json={"name": "federation.enabled", "value": True})
        snap = client.get("/v1/config").json()
        assert snap["flags"]["federation.enabled"] is True
        assert snap["served"] is True


def test_a_per_model_kill_switch_disables_a_model_without_a_release():
    with durable():
        client.post("/v1/config/set", headers=AUTH,
                    json={"name": "qwen2.5:7b", "value": False, "kind": "model"})
        assert client.get("/v1/config").json()["models"]["qwen2.5:7b"] is False


def test_unknown_flags_are_refused_so_the_plane_cannot_invent_authority():
    with durable():
        r = client.post("/v1/config/set", headers=AUTH,
                        json={"name": "capability.invented", "value": True})
        assert r.status_code == 422, "a typo must not quietly create a flag nothing honours"


def test_a_more_specific_scope_overrides_the_app_default():
    with durable():
        client.post("/v1/config/set", headers=AUTH, json={"name": "memory.banded", "value": False})
        client.post("/v1/config/set", headers=AUTH,
                    json={"name": "memory.banded", "value": True, "org": "kyroga"})
        assert client.get("/v1/config").json()["flags"]["memory.banded"] is False
        assert client.get("/v1/config", params={"org": "kyroga"}).json()["flags"]["memory.banded"] is True


def test_state_survives_a_restart_so_a_kill_switch_cannot_silently_revert():
    with durable():
        client.post("/v1/config/set", headers=AUTH, json={"name": "voice.wake_word", "value": False})
        persistence._reset_connection()          # simulate a pod restart
        receipts._CHAINS.clear()
        receipts.hydrate()
        assert client.get("/v1/config").json()["flags"]["voice.wake_word"] is False


def test_history_carries_the_receipt_that_set_each_value():
    with durable():
        client.post("/v1/config/set", headers=AUTH,
                    json={"name": "memory.banded", "value": True, "actor": "gus"})
        entries = client.get("/v1/config/history", headers=AUTH).json()["entries"]
        assert entries and entries[0]["actor"] == "gus"
        assert entries[0]["receipt"].startswith("sha256:")


def test_history_requires_a_token():
    assert client.get("/v1/config/history").status_code == 401


def test_without_durable_storage_the_plane_refuses_to_mutate_rather_than_lie():
    prev = os.environ.pop("GATEWAY_STORE_DIR", None)
    persistence._reset_connection()
    try:
        r = client.post("/v1/config/set", headers=AUTH, json={"name": "memory.banded", "value": True})
        assert r.status_code == 503, "an unpersisted kill-switch would revert on restart — refuse instead"
        assert client.get("/v1/config").json()["served"] is False, "and reads say so honestly"
    finally:
        if prev is not None:
            os.environ["GATEWAY_STORE_DIR"] = prev
        persistence._reset_connection()


def test_scope_chain_is_general_to_specific():
    chain = config_plane._scope_chain("noetica", "m", "o")
    assert chain[0] == config_plane.scope_key("noetica")
    assert chain[-1] == config_plane.scope_key("noetica", "m", "o")
