"""Durability: receipts and content-addressed artifacts survive a restart.

The whole point of the proof spine is that it outlives the process. These tests seal a
chain and store blobs against a real SQLite file, then SIMULATE a restart (drop the
in-memory caches + the db handle, re-hydrate) and assert the chain still verifies, the
blobs still resolve, and the data-lineage index is intact. With GATEWAY_STORE_DIR unset
the stores are pure in-memory, so the rest of the suite is unaffected."""
import contextlib
import importlib
import os
import tempfile

from compute_gateway import artifacts, persistence, receipts
from compute_gateway.contract import EpistemicStatus  # noqa: F401  (documents the seal contract)


@contextlib.contextmanager
def durable_store():
    """Point the stores at a fresh SQLite dir and hydrate; restore in-memory-only after."""
    prev = os.environ.get("GATEWAY_STORE_DIR")
    with tempfile.TemporaryDirectory() as d:
        os.environ["GATEWAY_STORE_DIR"] = d
        persistence._reset_connection()
        receipts._CHAINS.clear()
        artifacts._reset()
        receipts.hydrate()
        artifacts.hydrate()
        try:
            yield d
        finally:
            if prev is None:
                os.environ.pop("GATEWAY_STORE_DIR", None)
            else:
                os.environ["GATEWAY_STORE_DIR"] = prev
            persistence._reset_connection()
            receipts._CHAINS.clear()
            artifacts._reset()


def _restart() -> None:
    """Everything a fresh process loses, then boots back with: caches + db handle dropped,
    then re-hydrated from the durable file — exactly what import-time hydrate() does."""
    receipts._CHAINS.clear()
    artifacts._reset()
    persistence._reset_connection()
    receipts.hydrate()
    artifacts.hydrate()


def _seal(project: str, kind: str, out):
    return receipts.seal(project, kind=kind, backend="gateway", runtime="test",
                         inputs={"k": kind}, outputs=out, status="ok", actor="test",
                         epistemic_status="verified")


def test_receipt_chain_survives_restart_and_still_verifies():
    with durable_store():
        for i in range(3):
            _seal("ifm", f"stage{i}", {"row": i})
        before = receipts.verify("ifm")
        assert before["valid"] and before["count"] == 3 and before["signed"] >= 0
        ids = [r.id for r in receipts.chain("ifm")]

        _restart()

        after = receipts.verify("ifm")
        assert after["valid"] and after["count"] == 3        # chain rebuilt from disk
        assert [r.id for r in receipts.chain("ifm")] == ids  # same ids, same order
        # prev-links reloaded intact: first has no prev, each subsequent points at the last
        ch = receipts.chain("ifm")
        assert ch[0].prev is None and ch[1].prev == ch[0].id and ch[2].prev == ch[1].id


def test_artifacts_and_lineage_index_survive_restart():
    with durable_store():
        d0, d1 = artifacts.store_outputs("rcpt-1", [{"a": 1}, {"b": 2}])
        assert artifacts.get(d0) == {"a": 1} and artifacts.get(d1) == {"b": 2}

        _restart()

        # blobs resolve from the durable backend, index rebuilt from disk
        assert artifacts.get(d0) == {"a": 1} and artifacts.get(d1) == {"b": 2}
        assert artifacts.for_receipt("rcpt-1") == [d0, d1]


def test_dedup_holds_across_restart():
    with durable_store():
        artifacts.store_outputs("rcpt-1", [{"same": 1}])
        _restart()
        # identical content re-stored after restart is a dedup hit, not a second blob
        newly = artifacts._backend.put(artifacts.digest({"same": 1}), {"same": 1})
        assert newly is False


def test_disabled_by_default_is_pure_memory():
    # no GATEWAY_STORE_DIR ⇒ persistence is a no-op; the rest of the suite relies on this
    os.environ.pop("GATEWAY_STORE_DIR", None)
    persistence._reset_connection()
    assert persistence.enabled() is False
    assert persistence.load_receipts() == {} and persistence.load_index() == {}


def test_sql_load_dsn_follows_store_dir():
    from compute_gateway import adapters
    prev_dir = os.environ.get("GATEWAY_STORE_DIR")
    prev_dsn = os.environ.pop("SQL_LOAD_DSN", None)   # an explicit DSN wins by design; clear it here
    try:
        os.environ["GATEWAY_STORE_DIR"] = "/data/gw"
        importlib.reload(adapters)
        assert adapters.SQL_LOAD_DSN == "sqlite:////data/gw/ifm_extract.db"  # off /tmp, on the PVC
        os.environ.pop("GATEWAY_STORE_DIR")
        importlib.reload(adapters)
        assert adapters.SQL_LOAD_DSN == "sqlite:////tmp/ifm_extract.db"      # ephemeral fallback
    finally:
        if prev_dir is not None:
            os.environ["GATEWAY_STORE_DIR"] = prev_dir
        else:
            os.environ.pop("GATEWAY_STORE_DIR", None)
        if prev_dsn is not None:
            os.environ["SQL_LOAD_DSN"] = prev_dsn
        importlib.reload(adapters)
