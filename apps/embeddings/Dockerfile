FROM python:3.11-slim

ENV PIP_NO_CACHE_DIR=1 \
    HF_HOME=/opt/hf \
    SENTENCE_TRANSFORMERS_HOME=/opt/hf \
    EMBEDDINGS_MODEL_ID=nomic-ai/nomic-embed-text-v1.5

WORKDIR /app

# CPU-only torch first, so sentence-transformers doesn't drag in the ~2GB CUDA build.
RUN pip install torch==2.5.1 --index-url https://download.pytorch.org/whl/cpu

COPY requirements.txt .
RUN pip install -r requirements.txt

# Bake the model into the image at build (online here) so the running container needs NO HuggingFace
# egress — fully self-contained, pulled only from the sovereign registry.
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('${EMBEDDINGS_MODEL_ID}', trust_remote_code=True)" \
 && chmod -R a+rX /opt/hf

# Lock the runtime to offline — never reach out to HuggingFace on a request.
ENV HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1

COPY app.py .

EXPOSE 8080
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8080"]
