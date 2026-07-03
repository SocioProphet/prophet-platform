.PHONY: install test smoke

install:
	pip install -e ".[dev]"

test:
	pip install -q -r requirements-test.txt -e .
	pytest -q

smoke:
	python - <<'EOF'
import asyncio
from agent_session import AgentSession, Reasoning

async def _run():
    session = AgentSession(reasoning=Reasoning.MODERATE)
    print("AgentSession instantiated OK — provider:", session._provider.__class__.__name__)
    print("Routing effort:", session._effort)

asyncio.run(_run())
EOF
