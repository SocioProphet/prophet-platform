# syntax=docker/dockerfile:1.7
# holmes — claim deduction/verification engine (Go, stdlib-only, single main.go). `holmes serve`
# exposes /verify /search /analyze /healthz on :8091, reasoning over the canonical hellgraph via HTTP
# (HOLMES_HELLGRAPH). Vendored from ~/dev/holmes/cmd/holmes. Binds 0.0.0.0 (bind fix vs sherlock's
# trap). The serve/verify path reasons over the graph — no local files needed (self-test/analyze CLI
# paths read files, but those aren't the served endpoints).
FROM golang:1.22-alpine AS build
WORKDIR /src
COPY go.mod ./
COPY main.go ./
RUN CGO_ENABLED=0 go build -ldflags="-s -w" -o /holmes .

FROM gcr.io/distroless/static-debian12:nonroot
COPY --from=build /holmes /holmes
ENV PORT=8091
EXPOSE 8091
ENTRYPOINT ["/holmes", "serve"]
