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
