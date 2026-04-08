# syntax=docker/dockerfile:1.7
FROM golang:1.22-alpine AS build
WORKDIR /src
COPY . ./
RUN --mount=type=cache,target=/root/.cache/go-build <<EOF2
cd /src && go build -trimpath -o /out/socioprophet-api ./apps/api/cmd/socioprophet-api
EOF2

FROM alpine:3.20
RUN adduser -D -u 10001 app
USER app
WORKDIR /home/app
COPY --from=build /out/socioprophet-api /usr/local/bin/socioprophet-api
ENV TRITRPC_LISTEN_ADDR=tcp://0.0.0.0:9000
ENTRYPOINT ["/usr/local/bin/socioprophet-api"]
