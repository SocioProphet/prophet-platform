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
    {
        "arm", "cloudshell", "ctx", "csh", "doc", "git",
        "k3s", "mesh", "note", "noe", "runbook", "ticket",
        "transcript", "tunnel", "wormhole",
    }
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
    return str(Path.home() / "dev")


def _doc_feedback_bin() -> str:
    import shutil as _shutil
    found = _shutil.which("turtle-doc-feedback")
    if found:
        return found
    candidate = Path.home() / ".local" / "share" / "sourceos" / "bin" / "turtle-doc-feedback"
    if candidate.exists():
        return str(candidate)
    return "turtle-doc-feedback"


def _transcript_bin() -> str:
    import shutil as _shutil
    found = _shutil.which("turtle-transcript-extract")
    if found:
        return found
    candidate = Path.home() / ".local" / "share" / "sourceos" / "bin" / "turtle-transcript-extract"
    if candidate.exists():
        return str(candidate)
    return "turtle-transcript-extract"


def _transcript_pending_path() -> Path:
    return Path.home() / ".local" / "state" / "sourceos" / "transcript-claims" / "pending.jsonl"


def _arm_bin() -> str:
    import shutil as _shutil
    found = _shutil.which("turtle-arm-generate")
    if found:
        return found
    candidate = Path.home() / ".local" / "share" / "sourceos" / "bin" / "turtle-arm-generate"
    if candidate.exists():
        return str(candidate)
    return "turtle-arm-generate"


# ---------------------------------------------------------------------------
# Verb handlers
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
                    "Recipient runs: `wormhole receive {code}`"
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

    else:
        return DispatchResult(
            body=_error(f"Unknown wormhole sub-verb: {sub!r}. Try: send [file], recv <code>"),
            ok=False,
        )


def _handle_git(args: list[str]) -> DispatchResult:
    sub = args[0] if args else ""
    cwd = _git_root()

    if sub == "log":
        try:
            n = int(args[1]) if len(args) > 1 else 10
        except ValueError:
            n = 10
        ok, out = _run(["git", "log", "--oneline", f"-n{n}"], cwd=cwd)
        return DispatchResult(body=_truncate(out or "(empty log)"), ok=ok)

    elif sub == "diff":
        ref = args[1] if len(args) > 1 else "HEAD~1..HEAD"
        ok, out = _run(["git", "diff", ref], cwd=cwd)
        body = _truncate(f"```diff\n{out}\n```") if out else "(no diff)"
        return DispatchResult(body=body, ok=ok)

    elif sub == "status":
        ok, out = _run(["git", "status", "--short"], cwd=cwd)
        return DispatchResult(body=_truncate(out or "(clean)"), ok=ok)

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
        lines = path.read_text().splitlines()[-n:]
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
        return DispatchResult(body=_truncate("\n".join(formatted) or "(empty)"), ok=True)
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
        for candidate in [notes / slug, notes / f"{slug}.md"]:
            if candidate.exists():
                try:
                    return DispatchResult(body=candidate.read_text()[:3000], ok=True)
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
    ok, out = _run(["turtle-ssh-tunnel", "exec"] + list(args))
    if not ok and "Binary not found" in out:
        return DispatchResult(body="⚠ turtle-ssh-tunnel not found — cloudshell not configured", ok=False)
    return DispatchResult(body=_truncate(out if ok else _error(out)), ok=ok)


def _handle_tunnel(args: list[str]) -> DispatchResult:
    sub = args[0] if args else "status"

    if sub == "status":
        ok, out = _run(["turtle-ssh-tunnel", "status"])
        return DispatchResult(body=_truncate(out if ok else _error(out)), ok=ok)

    elif sub == "start":
        ok, out = _run(["turtle-ssh-tunnel", "tunnel", "start"])
        return DispatchResult(body=_truncate(out if ok else _error(out)), ok=ok)

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


def _handle_ticket(args: list[str]) -> DispatchResult:
    sub = args[0] if args else "list"
    rest = args[1:] if len(args) > 1 else []

    if sub == "open":
        if not rest:
            return DispatchResult(body=_error("Usage: !qes ticket open <title>"), ok=False)
        cmd = ["turtle-ticket", "open"] + rest
    elif sub in ("list", "ls"):
        cmd = ["turtle-ticket", "list", "--open"]
    elif sub == "show":
        if not rest:
            return DispatchResult(body=_error("Usage: !qes ticket show <id>"), ok=False)
        cmd = ["turtle-ticket", "show", rest[0]]
    elif sub == "close":
        if not rest:
            return DispatchResult(body=_error("Usage: !qes ticket close <id>"), ok=False)
        cmd = ["turtle-ticket", "close", rest[0]]
    elif sub in ("comment", "note"):
        if len(rest) < 2:
            return DispatchResult(
                body=_error("Usage: !qes ticket comment <id> <text>"), ok=False
            )
        cmd = ["turtle-ticket", "comment"] + rest
    elif sub == "search":
        if not rest:
            return DispatchResult(body=_error("Usage: !qes ticket search <query>"), ok=False)
        cmd = ["turtle-ticket", "search"] + rest
    elif sub == "summary":
        cmd = ["turtle-ticket", "summary"]
    else:
        return DispatchResult(
            body=_error(
                f"Unknown ticket sub-verb: {sub!r}. "
                "Try: open <title>, list, show <id>, close <id>, "
                "comment <id> <text>, search <query>, summary"
            ),
            ok=False,
        )

    ok, out = _run(cmd, timeout=15)
    return DispatchResult(body=_truncate(out if ok else _error(out)), ok=ok)


def _handle_doc(args: list[str]) -> DispatchResult:
    sub = args[0] if args else ""

    if sub == "feedback":
        rest = args[1:]
        if len(rest) < 2:
            return DispatchResult(
                body=_error("Usage: !qes doc feedback <doc_ref> <sentiment> [<comment>]"),
                ok=False,
            )
        ok, out = _run(["python3", _doc_feedback_bin(), "submit"] + list(rest), timeout=15)
        return DispatchResult(body=_truncate(out if ok else _error(out)), ok=ok)

    elif sub == "list":
        ok, out = _run(["python3", _doc_feedback_bin(), "list"] + args[1:], timeout=10)
        return DispatchResult(body=_truncate(out if ok else _error(out)), ok=ok)

    elif sub == "faq":
        ok, out = _run(["python3", _doc_feedback_bin(), "faq"] + args[1:], timeout=10)
        return DispatchResult(body=_truncate(out if ok else _error(out)), ok=ok)

    elif sub == "distill":
        rest = args[1:]
        try:
            subprocess.Popen(
                ["python3", _doc_feedback_bin(), "distill"] + list(rest),
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                env=_SUBPROCESS_ENV,
            )
        except Exception as exc:  # noqa: BLE001
            return DispatchResult(body=_error(f"Could not launch distill: {exc}"), ok=False)
        label = f" for {rest[0]!r}" if rest else ""
        return DispatchResult(
            body=f"⏳ Distilling{label}… (runs in background; use `!qes doc faq` when done)",
            ok=True,
        )

    else:
        return DispatchResult(
            body=_error(
                f"Unknown doc sub-verb: {sub!r}. "
                "Try: feedback <ref> <sentiment> [comment], list [ref], faq [ref], distill [ref]"
            ),
            ok=False,
        )


def _handle_transcript(args: list[str]) -> DispatchResult:
    sub = args[0] if args else ""

    if sub == "extract":
        since_h = 24
        i = 1
        while i < len(args):
            if args[i] == "--since" and i + 1 < len(args):
                try:
                    since_h = int(args[i + 1])
                except ValueError:
                    pass
                i += 2
            else:
                i += 1
        try:
            subprocess.Popen(
                ["python3", _transcript_bin(), "extract", "--since", str(since_h)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                env=_SUBPROCESS_ENV,
            )
        except Exception as exc:  # noqa: BLE001
            return DispatchResult(body=_error(f"Could not launch extract: {exc}"), ok=False)
        return DispatchResult(
            body=f"⏳ Extracting last {since_h}h… (runs in background; use `!qes transcript list` when done)",
            ok=True,
        )

    elif sub == "list":
        pending_path = _transcript_pending_path()
        if not pending_path.exists():
            return DispatchResult(body="(no pending claims)", ok=True)
        try:
            lines = [ln.strip() for ln in pending_path.read_text().splitlines() if ln.strip()]
        except Exception as exc:  # noqa: BLE001
            return DispatchResult(body=_error(str(exc)), ok=False)
        if not lines:
            return DispatchResult(body="(no pending claims)", ok=True)
        records = lines[-10:]
        rows: list[str] = []
        for line in records:
            try:
                r = json.loads(line)
                claim_id = r.get("id", "?")
                extracted_at = r.get("extracted_at", "?")[:16]
                preview = r.get("claim", "")[:60].replace("\n", " ")
                rows.append(f"{claim_id}  {extracted_at}  {preview}…")
            except Exception:
                rows.append(line[:80])
        total = len(lines)
        header = f"Pending claims ({total} total, showing last {len(records)}):"
        return DispatchResult(body=_truncate(header + "\n" + "\n".join(rows)), ok=True)

    elif sub == "commit":
        ok, out = _run(["python3", _transcript_bin(), "commit"], timeout=30)
        return DispatchResult(body=_truncate(out if ok else _error(out)), ok=ok)

    else:
        return DispatchResult(
            body=_error(
                f"Unknown transcript sub-verb: {sub!r}. "
                "Try: extract [--since <hours>], list, commit"
            ),
            ok=False,
        )


def _handle_arm(args: list[str]) -> DispatchResult:
    import re as _re

    sub = args[0] if args else "status"
    bin_path = _arm_bin()

    if sub == "generate":
        ok, out = _run(["python3", bin_path, "generate"], timeout=60)
        if ok:
            m = _re.search(r"\((\d+) ADRs", out)
            count = m.group(1) if m else "?"
            body = f"ARM generated ({count} ADRs)"
        else:
            body = _error(out)
        return DispatchResult(body=body, ok=ok)

    elif sub == "show":
        cmd = ["python3", bin_path, "show"]
        if args[1:]:
            cmd += ["--section", " ".join(args[1:])]
        ok, out = _run(cmd, timeout=15)
        return DispatchResult(body=_truncate(out[:3500] if ok else _error(out)), ok=ok)

    elif sub == "search":
        if not args[1:]:
            return DispatchResult(body=_error("Usage: !qes arm search <query>"), ok=False)
        ok, out = _run(["python3", bin_path, "search", " ".join(args[1:])], timeout=15)
        return DispatchResult(body=_truncate(out[:3000] if ok else _error(out)), ok=ok)

    elif sub == "status":
        ok, out = _run(["python3", bin_path, "status"], timeout=10)
        clean = _re.sub(r"\x1b\[[0-9;]*m", "", out)
        return DispatchResult(body=_truncate(clean if ok else _error(clean)), ok=ok)

    else:
        return DispatchResult(
            body=_error(
                f"Unknown arm sub-verb: {sub!r}. "
                "Try: generate, show [section], search <query>, status"
            ),
            ok=False,
        )


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

_HANDLERS = {
    "arm": _handle_arm,
    "cloudshell": _handle_cloudshell,
    "ctx": _handle_ctx,
    "csh": _handle_csh,
    "doc": _handle_doc,
    "git": _handle_git,
    "k3s": _handle_k3s,
    "mesh": _handle_mesh,
    "note": _handle_note,
    "noe": _handle_noe,
    "runbook": _handle_runbook,
    "ticket": _handle_ticket,
    "transcript": _handle_transcript,
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
