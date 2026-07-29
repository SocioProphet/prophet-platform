# arcticdb-gateway — versioned DataFrame artifacts over embedded ArcticDB/LMDB (tritfabric PHT-5
# dataset/version store, atoms-catalog section 3.3: "gateway Deployment wrapping embedded ArcticDB").
# python:3.11 (not 3.12): arcticdb 4.4.3 — the newest Apache-2.0-converted release (license audit in
# requirements.txt) — publishes wheels up to cp311.
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir --upgrade pip && pip install --no-cache-dir -r requirements.txt
COPY src ./src
ENV PORT=8080
EXPOSE 8080
CMD ["uvicorn", "arcticdb_gateway.server:app", "--host", "0.0.0.0", "--port", "8080", "--app-dir", "src"]
