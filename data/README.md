# BloodWatch dataset README and codebook

BloodWatch uses reproducible synthetic data. No records describe real patients, donors, blood banks, or equipment.

Each folder in `data/scenarios/` represents one dashboard scenario and contains the same five CSV files plus `metadata.json`. Every scenario has three refrigerators and one shared backup generator.

| Scenario | Current inventory | Purpose |
|---|---:|---|
| `normal` | 1,050 bags | Temperatures stay within range and the generator starts successfully |
| `refrigerator_breakdown` | 1,100 bags | A mechanical cooling failure produces an out-of-range temperature |
| `blackout_failed_backup` | 1,000 bags | One blackout and one failed generator start affect three refrigerators |

General rules:

- All timestamps are UTC.
- Blank means unknown or not applicable; numeric zero is an observed zero.
- `refrigerator_id`, `generator_id`, `incident_id`, and `blackout_id` join related files.
- One blackout is one generator demand even when it affects several refrigerators.
- The 1–6 °C range is a storage requirement, not a biological spoilage threshold.

## Overview

### `metadata.json`

Generated scenario context. In real collection, these values would come from study documentation and analysis configuration.

| Variable | Meaning |
|---|---|
| `id` | Scenario key |
| `name` | Display name |
| `description` | Short scenario summary |
| `synthetic` | Confirms the data are simulated |
| `reference_time_utc` | End of the dashboard observation window |
| `seed` | Random seed used for reproducibility |
| `generation_assumptions` | Modeling limitations |
| `planted_truth` | Events intentionally placed in the scenario for verification |

### `inventory_outcomes.csv`

Current blood inventory and historical incident outcomes. Real sources would be the blood inventory, incident-review, and finance systems.

| Variable | Meaning |
|---|---|
| `record_type` | `current_snapshot` or `incident_outcome` |
| `as_of_utc` | Time represented by the row |
| `incident_id` | Related incident; blank for a current snapshot |
| `lot_id` | Blood lot identifier used to prevent double counting |
| `refrigerator_id` | Refrigerator holding the inventory |
| `bags_present` | Number of bags stored or involved |
| `value_per_bag_usd` | Demonstration value per bag; blank if unknown |
| `bags_transferred` | Bags moved after an incident; blank if unknown or not applicable |
| `bags_written_off` | Bags confirmed written off; blank if unknown or not applicable |

## 1. Temperature

### `temperatures.csv`

Fifteen-minute refrigerator readings. Real data would come from calibrated temperature loggers and the monitoring-quality system.

| Variable | Meaning |
|---|---|
| `timestamp_utc` | Reading time |
| `refrigerator_id` | Refrigerator measured |
| `temperature_c` | Recorded temperature in °C; blank if missing |
| `reading_valid` | Whether the reading passed validation |

Invalid or missing readings are never replaced with zero. Readings exactly at 1 °C or 6 °C are within range.

## 2. Cooling loss to out-of-range temperature

### `cooling_incidents.csv`

One row per cooling-loss incident per refrigerator. Real data would combine alarm, maintenance, power-event, and root-cause records.

| Variable | Meaning |
|---|---|
| `incident_id` | Unique incident key |
| `refrigerator_id` | Refrigerator affected |
| `cause` | `mechanical`, `blackout_failed_start`, or `blackout_interruption` |
| `cooling_loss_utc` | Time effective cooling stopped |
| `observation_end_utc` | End of available evidence |
| `cooling_restored_utc` | Time effective cooling returned; blank if unresolved |
| `blackout_id` | Related blackout; blank for a mechanical incident |

The dashboard measures from `cooling_loss_utc` to the first valid temperature strictly outside 1–6 °C. This is an observed storage-limit crossing, not a spoilage time.

## 3. Failure risk

### `equipment_exposure.csv`

Refrigerator identity and operating exposure. Real sources would be the asset register, maintenance system, and runtime meter.

| Variable | Meaning |
|---|---|
| `equipment_id` | Refrigerator identifier |
| `site_id` | Site identifier |
| `equipment_type` | Equipment category; currently `refrigerator` |
| `model_group` | Refrigerators allowed to share one reliability estimate |
| `generator_id` | Shared backup generator |
| `observation_start_utc` | Exposure-period start |
| `observation_end_utc` | Exposure-period end |
| `mechanical_operating_hours` | Operating hours used as the mechanical-failure denominator |

### `blackout_demands.csv`

One row per blackout demand on the backup generator. Real sources would be utility, transfer-switch, and generator-controller logs.

| Variable | Meaning |
|---|---|
| `blackout_id` | Unique blackout demand |
| `site_id` | Site affected |
| `generator_id` | Generator asked to start |
| `start_utc` | Blackout start |
| `end_utc` | Blackout end |
| `auto_start_outcome` | `success`, `failure`, or `unknown` |

Scheduled generator tests are not blackout demands.

## 4. Reliability metrics

These dashboard fields are calculated, not collected as additional variables.

| Metric | Calculation |
|---|---|
| Failure rate `λ` | Mechanical failures ÷ mechanical operating hours |
| Reliability `R(t)` | `exp(−λt)` |
| Failure probability `F(t)` | `1 − R(t)` |
| Hazard `h(t)` | `λ` under the constant-rate model |
| MTBF | `1 ÷ λ`; unavailable when no failures are observed |
| Generator failed-start rate | Failed starts ÷ blackout demands with known outcomes |
| Generator uncertainty | 95% Wilson interval for the failed-start rate |

## 5. Process analysis

These fields are calculated from valid rows in `temperatures.csv`. If a visible incident exists, pre-incident readings form the baseline; otherwise the selected window is the exploratory baseline.

| Metric | Meaning |
|---|---|
| Mean | Average temperature |
| Sample SD | Spread of individual readings |
| Standard error | Sample SD ÷ square root of the reading count |
| Control limits | Individuals-chart limits estimated from moving ranges |
| Control signal | Reading outside the estimated control limits |
| Cp / Cpk | Potential and centered capability using within-process variation |
| Pp / Ppk | Overall performance using variation across the selected window |

Control limits describe observed process behavior. The 1–6 °C storage limits describe the product requirement.

## Reproduce the datasets

From the repository root:

```sh
python3 scripts/project.py data
```

The fixed seeds in `scripts/generate_scenarios.py` recreate the same files.
