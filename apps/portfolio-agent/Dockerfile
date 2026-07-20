# syntax=docker/dockerfile:1.7
# portfolio-agent — the sovereign cloud portfolio agent (Portfolio ②) on :8094. Same proof-carrying
# tool layer the cockpit runs in-browser (①), server-side. No native deps. Runs as uid 10001 under the
# chart's readOnlyRootFilesystem — tsx/esbuild writes only to /tmp (values sets tmpDir.enabled).
# http.listen(PORT) binds 0.0.0.0 by default (no localhost-bind CrashLoop trap).
FROM node:20-alpine
WORKDIR /app
COPY package.json ./
RUN npm install --no-audit --no-fund && chown -R 10001:10001 /app
COPY src ./src
ENV PORT=8094
EXPOSE 8094
USER 10001
CMD ["npx", "tsx", "src/server.ts"]
