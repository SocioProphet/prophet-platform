# BUILD CONTEXT = REPO ROOT (see .github/workflows/images.yml). main.py loads seven
# producer modules from ROOT/tools at import time (Path(__file__).parents[2]), and
# those producers read files from SEVERAL sibling trees at REQUEST time. Every path
# below was found by running the container and hitting each /v1 route the SPA calls,
# not by reading imports — the failures only show up at request time:
#   apps/dashboard-bff        main.py + its data/ (vdt, gyg)
#   tools                     the 7 emit_* producers (stdlib-only)
#   apps/hellgraph-service/seeds   gyg-supply-chain-causal.json (/v1/valuation/causal)
#   schemas/eval              metric-*.schema.json (/v1/intelligence-superiority validates)
# Missing any one = a 200 on /health and a 500 on the route that needs it — the
# estate's signature "healthy-looking, broken" shape. Copy exactly these, no more.
FROM python:3.11-slim

RUN useradd -u 10001 -m -s /usr/sbin/nologin app
WORKDIR /app

COPY apps/dashboard-bff/requirements.txt ./apps/dashboard-bff/requirements.txt
RUN pip install --no-cache-dir -r apps/dashboard-bff/requirements.txt

COPY apps/dashboard-bff ./apps/dashboard-bff
COPY tools ./tools
COPY apps/hellgraph-service/seeds ./apps/hellgraph-service/seeds
COPY schemas/eval ./schemas/eval

RUN chown -R 10001:10001 /app
USER 10001

# 8080 + /health is the chart contract (service.port / probes.path). The values file
# sets probes.path=/health because that is what main.py serves — asserted by the
# probe-contract gate, not assumed.
EXPOSE 8080
ENV DASHBOARD_BFF_CORS_ORIGINS="https://app.socioprophet.com"
WORKDIR /app/apps/dashboard-bff
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]
