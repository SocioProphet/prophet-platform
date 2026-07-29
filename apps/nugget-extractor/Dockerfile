# nugget-extractor — Seal-the-Walls W6.2: THE extraction spine. Documents (PDF text
# layer, plain text, markdown) become warrant-typed KnowledgeNuggets — the estate's L2
# content grain (SourceOS-Linux/sourceos-spec schemas/KnowledgeNugget.json v0.1.0,
# VENDORED and sha256-asserted at import) — validated fail-closed per nugget, written to
# the platform log as hellgraph-service graph writes (KKO-typed, warrant-labelled), and
# sealed one receipt per document on the estate spine via compute-gateway
# POST /v1/compute kind=nugget-emit. Never a fourth receipt lineage.
#
# NO OCR IN THIS IMAGE, deliberately. Scanned/image-only documents are REJECTED with an
# explicit 422 and counted on /healthz (`ocr_required`) — see src/nugget_extractor/
# extract.py for the seam and the image-size argument. Nothing here pretends to OCR.
#
# python:3.11-slim mirrors apps/market-replay + apps/prophet-materializer-clickhouse.
# The dependency closure is theirs plus pypdf (pure Python) — no apt layer, no native
# toolchain, no model weights.
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir --upgrade pip && pip install --no-cache-dir -r requirements.txt
COPY src ./src
ENV PORT=8080
EXPOSE 8080
CMD ["uvicorn", "nugget_extractor.server:app", "--host", "0.0.0.0", "--port", "8080", "--app-dir", "src"]
