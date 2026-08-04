FROM python:3.12-slim@sha256:cab2dbf575e971934a81e4622f5aba17aa7929719bd7e31033a3a83b97fd0464
WORKDIR /app
COPY requirements.lock ./requirements.txt
RUN pip install --no-cache-dir --require-hashes -r requirements.lock
COPY app ./app
COPY schemas ./schemas
EXPOSE 8080
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
