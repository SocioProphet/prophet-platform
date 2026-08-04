from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.commands import OperatorCommand, is_dispatch_verb  # noqa: E402
from app.dispatch import DispatchResult, execute  # noqa: E402


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _cmd(verb: str, *args: str) -> OperatorCommand:
    return OperatorCommand(
        verb=verb,
        args=list(args),
        actor="@ops:example.org",
        room_id="!room:example.org",
        thread_id="$thread1",
    )


def _fake_run_ok(stdout: str = "ok output", stderr: str = "") -> subprocess.CompletedProcess:  # type: ignore[type-arg]
    return subprocess.CompletedProcess(args=[], returncode=0, stdout=stdout, stderr=stderr)


def _fake_run_fail(stdout: str = "", stderr: str = "error text") -> subprocess.CompletedProcess:  # type: ignore[type-arg]
    return subprocess.CompletedProcess(args=[], returncode=1, stdout=stdout, stderr=stderr)


# ---------------------------------------------------------------------------
# is_dispatch_verb
# ---------------------------------------------------------------------------


def test_is_dispatch_verb_true() -> None:
    for verb in ("cloudshell", "ctx", "csh", "doc", "git", "k3s", "mesh", "note", "noe", "runbook", "tunnel", "wormhole"):
        assert is_dispatch_verb(verb), f"Expected {verb!r} to be a dispatch verb"


def test_is_dispatch_verb_false() -> None:
    for verb in ("ack", "investigate", "resolve", "close", "reopen"):
        assert not is_dispatch_verb(verb), f"Expected {verb!r} NOT to be a dispatch verb"


# ---------------------------------------------------------------------------
# cloudshell verb
# ---------------------------------------------------------------------------


def test_cloudshell_status_ok(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "app.dispatch.subprocess.run",
        lambda *a, **kw: _fake_run_ok("tunnel is UP"),
    )
    result = execute(_cmd("cloudshell", "status"))
    assert isinstance(result, DispatchResult)
    assert result.ok
    assert "tunnel is UP" in result.body


def test_cloudshell_status_default(monkeypatch: pytest.MonkeyPatch) -> None:
    """No sub-verb defaults to 'status'."""
    monkeypatch.setattr(
        "app.dispatch.subprocess.run",
        lambda *a, **kw: _fake_run_ok("tunnel is DOWN"),
    )
    result = execute(_cmd("cloudshell"))
    assert result.ok


def test_cloudshell_unknown_subverb() -> None:
    result = execute(_cmd("cloudshell", "restart"))
    assert not result.ok
    assert "Unknown cloudshell sub-verb" in result.body
    assert "⚠" in result.body


# ---------------------------------------------------------------------------
# k3s verb
# ---------------------------------------------------------------------------


def test_k3s_wraps_output_in_code_block(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "app.dispatch.subprocess.run",
        lambda *a, **kw: _fake_run_ok("NAME   READY\nnode1  True"),
    )
    result = execute(_cmd("k3s", "get", "nodes"))
    assert isinstance(result, DispatchResult)
    assert result.ok
    assert result.body.startswith("```")
    assert "node1" in result.body


def test_k3s_error_prefixed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "app.dispatch.subprocess.run",
        lambda *a, **kw: _fake_run_fail(stderr="connection refused"),
    )
    result = execute(_cmd("k3s", "get", "pods"))
    assert not result.ok
    assert "⚠" in result.body


def test_k3s_no_args() -> None:
    result = execute(_cmd("k3s"))
    assert not result.ok
    assert "Usage" in result.body


# ---------------------------------------------------------------------------
# runbook verb
# ---------------------------------------------------------------------------


def test_runbook_list(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "app.dispatch.subprocess.run",
        lambda *a, **kw: _fake_run_ok("runbook-a\nrunbook-b"),
    )
    result = execute(_cmd("runbook", "list"))
    assert result.ok
    assert "runbook-a" in result.body


def test_runbook_search(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "app.dispatch.subprocess.run",
        lambda *a, **kw: _fake_run_ok("found: db-restart"),
    )
    result = execute(_cmd("runbook", "search", "database"))
    assert result.ok
    assert "db-restart" in result.body


def test_runbook_show(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "app.dispatch.subprocess.run",
        lambda *a, **kw: _fake_run_ok("# DB Restart Runbook\nStep 1…"),
    )
    result = execute(_cmd("runbook", "show", "db-restart"))
    assert result.ok


def test_runbook_unknown_sub() -> None:
    result = execute(_cmd("runbook", "delete"))
    assert not result.ok
    assert "Unknown runbook sub-verb" in result.body


def test_runbook_search_missing_query() -> None:
    result = execute(_cmd("runbook", "search"))
    assert not result.ok
    assert "Usage" in result.body


# ---------------------------------------------------------------------------
# noe verb
# ---------------------------------------------------------------------------


def test_noe_ok(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "app.dispatch.subprocess.run",
        lambda *a, **kw: _fake_run_ok("Noetica response: the answer is 42"),
    )
    result = execute(_cmd("noe", "what", "is", "the", "answer"))
    assert result.ok
    assert "42" in result.body


def test_noe_no_query() -> None:
    result = execute(_cmd("noe"))
    assert not result.ok
    assert "Usage" in result.body


# ---------------------------------------------------------------------------
# wormhole verb — binary missing
# ---------------------------------------------------------------------------


def test_wormhole_send_binary_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.wormhole.shutil.which", lambda *a, **kw: None)
    monkeypatch.setattr("app.wormhole.Path.exists", lambda self: False)

    result = execute(_cmd("wormhole", "send", "/tmp/file.txt"))
    assert not result.ok
    assert "magic-wormhole" in result.body or "wormhole" in result.body.lower()


def test_wormhole_recv_binary_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.wormhole.shutil.which", lambda *a, **kw: None)
    monkeypatch.setattr("app.wormhole.Path.exists", lambda self: False)

    result = execute(_cmd("wormhole", "recv", "3-guitar-tango"))
    assert not result.ok
    assert "magic-wormhole" in result.body or "wormhole" in result.body.lower()


def test_wormhole_send_returns_code(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.wormhole.shutil.which", lambda *a, **kw: "/usr/local/bin/wormhole")
    monkeypatch.setattr(
        "app.wormhole.subprocess.run",
        lambda *a, **kw: _fake_run_ok("Sending file…\nwormhole receive 7-guitar-tango\n"),
    )

    result = execute(_cmd("wormhole", "send", "/tmp/report.pdf"))
    assert result.ok
    assert "7-guitar-tango" in result.body


def test_wormhole_recv_missing_code() -> None:
    result = execute(_cmd("wormhole", "recv"))
    assert not result.ok
    assert "Usage" in result.body


def test_wormhole_unknown_sub() -> None:
    result = execute(_cmd("wormhole", "list"))
    assert not result.ok
    assert "Unknown wormhole sub-verb" in result.body


def test_wormhole_pipe_calls_send_text(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: list[str] = []

    def fake_send_text(text: str, timeout: int = 30) -> str:
        captured.append(text)
        return "5-piano-hotel"

    monkeypatch.setattr("app.wormhole.shutil.which", lambda *a, **kw: "/usr/local/bin/wormhole")
    monkeypatch.setattr("app.dispatch.wormhole.send_text", fake_send_text)

    result = execute(_cmd("wormhole", "pipe", "hello", "world"))
    assert result.ok
    assert "5-piano-hotel" in result.body
    assert captured == ["hello world"]


def test_wormhole_pipe_no_text() -> None:
    result = execute(_cmd("wormhole", "pipe"))
    assert not result.ok
    assert "Usage" in result.body


# ---------------------------------------------------------------------------
# git verb
# ---------------------------------------------------------------------------


def test_git_log_returns_oneline(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "app.dispatch.subprocess.run",
        lambda *a, **kw: _fake_run_ok("abc1234 commit one\ndef5678 commit two"),
    )
    result = execute(_cmd("git", "log"))
    assert result.ok
    assert "abc1234" in result.body
    assert "def5678" in result.body


def test_git_log_custom_n(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[list[str]] = []

    def fake_run(cmd: list[str], **kw: object) -> subprocess.CompletedProcess:  # type: ignore[type-arg]
        calls.append(cmd)
        return _fake_run_ok("a1b2c3d first")

    monkeypatch.setattr("app.dispatch.subprocess.run", fake_run)
    result = execute(_cmd("git", "log", "5"))
    assert result.ok
    assert any("-n5" in part for part in calls[0])


def test_git_diff_wraps_in_fence(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "app.dispatch.subprocess.run",
        lambda *a, **kw: _fake_run_ok("- old line\n+ new line"),
    )
    result = execute(_cmd("git", "diff"))
    assert result.ok
    assert "```diff" in result.body
    assert "- old line" in result.body


def test_git_status_ok(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "app.dispatch.subprocess.run",
        lambda *a, **kw: _fake_run_ok("M  app/main.py\n?? scratch.txt"),
    )
    result = execute(_cmd("git", "status"))
    assert result.ok
    assert "main.py" in result.body


def test_git_unknown_sub() -> None:
    result = execute(_cmd("git", "push"))
    assert not result.ok
    assert "Unknown git sub-verb" in result.body


# ---------------------------------------------------------------------------
# mesh verb
# ---------------------------------------------------------------------------


def test_mesh_parses_jsonl(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    mesh_file = tmp_path / "context.jsonl"
    mesh_file.write_text(
        json.dumps({"ts": "2025-01-01T12:00:00Z", "type": "note", "title": "first note"}) + "\n"
        + json.dumps({"ts": "2025-01-02T13:00:00Z", "type": "event", "title": "second event"}) + "\n"
    )
    monkeypatch.setattr("app.dispatch._mesh_jsonl_path", lambda: mesh_file)

    result = execute(_cmd("mesh"))
    assert result.ok
    assert "note: first note" in result.body
    assert "event: second event" in result.body
    assert "2025-01-01T12:00" in result.body


def test_mesh_file_missing(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr("app.dispatch._mesh_jsonl_path", lambda: tmp_path / "nonexistent.jsonl")

    result = execute(_cmd("mesh"))
    assert not result.ok
    assert "mesh JSONL not found" in result.body


def test_mesh_custom_n(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    mesh_file = tmp_path / "context.jsonl"
    lines = [json.dumps({"ts": f"2025-01-{i:02d}T00:00:00Z", "type": "t", "title": f"item {i}"}) for i in range(1, 11)]
    mesh_file.write_text("\n".join(lines) + "\n")
    monkeypatch.setattr("app.dispatch._mesh_jsonl_path", lambda: mesh_file)

    result = execute(_cmd("mesh", "3"))
    assert result.ok
    # Only last 3 items (8, 9, 10)
    assert "item 10" in result.body
    assert "item 9" in result.body
    assert "item 8" in result.body
    # items 1-7 must not appear (use word-boundary check via " item 7")
    for absent in range(1, 8):
        assert f"item {absent}\n" not in result.body + "\n", f"item {absent} should not be in output"


# ---------------------------------------------------------------------------
# note verb
# ---------------------------------------------------------------------------


def test_note_list_returns_sorted(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    notes_dir = tmp_path / "notes"
    notes_dir.mkdir()
    # Create files with different mtimes
    older = notes_dir / "older.md"
    older.write_text("old content")
    newer = notes_dir / "newer.md"
    newer.write_text("new content")
    # Touch newer to ensure it has a later mtime
    import time
    time.sleep(0.01)
    newer.touch()

    monkeypatch.setattr("app.dispatch._notes_dir", lambda: notes_dir)

    result = execute(_cmd("note", "list"))
    assert result.ok
    assert "newer.md" in result.body
    assert "older.md" in result.body
    # newer should appear before older
    assert result.body.index("newer.md") < result.body.index("older.md")


def test_note_list_empty(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    notes_dir = tmp_path / "notes"
    notes_dir.mkdir()
    monkeypatch.setattr("app.dispatch._notes_dir", lambda: notes_dir)

    result = execute(_cmd("note", "list"))
    assert result.ok
    assert "no notes" in result.body


def test_note_show_returns_content(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    notes_dir = tmp_path / "notes"
    notes_dir.mkdir()
    note = notes_dir / "myslug.md"
    note.write_text("# My Note\nSome content here.")
    monkeypatch.setattr("app.dispatch._notes_dir", lambda: notes_dir)

    result = execute(_cmd("note", "show", "myslug"))
    assert result.ok
    assert "My Note" in result.body
    assert "Some content here." in result.body


def test_note_show_with_md_extension(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    notes_dir = tmp_path / "notes"
    notes_dir.mkdir()
    note = notes_dir / "myslug.md"
    note.write_text("content")
    monkeypatch.setattr("app.dispatch._notes_dir", lambda: notes_dir)

    # Passing slug without .md should still find the file
    result = execute(_cmd("note", "show", "myslug"))
    assert result.ok


def test_note_show_not_found(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    notes_dir = tmp_path / "notes"
    notes_dir.mkdir()
    monkeypatch.setattr("app.dispatch._notes_dir", lambda: notes_dir)

    result = execute(_cmd("note", "show", "ghost"))
    assert not result.ok
    assert "not found" in result.body.lower()


def test_note_show_missing_slug() -> None:
    result = execute(_cmd("note", "show"))
    assert not result.ok
    assert "Usage" in result.body


# ---------------------------------------------------------------------------
# csh verb
# ---------------------------------------------------------------------------


def test_csh_runs_tunnel_exec(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[list[str]] = []

    def fake_run(cmd: list[str], **kw: object) -> subprocess.CompletedProcess:  # type: ignore[type-arg]
        calls.append(cmd)
        return _fake_run_ok("remote output")

    monkeypatch.setattr("app.dispatch.subprocess.run", fake_run)
    result = execute(_cmd("csh", "ls", "-la"))
    assert result.ok
    assert "remote output" in result.body
    assert calls[0] == ["turtle-ssh-tunnel", "exec", "ls", "-la"]


def test_csh_binary_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    import subprocess as sp

    def fake_run(cmd: list[str], **kw: object) -> subprocess.CompletedProcess:  # type: ignore[type-arg]
        raise FileNotFoundError("turtle-ssh-tunnel")

    monkeypatch.setattr("app.dispatch.subprocess.run", fake_run)
    result = execute(_cmd("csh", "ls"))
    assert not result.ok
    assert "turtle-ssh-tunnel not found" in result.body
    assert "cloudshell not configured" in result.body


def test_csh_no_args() -> None:
    result = execute(_cmd("csh"))
    assert not result.ok
    assert "Usage" in result.body


# ---------------------------------------------------------------------------
# tunnel verb
# ---------------------------------------------------------------------------


def test_tunnel_status_calls_subprocess(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[list[str]] = []

    def fake_run(cmd: list[str], **kw: object) -> subprocess.CompletedProcess:  # type: ignore[type-arg]
        calls.append(cmd)
        return _fake_run_ok("tunnel: active")

    monkeypatch.setattr("app.dispatch.subprocess.run", fake_run)
    result = execute(_cmd("tunnel", "status"))
    assert result.ok
    assert "tunnel: active" in result.body
    assert calls[0] == ["turtle-ssh-tunnel", "status"]


def test_tunnel_start_calls_subprocess(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[list[str]] = []

    def fake_run(cmd: list[str], **kw: object) -> subprocess.CompletedProcess:  # type: ignore[type-arg]
        calls.append(cmd)
        return _fake_run_ok("started")

    monkeypatch.setattr("app.dispatch.subprocess.run", fake_run)
    result = execute(_cmd("tunnel", "start"))
    assert result.ok
    assert calls[0] == ["turtle-ssh-tunnel", "tunnel", "start"]


def test_tunnel_default_is_status(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[list[str]] = []

    def fake_run(cmd: list[str], **kw: object) -> subprocess.CompletedProcess:  # type: ignore[type-arg]
        calls.append(cmd)
        return _fake_run_ok("ok")

    monkeypatch.setattr("app.dispatch.subprocess.run", fake_run)
    result = execute(_cmd("tunnel"))
    assert result.ok
    assert calls[0][0:2] == ["turtle-ssh-tunnel", "status"]


def test_tunnel_unknown_sub() -> None:
    result = execute(_cmd("tunnel", "stop"))
    assert not result.ok
    assert "Unknown tunnel sub-verb" in result.body


# ---------------------------------------------------------------------------
# ctx verb
# ---------------------------------------------------------------------------


def test_ctx_reads_active_json(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    ctx_file = tmp_path / "active.json"
    ctx_file.write_text(json.dumps({"project": "prophet-platform", "branch": "main", "env": "prod"}))
    monkeypatch.setattr("app.dispatch._ctx_json_path", lambda: ctx_file)

    result = execute(_cmd("ctx"))
    assert result.ok
    assert "project: prophet-platform" in result.body
    assert "branch: main" in result.body
    assert "env: prod" in result.body


def test_ctx_missing_file(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr("app.dispatch._ctx_json_path", lambda: tmp_path / "no-active.json")

    result = execute(_cmd("ctx"))
    assert not result.ok
    assert "No active context" in result.body


# ---------------------------------------------------------------------------
# Output truncation
# ---------------------------------------------------------------------------


def test_output_truncated(monkeypatch: pytest.MonkeyPatch) -> None:
    long_output = "x" * 10_000
    monkeypatch.setattr(
        "app.dispatch.subprocess.run",
        lambda *a, **kw: _fake_run_ok(long_output),
    )
    result = execute(_cmd("cloudshell", "status"))
    assert len(result.body) <= 4_000
    assert result.body.endswith("…[truncated]")


# ---------------------------------------------------------------------------
# Unknown verb
# ---------------------------------------------------------------------------


def test_unknown_dispatch_verb() -> None:
    result = execute(_cmd("bogus"))
    assert not result.ok
    assert "bogus" in result.body


# ---------------------------------------------------------------------------
# doc verb
# ---------------------------------------------------------------------------


def test_doc_feedback_ok(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "app.dispatch.subprocess.run",
        lambda *a, **kw: _fake_run_ok("✓ Feedback recorded — question on 'ADR-031'"),
    )
    result = execute(_cmd("doc", "feedback", "ADR-031", "question", "What happens on tunnel drop?"))
    assert isinstance(result, DispatchResult)
    assert result.ok
    assert "Feedback recorded" in result.body


def test_doc_feedback_missing_args() -> None:
    result = execute(_cmd("doc", "feedback", "ADR-031"))
    assert not result.ok
    assert "Usage" in result.body


def test_doc_list_ok(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "app.dispatch.subprocess.run",
        lambda *a, **kw: _fake_run_ok("2026-08-04T12  question  ADR-031  — tunnel drop?"),
    )
    result = execute(_cmd("doc", "list", "ADR-031"))
    assert result.ok
    assert "ADR-031" in result.body


def test_doc_faq_ok(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "app.dispatch.subprocess.run",
        lambda *a, **kw: _fake_run_ok("── ADR-031\n   Q: tunnel drop?\n   A: It reconnects."),
    )
    result = execute(_cmd("doc", "faq"))
    assert result.ok
    assert "ADR-031" in result.body


def test_doc_distill_fires_async(monkeypatch: pytest.MonkeyPatch) -> None:
    launched: list[list[str]] = []

    class _FakePopen:
        def __init__(self, cmd: list[str], **kw: object) -> None:
            launched.append(cmd)

    monkeypatch.setattr("app.dispatch.subprocess.Popen", _FakePopen)
    result = execute(_cmd("doc", "distill", "ADR-031"))
    assert result.ok
    assert "⏳" in result.body
    assert len(launched) == 1


def test_doc_unknown_subverb() -> None:
    result = execute(_cmd("doc", "frobnicate"))
    assert not result.ok
    assert "Unknown doc sub-verb" in result.body
    assert "⚠" in result.body
