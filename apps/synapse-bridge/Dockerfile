# syntax=docker/dockerfile:1.7
# synapse-bridge — SynapseIQ language-intelligence (KKO classification + normalize) on :8092.
# Vendored from synapseiq/bridge; no native deps. Runs as uid 10001 under the chart's
# readOnlyRootFilesystem — tsx/esbuild writes only to /tmp (values sets tmpDir.enabled).
# Node http.listen(PORT) binds 0.0.0.0 by default (no localhost-bind trap).
FROM node:20-alpine
WORKDIR /app
COPY package.json ./
RUN npm install --no-audit --no-fund && chown -R 10001:10001 /app
COPY src ./src
ENV PORT=8092
EXPOSE 8092
USER 10001
CMD ["npx", "tsx", "src/server.ts"]
