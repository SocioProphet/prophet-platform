# Prophet Mail — cutover runbook (Google Workspace → sovereign)

Goal: migrate `socioprophet.ai` mail off Google Workspace **without losing or bouncing a single message**.
Principle: pick the most robust option at every step; never flip MX until every gate below is green.

## Send-path decision (Michael 2026-07-31)
GCP **permanently blocks outbound port 25**, so a GCP MTA can *receive* but not *send* direct-to-MX.
- **Interim = A (relay):** Postfix relays outbound via a smarthost on 587 (Google Workspace SMTP relay
  during transition = no new vendor; or SES/Postmark). Unblocks sending today for validation + warm-up.
- **Target = B (off-GCP):** host the sender on a **port-25-friendly provider (Hetzner)** — fully sovereign,
  direct-to-MX, no third party. The Postfix/Dovecot/startup config is portable; a `hetzner-mail` tofu env
  reuses it. GCP box can keep *receiving*, or mail moves wholesale to Hetzner. **B is the end state.**

## Current state (2026-07-31)
- ✅ Inbound MTA up on GCP VM `prophet-mail` (130.211.115.191): postfix+dovecot active, listening 25/587/993,
  on a persistent disk (cert survives replace). PTR set. Admin mailbox seeded.
- ⚠️ TLS = Let's Encrypt **staging** (untrusted) until prod quota clears → flip `acme_staging=false`.
- 🔴 OpenDKIM not signing yet (fixable). 🔴 Outbound needs A (relay) or B (off-GCP).
- MX still points at Google (unchanged — nothing at risk).

## Gates — ALL green before MX flip (in order)
1. **Inbound reachable** — verify from OUTSIDE (never the agent sandbox, which blocks mail ports):
   `nc mail.socioprophet.ai 25` from a laptop, or check-host.net / mxtoolbox SMTP test. Expect a `220` banner.
2. **TLS trusted** — swap staging→prod cert (`acme_staging=false` once LE quota clears). `openssl s_client
   -connect mail.socioprophet.ai:993` shows a valid chain.
3. **DKIM signing live** — OpenDKIM active; send a test and confirm `dkim=pass`.
4. **Outbound works** — via A (relay) now, or B (Hetzner) direct. Send to check-auth@verifier.port25.com.
5. **Auth alignment** — SPF (single record, `include:_spf.google.com ip4:<send-ip> ~all`), DMARC `p=none`,
   DKIM all **pass + aligned**. (2026 bulk rules are SMTP-reject-enforced; baseline applies to all senders.)
6. **mail-tester.com ≥ 9/10** — the go/no-go. SPF+DKIM+DMARC+PTR+TLS all green, not on RBLs.
7. **Mailboxes migrated** — `imapsync` from Google IMAP → Dovecot for each user (idempotent, re-runnable).

## Cutover (only when 1–7 pass)
1. Lower MX/A TTLs to 300s, 24h ahead.
2. Add the sovereign MX **alongside** Google at **equal priority** — watch both flow, no downtime.
3. Soak 24–48h; confirm mail arrives at the sovereign box; monitor bounces/deferrals.
4. Raise sovereign MX priority above Google; keep Google as lower-priority backup ~2 weeks.
5. **DMARC ramp:** `p=none` → `p=quarantine` (after a week of clean reports) → `p=reject`.
6. Remove Google MX; keep Google read-only ~2 weeks as a safety net; then cancel seats.

## Rollback (any gate regresses)
Raise Google MX priority back above the sovereign box (or remove the sovereign MX). TTL 300s = ~5-min revert.
Nothing is destructive until step 6; Google keeps receiving throughout.

## Robustness / lights-out (ties to the resiliency doctrine)
- Persistent disk (cert+mail survive replace) ✅ · resilient-vm module (MIG auto-heal) = #33/#34.
- Backups: `/var/mail` → object storage daily + disk snapshots. Restore-drill before trusting it.
- Monitoring: uptime (25/993), cert-expiry, disk, **RBL/blocklist watch** → alert. certbot auto-renew ✅.
