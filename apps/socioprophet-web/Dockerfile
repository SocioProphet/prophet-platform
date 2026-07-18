# syntax=docker/dockerfile:1.7
# BUILD CONTEXT = REPO ROOT (see images.yml). The app imports repo-root contracts via
# ../../../../contracts/*.json from src/components — those live OUTSIDE apps/socioprophet-web,
# so the whole repo (contracts + app) must be in context and the app must build from its own dir
# with the repo root at /app so the relative import resolves to /app/contracts.
FROM node:20-alpine AS build
WORKDIR /app
COPY contracts ./contracts
COPY apps/socioprophet-web ./apps/socioprophet-web
WORKDIR /app/apps/socioprophet-web
RUN corepack enable && (pnpm install --frozen-lockfile || pnpm install)
RUN pnpm build

FROM nginx:1.27-alpine
COPY --from=build /app/apps/socioprophet-web/dist /usr/share/nginx/html
# Replaces the stock conf, which listens on 80, serves no /healthz, and writes temp
# files outside the chart's writable mounts — see nginx.conf for the full contract.
COPY apps/socioprophet-web/nginx.conf /etc/nginx/nginx.conf
# The chart runs this as uid 10001 with a read-only root filesystem, so the temp dirs
# must already exist and be owned by that uid — nginx cannot mkdir them at runtime.
RUN mkdir -p /var/cache/nginx \
    && chown -R 10001:10001 /var/cache/nginx /usr/share/nginx/html
EXPOSE 8080
USER 10001
# Run nginx DIRECTLY, bypassing the stock /docker-entrypoint.sh helper scripts
# (10-listen-on-ipv6, 20-envsubst-on-templates, …). Those write under /etc/nginx,
# which is read-only here — under readOnlyRootFilesystem they abort the container
# before nginx ever binds 8080 (the probe verifier saw the port never publish). We
# use none of them; nginx.conf is complete (pid → /tmp, temp → /var/cache/nginx).
ENTRYPOINT ["nginx", "-g", "daemon off;"]
