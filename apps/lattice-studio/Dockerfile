# lattice-studio — the Studio BFF (FastAPI over product_spine + live fabric aggregation). Makes the surface live.
FROM python:3.12-slim
WORKDIR /app
COPY requirements.lock ./
RUN pip install --no-cache-dir --require-hashes -r requirements.lock
COPY src ./src
ENV PORT=8080
EXPOSE 8080
# 8080 + /healthz = the chart contract.
CMD ["uvicorn", "lattice_studio.server:app", "--host", "0.0.0.0", "--port", "8080", "--app-dir", "src"]
