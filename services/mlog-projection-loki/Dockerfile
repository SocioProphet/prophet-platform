# mlog-projection-loki — Map-Log (Kafka) -> Loki projection consumer.
# context: services/mlog-projection-loki, dockerfile: Dockerfile (images.yml matrix).
FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY *.py ./
RUN useradd -u 65532 -m svc && chown -R svc /app
USER 65532
EXPOSE 9109
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://localhost:9109/healthz').status==200 else 1)" || exit 1
CMD ["python", "app.py"]
