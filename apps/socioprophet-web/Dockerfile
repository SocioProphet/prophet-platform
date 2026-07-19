# syntax=docker/dockerfile:1.7
# socioprophet-web — THE unified analyst cockpit (client-vue / socioprophet-web-vue-shell), vendored from
# socioprophet/socioprophet-web/client-vue. Self-contained SPA (npm build → static dist), served by nginx
# which proxies /svc/<name> + /api to the in-cluster capability services (see nginx.conf).
# BUILD CONTEXT = REPO ROOT (see images.yml) — this app has no repo-root deps, so it only copies its own dir.
FROM node:20-alpine AS build
WORKDIR /app
COPY apps/socioprophet-web/package.json apps/socioprophet-web/package-lock.json ./
RUN npm ci
COPY apps/socioprophet-web ./
RUN npm run build

FROM nginx:1.27-alpine
COPY --from=build /app/dist /usr/share/nginx/html
# Replaces the stock conf (listens on 80, no /healthz, writes temp files outside the chart's writable
# mounts). nginx.conf is complete: pid → /tmp, temp → /var/cache/nginx, /svc + /api proxies.
COPY apps/socioprophet-web/nginx.conf /etc/nginx/nginx.conf
# The chart runs this as uid 10001 with a read-only root filesystem, so the temp dirs must exist and be
# owned by that uid — nginx cannot mkdir them at runtime.
RUN mkdir -p /var/cache/nginx \
    && chown -R 10001:10001 /var/cache/nginx /usr/share/nginx/html
EXPOSE 8080
USER 10001
# Run nginx directly, bypassing the stock /docker-entrypoint.sh helpers that write under /etc/nginx
# (read-only here). nginx.conf is complete on its own.
ENTRYPOINT ["nginx", "-g", "daemon off;"]
