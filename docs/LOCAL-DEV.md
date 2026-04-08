# Local Development Guide — Prophet Platform

## Overview

This guide covers getting the full Prophet Platform stack running on a developer workstation.

---

## Prerequisites

| Tool | Minimum version | Install |
|------|----------------|---------|
| Go | 1.22 | https://go.dev/dl |
| Node.js | 20 LTS | https://nodejs.org |
| corepack | bundled with Node 20 | `corepack enable` |
| pnpm | via corepack | `corepack enable` |
| Python | 3.10+ | https://python.org (for `make validate`) |
| Docker / Podman | any recent | optional, for container builds |

---

## Quick start

```bash
# 1. Clone the repo
git clone https://github.com/SocioProphet/prophet-platform.git
cd prophet-platform

# 2. Validate repository structure
make validate

# 3. Build the Go services
cd apps/api/cmd/socioprophet-api && go build && cd -
cd apps/gateway/cmd/tritrpc-gateway && go build && cd -

# 4. Build the web app
cd apps/socioprophet-web
corepack enable
pnpm install
pnpm build
cd -

# 5. Run the API service locally (plaintext exemplar)
cd apps/api/cmd/socioprophet-api && go run . &

# 6. Run the gateway (HTTP → UDS bridge)
cd apps/gateway/cmd/tritrpc-gateway && go run . &

# 7. Open the web UI in dev mode
cd apps/socioprophet-web && pnpm dev
```

The web UI dev server typically starts on `http://localhost:5173`.
The API health endpoint is available at `http://localhost:8080/health` via the gateway.

---

## Directory layout

```
prophet-platform/
├── apps/
│   ├── api/              ← Go UDS service (Health.Ping → Pong exemplar)
│   ├── gateway/          ← Go HTTP/WS → TritRPC bridge
│   ├── socioprophet-web/ ← Vue 3 + Vite portal
│   └── storage-demo/     ← storage integration demonstrator
├── infra/k8s/            ← Kustomize bases + overlays for Argo CD
├── contracts/            ← Versioned event/message contracts (JSON)
├── schemas/              ← Data schemas (contracts, dolt, typedb, examples)
├── docs/                 ← All platform documentation (start here)
├── adr/                  ← Architectural Decision Records
├── mcp/                  ← MCP server definitions
└── tools/                ← Dev tooling (validate_repo.py, tritrpc helpers)
```

---

## Environment variables

| Variable | Required | Description |
|----------|----------|-------------|
| `TRITRPC_AEAD_KEY` | In production | 32-byte hex AEAD key for TritRPC framing |
| `LISTEN_ADDR` | No (default `:8080`) | Gateway HTTP listen address |
| `UDS_SOCKET` | No (default `/tmp/api.sock`) | Path to the API Unix domain socket |

For local development without encryption, leave `TRITRPC_AEAD_KEY` unset (runs plaintext mode).

---

## Running validation only

```bash
make validate
```

This checks directory structure, absence of `.DS_Store` files, and basic doc sanity.
It does not require any services to be running.

---

## Linting / formatting

- **Go:** `gofmt -l ./apps/...` (or run `go vet ./...`)
- **Web:** `cd apps/socioprophet-web && pnpm lint` (if configured)
- **Python tools:** `python3 -m py_compile tools/validate_repo.py`

---

## Troubleshooting

See [TROUBLESHOOTING.md](TROUBLESHOOTING.md) for common issues.
