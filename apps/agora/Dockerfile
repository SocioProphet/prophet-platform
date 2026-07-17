# agora — the sovereign work + knowledge plane (Jira/Confluence killer). Work items + wiki pages as proof-
# carrying HellGraph facts. Alongside zot (registry) & gitea-sovereign (SCM) in the estate.
FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir --upgrade pip && pip install --no-cache-dir -r requirements.txt
COPY src ./src
ENV PORT=8080
EXPOSE 8080
# 8080 + /healthz = the chart contract.
CMD ["uvicorn", "agora.server:app", "--host", "0.0.0.0", "--port", "8080", "--app-dir", "src"]
