FROM node:20-slim

WORKDIR /app

# git is needed to install the @socioprophet/hellgraph git dependency
RUN apt-get update && apt-get install -y --no-install-recommends git && rm -rf /var/lib/apt/lists/*

COPY package.json ./
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
