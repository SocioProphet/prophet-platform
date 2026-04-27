# syntax=docker/dockerfile:1.7

FROM golang:1.25-alpine AS build
WORKDIR /src

COPY libs/go/tritrpcbridge ./libs/go/tritrpcbridge
COPY apps/gateway ./apps/gateway

WORKDIR /src/apps/gateway
RUN --mount=type=cache,target=/go/pkg/mod \
    --mount=type=cache,target=/root/.cache/go-build \
    CGO_ENABLED=0 GOOS=linux go build -trimpath -ldflags='-s -w' -o /out/tritrpc-gateway ./cmd/tritrpc-gateway

FROM scratch
COPY --from=build /out/tritrpc-gateway /tritrpc-gateway
USER 65532:65532
ENV TRITRPC_TARGET_ADDR=tcp://socioprophet-api:9000
ENV GATEWAY_PORT=8080
EXPOSE 8080
ENTRYPOINT ["/tritrpc-gateway"]
