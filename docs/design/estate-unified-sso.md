# Estate-Wide Unified SSO — Design

**Goal:** every `socioprophet.ai` service (`code.socioprophet.ai` gitea, `registry.socioprophet.ai` zot, and the rest) authenticates with the **same login as `socioprophet.com`**.

**Status:** design for review. **No live auth has been changed.** Auth is a break-glass surface — nothing here ships until the decisions in §6 are made and each step is verified non-breaking.

---

## 1. The reality: this is a convergence problem, not a build

The estate has drifted into **three parallel identity planes**:

| Plane | What | Status |
|---|---|---|
| **Firebase / Google Identity Platform** (project `socioprophet-web`) | The **live** IdP for `socioprophet.com` / `app.socioprophet.com` (Google + email/pw + SMS MFA) | ✅ LIVE, production |
| **socbase** (self-hosted GoTrue + PostgREST) | Intended Firebase *replacement* for the web SPA | 🔴 DOWN (bootstrap Job never ran → missing `authenticator`/`anon`/`service_role` roles; GoTrue `search_path` migration bug) |
| **sovereign-broker** (custom ed25519 OIDC issuer at `id.*`) | Intended SSO issuer for gitea/workspace | 🟡 Scaffolded, disabled, image built, **not wired** |

**The key insight:** gitea's OIDC integration is *already written* — `charts/prophet-workspace/templates/gitea.yaml` has a post-install `add-oauth` Job gated by `gitea.oidc.enabled: false`. Unifying is mostly **choosing one issuer and enabling wiring that already exists**, not greenfield work.

## 2. Current auth per service (verified, read-only)

| Host | Service | Auth today | SSO-ready? |
|---|---|---|---|
| `app.socioprophet.com` | web cockpit SPA (Vue) | **Firebase (Google)** — `client-vue/src/firebase.ts`, `GoogleAuthProvider` | via socbase or OIDC-direct |
| `code.socioprophet.ai` | gitea (ns `scm`, SQLite v1) | **Local accounts only** (`michael` admin/must-change, `estate-mirror` service) | ✅ OIDC Job coded, gated off |
| `registry.socioprophet.ai` | zot (v2.1.2) | **htpasswd + accessControl** (`ci`/`k8s-pull`/`admin` robots) | UI-OIDC capable; robots stay htpasswd |
| `id.socioprophet.ai` | sovereign-broker OIDC issuer | scaffolded, not live | — (this is the issuer itself) |
| `socbase.socioprophet.ai` | GoTrue+PostgREST | down | — |
| `mail/caldav.socioprophet.ai` | prophet-workspace | IMAP/SMTP/CalDAV creds; Google Workspace still live | later phase |

## 3. Recommended architecture — Option B: converge on `sovereign-broker`

Make **`sovereign-broker` at a single pinned `id.socioprophet.ai`** the one estate OIDC issuer, because:
- gitea's wiring already targets it (`--auto-discover-url …/.well-known/openid-configuration`);
- it's the leanest sovereign choice, consistent with the estate's gitea-over-GitLab / zot-over-Harbor posture;
- the web app reaches it via socbase/GoTrue federation (preserving the `supabase-js` DX plan) *or* OIDC-direct.

**Non-breaking transition:** keep **Google/Firebase as an upstream IdP the broker federates to**, so no one loses sign-in during cutover — the same "coexist with Google, don't break prod" posture already adopted for mail. The `socioprophet-web` Firebase OAuth client is **not deleted or rotated** until a real browser sign-in through the unified path is verified.

*(Alternatives considered: **A** socbase/GoTrue as the OIDC provider — fewest components but GoTrue's OIDC-provider maturity is weak; **C** off-the-shelf sovereign IdP (Zitadel/Keycloak/Dex) — most robust, most new infra the estate hasn't chosen. B best matches existing code + sovereignty + anti-bloat.)*

## 4. Per-service integration steps (once the issuer is chosen + hardened)

- **broker prereqs:** healthy TLS + auth-code endpoints at ONE `id.` host; `sovereign-broker-signing-key` secret; `BROKER_CLIENTS` populated.
- **gitea:** register a `gitea` client; set `gitea.oidc.{enabled=true,brokerUrl,clientId,clientSecretSecret}`; let the existing `workspace-gitea-oidc-setup` Job run the `gitea admin auth add-oauth --provider openidConnect …` (or run that one command against the live SQLite box). Keep `michael`/`estate-mirror` as **local break-glass**.
- **zot:** add an `openid`/`oauth2` block for **web-UI / human** logins → broker; **keep htpasswd robots** (`ci`, `k8s-pull`, gitea-actions) for CI push + kubelet pull (Docker token flow, not browser OIDC). Requires `rollout restart` (zot does not hot-reload).
- **web app:** socbase federates to broker (SPA keeps `supabase-js`) *or* SPA does OIDC-direct. **Do NOT touch the Firebase client** until a browser sign-in through the new path passes.

## 5. Rollout order (lowest blast radius first)

**broker (stand up + harden)** → **gitea** (code exists) → **zot UI** → **web app last** (highest risk; protects the never-delete Firebase client). Each step gated on a verified real sign-in before the next.

## 6. Decisions required (Michael)

1. **THE issuer:** (a) sovereign-broker OIDC *[recommended — matches existing gitea code]*, (b) socbase/GoTrue as OIDC provider, (c) off-the-shelf (Zitadel/Keycloak/Dex).
2. **Google now or sovereign-only:** keep **Google/Firebase as a federated upstream** during transition (non-breaking) *[recommended]* vs. hard-cut.
3. **Pin the issuer hostname:** `id.socioprophet.ai` (chart) vs `id.workspace.socioprophet.ai` (live deployment) — must be ONE value before any `--auto-discover-url` wiring.
4. **socbase:** fix it now (root-caused: run the schema bootstrap Job + the GoTrue `search_path` fix) or defer and go OIDC-direct for the web app?
5. **gitea two-sources-of-truth:** wire OIDC into the live SQLite `deploy/scm/gitea-sovereign.yaml`, or migrate onto the OIDC-ready Postgres Helm gitea first?
6. **Rollout order:** confirm broker → gitea → zot → web.
7. **Identity mapping:** humans → SSO (`michael@socioprophet.ai`); keep service/robot accounts (`estate-mirror`, zot `ci`/`k8s-pull`) as local/htpasswd (not federated). Confirm.
8. **Guardrail ack:** cutover explicitly preserves the `socioprophet-web` Firebase OAuth client/web key until a real browser sign-in through the unified path is verified.

## 7. Guardrails (hard constraints)

- 🔴 **Never delete/rotate the `socioprophet-web` Firebase OAuth client / web key** until the unified path is proven in a real browser (headless can't prove it).
- Pin **one** issuer hostname before wiring (auto-discover must match exactly).
- zot config changes need `rollout restart` (no hot-reload); a user needs to be in **both** htpasswd (authn) and accessControl (authz).
- Keep local/robot accounts as **break-glass** so an issuer outage can't lock everyone out.
- Sovereign + MIT/Apache posture: prefer the broker/GoTrue path over new heavyweight IdP infra unless a decision explicitly chooses Option C.

---

*Source: read-only discovery across `~/dev` (prophet-platform, socioprophet-web, gitea-sovereign) + the project memory graph. Key paths: `charts/prophet-workspace/templates/{gitea,broker}.yaml` + `values.yaml` `gitea.oidc.*`; `infra/k8s/sovereign-broker/base/deployment.yaml`; `infra/k8s/zot/base/configmap.yaml`; `socioprophet-web/client-vue/src/firebase.ts`.*
