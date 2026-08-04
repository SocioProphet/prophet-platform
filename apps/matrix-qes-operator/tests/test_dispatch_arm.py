from __future__ import annotations

"""Tests for the ``arm`` dispatch verb added to matrix-qes-operator."""

import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.commands import OperatorCommand  # noqa: E402
from app.dispatch import DISPATCH_VERBS, DispatchResult, execute  # noqa: E402


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
# DISPATCH_VERBS registration
# ---------------------------------------------------------------------------


def test_arm_in_dispatch_verbs() -> None:
    assert "arm" in DISPATCH_VERBS


# ---------------------------------------------------------------------------
# arm status
# ---------------------------------------------------------------------------


def test_arm_status_ok(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "app.dispatch.subprocess.run",
        lambda *a, **kw: _fake_run_ok("ARM status\n  Path: /home/x/.local/state/sourceos/arm/ARM.md\n  ADR count: 8"),
    )
    result = execute(_cmd("arm", "status"))
    assert isinstance(result, DispatchResult)
    assert result.ok
    assert "ARM status" in result.body


def test_arm_status_strips_ansi(monkeypatch: pytest.MonkeyPatch) -> None:
    ansi_output = "\x1b[38;2;57;197;207mARM status\x1b[0m\n  ADR count: 8"
    monkeypatch.setattr(
        "app.dispatch.subprocess.run",
        lambda *a, **kw: _fake_run_ok(ansi_output),
    )
    result = execute(_cmd("arm", "status"))
    assert "\x1b[" not in result.body
    assert "ARM status" in result.body


def test_arm_status_default_sub_verb(monkeypatch: pytest.MonkeyPatch) -> None:
    """No sub-verb defaults to 'status'."""
    monkeypatch.setattr(
        "app.dispatch.subprocess.run",
        lambda *a, **kw: _fake_run_ok("ARM status\n  ADR count: 4"),
    )
    result = execute(_cmd("arm"))
    assert result.ok


# ---------------------------------------------------------------------------
# arm generate
# ---------------------------------------------------------------------------


def test_arm_generate_ok(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "app.dispatch.subprocess.run",
        lambda *a, **kw: _fake_run_ok("✔ ARM generated: /path/ARM.md  (8 ADRs, 20000 bytes)"),
    )
    result = execute(_cmd("arm", "generate"))
    assert result.ok
    assert "ARM generated" in result.body
    assert "8" in result.body


def test_arm_generate_fail(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "app.dispatch.subprocess.run",
        lambda *a, **kw: _fake_run_fail(stderr="ADR directory not found"),
    )
    result = execute(_cmd("arm", "generate"))
    assert not result.ok
    assert "⚠" in result.body


# ---------------------------------------------------------------------------
# arm show
# ---------------------------------------------------------------------------


def test_arm_show_no_section(monkeypatch: pytest.MonkeyPatch) -> None:
    full_arm = "# Architecture Reference Manual\n\n## ADR-030: Foo Bar\n**Status:** Accepted"
    monkeypatch.setattr(
        "app.dispatch.subprocess.run",
        lambda *a, **kw: _fake_run_ok(full_arm),
    )
    result = execute(_cmd("arm", "show"))
    assert result.ok
    assert "Architecture Reference Manual" in result.body


def test_arm_show_with_section(monkeypatch: pytest.MonkeyPatch) -> None:
    section_text = "## ADR-030: Foo Bar\n**Status:** Accepted\n\n### Context\nSome context here."
    calls: list[list[str]] = []

    def _fake(cmd: list[str], **kw: object) -> subprocess.CompletedProcess:  # type: ignore[type-arg]
        calls.append(cmd)
        return _fake_run_ok(section_text)

    monkeypatch.setattr("app.dispatch.subprocess.run", _fake)
    result = execute(_cmd("arm", "show", "ADR-030"))
    assert result.ok
    # --section flag should have been passed
    assert any("--section" in c for call in calls for c in call)


def test_arm_show_truncates_long_output(monkeypatch: pytest.MonkeyPatch) -> None:
    large = "x" * 5000
    monkeypatch.setattr(
        "app.dispatch.subprocess.run",
        lambda *a, **kw: _fake_run_ok(large),
    )
    result = execute(_cmd("arm", "show"))
    assert len(result.body) <= 4_000


# ---------------------------------------------------------------------------
# arm search
# ---------------------------------------------------------------------------


def test_arm_search_ok(monkeypatch: pytest.MonkeyPatch) -> None:
    matches = "[line 43]\n## ADR-031: Runtime transport\n**Status:** Accepted"
    monkeypatch.setattr(
        "app.dispatch.subprocess.run",
        lambda *a, **kw: _fake_run_ok(matches),
    )
    result = execute(_cmd("arm", "search", "transport"))
    assert result.ok
    assert "transport" in result.body.lower()


def test_arm_search_no_query(monkeypatch: pytest.MonkeyPatch) -> None:
    result = execute(_cmd("arm", "search"))
    assert not result.ok
    assert "Usage" in result.body


def test_arm_search_multi_word_query(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[list[str]] = []

    def _fake(cmd: list[str], **kw: object) -> subprocess.CompletedProcess:  # type: ignore[type-arg]
        calls.append(cmd)
        return _fake_run_ok("match line")

    monkeypatch.setattr("app.dispatch.subprocess.run", _fake)
    result = execute(_cmd("arm", "search", "runtime", "transport"))
    assert result.ok
    # query should be joined into a single argument
    assert any("runtime transport" in c for call in calls for c in call)


# ---------------------------------------------------------------------------
# unknown sub-verb
# ---------------------------------------------------------------------------


def test_arm_unknown_subverb(monkeypatch: pytest.MonkeyPatch) -> None:
    result = execute(_cmd("arm", "frobnicate"))
    assert not result.ok
    assert "Unknown arm sub-verb" in result.body
    assert "frobnicate" in result.body
