# BloodWatch shared interfaces

This file is the contract between the synthetic-data generator, Python analysis, FastAPI service, and React dashboard. Interface changes should be agreed before data, statistics, and display branches edit them independently.

All timestamps are ISO-8601 UTC strings. All demonstration records are synthetic.

## Scenario layout

Each folder under `data/scenarios/` contains the same five analytical CSV files plus metadata:

```text
data/scenarios/<scenario_id>/
  equipment_exposure.csv
  temperatures.csv
  cooling_incidents.csv
  blackout_demands.csv
  inventory_outcomes.csv
  metadata.json
```

`metadata.json` contains the synthetic label, display reference time, description, seed, and generation assumptions. Planted-event truth and generation parameters are metadata, not analytical observations.

## Table schemas

### `equipment_exposure.csv`

One row per observed refrigerator.

| Column | Type/unit | Rules |
|---|---|---|
| `equipment_id` | string | Unique refrigerator ID in the scenario |
| `site_id` | string | Required site key |
| `equipment_type` | string | `refrigerator` in this foundation |
| `model_group` | string | Only explicitly comparable equipment may be pooled |
| `generator_id` | string | Generator supporting this refrigerator |
| `observation_start_utc` | UTC timestamp | Before observation end |
| `observation_end_utc` | UTC timestamp | At or before scenario reference time |
| `mechanical_operating_hours` | hours, nonnegative | Excludes blackout interruption; zero-failure equipment remains included |

Mechanical failures are counted from `cooling_incidents.csv`, not temperature rows.

### `temperatures.csv`

One row per logged reading.

| Column | Type/unit | Rules |
|---|---|---|
| `timestamp_utc` | UTC timestamp | Required |
| `refrigerator_id` | string | Must match equipment ID |
| `temperature_c` | °C or blank | Numeric when valid; never impute blank as zero |
| `reading_valid` | boolean | `true` or `false` |

Equality with the configured 1 °C and 6 °C demonstration limits is within range. Missing or stale latest readings produce an unknown current condition.

### `cooling_incidents.csv`

One row per loss of effective cooling for one refrigerator.

| Column | Type/unit | Rules |
|---|---|---|
| `incident_id` | string | Unique incident key |
| `refrigerator_id` | string | Must match equipment ID |
| `cause` | category | `mechanical`, `blackout_failed_start`, or `blackout_interruption` |
| `cooling_loss_utc` | UTC timestamp | Required start |
| `observation_end_utc` | UTC timestamp | Not before loss time |
| `cooling_restored_utc` | UTC timestamp or blank | Not before loss; blank means unresolved |
| `blackout_id` | string or blank | Required only for blackout-caused incidents |

Recovery means effective cooling was restored; it does not mean temperature was already back within range.

### `blackout_demands.csv`

One row per blackout demand per associated generator. A blackout affecting multiple refrigerators is still one generator demand.

| Column | Type/unit | Rules |
|---|---|---|
| `blackout_id` | string | Unique demand key in the scenario |
| `site_id` | string | Required site key |
| `generator_id` | string | Required generator key |
| `start_utc` | UTC timestamp | Required |
| `end_utc` | UTC timestamp | Not before start |
| `auto_start_outcome` | category | `success`, `failure`, or `unknown` |

Scheduled exercise tests are not included in this table.

### `inventory_outcomes.csv`

Current inventory snapshots and incident outcomes share a file but remain different record types.

| Column | Type/unit | Rules |
|---|---|---|
| `record_type` | category | `current_snapshot` or `incident_outcome` |
| `as_of_utc` | UTC timestamp | Required |
| `incident_id` | string or blank | Required for incident outcomes |
| `lot_id` | string | Used to deduplicate overlapping alerts |
| `refrigerator_id` | string | Must match equipment ID |
| `bags_present` | count, nonnegative integer | Bags associated with record |
| `value_per_bag_usd` | USD/bag, nonnegative | Blank means cost unknown, not zero |
| `bags_transferred` | count, nonnegative integer or blank | Blank means outcome unknown |
| `bags_written_off` | count, nonnegative integer or blank | Cannot exceed eligible bags |

Zero written-off bags must be recorded as `0`. A blank outcome is unknown and excluded from the corresponding denominator.

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
