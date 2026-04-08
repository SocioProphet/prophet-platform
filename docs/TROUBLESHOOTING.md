# Troubleshooting Guide — Prophet Platform

---

## 1. `make validate` fails with "missing required directory"

**Symptom:** `ERR: missing required directory: apps` (or `infra` / `docs`)

**Cause:** The directory was deleted or the repo was checked out with a sparse filter.

**Fix:**
```bash
# Ensure a full checkout
git checkout HEAD -- apps infra docs
```

---

## 2. Go build fails: `cannot find package`

**Symptom:**
```
cannot find package "..." in any of:
    /usr/local/go/src/...
```

**Cause:** Wrong Go version or missing module download.

**Fix:**
```bash
# Ensure Go 1.22+
go version

# Re-download modules
cd apps/api && go mod download
cd apps/gateway && go mod download
```

---

## 3. Web build fails: `pnpm: command not found`

**Symptom:** `pnpm: command not found` during `pnpm install`.

**Cause:** corepack not enabled.

**Fix:**
```bash
corepack enable
cd apps/socioprophet-web && pnpm install && pnpm build
```

---

## 4. API does not respond on `/health`

**Symptom:** `curl http://localhost:8080/health` returns `connection refused`.

**Possible causes and fixes:**

| Cause | Fix |
|-------|-----|
| API process not started | `cd apps/api/cmd/socioprophet-api && go run .` |
| Wrong port | Check the `--addr` flag or `LISTEN_ADDR` env var |
| UDS gateway not routing | Start the gateway: `cd apps/gateway/cmd/tritrpc-gateway && go run .` |

---

## 5. AEAD key errors at runtime

**Symptom:** `invalid key length` or `failed to decrypt frame`

**Cause:** `TRITRPC_AEAD_KEY` not set or wrong length (must be 32 bytes / 64 hex chars).

**Fix:**
```bash
export TRITRPC_AEAD_KEY=$(openssl rand -hex 32)
```

For production, load from a Kubernetes Secret (see [RUNBOOK.md](RUNBOOK.md#rotating-secrets)).

---

## 6. Argo CD shows app out-of-sync

**Symptom:** Argo CD UI shows `OutOfSync` for `prophet-platform`.

**Possible causes and fixes:**

| Cause | Fix |
|-------|-----|
| Manifests changed locally but not pushed | `git push` the infra changes |
| Resource drift (manual `kubectl` edit) | `argocd app sync --force prophet-platform` |
| Image tag mismatch | Verify the image digest in `infra/k8s/` overlays |

---

## 7. Accidental shell-snippet directory in repo

**Background:** A directory with a name resembling a shell command (beginning with `how-current)" && if ...`) was
accidentally created in the repository root. It has been removed as of the docs/ops-baseline cleanup (April 2026).
If you encounter it on an older branch, remove it with:

```bash
git rm -rf 'how-current)" && if ...'
```

No unique content was lost — the only file inside was a copy of `README.md`.

---

## Still stuck?

- Check [RUNBOOK.md](RUNBOOK.md) for operational procedures.
- Review [OBSERVABILITY.md](OBSERVABILITY.md) for logs and metrics.
- Open an issue in this repository with the error output.
