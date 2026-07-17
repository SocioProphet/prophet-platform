# owl-reasoner — RDFS/OWL-RL reasoning + SHACL validation over the HellGraph (Ontogenesis inference bridge).
FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir --upgrade pip && pip install --no-cache-dir -r requirements.txt
COPY src ./src
ENV PORT=8080
EXPOSE 8080
CMD ["uvicorn", "owl_reasoner.server:app", "--host", "0.0.0.0", "--port", "8080", "--app-dir", "src"]
