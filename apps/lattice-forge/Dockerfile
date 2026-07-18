# lattice-forge — governed, adapter-based notebook runtime (headless nbclient
# execution + JupyterLab session broker) with hash-chained receipts.
# Runs in the isolated `sovereign-runtime` namespace (executes user code).
FROM python:3.12-slim

# non-root: this service executes user code, so it must never run as root.
RUN useradd -m -u 10001 forge
WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir --upgrade pip && pip install --no-cache-dir -r requirements.txt

COPY src ./src
ENV PORT=8870 PYTHONUNBUFFERED=1
EXPOSE 8870
USER forge
CMD ["uvicorn", "lattice_forge.server:app", "--host", "0.0.0.0", "--port", "8870", "--app-dir", "src"]
