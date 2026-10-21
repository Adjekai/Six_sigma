PYTHON := .venv/bin/python

.PHONY: setup data test run

setup:
	python3 -m venv .venv
	$(PYTHON) -m pip install -r app/requirements-dev.txt

data:
	$(PYTHON) scripts/generate_scenarios.py

test:
	PYTHONPATH=app $(PYTHON) -m pytest -q

run:
	PYTHONPATH=app $(PYTHON) -m uvicorn api:app --host 127.0.0.1 --port 8000
