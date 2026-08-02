# catalog-gateway — the unified read/resolve/lineage + DCAT interop seam over the
# Crystal Atlas catalog families (the GMS-equivalent). Read/display + interop surface
# that also captures its own operational events. Control-plane only (no user code) →
# platform namespace.
FROM python:3.12-slim
RUN useradd -m -u 10001 gateway
WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir --upgrade pip && pip install --no-cache-dir -r requirements.txt
COPY app ./app
ENV PORT=8080 PYTHONUNBUFFERED=1 CATALOG_OPS_CAPTURE=true
EXPOSE 8080
USER gateway
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
