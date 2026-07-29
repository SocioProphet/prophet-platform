"""Unit gate for the materializer core: IDEMPOTENCY IS THE ACCEPTANCE BAR.

All three doors are faked. FakeClickHouse mimics the ReplacingMergeTree contract
honestly: raw inserts KEEP duplicates (parts before a merge), `final_rows()` dedups by
event_id keeping the max-seq version (what SELECT ... FINAL / argMax returns) — so the
no-duplicates assertions test the same semantics the real table provides, not a fake's
convenience.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from prophet_materializer_clickhouse.clients import GatewayError  # noqa: E402
from prophet_materializer_clickhouse.materializer import (  # noqa: E402
    MATERIALIZER_NAME, Materializer, batch_hash, to_row,
)

# ── fakes ────────────────────────────────────────────────────────────────────


def ev_node(seq: int, nid: str, labels=None, props=None):
    return {"seq": seq, "kind": "node", "id": nid, "labels": labels or ["T"],
            "properties": props or {}, "wallTime": "2026-07-29T12:00:00.000Z"}


def ev_edge(seq: int, eid: str, label: str, frm: str, to: str, props=None):
    return {"seq": seq, "kind": "edge", "id": eid, "label": label, "from": frm,
            "to": to, "properties": props or {}, "wallTime": "2026-07-29T12:00:01.500Z"}


class FakeHellGraph:
    """Implements the /api/graph/log contract: since-exclusive, seq-ascending, limited,
    cursor = last returned seq (or since when empty), version = top of the log."""

    def __init__(self, events):
        self.events = sorted(events, key=lambda e: e["seq"])

    @property
    def version(self):
        return self.events[-1]["seq"] if self.events else 0

    def poll(self, since: int, limit: int):
        page = [e for e in self.events if e["seq"] > since][:limit]
        return {"events": page,
                "cursor": page[-1]["seq"] if page else since,
                "version": self.version}


class FakeClickHouse:
    def __init__(self):
        self.raw_rows = []          # parts as inserted — duplicates SURVIVE here
        self.checkpoints = []       # (materializer, cursor) appends
        self.schema_created = 0
        self.fail_next_checkpoint = False

    def ensure_schema(self):
        self.schema_created += 1

    def insert_events(self, rows):
        self.raw_rows.extend(rows)

    def read_checkpoint(self, materializer):
        cs = [c for m, c in self.checkpoints if m == materializer]
        return max(cs) if cs else 0

    def write_checkpoint(self, materializer, cursor):
        if self.fail_next_checkpoint:
            self.fail_next_checkpoint = False
            raise RuntimeError("simulated crash between insert and checkpoint")
        self.checkpoints.append((materializer, cursor))

    def final_rows(self):
        """ReplacingMergeTree(seq) ORDER BY event_id at FINAL: one row per event_id,
        the max-seq version wins."""
        best = {}
        for r in self.raw_rows:
            k = r["event_id"]
            if k not in best or r["seq"] >= best[k]["seq"]:
                best[k] = r
        return list(best.values())


class FakeGateway:
    def __init__(self):
        self.mints = []
        self.down = False

    def mint(self, *, from_cursor, to_cursor, row_count, batch_hash, table="hellgraph.events"):
        if self.down:
            raise GatewayError("compute-gateway unreachable: connection refused")
        receipt = {"id": f"sha256:receipt-{from_cursor}-{to_cursor}",
                   "inputs_sha": batch_hash, "prev": self.mints[-1]["receipt"]["id"] if self.mints else None}
        self.mints.append({"from_cursor": from_cursor, "to_cursor": to_cursor,
                           "row_count": row_count, "batch_hash": batch_hash,
                           "table": table, "receipt": receipt})
        return receipt


THREE_EVENTS = [
    ev_node(5, "n:a", labels=["Person", "T"], props={"name": "Ada", "n": 1}),
    ev_node(9, "n:b"),
    ev_edge(12, "EvaluationLink(...)", "KNOWS", "n:a", "n:b", props={"w": 2}),
]


def make(events=None, batch_limit=500):
    hg, ch, gw = FakeHellGraph(events or THREE_EVENTS), FakeClickHouse(), FakeGateway()
    return Materializer(hellgraph=hg, clickhouse=ch, gateway=gw, batch_limit=batch_limit), hg, ch, gw


# ── (1) happy path: rows + checkpoint + receipt, all coherent ────────────────


def test_happy_path_batch_writes_rows_checkpoint_and_receipt():
    m, hg, ch, gw = make()
    r = m.run_once()

    assert r.checkpointed and r.events == 3
    assert (r.from_cursor, r.to_cursor) == (0, 12)
    # rows landed, mapped per the contract
    assert {row["event_id"] for row in ch.raw_rows} == {"node:n:a", "node:n:b", "edge:EvaluationLink(...)"}
    node_a = next(row for row in ch.raw_rows if row["event_id"] == "node:n:a")
    assert node_a["label"] == "Person,T" and node_a["seq"] == 5
    assert node_a["properties"] == '{"n": 1, "name": "Ada"}'          # canonical (sorted) JSON
    assert node_a["wall_time"] == "2026-07-29 12:00:00.000"
    edge = next(row for row in ch.raw_rows if row["kind"] == "edge")
    assert (edge["label"], edge["from_id"], edge["to_id"]) == ("KNOWS", "n:a", "n:b")
    # checkpoint = the page cursor, written ONCE, AFTER the receipt
    assert ch.checkpoints == [(MATERIALIZER_NAME, 12)]
    # exactly one receipt, binding the cut + the batch hash over sorted event_ids
    assert len(gw.mints) == 1
    mint = gw.mints[0]
    assert (mint["from_cursor"], mint["to_cursor"], mint["row_count"]) == (0, 12, 3)
    assert mint["batch_hash"] == batch_hash([to_row(e) for e in THREE_EVENTS])
    assert r.receipt_id == mint["receipt"]["id"]


# ── (2) crash after insert, before checkpoint → rerun → ZERO duplicates ─────


def test_crash_between_insert_and_checkpoint_then_rerun_no_duplicates():
    m, hg, ch, gw = make()
    ch.fail_next_checkpoint = True

    with pytest.raises(RuntimeError):
        m.run_once()                                  # rows inserted, receipt minted, then "crash"
    assert ch.checkpoints == []                       # nothing committed
    assert len(ch.raw_rows) == 3                      # the orphaned insert is real

    r = m.run_once()                                  # restart: re-reads checkpoint 0, replays the cut
    assert r.checkpointed and ch.checkpoints == [(MATERIALIZER_NAME, 12)]

    # raw parts DO carry the duplicates (6 rows) — proving dedup does the work…
    assert len(ch.raw_rows) == 6
    # …and the FINAL view has ZERO duplicate rows: one per event_id, exact set match
    final_ids = [row["event_id"] for row in ch.final_rows()]
    assert sorted(final_ids) == sorted(set(final_ids))
    assert set(final_ids) == {"node:n:a", "node:n:b", "edge:EvaluationLink(...)"}
    # the replayed batch is the SAME cut with the SAME hash (gateway memo collapses it)
    assert [x["batch_hash"] for x in gw.mints] == [gw.mints[0]["batch_hash"]] * len(gw.mints)


def test_restart_from_older_checkpoint_is_idempotent():
    # a checkpoint REGRESSION (restored older checkpoint row) replays events already
    # materialized — the acceptance bar says the view must not grow duplicates
    m, hg, ch, gw = make()
    m.run_once()
    assert ch.read_checkpoint(MATERIALIZER_NAME) == 12

    ch.checkpoints = [(MATERIALIZER_NAME, 5)]         # rewind: an older checkpoint survives a restore
    r = m.run_once()                                  # replays seq 9, 12
    assert r.checkpointed and r.to_cursor == 12
    final_ids = [row["event_id"] for row in ch.final_rows()]
    assert sorted(final_ids) == sorted(set(final_ids))
    assert set(final_ids) == {"node:n:a", "node:n:b", "edge:EvaluationLink(...)"}


# ── (3) empty poll → no receipt, no checkpoint, no insert ───────────────────


def test_empty_poll_mints_no_receipt():
    m, hg, ch, gw = make()
    m.run_once()
    assert len(gw.mints) == 1

    r = m.run_once()                                  # caught up — nothing new
    assert not r.checkpointed and r.events == 0
    assert len(gw.mints) == 1                         # STILL one — no heartbeat receipts
    assert ch.checkpoints == [(MATERIALIZER_NAME, 12)]
    assert len(ch.raw_rows) == 3
    assert r.lag == 0


# ── (4) gateway unreachable → NOT checkpointed (fail-closed), then retried ──


def test_gateway_down_fails_closed_and_batch_retries():
    m, hg, ch, gw = make()
    gw.down = True

    with pytest.raises(GatewayError):
        m.run_once()
    assert ch.checkpoints == []                       # the unattested cut was NOT committed

    gw.down = False
    r = m.run_once()                                  # same cut, retried in full
    assert r.checkpointed and r.to_cursor == 12
    assert len(gw.mints) == 1 and gw.mints[0]["from_cursor"] == 0
    final_ids = [row["event_id"] for row in ch.final_rows()]
    assert sorted(final_ids) == sorted(set(final_ids))  # and still no duplicates


# ── batching + mapping details ──────────────────────────────────────────────


def test_batch_limit_pages_the_backlog_one_receipt_per_batch():
    m, hg, ch, gw = make(batch_limit=2)
    r1 = m.run_once()
    assert (r1.from_cursor, r1.to_cursor, r1.events) == (0, 9, 2)
    assert r1.lag == 12 - 9
    r2 = m.run_once()
    assert (r2.from_cursor, r2.to_cursor, r2.events) == (9, 12, 1)
    assert ch.checkpoints == [(MATERIALIZER_NAME, 9), (MATERIALIZER_NAME, 12)]
    assert [x["to_cursor"] for x in gw.mints] == [9, 12]
    assert len(ch.final_rows()) == 3


def test_batch_hash_is_order_independent_and_content_bound():
    rows_a = [to_row(e) for e in THREE_EVENTS]
    rows_b = [to_row(e) for e in reversed(THREE_EVENTS)]
    assert batch_hash(rows_a) == batch_hash(rows_b)
    assert batch_hash(rows_a) != batch_hash(rows_a[:2])
    assert batch_hash(rows_a).startswith("sha256:")


def test_to_row_handles_malformed_walltime_without_dropping_the_event():
    row = to_row({"seq": 3, "kind": "node", "id": "x", "labels": [], "properties": {},
                  "wallTime": "not-a-timestamp"})
    assert row["wall_time"] == "1970-01-01 00:00:00.000"
    assert row["event_id"] == "node:x" and row["label"] == ""
