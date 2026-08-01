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

## 6. Decisions

### Taken (2026-08-01)
- ✅ **Transition:** keep **Google/Firebase federated now** (non-breaking), **PLAN a later hard-cut** to fully sovereign. (Decision #2 → 1-now, path-to-2.)
- ✅ **First target:** **gitea** (lowest blast radius, OIDC code already exists), then zot UI, then web app last. (Decision #6.)
- ✅ **Identity root BLESSED (2026-08-01):** finish the estate's own sovereign identity — **`did:key` (humans) + SPIFFE (workloads) → the built broker**, minting OIDC. Reject Urbit; consume ORCID only as a relayed factor; passkey/TPM = the enrollment layer. Finish build-plan steps 5–10. (Decision #1 & #2 root.)
- ✅ **Issuer URL PINNED:** **`socioprophet.id`** — `charts/prophet-workspace/values.yaml` `brokerHostname` updated `id.socioprophet.ai` → `socioprophet.id` (config only; gated on DNS + registrar-lock before deploy). (Decision #3.)
- ✅ **IdP layer:** lean **Authentik (MIT core)** behind the broker, with **user-selectable auth methods** — sovereign key (did:key/passkey) first, external factors (Google/GitHub/ORCID) as *relayed* options the user may choose. Keycloak (Apache-2.0) is the fallback; Zitadel EXCLUDED (AGPL-3.0). (Decision #4.)
- ✅🔬 **Issuer (#1) — RESOLVED by study: the estate already built the answer.** `prophet-platform/apps/identity-prime` (`docs/SOVEREIGN_ANONYMOUS_IDENTITY.md`) + `Noetica/agent-machine/lib/sovereign-{id,broker,oidc,vault}.ts` (build steps 1–4 ✅) already implement a sovereign broker. **Human root = `did:key` (Ed25519, user-held in OS keychain — "a KEY not an email"); per-scope HKDF(root, scope_id) → unlinkable pairwise pseudonyms; `sovereign-oidc.ts` already mints EdDSA OIDC tokens + JWKS.** Deployed by `charts/prophet-workspace/templates/broker.yaml` as `workspace-broker`. So the "issuer" IS this broker — Option B, but more built than §3 realized.
  - **Verdict on the named options:** ❌ **Urbit** — research/ideological, Ethereum-L1 root, no OIDC → reject. ❌ **ORCID** ("ochid"?) — centralized SaaS, disqualified as root; consume only as a *relayed factor*. ✅ **SPIFFE** — keep for AGENT/workload identity (already built, Apache-2.0, no human attestor); federate its `oidc-discovery-provider` into the broker. ✅ **Passkey/WebAuthn + TPM/Secure Enclave** — the **production-ready human enrollment/step-up** layer. ✅ **W3C DID/VC** — the honest unifying frame; `did:key`/`did:web:socioprophet.id` usable now; credential layer (SD-JWT-VC draft / BBS+) = research roadmap, not a launch dep.
  - **Shape:** two symmetric crypto roots — `did:key` (humans) + SPIFFE (workloads) → ONE sovereign broker → standard OIDC at **`socioprophet.id`** → gitea/zot/web/matrix. Everything needed to LAUNCH is real + coded (did:key, passkey/TPM attestation, HKDF pairwise, EdDSA OIDC); build steps 5–10 remain.
  - 🔴 **Immediate: pin the `iss`.** DNS `infra/tofu/envs/dns/domains.yaml` reserves `socioprophet.id` for the identity plane, but `values.yaml` sets `brokerHostname: id.socioprophet.ai`. The OIDC `iss` claim is load-bearing — pick ONE (recommend `socioprophet.id`) before any service binds.
  - 🔴 **License gate:** if a packaged IdP goes behind the broker (LDAP/admin/passkey UX), use **Keycloak (Apache-2.0)**. **Zitadel switched to AGPL-3.0 in 2025 → EXCLUDED** by the MIT/Apache-only rule. Authentik (MIT core) is fallback.
- 🏷️ **Issuer domain: `socioprophet.id`** — the estate owns it (per Michael); semantically ideal ("id") for the identity root, preferred over `id.socioprophet.ai` / `id.workspace.socioprophet.ai`. 🔴 **BLOCKER before use:** the domain audit ([[project_prod_auth_domain_audit]]) previously flagged `socioprophet.id` as **UNOWNED / takeover-risk**. Rooting estate identity on a takeover-able domain is catastrophic — treat as a hard gate. **Verified 2026-08-01 (DNS/whois):** registered at **Namecheap**, currently **PARKED** (`192.64.119.248`, NS `dns{1,2}.registrar-servers.com`, `www`→`parkingpage.namecheap.com`). Owned + DNS-controllable (consistent with the estate Namecheap portfolio), and the parking is Namecheap's own — **no active dangling-CNAME takeover vector**. Remaining gate (registrar-account level, not DNS-visible): confirm it sits in the **estate's** Namecheap account, enable **registrar-lock + DNSSEC**, then point DNS at the broker. Corrects the stale "unowned" note in the domain audit.

### Still open (detail — decide as we wire)
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
