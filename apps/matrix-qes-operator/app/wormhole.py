from __future__ import annotations

"""Wormhole helpers — thin wrappers around the magic-wormhole CLI.

The ``wormhole`` binary (or ``wormhole-william``) must be installed on the
host.  These functions locate the binary at call-time and return a clear error
message when it is absent so the caller can relay that to the Matrix room.
"""

import re
import shutil
import subprocess
import tempfile
from pathlib import Path

_FALLBACK_BINARY = "/usr/local/bin/wormhole-william"
_CODE_RE = re.compile(r"(\d+-[a-z]+-[a-z]+)")

# Ensure common binary install locations are reachable.
_SUBPROCESS_ENV_PATH = "/usr/local/bin:/opt/homebrew/bin:/usr/bin:/bin"


def _wormhole_bin() -> str | None:
    """Return the path to the wormhole binary, or None if unavailable."""
    found = shutil.which("wormhole", path=_SUBPROCESS_ENV_PATH)
    if found:
        return found
    p = Path(_FALLBACK_BINARY)
    if p.exists() and p.is_file():
        return str(p)
    return None


def _missing_binary_error() -> str:
    return (
        "wormhole binary not found. "
        "Install magic-wormhole (`pip install magic-wormhole`) or wormhole-william, "
        "then ensure it is on PATH."
    )


def _extract_code(output: str) -> str:
    """Extract the wormhole transfer code from subprocess output."""
    m = _CODE_RE.search(output)
    if m:
        return m.group(1)
    return output.strip()


def send_text(text: str, timeout: int = 30) -> str:
    """Send *text* via ``wormhole send --text -``.

    Returns the wormhole transfer code string (e.g. ``3-guitar-tango``) so the
    operator can post it into the Matrix thread.  Raises ``RuntimeError`` when
    the binary is missing or the command fails.
    """
    binary = _wormhole_bin()
    if binary is None:
        raise RuntimeError(_missing_binary_error())

    result = subprocess.run(
        [binary, "send", "--text", text],
        capture_output=True,
        text=True,
        timeout=timeout,
        env={"PATH": _SUBPROCESS_ENV_PATH},
    )
    combined = result.stdout + result.stderr
    if result.returncode != 0:
        raise RuntimeError(f"wormhole send failed: {combined.strip()}")
    return _extract_code(combined)


def send_file(path: str, timeout: int = 60) -> str:
    """Send *path* via ``wormhole send <path>``.

    Returns the wormhole transfer code string.  Raises ``RuntimeError`` on
    failure.
    """
    binary = _wormhole_bin()
    if binary is None:
        raise RuntimeError(_missing_binary_error())

    result = subprocess.run(
        [binary, "send", path],
        capture_output=True,
        text=True,
        timeout=timeout,
        env={"PATH": _SUBPROCESS_ENV_PATH},
    )
    combined = result.stdout + result.stderr
    if result.returncode != 0:
        raise RuntimeError(f"wormhole send failed: {combined.strip()}")
    return _extract_code(combined)


def receive(code: str, dest_dir: str | None = None, timeout: int = 120) -> str:
    """Receive via ``wormhole receive --accept-file <code>``.

    Files land in *dest_dir* (a new temp directory if not given).  Returns the
    path to the received file/directory, or a status message on timeout.
    Raises ``RuntimeError`` when the binary is missing.
    """
    binary = _wormhole_bin()
    if binary is None:
        raise RuntimeError(_missing_binary_error())

    if dest_dir is None:
        dest_dir = tempfile.mkdtemp(prefix="wormhole-recv-")

    result = subprocess.run(
        [binary, "receive", "--accept-file", code],
        capture_output=True,
        text=True,
        timeout=timeout,
        cwd=dest_dir,
        env={"PATH": _SUBPROCESS_ENV_PATH},
    )
    combined = result.stdout + result.stderr
    if result.returncode != 0:
        raise RuntimeError(f"wormhole receive failed: {combined.strip()}")

    # Try to identify the saved filename from output.
    for line in combined.splitlines():
        if "Received file written to" in line or "saved to" in line.lower():
            parts = line.split()
            if parts:
                candidate = Path(dest_dir) / parts[-1].strip("'\"")
                if candidate.exists():
                    return str(candidate)

    return dest_dir
