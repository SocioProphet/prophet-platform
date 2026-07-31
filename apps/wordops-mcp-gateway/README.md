# wordops-mcp-gateway

The WordOps lease-enforcing MCP gateway — the enforcement point where a
capability-lease is checked and a durable `ExecutionReceipt` is written. Matrix
rooms are collaboration context; **this gateway + the ledger are the authorization
sink**, never a room.

See [`docs/WORDOPS_REFERENCE_FLOW.md`](../../docs/WORDOPS_REFERENCE_FLOW.md) for the
end-to-end incident → containment flow.

## Endpoints

| Method + path | Purpose |
|---|---|
| `GET /healthz` | liveness/readiness |
| `GET /.well-known/oauth-protected-resource` | Protected Resource Metadata (RFC 9728): resource + Keycloak authorization server + scopes |
| `POST /mcp/invoke` | privileged tool call under a capability-lease |
| `DELETE /mcp/session` | explicit session teardown (`MCP-Session-Id`) |

## Enforcement (`POST /mcp/invoke`)

Body: `{ "lease": <capability-lease>, "tool": {name, audience, required_scope}, "params": {scope} }`.
The gateway authorizes the lease — mirroring OPA `wordops.authz.allow_action` plus
expiry and case/task binding:

- lease active (now within `[not_before, expires_at]`; malformed window → fail closed)
- `tool.audience` ∈ lease `aud` (string or array)
- `tool.required_scope` ∈ lease `scope`
- `case_id` + `task_id` present
- a `containment:sever*` scope is intrinsically **risk_class A4**

On **allow**: calls `gbrg-containment`, maps the `ContainmentProofArtifact` to a
verdict (`PROVED` → `verified`; a no-op `INCONCLUSIVE` sever → `pending`, never
verified), and `POST`s an `ExecutionReceipt` to the ledger.
On **deny**: fails closed **and** writes a `block`/`denied` receipt — A4 is heavily
audited (teeth both ways).

## Config (env)

| Var | Default |
|---|---|
| `PORT` | `8080` |
| `GBRG_CONTAINMENT_URL` | `http://gbrg-containment:8080` |
| `LEDGER_URL` | `http://agent-activity-ledger:8080` |
| `AUTH_SERVER` | `https://auth.socioprophet.ai/realms/wordops` |
| `RESOURCE_URL` | `https://agents.socioprophet.ai/mcp/wordops` |

## Test

```sh
cd apps/wordops-mcp-gateway && GOWORK=off go test ./...
```

Sessions are **not** authentication (they are bound to the authenticated caller);
durable workflow state lives outside MCP, in the ledger and the case kernel.

## Security scope (honest)

This increment enforces the lease **claims** (audience/scope/case/task/expiry,
containment ⇒ A4). It does **not** yet verify the lease's cryptographic
authenticity — JWT signature + issuer (Keycloak JWKS) and DPoP proof-of-possession
(`dpop_jkt`) are the next hardening step. Until then, treat the gateway as
claim-enforcing, not identity-verifying, and keep it reachable only from inside the
mesh. The token schema already carries `dpop_jkt` for the binding.
