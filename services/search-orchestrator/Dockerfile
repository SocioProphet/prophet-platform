FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app/services/search-orchestrator

COPY services/search-orchestrator/requirements.txt ./requirements.txt
RUN python -m pip install --upgrade pip \
    && pip install -r requirements.txt

COPY services/search-orchestrator/app ./app

USER 10001:10001
EXPOSE 8080

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
