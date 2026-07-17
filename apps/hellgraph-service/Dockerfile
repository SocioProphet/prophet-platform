# ── Stage 1: build the benchmarked hg_analytics Rust CSR kernel into an N-API addon ──
# This is the SAME kernel hellgraph-bench measured (PreparedGraph + parallel PageRank/WCC). Compiling it here
# means the shipping image actually RUNS the benchmarked code, not a separate TS re-implementation.
FROM rust:1-slim AS native
WORKDIR /native
COPY native/ ./
RUN cargo build --release -p hg_napi \
    && cp target/release/libhg_napi.so /native/hg_napi.node

# ── Stage 2: the Node service ──
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
# the compiled benchmarked analytics kernel (native/hg_napi.node) — analytics.ts loads it, TS fallback if absent
COPY --from=native /native/hg_napi.node ./native/hg_napi.node

ENV PORT=8090
# Isolated graph store (mount a volume at /data to persist). Never share
# Noetica's ~/.noetica/hellgraph single-writer log.
ENV HELLGRAPH_STORE_DIR=/data/hellgraph
VOLUME ["/data"]
EXPOSE 8090
CMD ["npx", "tsx", "src/server.ts"]
