# sherlock-engine — sovereign Discovery search (Tantivy, Rust, no JVM). Multi-stage: build the
# static-ish binary, ship it on a slim runtime with the corpus. Canonical source: SocioProphet/sherlock-search
# (engine/), vendored here for the estate image build (same pattern as other apps).
# Rust 1.83 was too old to parse a bumped transitive manifest (idna_adapter 1.2.2 via url/idna);
# pin a newer toolchain + a committed Cargo.lock so the build is reproducible and stops resolving
# newer, toolchain-incompatible deps on every run.
#
# GLIBC ALIGNMENT: the build and runtime bases MUST share a Debian codename. When the toolchain
# was bumped to rust:1.97-slim its base moved to Debian trixie (glibc 2.41), while the runtime
# stayed debian:bookworm-slim (glibc 2.36) — so the dynamically-linked binary required GLIBC_2.38
# the runtime could not provide and crashlooped ("version `GLIBC_2.38' not found"). Both stages are
# now pinned to trixie explicitly; keep them on the same codename whenever either is bumped.
FROM rust:1.97-slim-trixie AS build
WORKDIR /build
COPY Cargo.toml Cargo.lock ./
COPY src ./src
RUN cargo build --release --locked && strip target/release/sherlock-engine

FROM debian:trixie-slim
WORKDIR /app
RUN useradd -r -u 10001 sherlock
COPY --from=build /build/target/release/sherlock-engine /usr/local/bin/sherlock-engine
COPY corpus ./corpus
USER sherlock
ENV PORT=8093 SHERLOCK_CORPUS=/app/corpus/frontier-labs.json
EXPOSE 8093
# liveness: GET /healthz
CMD ["sherlock-engine"]
