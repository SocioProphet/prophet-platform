# algo-engine — real backtests over Yahoo daily bars + strategy-from-NL + a paper-execution ledger
# (FastAPI/numpy). Powers the Algo Trading cockpit surface. No in-cluster deps (pulls Yahoo directly).
FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir --upgrade pip && pip install --no-cache-dir -r requirements.txt
COPY src ./src
ENV PORT=8080
EXPOSE 8080
# liveness: GET /healthz
CMD ["uvicorn", "algo_engine.server:app", "--host", "0.0.0.0", "--port", "8080", "--app-dir", "src"]
