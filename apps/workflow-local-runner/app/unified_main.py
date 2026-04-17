from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType
from typing import Any

from fastapi import FastAPI

APP_DIR = Path(__file__).resolve().parent


def _load_module(name: str, path: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"unable to load module {name} from {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_runner_main = _load_module("workflow_local_runner_main_impl", APP_DIR / "main.py")
_materialize_main = _load_module("workflow_local_runner_materialize_main_impl", APP_DIR / "materialize_main.py")
_execute_bound_main = _load_module("workflow_local_runner_execute_bound_main_impl", APP_DIR / "execute_bound_main.py")

app = FastAPI(title="Prophet Platform Workflow Local Runner Unified", version="0.1.0")


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok", "service": "workflow-local-runner-unified"}


@app.post("/v1/runs/local-execute")
def local_execute(body: dict[str, Any]) -> dict[str, Any]:
    return _runner_main.local_execute(body)


@app.post("/v1/bundles/{service}/{correlation_id}/materialize")
def materialize(service: str, correlation_id: str) -> dict[str, str]:
    return _materialize_main.materialize(service=service, correlation_id=correlation_id)


@app.post("/v1/runs/local-execute-bound")
def local_execute_bound(body: dict[str, Any]) -> dict[str, Any]:
    return _execute_bound_main.local_execute_bound(body)
