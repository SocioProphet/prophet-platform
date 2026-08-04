# syntax=docker/dockerfile:1.7
# agent-activity-ledger — governed Executions Ledger service (Go, stdlib-only, single main.go).
# Serves /healthz + /executions on :8080; records mirror the prophet-core-contracts
# ExecutionReceipt schema (verdict + receipt warrant, never a bare boolean). Binds 0.0.0.0.
FROM golang:1.22-alpine@sha256:6d405dfc5fdf3a45df1529cf060b920041f52ce523487e0f36f02765af294a51 AS build
WORKDIR /src
COPY go.mod ./
COPY main.go ./
RUN CGO_ENABLED=0 go build -ldflags="-s -w" -o /agent-activity-ledger .

FROM gcr.io/distroless/static-debian12:nonroot@sha256:7a2bd171a18bdd39a4729600d0dca5f16e779d41156a6908b4f8a9a289e76d92
COPY --from=build /agent-activity-ledger /agent-activity-ledger
ENV PORT=8080
EXPOSE 8080
ENTRYPOINT ["/agent-activity-ledger"]
