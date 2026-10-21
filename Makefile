PYTHON := .venv/bin/python

.PHONY: setup data test build run

setup:
	python3 -m venv .venv
	$(PYTHON) -m pip install -r app/requirements-dev.txt
	cd app/frontend && npm ci

data:
	$(PYTHON) scripts/generate_scenarios.py

test:
	PYTHONPATH=app $(PYTHON) -m pytest -q
	cd app/frontend && npm run build

build:
	cd app/frontend && npm run build

run: build
	PYTHONPATH=app $(PYTHON) -m uvicorn api:app --host 127.0.0.1 --port 8000
