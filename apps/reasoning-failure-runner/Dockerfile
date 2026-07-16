# reasoning-failure-runner — the Chaos & Resilience Fabric orchestrator (CHAOS_RESILIENCE_FABRIC_V0.md).
# Clears the deploy scar: this app was in the platform-services ApplicationSet with NO Dockerfile, so it could
# only ImagePullBackOff. It is now a FastAPI service (was a batch CLI wrongly placed as a service).
FROM python:3.12-slim
WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir --upgrade pip \
 && pip install --no-cache-dir -r requirements.txt

COPY src ./src

ENV PORT=8080
EXPOSE 8080
# 8080 + /healthz = the chart contract (service.port / probes.path).
CMD ["uvicorn", "reasoning_failure_runner.server:app", "--host", "0.0.0.0", "--port", "8080", "--app-dir", "src"]
