# lifecycle-warden — the L5 governance executor (Node service over the vendored engine).
FROM node:20-slim
WORKDIR /app

COPY package.json ./
# @socioprophet/hellgraph is vendored as a prebuilt tarball (vendor/) — no git, no ssh, no
# network, no rebuild. Deterministic; re-vendor with `npm pack` in ~/dev/hellgraph on version
# bump (same tarball hellgraph-service ships). The engine's optionalDependencies are its P2P
# stack (autobase/corestore/hyperswarm/rocksdb) which the warden never loads — if their native
# builds skip on this slim image, npm tolerates it and nothing here misses them. esbuild's
# platform binary (needed by tsx) is a prebuilt optional package, so no toolchain is required.
COPY vendor ./vendor
RUN npm install --no-audit --no-fund

COPY tsconfig.json ./
COPY src ./src

ENV PORT=8095
# DRY-RUN unless BOTH levers are thrown (WARDEN_ENFORCE=on + WARDEN_DRY_RUN=off); enforcement
# without MinIO credentials refuses to boot (fail-closed) — see src/server.ts resolveBootConfig.
ENV WARDEN_DRY_RUN=on
ENV WARDEN_ENFORCE=off
EXPOSE 8095
CMD ["npx", "tsx", "src/server.ts"]
