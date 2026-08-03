# Receipt-emitting inference gateway — a transparent proxy that fronts an OpenAI-compatible
# embeddings/completions backend and emits a schema-conformant, hash-chained InferenceReceipt
# for every call (SEAM-011: durable, non-local ledger). Self-contained build context
# (apps/receipt-gateway) so it slots into the images.yml matrix like the other first-party apps.
FROM python:3.12-slim

WORKDIR /app
RUN pip install --no-cache-dir "jsonschema>=4.0.0"

COPY tools/inference_receipt_emitter.py tools/receipt_gateway.py /app/tools/
COPY schemas/model-plane/InferenceReceipt.schema.json /app/schemas/model-plane/

# Run unprivileged; own the ledger dir so a mounted volume inherits the right ownership.
RUN useradd --system --uid 10001 --create-home gateway \
    && mkdir -p /var/lib/receipt-gateway \
    && chown -R gateway:gateway /var/lib/receipt-gateway /app

# Ledger persists on a mounted volume (SEAM-011: durable, non-local ledger).
ENV RECEIPT_GATEWAY_LEDGER=/var/lib/receipt-gateway/ledger.jsonl \
    RECEIPT_GATEWAY_HOST=0.0.0.0 \
    RECEIPT_GATEWAY_PORT=8898 \
    RECEIPT_GATEWAY_BACKEND=http://embeddings:8080
VOLUME ["/var/lib/receipt-gateway"]
EXPOSE 8898
USER gateway

# RECEIPT_GATEWAY_MODEL_DIGEST(S) is provided at deploy time (the served model's real digest).
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
  CMD ["python", "-c", "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8898/health',timeout=2).status==200 else 1)"]

ENTRYPOINT ["python", "tools/receipt_gateway.py", "--serve"]
