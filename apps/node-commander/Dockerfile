# node-commander — node runtime control API (status / heartbeat), vendored into prophet-platform CI.
FROM python:3.12-slim
WORKDIR /app
COPY requirements.lock ./
RUN pip install --no-cache-dir --require-hashes -r requirements.lock
COPY app ./app
ENV PORT=8080
EXPOSE 8080
CMD ["uvicorn", "app.runtime_main:app", "--host", "0.0.0.0", "--port", "8080"]
