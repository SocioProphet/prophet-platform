#!/usr/bin/env bash
# Prophet Mail — sovereign MTA installer for a plain Debian 12 box (1984 Hosting / FlokiNET / any
# port-25-friendly VPS). Postfix + Dovecot + OpenDKIM + certbot, DIRECT-TO-MX (no relay, no cloud
# outbound-25 block). Portable descendant of the GCP startup, minus every GCP-ism. Idempotent.
#
# BEFORE running (on the VPS as root):
#   1. Point mail.<domain> A record at THIS box's IP; set the box's PTR (rDNS) -> mail.<domain>
#      (1984/FlokiNET set PTR from their panel or on request).
#   2. Place the two secrets (0600):
#        /root/mail-secrets/dkim.private   # the DKIM private key that matches the published DNS TXT
#        /root/mail-secrets/admin.hash     # doveadm pw -s SHA512-CRYPT  (or copy the existing hash)
#      Pull the DKIM key from the existing k8s secret:
#        kubectl -n socioprophet get secret workspace-dkim -o jsonpath='{.data.default\.private}' | base64 -d
#   3. Run:  MAIL_DOMAIN=socioprophet.ai ADMIN_EMAIL=michael@socioprophet.ai bash prophet-mail-install.sh
set -euo pipefail
export DEBIAN_FRONTEND=noninteractive
DOMAIN="${MAIL_DOMAIN:-socioprophet.ai}"
HOST="${MAIL_HOSTNAME:-mail.$DOMAIN}"
SELECTOR="${DKIM_SELECTOR:-default}"
ADMIN="${ADMIN_EMAIL:-michael@$DOMAIN}"
STAGING="${ACME_STAGING:-}"        # set to 1 for LE staging if prod quota is exhausted
SECRETS="${SECRETS_DIR:-/root/mail-secrets}"
[ -r "$SECRETS/dkim.private" ] || { echo "FATAL: $SECRETS/dkim.private missing (see header)"; exit 1; }
[ -r "$SECRETS/admin.hash" ]  || { echo "FATAL: $SECRETS/admin.hash missing (see header)"; exit 1; }
exec > >(tee -a /var/log/mail-install.log) 2>&1
echo "=== prophet-mail install $(date -u) host=$HOST ==="

hostnamectl set-hostname "$HOST" || true
echo "$HOST" > /etc/mailname
apt-get update -y
debconf-set-selections <<< "postfix postfix/main_mailer_type string 'Internet Site'"
debconf-set-selections <<< "postfix postfix/mailname string $HOST"
apt-get install -y postfix dovecot-imapd dovecot-lmtpd opendkim opendkim-tools certbot ca-certificates

# --- TLS (HTTP-01; mail.<domain> A record must already point here). Cert persists on the VPS disk. ---
CBFLAG=""; [ -n "$STAGING" ] && CBFLAG="--staging"
if [ ! -d "/etc/letsencrypt/live/$HOST" ]; then
  certbot certonly --standalone $CBFLAG --non-interactive --agree-tos -m "postmaster@$DOMAIN" -d "$HOST" \
    || echo "WARN: certbot failed — re-run: certbot certonly --standalone $CBFLAG -d $HOST"
fi
CERT="/etc/letsencrypt/live/$HOST/fullchain.pem"; KEY="/etc/letsencrypt/live/$HOST/privkey.pem"
mkdir -p /etc/letsencrypt/renewal-hooks/deploy
printf '#!/bin/sh\nsystemctl reload postfix dovecot\n' > /etc/letsencrypt/renewal-hooks/deploy/reload-mail.sh
chmod +x /etc/letsencrypt/renewal-hooks/deploy/reload-mail.sh

# --- OpenDKIM: key in an opendkim-owned dir; /etc/opendkim stays root-owned (root pre-check) ---
mkdir -p /etc/dkimkeys /run/opendkim
install -o opendkim -g opendkim -m 600 "$SECRETS/dkim.private" /etc/dkimkeys/$SELECTOR.private
chown opendkim:opendkim /run/opendkim
cat > /etc/opendkim.conf <<EOF
Syslog yes
UMask 002
Mode sv
Socket inet:8891@localhost
Domain $DOMAIN
Selector $SELECTOR
KeyFile /etc/dkimkeys/$SELECTOR.private
Canonicalization relaxed/simple
OversignHeaders From
EOF
cat > /etc/default/opendkim <<EOF
RUNDIR=/run/opendkim
SOCKET="inet:8891@localhost"
USER=opendkim
GROUP=opendkim
PID=/run/opendkim/opendkim.pid
EOF
systemctl enable opendkim
systemctl restart opendkim || echo "WARN: opendkim failed — mail continues unsigned; fix via journalctl -xeu opendkim"

# --- Dovecot: virtual users (passwd-file), IMAPS, TLS required ---
mkdir -p /var/mail/vhosts/$DOMAIN
groupadd -g 5000 vmail 2>/dev/null || true
useradd -g vmail -u 5000 vmail -d /var/mail 2>/dev/null || true
echo "$ADMIN:$(cat "$SECRETS/admin.hash")::::::" > /etc/dovecot/users
chown -R vmail:vmail /var/mail/vhosts
cat > /etc/dovecot/dovecot.conf <<EOF
protocols = imap lmtp
listen = *
ssl = required
ssl_cert = <$CERT
ssl_key = <$KEY
mail_location = maildir:/var/mail/vhosts/%d/%n/Maildir
mail_privileged_group = vmail
namespace inbox {
  inbox = yes
}
passdb {
  driver = passwd-file
  args = scheme=SHA512-CRYPT username_format=%u /etc/dovecot/users
}
userdb {
  driver = static
  args = uid=vmail gid=vmail home=/var/mail/vhosts/%d/%n
}
service lmtp {
  unix_listener /var/spool/postfix/private/dovecot-lmtp {
    mode = 0600
    user = postfix
    group = postfix
  }
}
service auth {
  unix_listener /var/spool/postfix/private/auth {
    mode = 0660
    user = postfix
    group = postfix
  }
}
auth_mechanisms = plain login
EOF
systemctl enable dovecot
systemctl restart dovecot || echo "WARN: dovecot restart returned non-zero"

# --- Postfix: DIRECT-TO-MX (no relay), TLS, submission 587 w/ SASL, LMTP delivery, DKIM milter ---
postconf -e "myhostname = $HOST" "mydomain = $DOMAIN" "myorigin = \$mydomain"
postconf -e "inet_interfaces = all" "inet_protocols = ipv4" "mydestination = localhost"
postconf -e "virtual_mailbox_domains = $DOMAIN" "virtual_transport = lmtp:unix:private/dovecot-lmtp"
postconf -e "smtpd_tls_cert_file = $CERT" "smtpd_tls_key_file = $KEY"
postconf -e "smtpd_tls_security_level = may" "smtp_tls_security_level = may"
postconf -e "smtpd_sasl_type = dovecot" "smtpd_sasl_path = private/auth"
postconf -e "milter_default_action = accept" "milter_protocol = 6"
postconf -e "smtpd_milters = inet:localhost:8891" "non_smtpd_milters = inet:localhost:8891"
postconf -M submission/inet="submission inet n - y - - smtpd"
postconf -P "submission/inet/syslog_name=postfix/submission" \
  "submission/inet/smtpd_tls_security_level=encrypt" \
  "submission/inet/smtpd_sasl_auth_enable=yes" \
  "submission/inet/smtpd_client_restrictions=permit_sasl_authenticated,reject"
systemctl enable postfix
systemctl restart postfix || echo "WARN: postfix restart returned non-zero"

echo "=== services: opendkim=$(systemctl is-active opendkim) dovecot=$(systemctl is-active dovecot) postfix=$(systemctl is-active postfix) ==="
ss -ltnp 2>/dev/null | grep -E ':25|:587|:993' || echo "WARN: nothing listening on mail ports"
echo "=== prophet-mail install complete $(date -u) — direct-to-MX, sovereign ==="
