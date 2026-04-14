from __future__ import annotations

from fastapi import FastAPI
from fastapi.responses import HTMLResponse

from . import service

app = FastAPI(title="Prophet Platform Evidence Console", version="0.1.0")


@app.get("/healthz")
def healthz() -> dict:
    return {"status": "ok", "service": "evidence-console"}


@app.get("/v1/console/frontier")
def frontier(limit: int = 20) -> dict:
    return service.get_frontier_view(limit=limit)


@app.get("/v1/console/models/{model_release_id}")
def model_view(model_release_id: str, limit: int = 30) -> dict:
    return service.get_model_view(model_release_id=model_release_id, limit=limit)


@app.get("/v1/console/coverage")
def coverage(limit: int = 20) -> dict:
    return service.get_coverage_view(limit=limit)


@app.get("/v1/console/recent-events")
def recent_events(limit: int = 25, per_service_limit: int = 15) -> dict:
    return service.get_recent_events_view(limit=limit, per_service_limit=per_service_limit)


@app.get("/console/evidence", response_class=HTMLResponse)
def console_ui() -> str:
    return """<!doctype html>
<html>
<head>
  <meta charset=\"utf-8\" />
  <title>Prophet Platform Evidence Console</title>
  <style>
    body { font-family: system-ui, sans-serif; margin: 2rem; }
    h1, h2 { margin-bottom: 0.4rem; }
    section { margin-bottom: 1.5rem; }
    pre { background: #111; color: #eee; padding: 1rem; overflow: auto; border-radius: 8px; }
  </style>
</head>
<body>
  <h1>Evidence Console</h1>
  <p>Minimal operator surface over evidence-receipts.</p>

  <section>
    <h2>Frontier</h2>
    <pre id=\"frontier\">loading...</pre>
  </section>
  <section>
    <h2>Model View</h2>
    <pre id=\"model\">loading...</pre>
  </section>
  <section>
    <h2>Coverage</h2>
    <pre id=\"coverage\">loading...</pre>
  </section>
  <section>
    <h2>Recent Events</h2>
    <pre id=\"recent\">loading...</pre>
  </section>

<script>
async function load(id, url) {
  const el = document.getElementById(id);
  try {
    const res = await fetch(url);
    const data = await res.json();
    el.textContent = JSON.stringify(data, null, 2);
  } catch (err) {
    el.textContent = String(err);
  }
}
load('frontier', '/v1/console/frontier');
load('model', '/v1/console/models/model.semantic-stack.2026-04-05');
load('coverage', '/v1/console/coverage');
load('recent', '/v1/console/recent-events');
</script>
</body>
</html>"""
