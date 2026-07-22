# reporting-watcher — the IFM cadence trigger: polls ASX reporting events, runs the
# governed doc→SQL workflow on the compute gateway the moment a pack lands.
FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir --upgrade pip && pip install --no-cache-dir -r requirements.txt
COPY main.py ./
ENV PORT=8080
EXPOSE 8080
# 8080 + /healthz = the chart contract.
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]
