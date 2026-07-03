#!/bin/sh
set -e

# Core substitutions (always)
sed -i "s/\${SMTP_HOSTNAME}/${SMTP_HOSTNAME:-mail.prophet.local}/g" /etc/postfix/main.cf
sed -i "s/\${DOVECOT_HOST}/${DOVECOT_HOST:-workspace-mail}/g" /etc/postfix/main.cf

for f in /etc/postfix/virtual_domains.cf /etc/postfix/virtual_mailbox.cf; do
  sed -i "s/\${POSTGRES_HOST}/${POSTGRES_HOST:-postgres}/g" "$f"
  sed -i "s/\${POSTGRES_USER}/${POSTGRES_USER:-prophet}/g" "$f"
  sed -i "s/\${POSTGRES_PASSWORD}/${POSTGRES_PASSWORD:-prophet}/g" "$f"
  sed -i "s/\${POSTGRES_DB}/${POSTGRES_DB:-prophet_platform}/g" "$f"
done

# TLS: append if cert is mounted (Helm mounts at /etc/postfix/tls/ when tls.certSecret is set)
if [ -f "/etc/postfix/tls/tls.crt" ] && [ -f "/etc/postfix/tls/tls.key" ]; then
  echo "[smtp] TLS cert found — enabling STARTTLS"
  cat >> /etc/postfix/main.cf <<'TLS'

# TLS — inbound (STARTTLS on port 25 / submission 587)
smtpd_tls_cert_file = /etc/postfix/tls/tls.crt
smtpd_tls_key_file = /etc/postfix/tls/tls.key
smtpd_tls_security_level = may
smtpd_tls_mandatory_protocols = !SSLv2, !SSLv3, !TLSv1, !TLSv1.1
smtpd_tls_loglevel = 1

# TLS — outbound
smtp_tls_security_level = may
smtp_tls_mandatory_protocols = !SSLv2, !SSLv3, !TLSv1, !TLSv1.1
smtp_tls_loglevel = 1
TLS
else
  echo "[smtp] No TLS cert at /etc/postfix/tls/ — running plaintext (dev mode)"
fi

# Smart-host relay: if SMTP_RELAY_HOST is set, route outbound through it
if [ -n "${SMTP_RELAY_HOST}" ]; then
  RELAY_PORT="${SMTP_RELAY_PORT:-587}"
  echo "[smtp] Relay host: [${SMTP_RELAY_HOST}]:${RELAY_PORT}"
  cat >> /etc/postfix/main.cf <<RELAY

# Smart-host relay — outbound via ${SMTP_RELAY_HOST}
relayhost = [${SMTP_RELAY_HOST}]:${RELAY_PORT}
RELAY
  # Relay credentials: mount a file at /etc/postfix/relay/sasl_passwd
  if [ -f "/etc/postfix/relay/sasl_passwd" ]; then
    cp /etc/postfix/relay/sasl_passwd /etc/postfix/sasl_passwd
    postmap /etc/postfix/sasl_passwd
    cat >> /etc/postfix/main.cf <<'RELAY_AUTH'
smtp_sasl_auth_enable = yes
smtp_sasl_password_maps = hash:/etc/postfix/sasl_passwd
smtp_sasl_security_options = noanonymous
RELAY_AUTH
  fi
fi

# DKIM: start opendkim + wire milter if the key secret is mounted
# Helm mounts dkim.existingSecret at /etc/postfix/dkim/ with key named "${selector}.private"
DKIM_SELECTOR="${DKIM_SELECTOR:-default}"
DKIM_HOSTNAME="${SMTP_HOSTNAME:-mail.prophet.local}"
# Derive bare domain from hostname (mail.example.com → example.com)
DKIM_DOMAIN="${DKIM_DOMAIN:-$(echo "${DKIM_HOSTNAME}" | awk -F. 'NF>2{print $(NF-1)"."$NF} NF<=2{print}')}"
DKIM_KEY="/etc/postfix/dkim/${DKIM_SELECTOR}.private"

if [ -f "${DKIM_KEY}" ]; then
  echo "[smtp] DKIM key at ${DKIM_KEY} — starting opendkim for domain ${DKIM_DOMAIN}"

  mkdir -p /etc/opendkim /var/run/opendkim

  cat > /etc/opendkim.conf <<OKCONF
Syslog                  yes
SyslogSuccess           yes
LogWhy                  yes
Canonicalization        relaxed/simple
Mode                    sv
SubDomains              no
AutoRestart             no
Background              yes
DNSTimeout              5
SignatureAlgorithm      rsa-sha256
Socket                  inet:8891@127.0.0.1
PidFile                 /var/run/opendkim/opendkim.pid
UMask                   002
UserID                  opendkim:opendkim
KeyTable                /etc/opendkim/KeyTable
SigningTable            refile:/etc/opendkim/SigningTable
InternalHosts           refile:/etc/opendkim/TrustedHosts
OKCONF

  # KeyTable: selector._domainkey.domain → domain:selector:/path/to/key
  printf '%s._domainkey.%s %s:%s:%s\n' \
    "${DKIM_SELECTOR}" "${DKIM_DOMAIN}" \
    "${DKIM_DOMAIN}" "${DKIM_SELECTOR}" "${DKIM_KEY}" \
    > /etc/opendkim/KeyTable

  # SigningTable: *@domain → selector._domainkey.domain
  printf '*@%s %s._domainkey.%s\n' \
    "${DKIM_DOMAIN}" "${DKIM_SELECTOR}" "${DKIM_DOMAIN}" \
    > /etc/opendkim/SigningTable

  printf '127.0.0.1\n::1\nlocalhost\n%s\n' "${DKIM_DOMAIN}" \
    > /etc/opendkim/TrustedHosts

  # Ensure opendkim user owns the key and runtime dirs
  id opendkim >/dev/null 2>&1 || adduser --system --no-create-home --group opendkim
  chown -R opendkim:opendkim /etc/opendkim /var/run/opendkim
  # Key must be readable but not world-accessible
  chmod 640 "${DKIM_KEY}"
  chown root:opendkim "${DKIM_KEY}"

  opendkim

  cat >> /etc/postfix/main.cf <<'MILTER'

# DKIM milter (opendkim on port 8891)
milter_protocol = 6
milter_default_action = accept
smtpd_milters = inet:127.0.0.1:8891
non_smtpd_milters = inet:127.0.0.1:8891
MILTER
else
  echo "[smtp] No DKIM key at ${DKIM_KEY} — DKIM signing disabled"
fi

exec "$@"
