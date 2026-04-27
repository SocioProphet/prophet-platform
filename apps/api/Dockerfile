# syntax=docker/dockerfile:1.7

FROM golang:1.25-alpine AS build
WORKDIR /src

COPY libs/go/tritrpcbridge ./libs/go/tritrpcbridge
COPY apps/api ./apps/api

WORKDIR /src/apps/api
RUN --mount=type=cache,target=/go/pkg/mod \
    --mount=type=cache,target=/root/.cache/go-build \
    CGO_ENABLED=0 GOOS=linux go build -trimpath -ldflags='-s -w' -o /out/socioprophet-api ./cmd/socioprophet-api

FROM scratch
COPY --from=build /out/socioprophet-api /socioprophet-api
USER 65532:65532
ENV TRITRPC_LISTEN_ADDR=tcp://0.0.0.0:9000
EXPOSE 9000
ENTRYPOINT ["/socioprophet-api"]
