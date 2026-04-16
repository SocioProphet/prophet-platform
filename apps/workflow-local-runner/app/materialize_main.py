from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType

from fastapi import FastAPI, HTTPException

APP_DIR = Path(__file__).resolve().parent
PLATFORM_ROOT = APP_DIR.parents[2]


def _load_module(name: str, path: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"unable to load module {name} from {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_store = _load_module(
    "workflow_local_runner_evidence_store",
    PLATFORM_ROOT / "evidence-receipts" / "app" / "store.py",
)
_materializer = _load_module(
    "workflow_local_runner_materializer_impl",
    APP_DIR / "materialize_bound_bundle.py",
)

app = FastAPI(title="Prophet Platform Workflow Bound Bundle Materializer", version="0.1.0")


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok", "service": "workflow-bound-bundle-materializer"}


@app.post("/v1/bundles/{service}/{correlation_id}/materialize")
def materialize(service: str, correlation_id: str) -> dict[str, str]:
    bundle = _store.get_bundle(service=service, correlation_id=correlation_id)
    if bundle is None:
        raise HTTPException(status_code=404, detail="receipt bundle not found")

    out_path = _materializer.materialize_bound_bundle(
        service=service,
        correlation_id=correlation_id,
        workflow_run=bundle["payload"]["workflow_run"],
        execution_envelope=bundle["payload"]["execution_envelope"],
        event_doc=bundle["event"],
        receipt_doc=bundle["receipt"],
        payload_doc=bundle["payload"],
        catalog_entry=bundle["catalog_entry"],
        platform_root=_store.platform_state_root(),
    )

    return {
        "service": service,
        "correlation_id": correlation_id,
        "bundle_ref": f"file://{Path(out_path).resolve()}",
    }
