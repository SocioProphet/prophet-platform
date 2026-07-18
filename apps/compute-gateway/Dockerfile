# compute-gateway — the Universal Compute Contract router. Control-plane only
# (routes to backend runtimes; executes no user code itself), so it lives in the
# platform namespace, not sovereign-runtime.
FROM python:3.12-slim
RUN useradd -m -u 10001 gateway
WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir --upgrade pip && pip install --no-cache-dir -r requirements.txt
COPY src ./src
ENV PORT=8080 PYTHONUNBUFFERED=1
EXPOSE 8080
USER gateway
CMD ["uvicorn", "compute_gateway.server:app", "--host", "0.0.0.0", "--port", "8080", "--app-dir", "src"]
