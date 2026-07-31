# syntax=docker/dockerfile:1.7
# gbrg-containment — governed containment/blast-radius service (Go, stdlib-only, single main.go).
# Serves /healthz + /containment on :8080; computes residual reachability with the same semantics
# as the authoritative Rust engine (gbrg-core::containment, sociosphere). Binds 0.0.0.0.
FROM golang:1.22-alpine AS build
WORKDIR /src
COPY go.mod ./
COPY main.go ./
RUN CGO_ENABLED=0 go build -ldflags="-s -w" -o /gbrg-containment .

FROM gcr.io/distroless/static-debian12:nonroot
COPY --from=build /gbrg-containment /gbrg-containment
ENV PORT=8080
EXPOSE 8080
ENTRYPOINT ["/gbrg-containment"]
