# syntax=docker/dockerfile:1.7
# wordops-room-factory — WordOps service (Go, stdlib-only, single main.go). Binds 0.0.0.0:8080.
FROM golang:1.22-alpine AS build
WORKDIR /src
COPY go.mod ./
COPY *.go ./
RUN CGO_ENABLED=0 go build -ldflags="-s -w" -o /wordops-room-factory .

FROM gcr.io/distroless/static-debian12:nonroot
COPY --from=build /wordops-room-factory /wordops-room-factory
ENV PORT=8080
EXPOSE 8080
ENTRYPOINT ["/wordops-room-factory"]
