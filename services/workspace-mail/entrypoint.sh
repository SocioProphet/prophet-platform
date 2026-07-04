#!/bin/sh
set -e

# TLS: Helm mounts the cert secret at /etc/dovecot/tls/ when tls.certSecret is set.
# Write a conf.d overlay so the base dovecot.conf stays clean (ssl = no is the safe default).
TLS_CERT="/etc/dovecot/tls/tls.crt"
TLS_KEY="/etc/dovecot/tls/tls.key"
TLS_CONF="/etc/dovecot/conf.d/99-tls.conf"

if [ -f "${TLS_CERT}" ] && [ -f "${TLS_KEY}" ]; then
  echo "[imap] TLS cert found — enabling SSL"
  cat > "${TLS_CONF}" <<TLSCONF
ssl = required
ssl_cert = <${TLS_CERT}
ssl_key = <${TLS_KEY}
ssl_min_protocol = TLSv1.2
ssl_prefer_server_ciphers = yes
TLSCONF
else
  echo "[imap] No TLS cert at /etc/dovecot/tls/ — SSL off (dev mode)"
fi

exec "$@"
