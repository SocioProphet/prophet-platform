FROM python:3.11-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    OSM_MAP_API_HOST=0.0.0.0 \
    OSM_MAP_API_PORT=8088

WORKDIR /app

COPY apps/osm-map-api/pyproject.toml /app/pyproject.toml
COPY apps/osm-map-api/osm_map_api /app/osm_map_api

RUN pip install --no-cache-dir .

USER 65532:65532

EXPOSE 8088

CMD ["python", "-m", "osm_map_api"]
