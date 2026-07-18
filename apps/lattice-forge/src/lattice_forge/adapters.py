"""Notebook-surface adapters.

Mirrors the NotebookSurfacePlane design record
(build/lattice-studio/notebook-plane/notebook-surface-plane.json):
adapter-based, and — per the plane's designRule — we must NOT hard-code Jupyter
as the ontology. JupyterLab is merely the default adapter.
"""
from __future__ import annotations

DEFAULT_ADAPTER = "jupyterlab"

ADAPTERS: dict[str, dict] = {
    "jupyterlab": {
        "role": "scientific-notebook",
        "capabilities": ["python", "r", "julia", "terminal", "kernel-spec", "general-purpose-notebook"],
        "kernels": ["python3", "ir", "julia"],
        "mode": "session",   # brokered — a full JupyterLab surface fronted for governance
    },
    "zeppelin": {
        "role": "collaborative-analytics",
        "capabilities": ["spark", "sql", "scala", "python", "r", "collaborative-documents"],
        "kernels": ["spark", "python3"],
        "mode": "session",
    },
    "observable": {
        "role": "reactive-visualization",
        "capabilities": ["javascript", "sql", "html", "markdown", "reactive-visualization"],
        "kernels": ["javascript"],
        "mode": "reactive",
    },
    "plutojl": {
        "role": "reactive-science",
        "capabilities": ["julia", "reactive-cells", "dependency-aware-reexecution"],
        "kernels": ["julia"],
        "mode": "reactive",
    },
    "quarto": {
        "role": "publishing",
        "capabilities": ["python", "r", "julia", "observable", "markdown", "publishing", "slides", "books"],
        "kernels": ["python3"],
        "mode": "headless",  # rendered/published, not interactively brokered
    },
}

# language -> kernel used for HEADLESS execution (nbclient path)
LANG_KERNEL = {"python": "python3", "python3": "python3", "r": "ir", "julia": "julia"}


def resolve(adapter: str | None) -> tuple[str, dict]:
    a = adapter or DEFAULT_ADAPTER
    if a not in ADAPTERS:
        raise KeyError(a)
    return a, ADAPTERS[a]
