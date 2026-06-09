#!/bin/sh
set -e

# Substitute env vars into postfix config files
sed -i "s/\${SMTP_HOSTNAME}/${SMTP_HOSTNAME:-mail.prophet.local}/g" /etc/postfix/main.cf
sed -i "s/\${DOVECOT_HOST}/${DOVECOT_HOST:-workspace-mail}/g" /etc/postfix/main.cf

for f in /etc/postfix/virtual_domains.cf /etc/postfix/virtual_mailbox.cf; do
  sed -i "s/\${POSTGRES_HOST}/${POSTGRES_HOST:-postgres}/g" "$f"
  sed -i "s/\${POSTGRES_USER}/${POSTGRES_USER:-prophet}/g" "$f"
  sed -i "s/\${POSTGRES_PASSWORD}/${POSTGRES_PASSWORD:-prophet}/g" "$f"
  sed -i "s/\${POSTGRES_DB}/${POSTGRES_DB:-prophet_platform}/g" "$f"
done

exec "$@"
