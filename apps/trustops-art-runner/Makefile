.PHONY: validate test smoke clean

validate: test smoke

test:
	test -d .venv || python3 -m venv .venv
	. .venv/bin/activate && python -m pip install --upgrade pip pytest && PYTHONPATH=src pytest -q tests

smoke:
	mkdir -p ../../build/trustops-art-runner
	PYTHONPATH=src python3 -m trustops_art_runner.cli run \
		--profile art-smoke \
		--manifest examples/functional-service.demo.json \
		--output ../../build/trustops-art-runner/trustops-art-smoke.receipt.json \
		--created-at 2026-05-05T00:00:00Z \
		--artifact-ref artifact://trustops/art-smoke/demo-classifier/receipt.json
	test -s ../../build/trustops-art-runner/trustops-art-smoke.receipt.json

clean:
	rm -rf .venv ../../build/trustops-art-runner
