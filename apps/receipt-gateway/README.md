# receipt-gateway

The estate's **governed inference seam**: a transparent, OpenAI-compatible proxy that fronts an
inference/embeddings backend and emits a schema-conformant, **hash-chained `InferenceReceipt`** for every
call. Point a consumer's `OPENAI_BASE_URL` / `EMBEDDINGS_URL` at this gateway and every completion or
embedding becomes receipted — **no per-service code change**.

## What it does

- Forwards `/v1/chat/completions` and `/v1/embeddings` (and the Ollama-native `/api/chat`,
  `/api/generate`, `/api/embeddings`, `/api/embed`) to `RECEIPT_GATEWAY_BACKEND`, preserving client
  headers (e.g. `Authorization`) and returning the backend's exact response.
- On a successful non-streaming JSON response, emits an `InferenceReceipt` with the backend's **real**
  usage token counts and real input/output hashes, appended to a durable ledger (`RECEIPT_GATEWAY_LEDGER`,
  SEAM-011: durable non-local ledger). Each receipt chains to the previous via `ledgerPrevHash`.
- Passes non-inference paths (`/health`, `/healthz`, and anything unrecognised) straight through.
- Exit codes: `0` ok · `1` conformance failure · `2` usage/infra error.

## How it's used in prophet-platform

`memoryd` (`deploy/values/memoryd.yaml`) sets `EMBEDDINGS_URL` to this gateway instead of straight at the
`embeddings` service, so its semantic vectors are receipted. `RECEIPT_GATEWAY_BACKEND` forwards to
`http://embeddings:8080`. Deployed via the reusable `charts/socioprophet-service` chart with
`deploy/values/receipt-gateway.yaml`; built by `.github/workflows/images.yml` like every other first-party
app; listed in `deploy/argocd/platform-services.yaml`.

## Configuration (env)

| Var | Purpose |
| --- | --- |
| `RECEIPT_GATEWAY_BACKEND` | Upstream OpenAI-compatible server (default `http://embeddings:8080`). |
| `RECEIPT_GATEWAY_HOST` / `RECEIPT_GATEWAY_PORT` | Listen address (default `0.0.0.0:8898`). |
| `RECEIPT_GATEWAY_LEDGER` | Append-only receipt ledger path (on the mounted PVC). |
| `RECEIPT_GATEWAY_MODEL_DIGESTS` | JSON `{model: digest}` map so each receipt records the served model's real digest. |
| `RECEIPT_GATEWAY_MODEL_DIGEST` / `_MODEL_PATH` | Single-model digest, or a weights path to hash, when not using the map. |

## Provenance

Vendored from the estate's contract repo `SociOS-Linux/workstation-contracts`
(`tools/receipt_gateway.py`, `tools/inference_receipt_emitter.py`,
`schemas/model-plane/InferenceReceipt.schema.json`) at commit
`c7c1071e4d4adfbf8ed73efe4609e48a7d9e5f68` — the same source and pin the Noetica compose overlay uses. This
is a first-party estate component (dogfooding the model-plane spec), not a third-party dependency. Re-vendor
from that repo when the gateway or the `InferenceReceipt` schema changes upstream.
