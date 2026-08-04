FROM python:3.12-slim
WORKDIR /app
COPY requirements.lock ./requirements.txt
RUN pip install --no-cache-dir --require-hashes -r requirements.lock
COPY app ./app
COPY third_party ./third_party
EXPOSE 8080
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
