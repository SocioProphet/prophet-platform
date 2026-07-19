# ie-engine — spaCy NER + dependency-parse relations + assert/hedge claims + glossary + vectors, plus
# /to-graph writeback into HellGraph (FastAPI). Powers the NLP & IE cockpit surface. The en_core_web_sm
# model is baked in at build so the runtime image is self-contained (no network model pull on boot).
FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt \
    && python -m spacy download en_core_web_sm
COPY src ./src
ENV PORT=8080 HELLGRAPH_BASE=http://hellgraph-service:8090
EXPOSE 8080
# liveness: GET /healthz
CMD ["uvicorn", "ie_engine.server:app", "--host", "0.0.0.0", "--port", "8080", "--app-dir", "src"]
