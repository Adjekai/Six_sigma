# BloodWatch shared interfaces

This file is the contract between the synthetic-data generator, Python analysis, FastAPI service, and browser-native dashboard. Interface changes should be agreed before data, statistics, and display branches edit them independently.

All timestamps are ISO-8601 UTC strings. All demonstration records are synthetic.

## Dataset contract

The single dataset README and codebook is [`data/README.md`](../data/README.md). It documents every file and variable, collection background, joins, missing-value rules, scenarios, and derived dashboard metrics.

## Analysis defaults

| Parameter | Default | Meaning |
|---|---:|---|
| `lower_limit_c` | 1 | Configurable lower red-cell demo limit |
| `upper_limit_c` | 6 | Configurable upper red-cell demo limit |
| `temperature_window_hours` | 24 | Window ending at scenario reference time |
| `stale_after_minutes` | 30 | Latest valid reading older than this is stale |
| `horizon_operating_days` | 30 | Future refrigerator operating time |
| `annual_operating_hours` | 8,760 | Assumption used only for annual mechanical-loss scenario |
| `confidence_level` | 0.95 | Rate and proportion intervals |

The operating horizon converts to hours as `days × 24`; it is not calendar aging.

## Missing-data and warning contract

- Missing/stale temperature: condition state is `unknown`; never `within`.
- Zero mechanical exposure: refrigerator reliability is unavailable.
- Zero mechanical failures with positive exposure: point rate is zero, MTBF is unavailable, and the upper rate bound is reported.
- No known generator demands: generator probability is unavailable.
- Infinite or undefined values: JSON `null` plus a structured warning/reason.
- Missing inventory value or outcome: unknown; never coerced to zero.
- Missing temperature evidence during an incident: breach status is `unknown`.

Warnings use this structure:

```json
{
  "code": "ZERO_FAILURES",
  "level": "info",
  "message": "No mechanical failures were observed; the upper rate bound remains positive."
}
```

## HTTP API

### `GET /health`

Response:

```json
{"status": "ok", "service": "bloodwatch-api"}
```

### `GET /api/scenarios`

Response:

```json
{
  "scenarios": [
    {"id": "normal", "name": "Normal / resilient", "synthetic": true}
  ]
}
```

### `GET /api/dashboard`

Query parameters:

| Parameter | Type | Default |
|---|---|---|
| `scenario` | scenario ID | `normal` |
| `site_id` | string or omitted | all sites in scenario |
| `refrigerator_id` | string or omitted | first available refrigerator |
| `temperature_window_hours` | positive number | 24 |
| `horizon_operating_days` | positive number | 30 |

Response shape:

```json
{
  "scenario": {"id": "normal", "name": "Normal / resilient", "synthetic": true},
  "selection": {
    "site_id": null,
    "refrigerator_id": "R-N1",
    "temperature_window_hours": 24,
    "horizon_operating_days": 30
  },
  "conditions": {
    "temperature_summary": {},
    "temperature_series": [],
    "equipment": [],
    "inventory_exposed_usd": 0
  },
  "reliability": {
    "refrigerators": [],
    "generators": [],
    "breach_recovery": {}
  },
  "financial": {
    "actual_historical_loss_usd": 0,
    "inventory_exposed_usd": 0,
    "expected_annual_mechanical_loss_usd": null,
    "expected_annual_blackout_loss_usd": null,
    "loss_by_cause": []
  },
  "warnings": []
}
```

Invalid scenarios, IDs, horizons, schemas, or event ordering return HTTP 400/404 with an understandable `detail` message. The frontend formats API values but performs no statistical calculations.
# Course-focused overview additions

The existing response fields remain available. The overview also uses:

- `conditions.temperature_summary.standard_deviation_c`: sample SD (`ddof=1`) in the selected window; null with fewer than two valid readings. It describes spread, not standard error.
- `conditions.inventory_summary`: current bag count, lot count, known inventory value, unknown-value lot count, snapshot time, and refrigerator-level breakdown for the selected site scope.
- `conditions.process_analysis`: standard error, individuals-chart center and limits, signal count, within-process sigma, Cp/Cpk, and Pp/Ppk for the selected refrigerator window.
- `reliability.selected_refrigerator_model`: the pooled model for the selected refrigerator's model group; label its group and equipment count explicitly.
- `reliability.selected_generator`: the generator mapped to the selected refrigerator.
- `reliability.selected_breach_recovery`: incident summaries restricted to the selected refrigerator, unlike the existing site-wide `breach_recovery` field.
- Each incident includes `cooling_loss_utc`, `first_breach_utc` (nullable), and `cooling_restored_utc` (nullable), used for labels and event markers.

Times to first observed breach are sample-limited storage-condition observations. They are not biological viability times. The overview does not infer a future temperature-breach probability from the small selected incident sample.
