# memoryd — sovereign memory-mesh service (recall/write/retract), vendored into prophet-platform CI.
FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir --upgrade pip && pip install --no-cache-dir -r requirements.txt
COPY src ./src
ENV PORT=8787
# Default store is in-memory (MEMORYMESH_STORE_URI=memory://); set postgresql:// / sqlite:/// to persist.
EXPOSE 8787
CMD ["uvicorn", "memoryd.main:app", "--host", "0.0.0.0", "--port", "8787", "--app-dir", "src"]
