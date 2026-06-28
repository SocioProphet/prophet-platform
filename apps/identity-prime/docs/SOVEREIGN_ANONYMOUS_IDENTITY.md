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

## Compulsion resistance — the core notion we protect ("can't," not "won't")
The operator must be **architecturally unable** to unlock an account or reveal confidential info — because the keys
and plaintext never exist on the operator's side. Not a policy promise; a structural impossibility.
- **Data is E2E-sealed under root-derived keys** (`sovereign-vault.ts`, proven): every scope's data is encrypted with
  `HKDF(root, data/<scope>)`; the root never leaves the edge. The service stores **only ciphertext + public
  verification material**. No operator-held key decrypts anything.
- **Auth forgery yields nothing.** Even if the IdP signing key were misused to forge a login, the account contains
  only ciphertext the forger can't read. Confidentiality is independent of auth and survives it.
- **No account "unlock."** Access is gated by the user's root-derived facet key; there is no operator credential that
  resets or unlocks an account. Recovery is user-side (seed backup / social-recovery threshold), never operator escrow.
- **Therefore a subpoena to the operator returns ciphertext and public keys — nothing confidential.** Lawful process
  must target the *user* (due process), who holds the only keys. That is the protection.

## Bounded accountability — WITHOUT an operator backdoor
Anonymous-first ≠ lawless, but accountability must never become an operator capability (that would be a compellable
backdoor). `RevocationToken` revokes a scoped facet (a public-state operation — reveals nothing). Any de-anonymization
(`TraceOpenRequest`) **requires the user's own root-derived disclosure key**, optionally split across the user's chosen
guardians via a **k-of-n threshold** — the operator and the DAO hold **zero** unilateral trace-open capability. So
"open this pseudonym" is impossible for us by construction; it can only happen with the user's (or their guardians')
cryptographic participation.

## DAO governance — no single compellable party (after a short bug-in period)
Run the service centrally only long enough to iron out bugs, then transfer governance to a **DAO** so there is no
single legal entity that can be compelled:
- The **IdP signing key becomes threshold (k-of-n)** across independent DAO operators → no one party can forge tokens
  or be compelled to forge; signing requires a quorum that no single jurisdiction controls.
- Protocol upgrades, revocation policy, and the (user-gated) trace-open *rules* are DAO-governed and public; the DAO
  still cannot decrypt user data or unilaterally de-anonymize — those powers don't exist anywhere in the system.
- SocioProphet may operate infrastructure but holds **no unilateral key** and so has nothing to surrender.
- Transition is the explicit milestone after stabilization; until then the same no-custody/E2E guarantees hold under
  central operation (we just haven't yet distributed the signing quorum).

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
1. ✅ **Broker core** — root seed + per-scope unlinkable facets + aliases (`sovereign-id.ts`, proven).
2. ✅ **Auth handshake** — root never leaves edge; passkey-style register/assert/verify (`sovereign-broker.ts`, proven).
3. ✅ **OIDC issuance** — standard EdDSA token, pairwise sub + alias, JWKS (`sovereign-oidc.ts`, proven).
4. ✅ **Compulsion-resistance vault** — E2E data sealing under root-derived keys (`sovereign-vault.ts`, proven).
5. ⬜ Stand up the IdP (Zitadel/Authentik) behind the broker; front Matrix + mail + DAV + web; migrate Firebase → one relayed factor.
6. ⬜ Per-scope **email aliasing** (wire `mail_aliases`) + external-IdP **relay** → Senzing defeat live.
7. ⬜ Wire the vault into app data paths (mail/drive/docs sealed under root keys) — make "we can't read it" true end-to-end.
8. ⬜ **Anonymous credentials** (SD-JWT-VC) + `AnonymousReputationReceipt`; **MDM** work-facet compartmentalization.
9. ⬜ **User-gated trace-open** (threshold across user-chosen guardians; operator/DAO hold none) + recovery (social/threshold).
10. ⬜ **DAO transition** — threshold (k-of-n) IdP signing key across independent operators; governance handover. No single compellable party.

## Why this is a moat
No mainstream identity (Google, Okta, Entra) is anonymous-first or unlinkable by construction — they're built *for*
correlation. This is the inverse: consume everything, correlate nothing, prove anything, stay sovereign. It's also
exactly what the platform's governance/ontology/scope-d stack is positioned to enforce.
