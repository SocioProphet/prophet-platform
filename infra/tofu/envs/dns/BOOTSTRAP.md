# envs/dns — bootstrap to live

Turns the plan-only `envs/dns` PR into an applied DNS plane. Follow in order. Nothing
here is auto-run; each step is a deliberate, reviewable action. Doctrine: secrets are
**minted in CI / stored in a secret manager, never committed, never long-lived PATs**.

## 0. Prerequisites

- The `feat/dns-portfolio-iac` PR is merged (code on `main`).
- WIF is already wired for CI (`WIF_PROVIDER`, `WIF_SERVICE_ACCOUNT` secrets exist — the
  `gcp-landing` plan job uses them).
- Decide which GCP project hosts the zones (a dedicated `…-dns` project is cleanest; a
  shared prod project is fine to start).

## 1. GCP project + API + state

```bash
PROJECT=<your-dns-project>            # e.g. socioprophet-dns
gcloud config set project "$PROJECT"
gcloud services enable dns.googleapis.com --project "$PROJECT"

# State bucket already exists (prophet-tofu-state-prod); prefix dns/ is set in versions.tf.
# Grant the CI service account DNS admin on the project:
gcloud projects add-iam-policy-binding "$PROJECT" \
  --member="serviceAccount:<WIF_SERVICE_ACCOUNT>" \
  --role="roles/dns.admin"
```

Add the CI secret so the WIF-gated `plan-dns` job activates:

```bash
gh secret set GCP_DNS_PROJECT --body "$PROJECT" --repo SocioProphet/prophet-platform
```

Optional: override the DMARC reporting mailbox (defaults to `dmarc@socioprophet.ai`) by
setting `TF_VAR_dmarc_rua` in the `gcp-plan` environment.

## 2. First apply — the security baseline (no registrar changes yet)

`manage_registrar` stays `false`, so this creates **zones + baseline records only**. It
does **not** touch the registrar, so nothing goes live until you delegate NS in step 4.

```bash
cd infra/tofu/envs/dns
tofu init
TF_VAR_project="$PROJECT" tofu plan -out=plan.out    # review carefully
# apply follows the gcp-landing apply-gate: manual GH environment approval + signed plan
TF_VAR_project="$PROJECT" tofu apply plan.out
tofu output name_servers                              # per-domain NS to delegate
```

## 3. Namecheap API — creds + the static-IP allowlist (the real gate)

Namecheap's API requires the **calling IP to be pre-allowlisted**, and CI runner IPs are
dynamic. Pick one:

- **Cloud NAT with a reserved static IP** (recommended, and codified): the `egress-nat`
  module provisions a reserved external IP + Cloud Router + Cloud NAT. Enable it in this env:
  ```bash
  TF_VAR_project="$PROJECT" TF_VAR_create_egress_nat=true \
    TF_VAR_egress_network=<vpc-name-or-self-link> TF_VAR_egress_region=<region> \
    tofu apply
  tofu output egress_ips        # -> the IP(s) to allowlist and use as namecheap_client_ip
  ```
  Whatever performs the registrar call (self-hosted runner / Cloud Run job / GCE) must
  egress through that VPC to inherit the fixed IP.
- **Small bastion / self-hosted runner** with a fixed public IP (alternative to the module).

Then, in the Namecheap dashboard: Profile → Tools → **API Access** → enable, and add that IP
to the **whitelist**. (API access is available with 20+ domains — met.)

Mint the creds as CI secrets (never commit):

```bash
gh secret set NAMECHEAP_API_USER   --body "<api_user>"   --repo SocioProphet/prophet-platform
gh secret set NAMECHEAP_USER_NAME  --body "<username>"   --repo SocioProphet/prophet-platform
gh secret set NAMECHEAP_API_KEY    --body "<api_key>"    --repo SocioProphet/prophet-platform
gh secret set NAMECHEAP_CLIENT_IP  --body "<static_ip>"  --repo SocioProphet/prophet-platform
```

Wire them into the `plan-dns` / apply job as `TF_VAR_namecheap_*` (sandbox first via
`TF_VAR_namecheap_sandbox=true`).

## 4. Delegate NS (go live, per domain)

Flip delegation on, ideally a few domains at a time (set `manage_ns: true` on those in
`domains.yaml`), starting with **parked/reserved** domains — never a live-mail canonical
until its baseline is confirmed.

```bash
TF_VAR_project="$PROJECT" TF_VAR_manage_registrar=true \
  TF_VAR_namecheap_api_user=... TF_VAR_namecheap_user_name=... \
  TF_VAR_namecheap_api_key=... TF_VAR_namecheap_client_ip=<static_ip> \
  tofu apply
```

Verify: `dig NS <domain> +short` should return the Cloud DNS nameservers; then
`dig TXT <domain>` / `dig TXT _dmarc.<domain>` to confirm the baseline.

## 5. Promote DMARC on mail domains (observe → enforce)

`socioprophet.com` / `.ai` start at `p=none` (observe). After ~1–2 weeks of clean `rua`
reports (all legit senders aligned), tighten per-domain in `domains.yaml`:

```yaml
- domain: socioprophet.ai
  role: canonical
  mail: true
  dmarc_policy: quarantine   # then reject
```

Only touch SPF/MX on a mail domain by setting explicit `spf:` / `mx:` in `domains.yaml`
(e.g. Google Workspace) — the module never guesses them.

## Adversarial review — operational risks (read before delegating)

The safe first apply (zones + baseline, `manage_registrar=false`) has no known failure
mode. The following bite only at **delegation** time and are gated off by default:

1. **Redirect/canonical domains go dark if delegated before they have records.** Delegating
   NS to Cloud DNS replaces Namecheap DNS entirely — any current Namecheap URL-redirect or
   email-forwarding stops. Only delegate `reserved`/parked domains first; do not flip
   `manage_ns: true` on a `redirect`/`canonical` domain until its A/redirect records exist in
   `domains.yaml`. (The redirect target service — GCLB URL map — is not built yet.)
2. **DNSSEC needs a DS record at the registrar.** The zone is signed (`dnssec on`), but the
   chain of trust is inert until you upload the zone's DS record to Namecheap *after*
   delegation. Until then resolution works but is unvalidated. Do the DS upload as the final
   go-live step per domain (verify with `dig DS <domain> +short`).
3. **Cross-domain DMARC reports need authorization.** All domains report to
   `dmarc@socioprophet.ai`. Per RFC 7489 §7.1, a receiver only sends aggregate reports to an
   out-of-domain mailbox if the reporting domain publishes an authorization record, e.g.
   `sourceos.org._report._dmarc.socioprophet.ai TXT "v=DMARC1"`. Without it, `p=reject` still
   protects the domain — you just won't receive its `rua` reports. Add these authorization
   records in the `socioprophet.ai` zone (via `records:` in `domains.yaml`) if you want the
   reports, or set a per-domain `dmarc_rua`.
4. **null-MX / CAA formats** (`0 .`, `0 issue "…"`) are validated at `tofu plan` against
   Cloud DNS — review the first plan output before applying.

## Rollback

- Baseline records: `tofu destroy -target=module.zone["<domain>"]` (or remove from
  `domains.yaml`). Registrar NS: set `manage_ns: false` and re-point at the registrar, or
  restore the previous NS in the Namecheap dashboard. Keep TTLs (3600s) in mind for
  propagation.
