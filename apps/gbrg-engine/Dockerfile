# syntax=docker/dockerfile:1.7
# gbrg-engine — the AUTHORITATIVE GBRG containment engine (Rust), served over HTTP.
#
# Builds gbrg-engine from the sociosphere gbrg workspace at a PINNED public commit.
# No source is vendored into this repo: cargo fetches sociosphere (this clone) and
# hellgraph (a git dep) directly — both are public, so the build needs no creds.
# gbrg-parser pulls tree-sitter (C), so the build needs a C toolchain (rust:bookworm
# has it) and the runtime needs glibc (distroless/cc), not the static base.
FROM rust:1-bookworm AS build
RUN apt-get update && apt-get install -y --no-install-recommends git ca-certificates \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /src
# Pin: the sociosphere main commit that carries crates/gbrg-engine (repoint on bump).
ARG SOCIOSPHERE_REV=62020ea3721b6b389ae5e33cd2d1bf98c18edcc9
RUN git clone https://github.com/SocioProphet/sociosphere.git . \
    && git checkout "${SOCIOSPHERE_REV}"
WORKDIR /src/gbrg
RUN cargo build --release -p gbrg-engine

FROM gcr.io/distroless/cc-debian12:nonroot
COPY --from=build /src/gbrg/target/release/gbrg-engine /gbrg-engine
ENV PORT=8080
EXPOSE 8080
ENTRYPOINT ["/gbrg-engine"]
