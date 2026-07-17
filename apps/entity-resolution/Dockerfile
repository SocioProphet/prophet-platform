# entity-resolution — the ER resolver (blocking + similarity + clustering, proof-carrying decisions).
FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir --upgrade pip && pip install --no-cache-dir -r requirements.txt
COPY src ./src
ENV PORT=8080
EXPOSE 8080
CMD ["uvicorn", "entity_resolution.server:app", "--host", "0.0.0.0", "--port", "8080", "--app-dir", "src"]
