# syntax=docker/dockerfile:1.7
# wordops-capability-broker — WordOps service (Go, stdlib-only, single main.go). Binds 0.0.0.0:8080.
FROM golang:1.22-alpine AS build
WORKDIR /src
COPY go.mod ./
COPY *.go ./
RUN CGO_ENABLED=0 go build -ldflags="-s -w" -o /wordops-capability-broker .

FROM gcr.io/distroless/static-debian12:nonroot
COPY --from=build /wordops-capability-broker /wordops-capability-broker
ENV PORT=8080
EXPOSE 8080
ENTRYPOINT ["/wordops-capability-broker"]
