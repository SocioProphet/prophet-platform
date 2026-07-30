# prophet-workspace mail — deploy + cutover runbook

Goal: stand up self-hosted mail (Postfix + Dovecot + Radicale) on GKE and migrate `socioprophet.ai` off Google
Workspace **without losing deliverability or dropping mail**. The steps below are the parts that live outside k8s
(DNS, IPs, certs, reputation) and the safe cutover.

> ⚠️ **Canonical deploy = kustomize via ArgoCD, NOT the Helm chart.** The mail/cal/drive daemons run **live today**
> in namespace **`socioprophet`**, deployed by the ArgoCD ApplicationSet `workspace-services` from
> `infra/k8s/workspace-*/overlays/p0-lab`, pulling images from **`registry.socioprophet.ai`** (sovereign zot).
> `charts/prophet-workspace` is a richer **design reference** (it carries the opt-in TLS/DKIM/relay/LB wiring), but it
> is **deployed by nothing**. **Do NOT `helm install` it** — that stands up a *second*, GHCR-imaged stack in `ns/workspace`
> alongside the live one. The provisioning steps here (static IPs, PTR, TLS, DKIM, DNS, relay) still apply; the chart's
> value keys are being ported into the kustomize base as opt-in components. Until that lands, treat this runbook's
> `values.yaml`/`helm` references as the *design intent*, and apply the equivalent config through the kustomize overlays.

## 0. Prereqs
- GKE cluster + `kubectl`/`helm`; the platform Postgres reachable in-cluster as `postgres` with secret `postgres-credentials`.
- GHCR access. Build + push the images: `REGISTRY=ghcr.io/socioprophet/prophet-platform TAG=dev scripts/build-push-workspace.sh`
- cert-manager installed (for TLS), or bring your own TLS secret.

## 1. Static IPs + reverse DNS (do FIRST — reputation depends on it)
```
gcloud compute addresses create ws-smtp --region <region>   # MX/SMTP IP
gcloud compute addresses create ws-imap --region <region>   # IMAPS IP
```
- Put the SMTP IP in `loadBalancer.smtp.staticIP`, the IMAP IP in `loadBalancer.imap.staticIP`.
- **Set PTR (reverse DNS) on the SMTP IP → `mail.socioprophet.ai`.** Without a matching PTR, most receivers reject you.
  (GCP: set the reverse record on the external address; or via your provider. Test: `dig -x <smtp-ip> +short`.)

## 2. DNS records (at the socioprophet.ai zone)
| Type | Host | Value |
|------|------|-------|
| A | `mail` | <smtp static IP> |
| A | `imap` | <imap static IP> |
| MX | `@` | `10 mail.socioprophet.ai.` |
| TXT (SPF) | `@` | `v=spf1 ip4:<smtp-ip> ~all` (add the relay's include if using one) |
| TXT (DKIM) | `default._domainkey` | `v=DKIM1; k=rsa; p=<public key>` (see step 4) |
| TXT (DMARC) | `_dmarc` | `v=DMARC1; p=quarantine; rua=mailto:postmaster@socioprophet.ai; adkim=s; aspf=s` |
| A | `caldav` | <ingress IP> |

Keep the **Google MX in place** during setup (lower priority test on a subdomain or a parallel domain first).

## 3. TLS
- `kubectl create secret tls mail-tls --cert=fullchain.pem --key=privkey.pem -n workspace` (or cert-manager Certificate for `mail.`/`imap.`/`caldav.socioprophet.ai`). Set `tls.certSecret: mail-tls`.

## 4. DKIM
- Generate: `opendkim-genkey -s default -d socioprophet.ai` → `default.private` (key) + `default.txt` (DNS).
- `kubectl create secret generic mail-dkim --from-file=default.private -n workspace` → set `dkim.existingSecret: mail-dkim`.
- Publish `default.txt` as the DKIM TXT (step 2). (Postfix DKIM milter/opendkim wiring is the one image TODO — see Gaps.)

## 5. Mailboxes
- Hash each password: `doveadm pw -s SHA512-CRYPT` (or `openssl passwd -6`).
- Add to values `seed.users: [{ email: gus@socioprophet.ai, passwordHash: "{SHA512-CRYPT}$6$..." }]`. The post-install
  Job applies `mail-schema.sql` + seeds `mail_domains`/`mail_users` (idempotent).

## 6. Outbound deliverability — use a relay until the IP is warm
A brand-new cloud IP has near-zero sending reputation; direct-to-MX mail will be junked or rejected. Sovereign-default
policy: **stay decoupled, local-first, and treat any external smarthost as opt-in only.**
- **Default (sovereign):** direct-to-MX from our own IP, after PTR is set + IP warm-up + clean RBL checks. No third
  party sees our mail. Ramp send volume gradually to build reputation.
- **Opt-in crutch (temporary):** if early deliverability is unacceptable, `relay.enabled: true` with an external
  smarthost (SES/Postmark, or Google's SMTP relay during transition) + `relay.existingSecret`. Explicitly opt-in,
  time-boxed to the warm-up window, then dropped. Not the default — it hands mail to a third party.

## 7. Deploy + verify BEFORE cutover
```
helm upgrade --install prophet-workspace charts/prophet-workspace -n workspace --create-namespace -f your-values.yaml
```
- `kubectl get svc -n workspace` → confirm the LB IPs match your static IPs.
- Send a test to `check-auth@verifier.port25.com` / use **mail-tester.com** → aim for **≥ 9/10** (SPF+DKIM+DMARC+PTR all green).
- IMAP login test (`openssl s_client -connect imap.socioprophet.ai:993`), send/receive a round-trip.

## 8. Cutover (only when step 7 passes)
1. Lower TTLs on the MX/A records 24h ahead.
2. Add the new MX **alongside** Google at equal-or-lower priority; watch both flow.
3. Migrate existing mailboxes (imapsync from Google IMAP → Dovecot).
4. Remove the Google MX; keep Google read-only ~2 weeks as a safety net.
5. Cancel Google Workspace seats.

## Gaps / TODO before production
- **DKIM signing isn't wired into the Postfix image yet** — add opendkim (milter) to `services/workspace-smtp` +
  mount `dkim.existingSecret`. Until then, outbound is unsigned (relay providers can sign for you as a stopgap).
- **TLS isn't referenced in `main.cf`/`dovecot.conf` yet** — add `smtpd_tls_*` / dovecot `ssl=required` pointing at
  `/etc/postfix/tls` `/etc/dovecot/tls`. (Mounts are wired in the chart; the config lines are the remaining edit.)
- Backups for the `vmail` + Radicale PVCs (Velero or scheduled snapshots).
- Spam filtering (rspamd) is not included — add as a milter if needed.
