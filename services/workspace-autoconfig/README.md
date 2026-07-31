# workspace-autoconfig — zero-touch mail setup ("type email + password, done")

The make-or-break of the SME promise: a user enters `you@socioprophet.ai` + password and every client
configures itself. This directory holds the static discovery documents for all three ecosystems.

## Canonical mail settings (single hostname — cert-clean)

| | Host | Port | Security | Auth | Username |
|---|---|---|---|---|---|
| IMAP | `mail.socioprophet.ai` | 993 | implicit TLS (SSL) | password | full email |
| SMTP submission | `mail.socioprophet.ai` | 587 | STARTTLS | password | full email |

One hostname for both so the certbot cert (`-d mail.socioprophet.ai`) matches exactly — no `imap.`/`smtp.`
hostname-vs-cert mismatch. `imap.socioprophet.ai` may later be added as a cert SAN + CNAME if desired.

## Discovery mechanisms (what each client probes, in order)

- **Thunderbird / K-9 / FairEmail / Evolution** → `https://autoconfig.socioprophet.ai/mail/config-v1.1.xml?emailaddress=<addr>`
  then `https://socioprophet.ai/.well-known/autoconfig/mail/config-v1.1.xml`, then the DB, then SRV.
  Served by: [`autoconfig/mail/config-v1.1.xml`](autoconfig/mail/config-v1.1.xml) (+ mirrored under `.well-known/`).
- **Outlook / Windows Mail** → `https://autodiscover.socioprophet.ai/autodiscover/autodiscover.xml` (POST),
  then `https://socioprophet.ai/autodiscover/...`, then SRV `_autodiscover._tcp`.
  Served by: [`autodiscover/autodiscover.xml`](autodiscover/autodiscover.xml).
- **Apple Mail (iOS/macOS)** → also reads the Mozilla autoconfig, OR install the one-tap profile
  [`apple/socioprophet-mail.mobileconfig`](apple/socioprophet-mail.mobileconfig).
- **DNS SRV** (already published by the `dns` module, PR #1137): `_imaps._tcp`, `_submission._tcp` — the
  universal fallback so even clients that skip HTTP discovery land on the right host/port.

## Serving (deployment — next step)

A tiny static web layer over HTTPS. Two options, both sovereign:
1. **On the mail VM** — add nginx to the VM cloud-init, add `autoconfig`/`autodiscover` to the certbot `-d`
   list (both A records → the VM IP), serve this dir. Fewest moving parts; co-located with mail.
2. **In-cluster** — a small nginx Deployment + Ingress + ManagedCertificate for `autoconfig.` / `autodiscover.`.

Required DNS: `A autoconfig → <mail VM IP>`, `A autodiscover → <mail VM IP>` (or the ingress IP for option 2).
Serve `.mobileconfig` as `Content-Type: application/x-apple-aspen-config`.

## Hardening before GA

- **Sign the `.mobileconfig`** (`openssl smime -sign` with a trusted cert) so iOS shows "Verified", not a warning.
- **Dynamic autodiscover** responder that echoes the posted `<LoginName>` (a ~20-line handler) for the smoothest
  Outlook path; the static file already covers the common case.
- Add `autoconfig`/`autodiscover` (and optionally `imap`/`smtp`) as **cert SANs**.

## Verify

- Thunderbird: New Account → type address+password → should auto-fill `mail.socioprophet.ai` 993/587.
- iOS: open the `.mobileconfig` URL in Safari → Install → enter address+password.
- Outlook: Add Account → email → should discover IMAP/SMTP automatically.
- `dig SRV _imaps._tcp.socioprophet.ai` → `mail.socioprophet.ai:993`.
