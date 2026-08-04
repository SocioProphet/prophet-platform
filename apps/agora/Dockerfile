# agora — the sovereign work + knowledge plane (Jira/Confluence killer). Work items + wiki pages as proof-
# carrying HellGraph facts. Alongside zot (registry) & gitea-sovereign (SCM) in the estate.
FROM python:3.12-slim@sha256:cab2dbf575e971934a81e4622f5aba17aa7929719bd7e31033a3a83b97fd0464
WORKDIR /app
COPY requirements.lock ./
RUN pip install --no-cache-dir --require-hashes -r requirements.lock
COPY src ./src
ENV PORT=8080
EXPOSE 8080
# 8080 + /healthz = the chart contract.
CMD ["uvicorn", "agora.server:app", "--host", "0.0.0.0", "--port", "8080", "--app-dir", "src"]
