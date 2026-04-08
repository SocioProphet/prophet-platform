# eval-fabric-api

Thin FastAPI starter for the Prophet Platform evaluation, observability, and intelligence lane.

Current routes:
- `/healthz`
- `/v1/frontier`
- `/v1/models/{model_release_id}/dossier`
- `/v1/competition/radar`

This app is intentionally seeded. Its job in this repo is to anchor the platform surface, container wiring, and database responsibility for the lane.
