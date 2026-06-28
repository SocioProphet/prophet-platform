# Sovereign, anonymous-first identity — architecture

The keystone the whole suite fronts (Matrix, mail, DAV, Collabora, web, AI Studio). Requirement: a **sovereign,
anonymous-first** identity that can *consume any external ID* (Google, corp SSO, MDM, GitHub, passkey) as a login
factor, while **obfuscating those parties' ability to correlate** — no external system (MDM, Senzing-style entity
resolution, an ad network, even our own apps beyond consent) can determine that two facets are the same sovereign
person. Built on the estate's existing identity contracts, not a parallel system.

## Model
```
            SOVEREIGN ROOT  (Ed25519 keypair / did:key — user-held, in the OS keychain; anonymous-first: a KEY, not an email)
                   │  per-relationship derivation (HKDF(root, scope_id) → unlinkable subkey)
   ┌───────────────┼───────────────┬───────────────┬───────────────┐
 scope: Google   scope: corp/MDM  scope: Matrix   scope: mail     scope: relying-party-N
 pseudonym A     pseudonym B      pseudonym C     pseudonym D     pseudonym N
 alias-email A   work-facet only  @matrix C       alias-email D   alias N
```
- **Root = a keypair the user owns** (reuse noetica's Ed25519 + OS keychain at-rest). No PII at the root. Anonymous-first.
- **Per-scope pseudonym** (`LinkabilityScope` + `pseudonymous_subject_commitment`): each relying party / external
  relationship gets a *deterministically-derived-but-cryptographically-unlinkable* facet — pairwise subject IDs
  (OIDC pairwise / Sign-in-with-Apple-relay model), derived `HKDF(root_secret, scope_id)`. Two facets can't be
  linked without the root.

## Defeating correlation (the core requirement)
1. **No shared correlatable attribute ever crosses two scopes** — this is what defeats **Senzing** (it matches
   entities on common name/email/phone/address/DOB). Each scope gets a **unique relay email alias**, **no shared
   phone/name/address**, a **distinct pseudonym**. Senzing sees N unrelated entities, never one. Enforced *by
   construction* in `IdentitySubjectContext` normalization: the broker refuses to emit a shared identifier to two scopes.
2. **Privacy relay for external IdP** — "sign in with Google/corp" routes through a relay that strips correlatable
   signals and presents a per-party alias (à la Apple Private Relay + Hide-My-Email). Google/corp authenticate you
   but can't see cross-app activity or join you to other facets.
3. **MDM compartmentalization** — the sovereign root is **never** the MDM/corp identity. On a managed device the
   corp/MDM sees only the **corp facet** (a scoped pseudonym + a disposable device identifier); the root + all other
   facets live in a compartment MDM can't read (the local-first edge: separate encrypted profile / work-profile /
   VM boundary). Principle: the MDM-enrolled identity is a *leaf the root issues*, not the root. MDM can't enumerate
   the person's other identities or correlate activity to a sovereign self.
4. **Anonymous credentials for attestations** — prove "employee" / "over-18" / "member-in-good-standing" /
   reputation **without revealing the root or a reusable handle**: BBS+ / SD-JWT-VC selective disclosure + ZK
   predicates. The verifier learns the claim, not the identity. (This is what `AnonymousReputationReceipt` already
   models — reputation under a commitment, not a name.)
5. **Compartmentalized even from our own apps** — the IdP issues *per-app pairwise* subjects, so Mail, Matrix,
   Drive, etc. each see a distinct subject; cross-app correlation requires the user's explicit consent (a "link
   these facets" action), not platform default. Privacy by compartmentalization, sovereign by default.

## Consume any external ID (without becoming it)
External OIDC/SAML/MDM/passkey/Google are **auth factors bound to the root** via `IdentityProofIngressRecord` →
normalized by `IdentitySubjectContext`. The external proof raises *assurance* on the root; it never becomes the
exposed identity. Downstream relying parties only ever receive the scoped pseudonym. So you can log in *with*
anything, but no one you log in with (or who manages your device) can resolve you across contexts.

## Bounded accountability (anonymous, not unaccountable)
Anonymous-first ≠ lawless. `RevocationToken` revokes a scoped facet; `TraceOpenRequest` can open a pseudonym to a
real subject **only under explicit, audited, scope-d-governed policy** (e.g., a warrant, an org compliance rule the
user accepted). The user/holder controls the trace-open keys; it's a constitutional floor, not a backdoor.

## Fronting the suite (the IdP)
A **sovereign broker** sits in front of a standard IdP (Authentik / Zitadel / Keycloak) and does the per-scope
pseudonym derivation + relay + attribute-aliasing. The IdP issues OIDC tokens to each app:
- **Matrix** (OIDC) → subject = Matrix-scope pseudonym. **Mail/DAV** → LDAP/OIDC bridge, scope pseudonym = the
  mailbox/principal. **Collabora/Drive/web/AI Studio** → per-app pairwise OIDC. One sovereign login; distinct
  per-app subjects.
- Migrates the current Firebase auth → the broker (Firebase becomes just *one* external factor, relayed + scoped).

## Tech mapping
- Root keypair + at-rest: reuse `noetica/agent-machine/lib/audit-key.ts` (Ed25519) + the OS keychain.
- DID: `did:key` (offline) / `did:web` (discoverable). Per-scope derivation: HKDF over the root secret.
- Contracts (already in the estate): `IdentityProofIngressRecord`, `IdentitySubjectContext`, `LinkabilityScope`,
  `AnonymousReputationReceipt`, `RevocationToken`, `TraceOpenRequest` — the data model is done; this builds the runtime.
- Anonymous creds: SD-JWT-VC (near-term, standardized) → BBS+ (full unlinkability) later.
- IdP: Zitadel or Authentik (OIDC + LDAP backends for mail/DAV), behind the sovereign broker.
- Relay: a small egress relay for external-IdP flows (alias email via the mail stack's `mail_aliases`).

## Build plan
1. **Broker + root keypair + per-scope pseudonym derivation** (HKDF) + `IdentitySubjectContext` runtime — the core.
2. Stand up the IdP (Zitadel/Authentik), OIDC, behind the broker; per-app pairwise subjects.
3. Front Matrix + mail + DAV + web on it; migrate Firebase → one relayed external factor.
4. Per-scope **email aliasing** (wire to `mail_aliases`) + the external-IdP **relay** → Senzing defeat live.
5. **Anonymous credentials** (SD-JWT-VC) for attestations; `AnonymousReputationReceipt` runtime.
6. **MDM compartmentalization** profile (managed-device work-facet isolation) + `TraceOpenRequest` governance via scope-d.

## Why this is a moat
No mainstream identity (Google, Okta, Entra) is anonymous-first or unlinkable by construction — they're built *for*
correlation. This is the inverse: consume everything, correlate nothing, prove anything, stay sovereign. It's also
exactly what the platform's governance/ontology/scope-d stack is positioned to enforce.
