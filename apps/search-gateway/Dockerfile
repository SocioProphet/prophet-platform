# search-gateway — the public read-only search fan-out for socioprophet.ai (blends SearXNG + commons-search).
# Pure Node/TS, no native deps. Mirrors commons-search.
FROM node:20-slim
WORKDIR /app
COPY package.json package-lock.json* ./
RUN npm install --no-audit --no-fund --omit=dev \
    && npm install --no-audit --no-fund --no-save tsx@^4.0.0
COPY tsconfig.json ./
COPY src ./src
ENV PORT=8080
EXPOSE 8080
USER node
CMD ["npx", "tsx", "src/server.ts"]
