# Regis / ACR API — the deployable runtime for the regis-entity-graph domain
# (per regis-entity-graph docs/specs/prophet-platform-service-binding-v0.1.md:
#  domain/schemas stay in regis-entity-graph; the service runtime lives here).
FROM python:3.12-slim
WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir --upgrade pip \
 && pip install --no-cache-dir -r requirements.txt

COPY src ./src

ENV PORT=8080
EXPOSE 8080
CMD ["uvicorn", "regis_acr_api.main:app", "--host", "0.0.0.0", "--port", "8080", "--app-dir", "src"]
