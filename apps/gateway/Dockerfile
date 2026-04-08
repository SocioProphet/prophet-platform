# syntax=docker/dockerfile:1.7
FROM golang:1.22-alpine AS build
WORKDIR /src
COPY . ./
RUN --mount=type=cache,target=/root/.cache/go-build <<EOF2
cd /src && go build -trimpath -o /out/tritrpc-gateway ./apps/gateway/cmd/tritrpc-gateway
EOF2

FROM alpine:3.20
RUN adduser -D -u 10002 app
USER app
WORKDIR /home/app
COPY --from=build /out/tritrpc-gateway /usr/local/bin/tritrpc-gateway
ENV TRITRPC_TARGET_ADDR=tcp://socioprophet-api:9000
ENV GATEWAY_PORT=8080
ENTRYPOINT ["/usr/local/bin/tritrpc-gateway"]
