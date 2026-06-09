FROM debian:bookworm-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    postfix \
    postfix-pgsql \
    ca-certificates \
    libsasl2-modules \
    && rm -rf /var/lib/apt/lists/*

COPY postfix/main.cf /etc/postfix/main.cf
COPY postfix/master.cf /etc/postfix/master.cf
COPY postfix/virtual_domains.cf /etc/postfix/virtual_domains.cf
COPY postfix/virtual_mailbox.cf /etc/postfix/virtual_mailbox.cf

# Entrypoint: substitute env vars then start
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

EXPOSE 25 587

ENTRYPOINT ["/entrypoint.sh"]
CMD ["postfix", "start-fg"]
