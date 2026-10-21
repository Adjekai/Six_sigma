# BloodWatch application

## Module map

```text
api.py                       FastAPI routes only
qc.py                        public import surface for statistics
bloodwatch/
  repository.py              CSV parsing and cross-table validation
  temperature.py             temperature summaries/current state
  reliability.py             refrigerator and generator estimates
  incidents.py               breach-time and recovery summaries
  financial.py               exposed, actual, and expected loss
  service.py                 combines module outputs for the dashboard
frontend/
  src/api.js                  HTTP calls
  src/App.jsx                 three dashboard sections and controls
  src/components/             small display-only components
```

The dependency direction is one way:

```text
React → FastAPI → service → focused analysis modules → validated scenario data
```

Python owns every analytical calculation. React formats values and draws the API-provided data.

## API routes

- `GET /health`
- `GET /api/scenarios`
- `GET /api/dashboard`

The complete query/response contract is in [`docs/interfaces.md`](../docs/interfaces.md).

## Local commands

From the repository root:

```sh
make test
make run
```

`make run` builds React, then serves the API and built dashboard together on port 8000.

## Adding a statistic

1. Write a plain function in the most relevant `bloodwatch/` module.
2. Add a known-answer test and edge cases under `tests/`.
3. Add the result to `service.py` and document it in `docs/interfaces.md`.
4. Render that API field in React without recreating the formula.
