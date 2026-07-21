# syntax=docker/dockerfile:1.7
# academy-board — the sovereign scoring service behind the Academy mastery check, on :8095.
# The answer key lives in the image, never in the browser bundle, so grading is a real authority
# a client cannot read or forge; each verdict carries a deterministic receipt. No native deps.
# Runs as uid 10001 under the chart's readOnlyRootFilesystem — tsx/esbuild writes only to /tmp
# (values sets tmpDir.enabled). http.listen(PORT) binds 0.0.0.0 (no localhost-bind CrashLoop trap).
FROM node:20-alpine
WORKDIR /app
COPY package.json ./
RUN npm install --no-audit --no-fund && chown -R 10001:10001 /app
COPY src ./src
ENV PORT=8095
EXPOSE 8095
USER 10001
CMD ["npx", "tsx", "src/server.ts"]
