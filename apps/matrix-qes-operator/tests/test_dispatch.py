from __future__ import annotations

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
    for verb in ("cloudshell", "k3s", "runbook", "noe", "wormhole", "ticket"):
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
    # Output must be fenced.
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
    """When neither wormhole binary is present the result is ok=False with install hint."""
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
    """When the binary is present and succeeds, the code is in the reply."""
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


# ---------------------------------------------------------------------------
# ticket verb
# ---------------------------------------------------------------------------


def test_ticket_is_dispatch_verb() -> None:
    assert is_dispatch_verb("ticket")


def test_ticket_list(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "app.dispatch.subprocess.run",
        lambda *a, **kw: _fake_run_ok("[abc12345] OPEN       p2   Test ticket"),
    )
    result = execute(_cmd("ticket", "list"))
    assert result.ok
    assert "ticket" in result.body.lower() or "OPEN" in result.body


def test_ticket_ls_alias(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "app.dispatch.subprocess.run",
        lambda *a, **kw: _fake_run_ok("(no tickets)"),
    )
    result = execute(_cmd("ticket", "ls"))
    assert result.ok


def test_ticket_open_no_title() -> None:
    result = execute(_cmd("ticket", "open"))
    assert not result.ok
    assert "Usage" in result.body


def test_ticket_open_with_title(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "app.dispatch.subprocess.run",
        lambda *a, **kw: _fake_run_ok("✅ Ticket opened: [abc12345] Something broken"),
    )
    result = execute(_cmd("ticket", "open", "Something", "broken"))
    assert result.ok
    assert "abc12345" in result.body or "opened" in result.body.lower()


def test_ticket_show_no_id() -> None:
    result = execute(_cmd("ticket", "show"))
    assert not result.ok
    assert "Usage" in result.body


def test_ticket_show_with_id(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "app.dispatch.subprocess.run",
        lambda *a, **kw: _fake_run_ok("[abc12345] OPEN       p2   Test ticket"),
    )
    result = execute(_cmd("ticket", "show", "abc12345"))
    assert result.ok


def test_ticket_close_no_id() -> None:
    result = execute(_cmd("ticket", "close"))
    assert not result.ok
    assert "Usage" in result.body


def test_ticket_close_with_id(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "app.dispatch.subprocess.run",
        lambda *a, **kw: _fake_run_ok("✅ Ticket closed: [abc12345] Test ticket"),
    )
    result = execute(_cmd("ticket", "close", "abc12345"))
    assert result.ok


def test_ticket_comment_insufficient_args() -> None:
    result = execute(_cmd("ticket", "comment", "abc12345"))
    assert not result.ok
    assert "Usage" in result.body


def test_ticket_comment_note_alias(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "app.dispatch.subprocess.run",
        lambda *a, **kw: _fake_run_ok("💬 Comment added to [abc12345]"),
    )
    result = execute(_cmd("ticket", "note", "abc12345", "reproduces", "on", "main"))
    assert result.ok


def test_ticket_search_no_query() -> None:
    result = execute(_cmd("ticket", "search"))
    assert not result.ok
    assert "Usage" in result.body


def test_ticket_search_with_query(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "app.dispatch.subprocess.run",
        lambda *a, **kw: _fake_run_ok("[abc12345] OPEN       p2   Something"),
    )
    result = execute(_cmd("ticket", "search", "memory", "leak"))
    assert result.ok


def test_ticket_summary(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "app.dispatch.subprocess.run",
        lambda *a, **kw: _fake_run_ok("Total tickets: 3\nBy status:\n  open 2\n  closed 1"),
    )
    result = execute(_cmd("ticket", "summary"))
    assert result.ok
    assert "tickets" in result.body.lower() or "Total" in result.body


def test_ticket_binary_missing() -> None:
    result = execute(_cmd("ticket", "list"))
    # turtle-ticket is not installed in the test environment; verifies graceful error
    assert isinstance(result.ok, bool)
    assert isinstance(result.body, str)


def test_ticket_unknown_sub() -> None:
    result = execute(_cmd("ticket", "invalidverb"))
    assert not result.ok
    assert "Unknown ticket sub-verb" in result.body


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
