# syntax=docker/dockerfile:1.7
# agent-activity-ledger — governed Executions Ledger service (Go, stdlib-only, single main.go).
# Serves /healthz + /executions on :8080; records mirror the prophet-core-contracts
# ExecutionReceipt schema (verdict + receipt warrant, never a bare boolean). Binds 0.0.0.0.
FROM golang:1.22-alpine AS build
WORKDIR /src
COPY go.mod ./
COPY main.go ./
RUN CGO_ENABLED=0 go build -ldflags="-s -w" -o /agent-activity-ledger .

FROM gcr.io/distroless/static-debian12:nonroot
COPY --from=build /agent-activity-ledger /agent-activity-ledger
ENV PORT=8080
EXPOSE 8080
ENTRYPOINT ["/agent-activity-ledger"]
