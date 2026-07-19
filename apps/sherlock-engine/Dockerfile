# sherlock-engine — sovereign Discovery search (Tantivy, Rust, no JVM). Multi-stage: build the
# static-ish binary, ship it on a slim runtime with the corpus. Canonical source: SocioProphet/sherlock-search
# (engine/), vendored here for the estate image build (same pattern as other apps).
FROM rust:1.83-slim AS build
WORKDIR /build
COPY Cargo.toml ./
COPY src ./src
RUN cargo build --release && strip target/release/sherlock-engine

FROM debian:bookworm-slim
WORKDIR /app
RUN useradd -r -u 10001 sherlock
COPY --from=build /build/target/release/sherlock-engine /usr/local/bin/sherlock-engine
COPY corpus ./corpus
USER sherlock
ENV PORT=8093 SHERLOCK_CORPUS=/app/corpus/frontier-labs.json
EXPOSE 8093
# liveness: GET /healthz
CMD ["sherlock-engine"]
