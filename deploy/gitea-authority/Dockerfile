# gitea-sovereign authority — vendored zero-dependency closure (4 files). Built
# here because prophet-platform holds the estate WIF + Artifact Registry the GKE
# cluster can pull from. Source of truth: SocioProphet/gitea-sovereign.
FROM node:20-alpine
WORKDIR /app
COPY gateway ./gateway
COPY core ./core
ENV PORT=8081
USER node
EXPOSE 8081
CMD ["node", "gateway/authority-server.js"]
