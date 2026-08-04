from __future__ import annotations

"""Shell command dispatcher for the Matrix QES operator.

Handles non-incident ``!qes`` verbs by running local subprocesses and
returning room-safe formatted output (max 4000 chars, truncated with ``…``).
"""

import subprocess
from dataclasses import dataclass

from . import wormhole
from .commands import OperatorCommand

# ---------------------------------------------------------------------------
# Public constants
# ---------------------------------------------------------------------------

DISPATCH_VERBS: frozenset[str] = frozenset(
    {"cloudshell", "k3s", "runbook", "noe", "wormhole"}
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


def _run(cmd: list[str], timeout: int = 30) -> tuple[bool, str]:
    """Run *cmd* and return ``(success, combined_output)``."""
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            env=_SUBPROCESS_ENV,
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
    # Embed the kubeconfig via environment
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
    # Wrap error prefix outside the code block for readability.
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
                # Send placeholder text; document usage.
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


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

_HANDLERS = {
    "cloudshell": _handle_cloudshell,
    "k3s": _handle_k3s,
    "runbook": _handle_runbook,
    "noe": _handle_noe,
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
