"""Headless cell execution with PERSISTENT per-session kernels.

A notebook is not a pile of one-shot cells — state must carry across them
(`a = 1` in one cell is visible in the next). So we keep a live kernel per
session_id (jupyter_client.KernelManager) and route each cell to its session's
kernel. Kernels are pod-local process state, so the forge Deployment runs a
single replica (see values) — no cross-pod session bleed.

Kernel libs are imported lazily so the service still boots (and degrades
honestly) where a kernel isn't installed. The executor is injectable so tests
never need a live kernel.
"""
from __future__ import annotations

import queue
from typing import Callable

from .adapters import LANG_KERNEL


class ForgeUnavailable(RuntimeError):
    """No execution kernel available — caller should degrade, never fake a result."""


# ── persistent kernel registry: session_id -> (KernelManager, KernelClient) ──
_KERNELS: dict[str, tuple] = {}


def _ensure_kernel(session_id: str, language: str):
    if session_id in _KERNELS:
        return _KERNELS[session_id]
    try:
        from jupyter_client import KernelManager
    except Exception as e:  # pragma: no cover - import guard
        raise ForgeUnavailable(f"jupyter_client/ipykernel not installed: {e}")
    kname = LANG_KERNEL.get(language, "python3")
    km = KernelManager(kernel_name=kname)
    km.start_kernel()
    kc = km.client()
    kc.start_channels()
    kc.wait_for_ready(timeout=30)
    _KERNELS[session_id] = (km, kc)
    return km, kc


def shutdown(session_id: str) -> None:
    pair = _KERNELS.pop(session_id, None)
    if pair:
        km, kc = pair
        try:
            kc.stop_channels(); km.shutdown_kernel(now=True)
        except Exception:  # pragma: no cover
            pass


def _live_run(code: str, language: str, timeout: int, session_id: str) -> dict:
    _, kc = _ensure_kernel(session_id, language)
    msg_id = kc.execute(code)
    outputs: list[dict] = []
    status = "ok"
    while True:
        try:
            msg = kc.get_iopub_msg(timeout=timeout)
        except queue.Empty:
            status = "timeout"
            break
        if msg.get("parent_header", {}).get("msg_id") != msg_id:
            continue
        mt, c = msg["msg_type"], msg["content"]
        if mt == "stream":
            outputs.append({"type": "stream", "name": c.get("name"), "text": c.get("text", "")})
        elif mt in ("execute_result", "display_data"):
            data = c.get("data", {})
            out = {"type": mt, "text": data.get("text/plain", ""), "mime": list(data.keys())}
            # carry RICH representations so the surface can render plots/tables/HTML
            # (matplotlib PNG, DataFrame HTML, SVG) — not just text. Better-than-Databricks
            # needs real DS outputs; the receipt still seals over all of it.
            if "image/png" in data:
                out["png"] = data["image/png"]           # base64 (data URI on the client)
            if "image/svg+xml" in data:
                out["svg"] = data["image/svg+xml"]
            if "text/html" in data:
                out["html"] = data["text/html"]           # e.g. df._repr_html_()
            outputs.append(out)
        elif mt == "error":
            status = "error"
            outputs.append({"type": "error", "ename": c.get("ename"), "evalue": c.get("evalue")})
        elif mt == "status" and c.get("execution_state") == "idle":
            break
    return {"status": status, "outputs": outputs,
            "error": next((o["ename"] + ": " + o["evalue"] for o in outputs if o["type"] == "error"), None)}


# module-level executor — overridable in tests via set_executor()
_EXECUTOR: Callable[[str, str, int, str], dict] = _live_run


def set_executor(fn) -> None:
    """Install a test/alt executor. Accepts (code, language, timeout[, session_id])."""
    global _EXECUTOR
    import inspect
    n = len(inspect.signature(fn).parameters)
    _EXECUTOR = fn if n >= 4 else (lambda code, lang, to, sid: fn(code, lang, to))


def run_cell(code: str, language: str = "python", timeout: int = 60, session_id: str = "default") -> dict:
    return _EXECUTOR(code, language, timeout, session_id)


def live_kernels(project: str | None = None) -> int:
    """Count live persistent kernels — all of them, or just one project's.

    Cheap and side-effect-free (for /v1/stats). Project scoping matches on the
    session_id convention used by the server (`<project>:default`,
    `<project>:sched:<id>`), so ops can see a single project's kernel footprint.
    """
    if project is None:
        return len(_KERNELS)
    return sum(1 for sid in _KERNELS if sid == project or sid.startswith(project + ":"))


def kernel_available() -> bool:
    """True when a real execution kernel is importable (for /healthz)."""
    if _EXECUTOR is not _live_run:
        return True
    try:
        import jupyter_client  # noqa: F401
        import ipykernel  # noqa: F401
        return True
    except Exception:
        return False
