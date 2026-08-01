# syntax=docker/dockerfile:1.7
# wordops-mcp-gateway — WordOps lease-enforcing MCP gateway (Go, stdlib-only, single main.go).
# Authorizes capability-leases (audience/scope/case/task/expiry; containment ⇒ A4), calls
# gbrg-containment, and writes the durable ExecutionReceipt to agent-activity-ledger. Binds 0.0.0.0:8080.
FROM golang:1.22-alpine AS build
WORKDIR /src
COPY go.mod ./
COPY *.go ./
RUN CGO_ENABLED=0 go build -ldflags="-s -w" -o /wordops-mcp-gateway .

FROM gcr.io/distroless/static-debian12:nonroot
COPY --from=build /wordops-mcp-gateway /wordops-mcp-gateway
ENV PORT=8080
EXPOSE 8080
ENTRYPOINT ["/wordops-mcp-gateway"]
