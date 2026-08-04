# hellgraph-percolator — the live percolation trigger. Tails hellgraph-service GET /api/graph/log
# (and accepts exchange-envelope.v0 on POST /percolate), rebuilds the dependency catalog from live
# /api/graph/subgraph state, re-materialises the affected closure through tools.hellgraph_percolation
# (idempotent, isolation-carrying upserts), and seals ONE receipt per batch on compute-gateway.
#
# Build context is the REPO ROOT (images.yml `context: .`) so the image can carry the CANONICAL shared
# library `tools/hellgraph_percolation` without forking it. python:3.11-slim mirrors the materializer.
FROM python:3.11-slim
WORKDIR /app
COPY apps/hellgraph-percolator/requirements.txt ./
RUN pip install --no-cache-dir --upgrade pip && pip install --no-cache-dir -r requirements.txt
COPY apps/hellgraph-percolator/src ./src
COPY tools/hellgraph_percolation ./tools/hellgraph_percolation
ENV PYTHONPATH=/app:/app/src
ENV PORT=8080
EXPOSE 8080
CMD ["uvicorn", "hellgraph_percolator.server:app", "--host", "0.0.0.0", "--port", "8080", "--app-dir", "src"]
