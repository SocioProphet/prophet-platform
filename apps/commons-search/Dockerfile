# commons-search — the open-chat community-commons aggregator.
# BUILD CONTEXT = apps/commons-search (see .github/workflows/images.yml).
#
# No native addons: the service itself is pure Node/TS (the hellgraph backend emits a JSONL delta outbox for a
# separate federation tailer rather than embedding autobase, so node:20-slim needs no build toolchain). `minio` is
# an OPTIONAL dependency — only installed/loaded when COMMONS_STORE=minio; its absence soft-degrades to memory.
FROM node:20-slim

WORKDIR /app

COPY package.json package-lock.json* ./
# --omit=dev: ship only runtime deps. tsx is a runtime dep? No — we run via npx tsx, so keep tsx. Install all
# non-dev deps + tsx explicitly (it's a devDependency used as the runtime loader, mirroring hellgraph-service).
RUN npm install --no-audit --no-fund --omit=dev \
    && npm install --no-audit --no-fund --no-save tsx@^4.0.0

COPY tsconfig.json ./
COPY src ./src

# 8080 + /healthz is the chart contract (service.port / probes.path) for when this is wired into the ApplicationSet.
ENV PORT=8080
# Default store is memory (per-pod, safe). A deployment sets COMMONS_STORE + the backend's env to go shared.
ENV COMMONS_STORE=memory
EXPOSE 8080

# Run as the built-in non-root node user.
USER node
CMD ["npx", "tsx", "src/server.ts"]
