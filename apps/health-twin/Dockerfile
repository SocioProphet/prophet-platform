# syntax=docker/dockerfile:1.7
# health-twin — the Digital Health Twin engine (walking skeleton) on :8097. FHIR-lite record bundle
# keyed to organ systems + governed, receipted, revocable consent grants. In production this runs
# LOCAL-FIRST on the person's own node (never a shared cloud); this image holds synthetic data only.
# No native deps. Runs as uid 10001 under readOnlyRootFilesystem — tsx/esbuild writes only to /tmp
# (values sets tmpDir.enabled). http.listen(PORT) binds 0.0.0.0 (no localhost-bind CrashLoop trap).
FROM node:20-alpine
WORKDIR /app
COPY package.json ./
RUN npm install --no-audit --no-fund && chown -R 10001:10001 /app
COPY src ./src
ENV PORT=8097
EXPOSE 8097
USER 10001
CMD ["npx", "tsx", "src/server.ts"]
