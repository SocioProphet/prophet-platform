from __future__ import annotations

"""Shell command dispatcher for the Matrix QES operator.

Handles non-incident ``!qes`` verbs by running local subprocesses and
returning room-safe formatted output (max 4000 chars, truncated with ``…``).
"""

import datetime
import json
import os
import subprocess
from dataclasses import dataclass
from pathlib import Path

from . import wormhole
from .commands import OperatorCommand

# ---------------------------------------------------------------------------
# Public constants
# ---------------------------------------------------------------------------

DISPATCH_VERBS: frozenset[str] = frozenset(
    {"cloudshell", "ctx", "csh", "git", "k3s", "mesh", "note", "noe", "runbook", "tunnel", "wormhole"}
)

_MAX_BODY = 4_000
_TRUNCATION_SUFFIX = "\n…[truncated]"
_SUBPROCESS_PATH = "/usr/local/bin:/opt/homebrew/bin:/usr/bin:/bin"
_SUBPROCESS_ENV = {"PATH": _SUBPROCESS_PATH}


# ---------------------------------------------------------------------------
# Result type
# ---------------------------------------------------------------------------


@dataclass(slots=True)
class DispatchResult:
    body: str  # room-safe reply text (≤ 4000 chars)
    ok: bool


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _truncate(text: str) -> str:
    if len(text) <= _MAX_BODY:
        return text
    cut = _MAX_BODY - len(_TRUNCATION_SUFFIX)
    return text[:cut] + _TRUNCATION_SUFFIX


def _run(cmd: list[str], timeout: int = 30, cwd: str | None = None) -> tuple[bool, str]:
    """Run *cmd* and return ``(success, combined_output)``."""
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            env=_SUBPROCESS_ENV,
            cwd=cwd,
        )
        combined = result.stdout + (("\n" + result.stderr) if result.stderr.strip() else "")
        return result.returncode == 0, combined.strip()
    except subprocess.TimeoutExpired:
        return False, f"Command timed out after {timeout}s."
    except FileNotFoundError:
        return False, f"Binary not found: {cmd[0]!r}. Check PATH ({_SUBPROCESS_PATH})."
    except Exception as exc:  # noqa: BLE001
        return False, f"Unexpected error running {cmd[0]!r}: {exc}"


def _code_block(text: str) -> str:
    return f"```\n{text}\n```"


def _error(text: str) -> str:
    return f"⚠ {text}"


# ---------------------------------------------------------------------------
# Path helpers (extracted so tests can monkeypatch them)
# ---------------------------------------------------------------------------


def _mesh_jsonl_path() -> Path:
    return Path.home() / ".local" / "state" / "sourceos" / "memory-mesh" / "context.jsonl"


def _ctx_json_path() -> Path:
    return Path.home() / ".local" / "state" / "sourceos" / "memory-mesh" / "active.json"


def _notes_dir() -> Path:
    return Path.home() / "notes"


def _git_root() -> str:
    val = os.environ.get("SOURCEOS_GIT_ROOT")
    if val:
        return val
    candidate = Path.home() / "dev"
    return str(candidate)


# ---------------------------------------------------------------------------
# Verb handlers — original set
# ---------------------------------------------------------------------------


def _handle_cloudshell(args: list[str]) -> DispatchResult:
    sub = args[0] if args else "status"
    if sub != "status":
        return DispatchResult(body=_error(f"Unknown cloudshell sub-verb: {sub!r}. Try: status"), ok=False)
    ok, out = _run(["turtle-ssh-tunnel", "status"])
    body = _truncate(out if ok else _error(out))
    return DispatchResult(body=body, ok=ok)


def _handle_k3s(args: list[str]) -> DispatchResult:
    if not args:
        return DispatchResult(body=_error("Usage: !qes k3s <kubectl args…>"), ok=False)
    cmd = ["kubectl"] + list(args)
    env = dict(_SUBPROCESS_ENV)
    env["KUBECONFIG"] = "~/.kube/config-k3s-twin"
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=30,
            env=env,
        )
        combined = result.stdout + (("\n" + result.stderr) if result.stderr.strip() else "")
        out = combined.strip()
        ok = result.returncode == 0
    except subprocess.TimeoutExpired:
        return DispatchResult(body=_error("kubectl timed out after 30s."), ok=False)
    except FileNotFoundError:
        return DispatchResult(body=_error("kubectl binary not found. Check PATH."), ok=False)
    except Exception as exc:  # noqa: BLE001
        return DispatchResult(body=_error(str(exc)), ok=False)

    formatted = _code_block(_truncate(out)) if out else _code_block("(no output)")
    if not ok:
        formatted = _error("kubectl returned non-zero exit code.\n") + formatted
    return DispatchResult(body=_truncate(formatted), ok=ok)


def _handle_runbook(args: list[str]) -> DispatchResult:
    sub = args[0] if args else "list"

    if sub == "list":
        cmd = ["turtle-runbook", "list"]
    elif sub == "search":
        if len(args) < 2:
            return DispatchResult(body=_error("Usage: !qes runbook search <query>"), ok=False)
        cmd = ["turtle-runbook", "search"] + args[1:]
    elif sub == "show":
        if len(args) < 2:
            return DispatchResult(body=_error("Usage: !qes runbook show <name>"), ok=False)
        cmd = ["turtle-runbook", "show"] + args[1:]
    else:
        return DispatchResult(
            body=_error(f"Unknown runbook sub-verb: {sub!r}. Try: list, search <q>, show <name>"),
            ok=False,
        )

    ok, out = _run(cmd)
    body = _truncate(out if ok else _error(out))
    return DispatchResult(body=body, ok=ok)


def _handle_noe(args: list[str]) -> DispatchResult:
    query = " ".join(args)
    if not query:
        return DispatchResult(body=_error("Usage: !qes noe <query>"), ok=False)
    ok, out = _run(["turtle-noetica-stream", query], timeout=30)
    body = _truncate(out if ok else _error(out))
    return DispatchResult(body=body, ok=ok)


def _handle_wormhole(args: list[str]) -> DispatchResult:
    sub = args[0] if args else ""

    if sub == "send":
        file_arg = args[1] if len(args) > 1 else None
        try:
            if file_arg:
                code = wormhole.send_file(file_arg)
                body = f"Wormhole transfer code: `{code}`\nRecipient runs: `wormhole receive {code}`"
            else:
                code = wormhole.send_text("(placeholder — pipe your content in a follow-up)")
                body = (
                    f"Wormhole transfer code: `{code}`\n"
                    "No file specified — a placeholder text was sent.\n"
                    "To send a file: `!qes wormhole send <path>`\n"
                    f"Recipient runs: `wormhole receive {code}`"
                )
        except RuntimeError as exc:
            return DispatchResult(body=_error(str(exc)), ok=False)
        return DispatchResult(body=body, ok=True)

    elif sub == "recv":
        if len(args) < 2:
            return DispatchResult(body=_error("Usage: !qes wormhole recv <code>"), ok=False)
        code = args[1]
        try:
            path = wormhole.receive(code, timeout=120)
            body = f"Received. Saved to: `{path}`"
        except RuntimeError as exc:
            return DispatchResult(body=_error(str(exc)), ok=False)
        return DispatchResult(body=body, ok=True)

    elif sub == "pipe":
        text_parts = args[1:]
        if not text_parts:
            return DispatchResult(body=_error("Usage: !qes wormhole pipe <text…>"), ok=False)
        text = " ".join(text_parts)
        try:
            code = wormhole.send_text(text, timeout=30)
            body = f"Wormhole transfer code: `{code}`\nRecipient runs: `wormhole receive {code}`"
        except RuntimeError as exc:
            return DispatchResult(body=_error(str(exc)), ok=False)
        return DispatchResult(body=body, ok=True)

    else:
        return DispatchResult(
            body=_error(f"Unknown wormhole sub-verb: {sub!r}. Try: send [file], recv <code>, pipe <text…>"),
            ok=False,
        )


# ---------------------------------------------------------------------------
# Verb handlers — new set
# ---------------------------------------------------------------------------


def _handle_git(args: list[str]) -> DispatchResult:
    sub = args[0] if args else ""

    cwd = _git_root()

    if sub == "log":
        try:
            n = int(args[1]) if len(args) > 1 else 10
        except ValueError:
            n = 10
        ok, out = _run(["git", "log", "--oneline", f"-n{n}"], cwd=cwd)
        body = _truncate(out or "(empty log)")
        return DispatchResult(body=body, ok=ok)

    elif sub == "diff":
        ref = args[1] if len(args) > 1 else "HEAD~1..HEAD"
        ok, out = _run(["git", "diff", ref], cwd=cwd)
        if out:
            body = _truncate(f"```diff\n{out}\n```")
        else:
            body = "(no diff)"
        return DispatchResult(body=body, ok=ok)

    elif sub == "status":
        ok, out = _run(["git", "status", "--short"], cwd=cwd)
        body = _truncate(out or "(clean)")
        return DispatchResult(body=body, ok=ok)

    else:
        return DispatchResult(
            body=_error(f"Unknown git sub-verb: {sub!r}. Try: log [n], diff [ref], status"),
            ok=False,
        )


def _handle_mesh(args: list[str]) -> DispatchResult:
    try:
        n = int(args[0]) if args else 20
    except ValueError:
        n = 20

    path = _mesh_jsonl_path()
    if not path.exists():
        return DispatchResult(body="⚠ mesh JSONL not found.", ok=False)

    try:
        lines = path.read_text().splitlines()
        lines = lines[-n:]
        formatted: list[str] = []
        for line in lines:
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
                ts = str(record.get("ts", ""))[:16]
                rtype = record.get("type", "?")
                title = record.get("title", "")
                formatted.append(f"{ts} {rtype}: {title}")
            except (json.JSONDecodeError, KeyError):
                formatted.append(line[:80])
        body = "\n".join(formatted) or "(empty)"
        return DispatchResult(body=_truncate(body), ok=True)
    except Exception as exc:  # noqa: BLE001
        return DispatchResult(body=_error(str(exc)), ok=False)


def _handle_note(args: list[str]) -> DispatchResult:
    sub = args[0] if args else "list"
    notes = _notes_dir()

    if sub == "list":
        try:
            files = sorted(notes.glob("*.md"), key=lambda p: p.stat().st_mtime, reverse=True)
            if not files:
                return DispatchResult(body="(no notes found)", ok=True)
            lines: list[str] = []
            for f in files:
                mtime = datetime.datetime.fromtimestamp(f.stat().st_mtime).strftime("%Y-%m-%d %H:%M")
                lines.append(f"{f.name}  {mtime}")
            return DispatchResult(body=_truncate("\n".join(lines)), ok=True)
        except Exception as exc:  # noqa: BLE001
            return DispatchResult(body=_error(str(exc)), ok=False)

    elif sub == "show":
        if len(args) < 2:
            return DispatchResult(body=_error("Usage: !qes note show <slug>"), ok=False)
        slug = args[1]
        candidates = [notes / slug, notes / f"{slug}.md"]
        for candidate in candidates:
            if candidate.exists():
                try:
                    content = candidate.read_text()
                    return DispatchResult(body=content[:3000], ok=True)
                except Exception as exc:  # noqa: BLE001
                    return DispatchResult(body=_error(str(exc)), ok=False)
        return DispatchResult(body=_error(f"Note not found: {slug!r}"), ok=False)

    else:
        return DispatchResult(
            body=_error(f"Unknown note sub-verb: {sub!r}. Try: list, show <slug>"),
            ok=False,
        )


def _handle_csh(args: list[str]) -> DispatchResult:
    if not args:
        return DispatchResult(body=_error("Usage: !qes csh <cmd…>"), ok=False)
    cmd = ["turtle-ssh-tunnel", "exec"] + list(args)
    ok, out = _run(cmd)
    if not ok and "Binary not found" in out:
        return DispatchResult(body="⚠ turtle-ssh-tunnel not found — cloudshell not configured", ok=False)
    body = _truncate(out if ok else _error(out))
    return DispatchResult(body=body, ok=ok)


def _handle_tunnel(args: list[str]) -> DispatchResult:
    sub = args[0] if args else "status"

    if sub == "status":
        ok, out = _run(["turtle-ssh-tunnel", "status"])
        body = _truncate(out if ok else _error(out))
        return DispatchResult(body=body, ok=ok)

    elif sub == "start":
        ok, out = _run(["turtle-ssh-tunnel", "tunnel", "start"])
        body = _truncate(out if ok else _error(out))
        return DispatchResult(body=body, ok=ok)

    else:
        return DispatchResult(
            body=_error(f"Unknown tunnel sub-verb: {sub!r}. Try: status, start"),
            ok=False,
        )


def _handle_ctx(args: list[str]) -> DispatchResult:  # noqa: ARG001
    path = _ctx_json_path()
    if not path.exists():
        return DispatchResult(body="⚠ No active context.", ok=False)
    try:
        data = json.loads(path.read_text())
        lines: list[str] = [f"{k}: {v}" for k, v in data.items()]
        return DispatchResult(body=_truncate("\n".join(lines)), ok=True)
    except Exception as exc:  # noqa: BLE001
        return DispatchResult(body=_error(str(exc)), ok=False)


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

_HANDLERS = {
    "cloudshell": _handle_cloudshell,
    "ctx": _handle_ctx,
    "csh": _handle_csh,
    "git": _handle_git,
    "k3s": _handle_k3s,
    "mesh": _handle_mesh,
    "note": _handle_note,
    "noe": _handle_noe,
    "runbook": _handle_runbook,
    "tunnel": _handle_tunnel,
    "wormhole": _handle_wormhole,
}


def execute(command: OperatorCommand) -> DispatchResult:
    """Dispatch *command* to the appropriate shell handler.

    Returns a :class:`DispatchResult` with a room-safe reply body (≤ 4000 chars).
    """
    handler = _HANDLERS.get(command.verb)
    if handler is None:
        return DispatchResult(
            body=_error(f"No dispatch handler for verb: {command.verb!r}"),
            ok=False,
        )
    return handler(command.args)
