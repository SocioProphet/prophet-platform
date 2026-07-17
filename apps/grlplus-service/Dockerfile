# grlplus-service — the GRLPlus policy evaluator (FastAPI). Evaluates worklist closure/escalation
# rules against the proof-carrying HellGraph → makes GRLPlus a live, graph-integrated service.
FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir --upgrade pip && pip install --no-cache-dir -r requirements.txt
COPY src ./src
ENV PORT=8080
EXPOSE 8080
# 8080 + /healthz = the chart contract.
CMD ["uvicorn", "grlplus_service.server:app", "--host", "0.0.0.0", "--port", "8080", "--app-dir", "src"]
