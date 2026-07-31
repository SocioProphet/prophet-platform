# envs/dns — domain portfolio DNS-as-code

One managed zone per owned domain, driven by [`domains.yaml`](./domains.yaml). Namecheap
stays the **registrar**; DNS is served by a cloud you choose. Repeatable, automatable
replacement for the manual `infra/terraform/modules/dns` stub.

## Architecture — cloud-portable by construction

```
domains.yaml ──▶ module dns-records (cloud-AGNOSTIC record model + all safety logic)
                      │  outputs: { zone, records:[{name,type,ttl,rrdatas}], … }
                      ▼
           ┌──────────────────────────┐
           │  emitter (var.dns_cloud)  │   gcp → dns-zone-gcp (Cloud DNS)
           │  renders records 1:1      │   aws → dns-zone-aws (Route53)
           └──────────────────────────┘   +cloud → one new emitter, same contract
```

All safety derivation lives once in `dns-records`, so it can never diverge between clouds.
Switching or adding a cloud is a new emitter against the same record contract — **no rewiring
of `domains.yaml`, the baseline, or the safety model.** Select with `var.dns_cloud` (`gcp`
default, `aws` supported; unimplemented values fail closed via validation).

## What it does

- Creates a managed zone (DNSSEC on) per domain.
- Applies a **safety-aware email-security baseline** to every zone:
  - **Parked / non-mail** (`mail: false`, the default): hard anti-spoof lockdown —
    `SPF -all`, **null-MX** (`0 .`, RFC 7505), `DMARC p=reject`, `CAA`.
  - **Mail** (`mail: true`): never auto-guessed — SPF/MX left unmanaged, `DMARC p=none`
    (observe) with `rua` reporting, so live deliverability cannot be broken. Move to
    `quarantine`/`reject` per-domain via `dmarc_policy` once reports look clean.
  - Cross-domain DMARC aggregate reporting is authorized automatically (`_report._dmarc`
    records generated in the `rua` domain's zone, per RFC 7489 §7.1).
- Optionally delegates nameservers at Namecheap (`registrar-namecheap`), OFF by default and
  **fail-closed**: it refuses to delegate a `canonical`/`redirect` domain that has no records
  (which would make it resolve to nothing).

## Audit

`tofu output -json record_manifest` renders the exact record set that will exist per domain —
cloud-agnostic, reviewable before apply. Every zone carries `managed_by=tofu-dns-portfolio`.
CI posts the `tofu plan` to the PR as the change-level audit trail.

## Add / change a domain

Edit `domains.yaml` and open a PR. CI runs `tofu fmt` + `validate`; the plan is posted to
the PR. That is the whole workflow — no console clicks.

## Apply gate (same doctrine as envs/gcp-landing)

Plan-only in CI. Apply requires manual GitHub Actions environment approval + a signed plan.
Registrar NS delegation (`var.manage_registrar = true`) stays OFF until:

1. A plan is reviewed, and
2. The **Namecheap API `client_ip` is allowlisted**. Namecheap's API requires the calling
   IP to be pre-authorized; GitHub runner IPs are dynamic, so run registrar changes from a
   **static egress IP / bastion** (or a self-hosted runner with a fixed NAT). API access is
   enabled once the account has 20+ domains (met).

## Variables / secrets (mint in CI, never commit)

| Variable | Source |
|---|---|
| `project` | GCP project hosting the zones (`TF_VAR_project` / secret) |
| `dmarc_rua` | reporting mailbox (default `dmarc@socioprophet.ai`) |
| `manage_registrar` | keep `false` until the plan is reviewed |
| `namecheap_api_key` (sensitive), `namecheap_api_user`, `namecheap_user_name`, `namecheap_client_ip` | Namecheap API creds, minted in CI |

## First-run bootstrap

```bash
cd infra/tofu/envs/dns
# comment out the gcs backend in versions.tf for the very first local run, or:
tofu init
TF_VAR_project=<gcp-project> tofu plan
```

After apply, read `tofu output name_servers` for the per-domain Cloud DNS nameservers
to delegate at the registrar (or flip `manage_registrar` once the client_ip is allowlisted).
