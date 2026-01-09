# syntax=docker/dockerfile:1.7
FROM golang:1.22-alpine AS build
WORKDIR /src
COPY . ./
RUN --mount=type=cache,target=/root/.cache/go-build <<EOF
cd cmd/tritrpc-gateway && go build -trimpath -o /out/tritrpc-gateway
EOF

FROM alpine:3.20
RUN adduser -D -u 10002 app
USER app
WORKDIR /home/app
COPY --from=build /out/tritrpc-gateway /usr/local/bin/tritrpc-gateway
ENV TRITRPC_SOCK=/tmp/socioprophet.sock
ENV GATEWAY_PORT=8080
ENTRYPOINT ["/usr/local/bin/tritrpc-gateway"]
