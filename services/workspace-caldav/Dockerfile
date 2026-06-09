FROM python:3.12-slim

RUN pip install --no-cache-dir radicale==3.3.0 passlib bcrypt

RUN useradd -r -s /sbin/nologin radicale \
    && mkdir -p /var/lib/radicale/collections /config \
    && chown -R radicale:radicale /var/lib/radicale

COPY radicale/config /config/config

EXPOSE 5232

USER radicale
CMD ["python", "-m", "radicale", "--config", "/config/config"]
