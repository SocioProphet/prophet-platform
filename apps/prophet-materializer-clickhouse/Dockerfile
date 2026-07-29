# prophet-materializer-clickhouse — Seal-the-Walls W1.1: the first proof-carrying
# materializer. Tails the HellGraph log surface (GET /api/graph/log), writes the
# hellgraph.events derived view into ClickHouse idempotently (ReplacingMergeTree keyed
# by event_id, versioned by seq), checkpoints by the log's logical clock, and seals a
# receipt per batch on the estate spine via compute-gateway (never a new lineage).
# python:3.11-slim mirrors apps/arcticdb-gateway (the PHT-5 sibling).
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir --upgrade pip && pip install --no-cache-dir -r requirements.txt
COPY src ./src
ENV PORT=8080
EXPOSE 8080
CMD ["uvicorn", "prophet_materializer_clickhouse.server:app", "--host", "0.0.0.0", "--port", "8080", "--app-dir", "src"]
