# voice-substrate — ASR + diarization + redaction (FastAPI). Step 1 of the Needs-vs-Wants
# build order (§10.3). The runtime image deliberately ships WITHOUT any speech dependency:
# redaction is pure Python and always works, and the ASR/diarization adapters report
# themselves unavailable on GET /healthz rather than failing opaquely at request time.
# To build an image that can actually transcribe, add:
#   RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg \
#       && pip install --no-cache-dir -r requirements-asr.txt
FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt
COPY src ./src
ENV PORT=8087
EXPOSE 8087
# liveness: GET /healthz — also reports which adapters are available in this image
CMD ["uvicorn", "voice_substrate.server:app", "--host", "0.0.0.0", "--port", "8087", "--app-dir", "src"]
