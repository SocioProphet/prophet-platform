# compute-gateway — the Universal Compute Contract router. Control-plane only
# (routes to backend runtimes; executes no user code itself), so it lives in the
# platform namespace, not sovereign-runtime.
FROM python:3.12-slim@sha256:cab2dbf575e971934a81e4622f5aba17aa7929719bd7e31033a3a83b97fd0464
RUN useradd -m -u 10001 gateway
WORKDIR /app
COPY requirements.lock ./
RUN pip install --no-cache-dir --require-hashes -r requirements.lock
COPY src ./src
ENV PORT=8080 PYTHONUNBUFFERED=1
EXPOSE 8080
USER gateway
CMD ["uvicorn", "compute_gateway.server:app", "--host", "0.0.0.0", "--port", "8080", "--app-dir", "src"]
