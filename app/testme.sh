#!/usr/bin/env sh
set -eu

PYTHONPATH=app .venv/bin/python -m pytest -q
