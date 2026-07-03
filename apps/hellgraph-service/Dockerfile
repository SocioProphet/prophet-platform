FROM node:20-slim

WORKDIR /app

# git is needed to install the @socioprophet/hellgraph git dependency
RUN apt-get update && apt-get install -y --no-install-recommends git && rm -rf /var/lib/apt/lists/*

COPY package.json ./
# npm normalizes the @socioprophet/hellgraph git dep to git+ssh://git@github.com even when
# package.json says git+https; the builder has no ssh key. Rewrite ssh→https at the git layer
# (hellgraph is a PUBLIC repo, so https needs no auth) so the install resolves cleanly.
RUN git config --global url."https://github.com/".insteadOf "ssh://git@github.com/" \
 && git config --global url."https://github.com/".insteadOf "git@github.com:" \
 && npm install --no-audit --no-fund

COPY tsconfig.json ./
COPY src ./src

ENV PORT=8090
# Isolated graph store (mount a volume at /data to persist). Never share
# Noetica's ~/.noetica/hellgraph single-writer log.
ENV HELLGRAPH_STORE_DIR=/data/hellgraph
VOLUME ["/data"]
EXPOSE 8090
CMD ["npx", "tsx", "src/server.ts"]
