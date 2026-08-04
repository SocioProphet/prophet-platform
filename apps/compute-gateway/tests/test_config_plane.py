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
        # Reset BOTH the chain cache and the tip index for the fresh store. seal() reads prev/seq
        # from _TIPS in persistence-enabled mode, so a stale tip carried from a prior durable()
        # context would give the first receipt a bogus prev and break verify(). (The restart-sim
        # test below reloads tips via receipts.hydrate() for the same reason.)
        receipts._CHAINS.clear()
        receipts._TIPS.clear()
        try:
            yield d
        finally:
            if prev is None:
                os.environ.pop("GATEWAY_STORE_DIR", None)
            else:
                os.environ["GATEWAY_STORE_DIR"] = prev
            persistence._reset_connection()
            receipts._CHAINS.clear()
            receipts._TIPS.clear()


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
        scoped = client.get("/v1/config", params={"org": "kyroga"}, headers=AUTH).json()
        assert scoped["flags"]["memory.banded"] is True


def test_scoped_reads_require_a_token_so_tenants_cannot_be_enumerated():
    """Raised in review: the open read also accepted org/model selectors, so any caller
    could fish for another tenant's snapshot by guessing identifiers."""
    with durable():
        assert client.get("/v1/config").status_code == 200, "the default scope stays open"
        assert client.get("/v1/config", params={"org": "someone-else"}).status_code == 401
        assert client.get("/v1/config", params={"model": "qwen2.5:7b"}).status_code == 401


def test_the_app_selector_is_gated_too():
    """The org/model half of this was fixed and `app` was left open, which still allowed
    enumerating any other app's snapshot by guessing the name (Copilot #1029, :292/:303)."""
    # Literal, not server.DEFAULT_APP: this must fail on the RESPONSE when the gate is
    # reverted, not on a missing attribute.
    with durable():
        assert client.get("/v1/config", params={"app": "noetica"}).status_code == 200, \
            "the default app is the open scope"
        assert client.get("/v1/config", params={"app": "someone-elses-app"}).status_code == 401
        assert client.get("/v1/config", params={"app": "someone-elses-app"},
                          headers=AUTH).status_code == 200, "a token still reads any scope"


def test_a_scoped_read_fails_closed_when_no_token_is_configured():
    """The hand-rolled check compared against GATEWAY_TOKEN directly, so an UNCONFIGURED
    gateway ("" != "" is False) authenticated an anonymous scoped read — fail-open, the
    inverse of the 503 every require_token route answers."""
    with durable():
        prev = server.GATEWAY_TOKEN
        server.GATEWAY_TOKEN = ""
        try:
            r = client.get("/v1/config", params={"org": "someone-else"})
            assert r.status_code == 503, f"unconfigured gateway must refuse, got {r.status_code}"
        finally:
            server.GATEWAY_TOKEN = prev


def test_the_bearer_scheme_is_matched_case_insensitively():
    """RFC 7235 makes the scheme case-insensitive; removeprefix("Bearer ") matched exactly
    one casing and fed the whole header through as the token for every other input."""
    with durable():
        assert client.get("/v1/config", params={"org": "kyroga"},
                          headers={"Authorization": "bearer t"}).status_code == 200
        assert client.get("/v1/config", params={"org": "kyroga"},
                          headers={"Authorization": "BEARER t"}).status_code == 200
        assert client.get("/v1/config", params={"org": "kyroga"},
                          headers={"Authorization": "Basic t"}).status_code == 401, \
            "a non-Bearer scheme is not a credential"
        assert client.get("/v1/config", params={"org": "kyroga"},
                          headers={"Authorization": "t"}).status_code == 401, \
            "a raw token with no scheme is not a credential — removeprefix() accepted this"
        assert client.get("/v1/config", params={"org": "kyroga"},
                          headers={"Authorization": "Bearer\tt"}).status_code == 200, \
            "HTAB between scheme and credential is tolerated, not a confusing 401"


def test_an_empty_selector_is_still_a_selector():
    """`?model=` arrives as "" and is falsy. It collapses to the default scope today, so
    nothing leaks — but gating on truthiness would make this endpoint's security depend on
    a falsiness convention in config_plane. Gate on presence instead (Copilot on #1085)."""
    with durable():
        assert client.get("/v1/config", params={"model": ""}).status_code == 401
        assert client.get("/v1/config", params={"org": ""}).status_code == 401
        assert client.get("/v1/config", params={"model": ""}, headers=AUTH).status_code == 200


def test_a_model_kill_switch_must_be_a_real_boolean():
    """bool("false") is True — coercing a string here could flip a switch the wrong way."""
    with durable():
        r = client.post("/v1/config/set", headers=AUTH,
                        json={"name": "qwen2.5:7b", "value": "false", "kind": "model"})
        assert r.status_code == 422


def test_concurrent_mutations_cannot_seal_contradictory_receipts():
    """The read of `previous` and the write are one transaction (BEGIN IMMEDIATE); without
    it two writers both read the same prior value and the chain disagrees with itself."""
    with durable():
        first = client.post("/v1/config/set", headers=AUTH,
                            json={"name": "memory.banded", "value": True}).json()
        second = client.post("/v1/config/set", headers=AUTH,
                             json={"name": "memory.banded", "value": False}).json()
        assert first["previous"] is None and second["previous"] is True
        chain = client.get("/v1/receipts", params={"project": "config-plane"}, headers=AUTH).json()
        changes = [c for c in chain["receipts"] if c["kind"] == "config-change"]
        assert len(changes) == 2, "every change is sealed exactly once"
        assert client.get("/v1/receipts/verify", params={"project": "config-plane"},
                          headers=AUTH).json()["valid"]


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
