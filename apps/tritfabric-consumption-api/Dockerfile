# tritfabric-consumption-api — the prophet-platform consumption surface for TritFabric (readiness/contract
# reporting; deliberately non-mutating). Root build context so the integration contract travels with the app.
FROM python:3.11-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY apps/tritfabric-consumption-api/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir --upgrade pip && pip install --no-cache-dir -r /app/requirements.txt
COPY apps/tritfabric-consumption-api /app/apps/tritfabric-consumption-api
COPY contracts/integrations/tritfabric-consumption.v0.json /app/contracts/integrations/tritfabric-consumption.v0.json
ENV PORT=8080
EXPOSE 8080
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080", "--app-dir", "apps/tritfabric-consumption-api"]
