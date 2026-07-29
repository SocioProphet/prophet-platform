# market-replay — Seal-the-Walls W1.2: the first sourceos-spec-conformant event
# producer. A deterministic seeded random walk emits SYNTHETIC MarketDataEvent objects
# (validated per event against the vendored sourceos-spec schema, fail-closed) into the
# platform log as hellgraph-service graph writes (POST /api/graph/node|edge); the W1.1
# materializer tails the log and lands them in ClickHouse. No real market data.
# python:3.11-slim mirrors apps/arcticdb-gateway + apps/prophet-materializer-clickhouse.
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir --upgrade pip && pip install --no-cache-dir -r requirements.txt
COPY src ./src
ENV PORT=8080
EXPOSE 8080
CMD ["uvicorn", "market_replay.server:app", "--host", "0.0.0.0", "--port", "8080", "--app-dir", "src"]
