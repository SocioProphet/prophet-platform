.PHONY: install test validate

install:
	pip install -e ".[dev]"

test:
	pip install -q -r requirements-test.txt -e .
	pytest -q

validate:
	python ../../../tools/validate_mount_intent_egress.py
