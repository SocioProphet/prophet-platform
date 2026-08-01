# Web Intelligence metrics app

Deployable consumer for the **Web Intelligence** lane (`contracts/web-intel`).
Serves governed web-intelligence metric bundles — site audit, backlink profile,
AI-search visibility, SERP/rank, content gap, and the unified scorecard —
**symmetrically for our own domains and for competitors**.

## Responsibilities

- expose liveness
- expose the lane's event types
- expose recent metric/scorecard bundles
- expose bundles filtered **by subject domain** (self or competitor)
- expose bundle detail by correlation id

## Endpoints

- `GET /healthz`
- `GET /v1/web-intel/event-types`
- `GET /v1/web-intel/recent?limit=`
- `GET /v1/web-intel/by-subject/{subject}?limit=`
- `GET /v1/web-intel/{correlation_id}`

## Service name

`web-intel-metrics`

## State layout

Reads the platform state conventions used elsewhere in `prophet-platform`:
`~/.local/state/prophet-platform/{payloads,events,receipts}/web-intel-metrics/`
(overridable via `SOCIOPROFIT_STATE_HOME`). Scorecard bundles are written there
by `tools/emit_web_intel_scorecard.py --emit`.

## Test

```bash
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements-test.txt
PYTHONPATH=. pytest -q tests
```
