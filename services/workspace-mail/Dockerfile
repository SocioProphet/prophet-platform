FROM debian:bookworm-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    dovecot-core \
    dovecot-imapd \
    dovecot-lmtpd \
    dovecot-pgsql \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY dovecot/dovecot.conf /etc/dovecot/dovecot.conf
COPY dovecot/conf.d/ /etc/dovecot/conf.d/

RUN mkdir -p /var/mail/vhosts \
    && groupadd -g 5000 vmail \
    && useradd -g vmail -u 5000 vmail -d /var/mail \
    && chown -R vmail:vmail /var/mail

EXPOSE 143 993 24

CMD ["dovecot", "-F"]
