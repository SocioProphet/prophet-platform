# spark-runner — the sovereign Apache Spark execution backend for the Studio execution plane.
FROM python:3.12-slim
# Spark needs a JRE.
RUN apt-get update && apt-get install -y --no-install-recommends default-jre-headless procps \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir --upgrade pip && pip install --no-cache-dir -r requirements.txt
COPY src ./src
ENV PORT=8080
EXPOSE 8080
# 8080 + /healthz = the chart contract.
CMD ["uvicorn", "spark_runner.server:app", "--host", "0.0.0.0", "--port", "8080", "--app-dir", "src"]
