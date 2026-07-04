FROM node:20-slim

WORKDIR /app

# Native deps (rocksdb-native/sodium-native via autobase/corestore/hyperswarm, used by
# HELLGRAPH_MODE=superpeer) need a build toolchain — node:20-slim lacks one, so the addons
# silently fail to load at runtime without this. node-gyp needs python3 + make + g++.
RUN apt-get update && apt-get install -y --no-install-recommends build-essential python3 \
    && rm -rf /var/lib/apt/lists/*

COPY package.json ./
# @socioprophet/hellgraph is vendored as a prebuilt tarball (vendor/) — no git, no ssh, no
# network, no rebuild. Deterministic; re-vendor with `npm pack` in ~/dev/hellgraph on version bump.
COPY vendor ./vendor
RUN npm install --no-audit --no-fund

COPY tsconfig.json ./
COPY src ./src

ENV PORT=8090
# Isolated graph store (mount a volume at /data to persist). Never share
# Noetica's ~/.noetica/hellgraph single-writer log.
ENV HELLGRAPH_STORE_DIR=/data/hellgraph
VOLUME ["/data"]
EXPOSE 8090
CMD ["npx", "tsx", "src/server.ts"]
