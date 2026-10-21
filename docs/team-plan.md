# BloodWatch team handoff

The current foundation is intentionally small: generated CSV scenarios → plain Python functions → FastAPI JSON → browser-native display.

## Shared foundation ownership

| Area | Current paths | Owner after foundation review |
|---|---|---|
| Interface contract/integration | `docs/interfaces.md`, `app/api.py`, `app/bloodwatch/service.py` | Integration owner: assign name |
| Data | `scripts/generate_scenarios.py`, `data/` | `feature/data`: assign name |
| Statistics | `app/qc.py`, `app/bloodwatch/{temperature,reliability,incidents,financial}.py`, statistical tests | `feature/statistics`: assign name |
| Display | `app/frontend/` | `feature/display`: assign name |
| Documentation/demo/deployment | `ReadMe.md`, `demo/`, future manifest/deploy scripts | Assign name |

Agree on any change to `docs/interfaces.md` before changing schemas or response fields.

## Branch creation

These commands are for use **after this foundation is reviewed and merged into `main`**. Each teammate branches independently from `main`; do not branch from another unmerged feature.

### Data branch

```sh
git switch main
git pull --ff-only
git switch -c feature/data
```

Next tasks:

- Add validation tests for overlapping incidents and inventory deduplication.
- Add an explicit unknown generator outcome and missing inventory-cost example.
- Review whether mechanical exposure can be collected realistically.
- Keep generation truth out of analytical inputs.

### Statistics branch

```sh
git switch main
git pull --ff-only
git switch -c feature/statistics
```

Next tasks:

- Add confidence intervals for annual expected loss or label them unavailable.
- Add stronger inventory-loss deduplication tests.
- Review recovery censoring language and all incomplete-outcome warnings.
- Cross-check exact Poisson and Wilson intervals against a trusted independent package.

### Display branch

```sh
git switch main
git pull --ff-only
git switch -c feature/display
```

Next tasks:

- Improve chart time labels and add power/incident markers.
- Add compact refrigerator and site selectors without adding new calculations.
- Add accessibility checks and responsive-table refinements.
- Keep every metric definition, denominator, period, and unavailable state visible.

## Integration owner checklist

- Protect the JSON contract and review cross-workstream changes.
- Keep all calculations in Python.
- Run `make test` before accepting a branch.
- Exercise all scenarios after merges.
- Add course `manifestme` and deployment scripts once the official starter files are incorporated.
- Never push secrets or publish automatically.
