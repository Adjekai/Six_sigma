# BloodWatch

BloodWatch is a class-project dashboard prototype for monitoring blood-bank refrigerator temperatures, cooling interruptions, equipment reliability, and the inventory exposed at each refrigerator. It combines three related CSV history files with optional incoming temperature readings and offers reproducible synthetic scenarios for demonstrations.

Team: Audrey Sakcey, Isabelle Seidenberg, Jasmine Tamous, Ameera El'Amin-White, Jonathan Engle.

## 1. Supervisor overview

### Project purpose

Regional blood banks depend on refrigerators and backup generators to protect stored blood products. BloodWatch demonstrates how a single dashboard could help staff review current temperature conditions, identify cooling events, compare historical equipment reliability, and see how much inventory is stored in each unit.

The dashboard is a decision-support demonstration. It flags readings or trends for review; it does not declare products safe or unsafe, diagnose an equipment fault, or replace a qualified person's response process.

### What the tool shows

- **Supply overview:** bag and lot counts, estimated inventory value, refrigerator status, and a per-unit warning table.
- **Temperature history:** latest, average, minimum, and maximum valid readings for the selected refrigerator, plotted against configurable temperature limits.
- **Cooling interruptions:** time from recorded cooling loss to the first valid out-of-range reading, plus time to recorded cooling restoration. A temperature-limit crossing is not a biological spoilage time.
- **Reliability estimates:** pooled refrigerator mechanical-failure estimates from failure counts and operating-hour exposure; generator failed-start estimates from known blackout outcomes.
- **Scenario demonstrations:** stable conditions, a planted refrigerator cooling failure, and a failed generator start during a blackout.

### Data modes

| Mode | Data used | Intended use |
|---|---|---|
| Live data | The three baseline CSV files plus valid readings stored in SQLite | Demonstrate the incoming-reading path. With no sensor connected, the dashboard shows CSV history only. |
| Stable conditions | Rebuilt synthetic readings and event history | Show a no-alarm example. |
| Degrading refrigerator | Synthetic replay with a planted failure on R1 | Show a refrigerator cooling-loss response. |
| Blackout with failed generator | Synthetic replay of one failed start affecting the refrigerators connected to G1 | Show a shared-power event. |

The bundled temperature producer is a simulator, not a hardware sensor. All baseline files and scenario events are synthetic educational data.

### Quick start

Python 3.12–3.15 is supported; Python 3.14 or 3.15 is recommended.

| Task | macOS | Windows PowerShell |
|---|---|---|
| Create environment, install packages, generate the baseline CSV files | `python3 scripts/project.py setup` | `py scripts\project.py setup` |
| Check Python and installed packages | `python3 scripts/project.py doctor` | `py scripts\project.py doctor` |
| Run the dashboard | `python3 scripts/project.py run` | `py scripts\project.py run` |
| Run the automated checks | `python3 scripts/project.py test` | `py scripts\project.py test` |
| Regenerate the three baseline CSV files | `python3 scripts/project.py data` | `py scripts\project.py data` |

Open <http://127.0.0.1:8000>. Stop the server with Ctrl+C in its terminal.

To send simulated readings from another terminal while the dashboard is running:

```sh
python scripts/stream_temperature.py --interval 15
```

The simulator sends one reading for each selected refrigerator per cycle. Options include `--api-url`, `--interval`, `--refrigerators`, and `--once`; see the function and CLI reference below.

### Important assumptions and limitations

- All supplied data is synthetic and is not evidence about a real blood bank, sensor, refrigerator, generator, or product lot.
- The default 1–6 °C range is a demonstration setting for red-cell storage. Confirm product-specific requirements and local policy before using different limits.
- Refrigerator reliability assumes a constant event rate and pools comparable equipment by model group. The estimate is not a prediction of which individual unit will fail or exactly when.
- Generator estimates assume future blackout demands resemble the observed known outcomes. Unknown outcomes are excluded from the rate denominator.
- Temperature projections extend a recent linear trend over a short horizon. They can be wrong if conditions change.
- The local API has no sensor authentication. It binds to localhost by default; do not expose it to a network without appropriate authentication and transport security.
- Inventory values use the synthetic per-bag value in the equipment file. They represent modeled exposure, not audited financial losses.

## 2. Dataset codebook and tool documentation

### Documentation labels

Function and endpoint notes use small labels to make their purpose and configuration easy to scan:

- **INPUT** — data supplied by a caller or request.
- **PARAMETERS** — optional settings and their defaults.
- **OUTPUT** — the returned value or visible effect.
- **NOTE** — assumptions, validation, or important behavior.

### Repository map

#### Data files

| File | Purpose |
|---|---|
| `data/blood_temperature.csv` | Timestamped baseline and event-related temperature readings. |
| `data/refrigerator_failures.csv` | Refrigerator identity, operating exposure periods, mechanical events, normal-baseline periods, and one current-inventory snapshot per refrigerator. |
| `data/generator_failures.csv` | One row per blackout demand on a backup generator, including the start outcome and any resulting cooling-loss interval. |
| `data/live_readings.sqlite3` | Created at runtime when a reading is received. Holds incoming readings and rejected-reading records; it is not a checked-in baseline dataset. |

#### Application and analysis code

| File | Purpose |
|---|---|
| `app/api.py` | FastAPI application, health/dashboard/scenario routes, incoming-reading validation and persistence, and static frontend serving. It also retains a direct CSV API endpoint; the browser dashboard has no CSV file-picker option. |
| `app/bloodwatch/service.py` | Joins repository data and analysis functions into the JSON object consumed by the dashboard. Builds equipment status, forecasts, inventory summaries, reliability estimates, and scenario alarm summaries. |
| `app/bloodwatch/repository.py` | Reads, converts, and validates the three baseline CSV files; merges SQLite readings in live mode; determines the data reference time. |
| `app/bloodwatch/temperature.py` | Temperature summaries, short trend forecasts, and process/capability calculations. Process-analysis values remain in the API response even though the advanced diagnostics panel was removed from the browser view. |
| `app/bloodwatch/incidents.py` | Matches event-related temperature readings to cooling interruptions and summarizes crossings, recovery, censoring, and missing observations. |
| `app/bloodwatch/reliability.py` | Constant-rate refrigerator reliability estimates and generator failed-start proportions with confidence intervals. |
| `app/bloodwatch/financial.py` | Standalone expected-loss and financial-summary calculations. `expected_inventory_loss` is used by the dashboard service; `summarize_financials` is available as a module function but is not currently called by the dashboard service. |
| `app/bloodwatch/live_data.py` | SQLite path selection, insertion and loading of readings, rejected-reading logging, and rejection summaries. |
| `app/bloodwatch/scenarios.py` | Stable and event scenario transformations applied to copies of the baseline data. |
| `app/bloodwatch/common.py` | Shared UTC parsing, warning formatting, finite-number handling, and nonnegative-value validation helpers. |
| `app/bloodwatch/__init__.py` | Marks `bloodwatch` as a Python package. |
| `app/qc.py` | Convenient public exports for the main statistical functions. |

#### Browser interface

| File | Purpose |
|---|---|
| `app/frontend/index.html` | HTML shell, page title/description, and links to the frontend assets. |
| `app/frontend/app.js` | Fetches dashboard JSON, tracks selected controls, renders the summary, charts, scenario banner, and expandable sections, and refreshes the dashboard. |
| `app/frontend/src/styles.css` | Responsive layout, colors, typography, tables, charts, banners, and expandable-section styling. |
| `app/frontend/favicon.ico` | Browser-tab icon. |

#### Scripts, setup, and tests

| File | Purpose |
|---|---|
| `scripts/project.py` | Cross-platform `doctor`, `setup`, `test`, `run`, and `data` command-line helper. |
| `scripts/generate_scenarios.py` | Deterministically generates the three related synthetic baseline CSV files in `data/`. Despite its historical filename, it writes the baseline files, not separate scenario folders. |
| `scripts/stream_temperature.py` | Generates and posts simulated temperature readings to the API. |
| `tests/test_api.py` | API routes, frontend delivery, parameter validation, live-reading ingestion, and scenario response checks. |
| `tests/test_class_dashboard.py` | Dataset relationships, dashboard response shape, incident timing, selected refrigerator behavior, and baseline process-analysis behavior. |
| `tests/test_scenarios.py` | Scenario construction, synthetic event behavior, and the effect of live readings on live versus replay data. |
| `tests/test_statistics.py` | Known-answer and edge-case checks for temperature, incident, reliability, and financial calculations. |
| `app/requirements.txt` | Runtime Python dependencies: FastAPI, SciPy, and Uvicorn. |
| `app/requirements-dev.txt` | Development dependencies; includes runtime requirements plus HTTPX and pytest. |
| `app/run.sh` | Unix helper that starts Uvicorn from the local virtual environment. |
| `app/testme.sh` | Unix helper that runs pytest from the local virtual environment. |
| `Makefile` | Alternative setup, data-generation, test, and run commands for Make users. |
| `.gitignore` | Excludes local environment, runtime data, and generated files from version control. |
| `project.Rproj` | RStudio project settings; not required to run the Python dashboard. |
| `new_file.R` | Auxiliary R/Git example that requests a GitHub token and demonstrates pull/add/commit/push. It is unrelated to the dashboard and is not needed to run it. |
| `ReadMe.md` | This project overview, dataset codebook, and technical reference. |

Local `.venv/`, Python `__pycache__/` folders, and the SQLite live database are generated/runtime artifacts and are not source datasets.

### Dataset background and collection guidance

The three files are linked by `refrigerator_id`, `generator_id`, site IDs, and event IDs. They are designed to model the records a real deployment would need to collect from calibrated temperature loggers, an equipment/maintenance register, generator or transfer-switch logs, and inventory snapshots. This repository does not connect to those real systems.

The sample contains three refrigerators (`R1`–`R3`) at one site, all assigned to generator `G1` and model group `CW-100`. Current stock and per-bag values are illustrative sample values, not a regional inventory claim.

**Shared data conventions**

- Times are ISO-8601 timestamps in UTC, normally written with a trailing `Z`. Runtime API readings must include a timezone.
- Empty cells mean unknown or not applicable; they do not mean zero.
- Numeric values are measurements or quantities. A zero is an observed zero.
- IDs must be stable across files so that equipment and event records can be joined.
- Temperature readings exactly at the configured lower or upper limit are in range; only values strictly below or above a limit cross it.
- Keep the collected value, validity/quality result, unit identifier, source, and timestamp. Do not replace missing or invalid temperatures with zero.

#### `blood_temperature.csv` codebook

One row represents one refrigerator reading. The synthetic logger interval is 15 minutes, with normal baseline, recent history, and short event histories.

| Variable | Type / units | Meaning and collection notes |
|---|---|---|
| `timestamp_utc` | ISO-8601 UTC timestamp | Time the logger took the reading. In real collection, preserve the logger's original timestamp and timezone/clock quality. |
| `refrigerator_id` | Text ID | Refrigerator measured; must match an ID in `refrigerator_failures.csv`. |
| `temperature_c` | Decimal °C or blank | Measured temperature. Blank when `reading_valid` is false. Never use zero to represent a missing reading. |
| `reading_valid` | Boolean (`true`/`false`) | Whether the reading passed the monitoring/quality check. A valid row requires a numeric temperature; an invalid row requires a blank temperature. |
| `related_failure_event_id` | Text ID or blank | Event associated with the reading, matching `failure_event_id` or `blackout_event_id`. Blank for ordinary readings. |

For a real logger, record device/source identity, calibration status, sampling interval, clock synchronization, and quality flags as part of the collection process. The current CSV schema has no separate source column; live readings do store a source string in SQLite.

#### `refrigerator_failures.csv` codebook

Each row represents an equipment operating period. A refrigerator has historical exposure, one normal-baseline period, and a current period/inventory snapshot. Mechanical-failure rows include event timing. Inventory fields are populated on one current-snapshot row per refrigerator.

| Variable | Type / units | Meaning and collection notes |
|---|---|---|
| `operating_period_id` | Unique text ID | Identifier for this exposure period. |
| `refrigerator_id` | Text ID | Refrigerator identifier; joins to temperature readings and affected inventory. |
| `site_id` | Text ID | Blood-bank site identifier. |
| `model_group` | Text category | Comparable refrigerator model group used to pool failure exposure. Pool only equipment with defensible comparability. |
| `generator_id` | Text ID | Backup generator serving this refrigerator; joins to generator demand rows. |
| `period_start_utc` | ISO-8601 UTC timestamp | Start of the operating/exposure period. |
| `period_end_utc` | ISO-8601 UTC timestamp | End of the operating/exposure period. Must follow the period start; periods for one unit cannot overlap. |
| `observed_operating_hours` | Decimal hours | Mechanical operating-time exposure used as the refrigerator failure-rate denominator. Exclude downtime when the unit is not operating. |
| `mechanical_failure` | Boolean | Whether a mechanical failure occurred in this period. |
| `failure_event_id` | Text ID or blank | Unique mechanical event ID when `mechanical_failure` is true; blank otherwise. |
| `cooling_loss_utc` | ISO-8601 UTC timestamp or blank | Effective time cooling stopped for the mechanical event. |
| `cooling_restored_utc` | ISO-8601 UTC timestamp or blank | Time effective cooling was restored. Required for failure events in the current CSV validation rules; blank for periods without a failure. |
| `normal_baseline` | Boolean | Marks the designated normal-operation period used to estimate fixed process-control behavior. Exactly one period per refrigerator is required. |
| `current_bags` | Nonnegative integer or blank | Current inventory snapshot count for this refrigerator. Populated on exactly one row per refrigerator. |
| `current_lot_count` | Nonnegative integer or blank | Number of current inventory lots in the refrigerator snapshot. |
| `value_per_bag_usd` | Nonnegative decimal USD or blank | Assumed per-bag value used for modeled inventory exposure. Replace with a locally approved valuation source in real collection. |

Real sources would include the asset register, maintenance/work-order records, runtime meters, and inventory/lot snapshots. Document the exposure definition and whether periods include standby, defrost, maintenance, or downtime.

#### `generator_failures.csv` codebook

One row is one blackout demand on a backup generator. A single failed start can produce one cooling-interruption record for every refrigerator attached to that generator, but it remains one generator demand for the failure-rate denominator. Scheduled tests are not included as blackout demands in this sample.

| Variable | Type / units | Meaning and collection notes |
|---|---|---|
| `blackout_event_id` | Unique text ID | Identifier for one blackout/generator demand; joins to temperature event references. |
| `generator_id` | Text ID | Generator asked to start; must match the equipment file. |
| `site_id` | Text ID | Site affected by the blackout. |
| `blackout_start_utc` | ISO-8601 UTC timestamp | Time utility power was lost / generator demand began. |
| `blackout_end_utc` | ISO-8601 UTC timestamp | Time the blackout ended. Must not precede its start. |
| `start_outcome` | `success`, `failure`, or `unknown` | Observed automatic start outcome. Unknown outcomes are excluded from the known-outcome denominator and reported separately. |
| `cooling_loss_utc` | ISO-8601 UTC timestamp or blank | Effective cooling-loss time when the automatic start failed. |
| `cooling_restored_utc` | ISO-8601 UTC timestamp or blank | Time cooling was restored after a failed start. Required for failed-start event records in the current validation rules. |

Real sources would be utility outage logs, generator controller logs, transfer-switch records, and maintenance/event review. Preserve unknown outcomes instead of guessing success or failure.

### Collection, validation, and scenario notes

- `repository.load_data()` validates IDs, periods, event relationships, validity/value consistency, baseline/snapshot counts, and generator outcomes before analysis.
- The dashboard's baseline reference time is the latest valid, non-baseline reading from the CSV history plus any accepted live readings. Baseline observations are kept separately for process analysis.
- The scenario selector transforms copies of the loaded baseline data. It does not rewrite baseline CSVs or use the SQLite live feed.
- `scripts/generate_scenarios.py` uses a fixed random seed (`5930`) for reproducible normal readings. It overwrites the three named CSV files when run; review/version-control changes before regenerating customized datasets.
- In Live mode, set `BLOODWATCH_LIVE_DB` to choose a different SQLite database path. Otherwise the application uses `data/live_readings.sqlite3`.

### Running, dashboard controls, and API

The browser page refreshes its dashboard data every 15 seconds. Its current controls are:

| Control | Effect |
|---|---|
| Data view | Selects live CSV-plus-SQLite data or one of the synthetic scenarios. |
| Refrigerator to inspect | Changes the unit used for the detailed temperature chart and cooling-interruption summary. |
| Temperature history | Selects the recent chart window. The browser offers 6 or 24 hours. |
| Analysis settings | Changes lower/upper temperature status limits and the historical refrigerator failure estimate period. These settings do not modify readings. |

#### HTTP routes

| Method and path | Inputs | Result |
|---|---|---|
| `GET /health` | None | Small service health object. |
| `GET /api/scenarios` | None | Scenario IDs, labels, and descriptions. |
| `GET /api/dashboard` | Query parameters below | Full dashboard JSON. |
| `POST /api/readings` | JSON body below | Validates and stores one live reading; returns HTTP 201 when accepted. |
| `POST /api/readings/upload` | CSV body with `unit_id,timestamp,temp_C` columns | Direct API CSV ingestion; the browser UI does not expose a CSV upload control. |
| `GET /` and static paths | None | Serves the browser interface and its assets. |

**`GET /api/dashboard` query parameters**

| Parameter | Default | Accepted values / effect |
|---|---:|---|
| `refrigerator_id` | First sorted known ID | Must exist in `refrigerator_failures.csv`, for example `R1`. |
| `temperature_window_hours` | 24 | Greater than 0 and at most 168. Selects recent history used in the response. |
| `horizon_operating_days` | 30 | Greater than 0 and at most 365. Sets the future operating-time horizon for refrigerator reliability. |
| `scenario` | omitted (live data) | `stable`, `degrading_refrigerator`, or `blackout_failed_generator`. Scenario mode excludes SQLite live readings. |
| `lower_limit_c` | 1 | From −50 to 50 °C; must be below `upper_limit_c`. |
| `upper_limit_c` | 6 | From −50 to 50 °C; must be above `lower_limit_c`. |

**`POST /api/readings` JSON body**

```json
{
  "refrigerator_id": "R1",
  "timestamp_utc": "2026-10-22T12:00:00Z",
  "temperature_c": 4.2,
  "reading_valid": true,
  "source": "logger-01"
}
```

`refrigerator_id` must be known; `timestamp_utc` must include a timezone and cannot be in the future; `temperature_c` must be finite and between −50 and 50 °C; and incoming readings must be valid. `source` defaults to `sensor`. Duplicate refrigerator/timestamp readings are rejected. Invalid, unknown-unit, future, and duplicate submissions are recorded in the rejected-reading summary where applicable.

The dashboard response is grouped under `dataset`, `selection`, `conditions`, `reliability`, `financial_estimates`, and `warnings`. It includes synthetic/live provenance and the reference timestamp so a reader can interpret the estimates in context.

### Function reference

This is a practical reference to the callable functions and routes. Private helpers are included so a developer can follow how CSV rows become dashboard results.

#### `scripts/project.py` — project commands

| Function | INPUT / PARAMETERS | OUTPUT / behavior |
|---|---|---|
| `run(command, cwd=ROOT, env=None)` | Command as a list of strings; optional working directory and process environment. | Runs a child process, handles Ctrl+C cleanup, and raises `ProjectError` for nonzero exit. |
| `python_supported()` | No arguments. | `True` for Python 3.12–3.15. |
| `doctor()` | No arguments. | Prints interpreter/environment checks; returns readiness as a boolean. |
| `setup()` | No arguments. | Creates `.venv` if needed, installs `app/requirements-dev.txt`, then regenerates the three CSVs. |
| `require_setup()` | No arguments. | Ensures the project virtual environment exists; otherwise raises `ProjectError`. |
| `test()` | No arguments. | Runs `pytest -q` with `app/` on `PYTHONPATH`. |
| `serve()` | No arguments. | Runs Uvicorn at `127.0.0.1:8000`. |
| `generate_data()` | No arguments. | Runs `scripts/generate_scenarios.py` using the project environment. |
| `main()` | CLI action: `doctor`, `setup`, `test`, `run`, or `data`. | Dispatches the action and returns a process exit code. |

`ProjectError` is the helper's user-facing error type. Run the script as `python scripts/project.py ACTION`.

#### `scripts/generate_scenarios.py` — synthetic baseline generation

| Function | INPUT / PARAMETERS | OUTPUT / behavior |
|---|---|---|
| `iso(value)` | A datetime or `None`. | ISO-8601 UTC text ending in `Z`, or an empty string. |
| `write_csv(name, rows)` | Output filename and nonempty list of row dictionaries. | Writes a header and rows under `data/`; raises for an empty row list. |
| `refrigerator_rows()` | Uses module constants and fixed sample facts. | Operating periods, mechanical events, baseline markers, and inventory snapshots. |
| `generator_rows()` | Uses module constants and fixed sample events. | Blackout-demand rows with success, failure, and unknown outcomes. |
| `normal_temperature(rng, refrigerator_id, timestamp)` | Seeded random generator, refrigerator ID, timestamp. | Synthetic normal-operation temperature in °C. |
| `temperature_rows()` | Uses a fixed seed, configured date ranges, and planted events. | Sorted timestamped readings, including baseline, routine, and event readings. |
| `main()` | No arguments. | Writes the three CSV files and prints their output directory. |

The constants `REFERENCE`, `BASELINE_START`, `BASELINE_END`, and `REFRIGERATORS` control the sample time window and equipment list.

#### `scripts/stream_temperature.py` — simulated live readings

| Function | INPUT / PARAMETERS | OUTPUT / behavior |
|---|---|---|
| `send_reading(api_url, refrigerator_id, temperature_c)` | API base URL, known unit ID, temperature value. | Posts one timestamped reading with `source="simulator"`; prints the result or lets network errors reach the caller. |
| `main()` | CLI options: `--api-url` (default localhost API), `--interval` seconds (default 15), `--refrigerators` comma-separated IDs (default `R1,R2,R3`), `--once`. | Produces a smooth, noisy synthetic temperature near 4 °C for each unit per cycle. `--once` exits after one cycle. |

#### `app/api.py` — HTTP interface

| Function / model | INPUT / PARAMETERS | OUTPUT / behavior |
|---|---|---|
| `track_invalid_request(request, error)` | FastAPI request and validation error. | Logs rejected reading payload errors for reading routes; returns HTTP 422 details. |
| `health()` | No arguments. | `{"status":"ok","service":"bloodwatch-api"}`. |
| `dashboard(refrigerator_id, temperature_window_hours, horizon_operating_days, scenario, lower_limit_c, upper_limit_c)` | Query fields documented above. | Calls `build_dashboard`; maps data/value errors to HTTP 400. |
| `scenarios()` | No arguments. | Returns available scenario metadata. |
| `TemperatureReading` | Fields `refrigerator_id`, `timestamp_utc`, `temperature_c`, `reading_valid=True`, `source="sensor"`. | Pydantic model rejects extra fields, timezone-naive timestamps, invalid values, blank IDs/sources, and invalid incoming readings. |
| `TemperatureReading.validate_reading()` | Model's values. | Enforces timestamp, finite/range, validity, and nonblank-field rules. |
| `ingest_reading(reading)` | A validated `TemperatureReading`. | Rejects future/unknown/duplicate records; stores accepted readings in SQLite and returns accepted status. |
| `upload_readings(request)` | Raw CSV request body with `unit_id`, `timestamp`, `temp_C` header fields. | Parses and submits each row through the reading validation path; returns accepted row count or an HTTP 400 identifying the failing row. |

#### `app/bloodwatch/` — analysis functions

**Temperature (`temperature.py`)**

| Function | INPUT / PARAMETERS | OUTPUT / behavior |
|---|---|---|
| `summarize_temperature(rows, reference_time, lower_limit_c=1.0, upper_limit_c=6.0, stale_after_minutes=30.0)` | Reading dictionaries, reference datetime, limits, and freshness cutoff. | Latest reading, count, mean/range/sample deviation, freshness, state, and warnings. Invalid/missing readings are excluded from statistics. |
| `forecast_temperature_limit_crossing(rows, reference_time, lower_limit_c=1.0, upper_limit_c=6.0, forecast_minutes=60.0, stale_after_minutes=30.0, minimum_readings=4, minimum_span_minutes=30.0)` | Recent reading dictionaries, as-of datetime, limits, forecast horizon, freshness and minimum-data thresholds. | Status, linear-fit slope, projected temperature, estimated minutes to a limit, and warnings. Returns unknown/insufficient status when data is stale or inadequate. |
| `analyze_temperature_process(displayed_rows, baseline_rows, overall_rows, lower_limit_c=1.0, upper_limit_c=6.0)` | Recent displayed readings, documented normal-baseline rows, complete operational rows, and specification limits. | Process-control/capability metrics and signals. Baseline moving ranges set the control limits; full operational data is used for overall capability measures. This result remains part of the API response though the advanced UI panel was removed. |

**Cooling incidents (`incidents.py`)**

`summarize_breach_and_recovery(incidents, temperatures, lower_limit_c=1.0, upper_limit_c=6.0)` matches valid, event-linked readings to each incident. It returns per-event first crossing, recovery duration, status (`breached`, `unbreached_censored`, `unknown`), aggregate counts/timing, and warnings. A recovery before any crossing is treated as a censored observation, not proof of unlimited safe storage.

**Reliability (`reliability.py`)**

| Function | INPUT / PARAMETERS | OUTPUT / behavior |
|---|---|---|
| `refrigerator_reliability(mechanical_failures, exposure_hours, horizon_hours, confidence_level=0.95)` | Nonnegative failure count, operating-hour exposure, horizon, confidence level. | Constant-rate failure rate, reliability/failure probability, rate and probability intervals, MTBF where estimable, and CDF points. Assumes independent failures and comparable pooled equipment. |
| `generator_reliability(failed_demands, successful_demands, unknown_demands=0, confidence_level=0.95, future_demands=5)` | Counts of failed, successful, and unknown blackout start outcomes; confidence level; number of future demands for the cumulative curve. | Failed-start proportion, Wilson confidence interval, cumulative probability over future demands, status, assumptions, and warnings. Unknown outcomes are excluded from the known denominator. |

**Financial estimates (`financial.py`)**

| Function | INPUT / PARAMETERS | OUTPUT / behavior |
|---|---|---|
| `expected_inventory_loss(failure_probability, inventory_value_usd)` | Probability from 0 to 1 and nonnegative inventory value. | Probability multiplied by inventory value, or `None` if an input is unknown. |
| `expected_annual_blackout_loss(blackouts_per_year, failed_start_probability, loss_probability_given_failed_start, mean_loss_given_loss_usd)` | Annual demand rate and three conditional probability/value factors. | Product of the supplied factors, or `None` when any factor is unknown. |
| `summarize_financials(equipment, incidents, blackouts, inventory, affected_refrigerators, mechanical_rate_per_hour, annual_operating_hours=8760)` | Equipment, incident, demand, inventory row lists; affected-unit set; mechanical rate; annual-hours assumption. | Historical loss, exposed inventory, estimated annual losses by pathway, factors, and warnings. This broader summary is not currently wired into `build_dashboard()`. |

**Data access (`repository.py`, `live_data.py`)**

| Function | INPUT / PARAMETERS | OUTPUT / behavior |
|---|---|---|
| `load_data(include_live_readings=True)` | Whether to merge valid SQLite readings. | Reads and validates CSVs, preserves baseline temperature rows, merges live rows when enabled, and calculates the reference timestamp. |
| `known_refrigerator_ids()` | No arguments. | Set of IDs available to live ingestion. |
| `_read_csv(name)` | Basename under `data/`. | Reads dictionaries or raises `DatasetError` when the file is missing. |
| `_coerce(data)` / `_validate(data)` | Raw dataset dictionary / converted dataset dictionary. | Converts timestamp, number, and boolean fields; enforces relational, temporal, and value constraints. |
| `_optional_time(value)`, `_optional_int(value)`, `_optional_float(value)` | CSV cell text. | Convert a populated cell to a UTC datetime, integer, or float; return `None` for a blank cell. |
| `_boolean(value, field)` | Cell text and field name. | Accepts only `true` or `false`; otherwise raises `DatasetError`. |
| `_duplicates(values)` | List of IDs. | Returns repeated IDs for validation. |
| `_is_baseline_reading(row, data)` | Converted temperature row and dataset. | Checks whether the reading timestamp falls in that refrigerator's designated normal baseline period. |
| `_database_path()` | Reads `BLOODWATCH_LIVE_DB` if set. | SQLite path; defaults to `data/live_readings.sqlite3`. |
| `record_temperature_reading(refrigerator_id, timestamp, temperature_c, reading_valid, source)` | Validated reading fields. | Inserts into SQLite; returns false for a duplicate unit/timestamp. |
| `record_rejected_reading(reason)` | Rejection reason string. | Stores the rejection and UTC time in SQLite. |
| `rejected_reading_summary()` | No arguments. | Count and grouped reason list for rejected readings. |
| `load_temperature_readings()` | No arguments. | SQLite readings as normalized dictionaries, ordered by time. |

**Scenarios and dashboard service (`scenarios.py`, `service.py`)**

| Function | INPUT / PARAMETERS | OUTPUT / behavior |
|---|---|---|
| `scenario_options()` | No arguments. | List of scenario IDs, labels, and descriptions. |
| `load_scenario_data(source, scenario)` | Loaded source data and one valid scenario ID. | Copy with stable or planted event data; raises `ValueError` for an unknown scenario. |
| `_temperature(timestamp, refrigerator_id, temperature_c, event_id=None)` | Timestamp, unit ID, temperature, optional related event ID. | Creates one normalized synthetic reading dictionary. |
| `_stable_data(source)` | Baseline data dictionary. | Rebuilds steady temperature histories and clears failure events in a copy. |
| `_event_data(source, scenario)` | Baseline data and event-scenario ID. | Adds generated event readings and failure/demand records to a copy. |
| `build_dashboard(refrigerator_id=None, temperature_window_hours=24, horizon_operating_days=30, lower_limit_c=1, upper_limit_c=6, scenario=None)` | Optional unit, recent window, reliability horizon, temperature limits, and scenario. | Produces the complete dashboard response dictionary. Rejects invalid windows, unknown units, or scenarios. |
| `_equipment(periods)` / `_incidents(data, equipment)` | Converted period rows / data plus equipment summaries. | Builds per-unit snapshots and derived cooling-incident rows used by service calculations. |

**Common helpers (`common.py`)**

| Function | INPUT | OUTPUT |
|---|---|---|
| `parse_utc(value)` | ISO timestamp string with timezone. | A timezone-aware UTC datetime; rejects naive timestamps. |
| `warning(code, message, level="warning")` | Stable code, human-readable message, optional level. | JSON-ready warning dictionary. |
| `finite_or_none(value)` | Float or `None`. | Finite float or `None` for NaN/infinity. |
| `require_nonnegative(value, name)` | Number and field name. | Returns normally or raises `ValueError` for a negative number. |

#### Statistical API (`app/qc.py`)

`app/qc.py` re-exports `expected_annual_blackout_loss`, `analyze_temperature_process`, `generator_reliability`, `refrigerator_reliability`, `summarize_breach_and_recovery`, `summarize_financials`, and `summarize_temperature`. Import these names from `qc` when `app/` is on `PYTHONPATH`, or from their focused `bloodwatch` modules in application code.

#### Tests and extending the project

The test suite checks route responses and validation, dataset joins and scenario generation, incident timing, and statistical calculations against known-answer examples. Add new dataset fields with coordinated updates to the CSV generator, repository coercion/validation, codebook, and tests. If an API field or dashboard control changes, update its route/service behavior and this documentation together.

### Metric definitions

| Metric | Meaning |
|---|---|
| Refrigerator failure rate `λ` | Mechanical failures divided by mechanical operating hours. |
| Reliability `R(t)` | `exp(−λt)`, estimated probability of no modeled failure in operating time `t`. |
| Failure probability `F(t)` | `1 − R(t)`. |
| MTBF | `1 ÷ λ`; not estimable when no failures are observed. |
| Generator failed-start probability | Failed starts divided by demands with known outcomes; 95% Wilson interval shown. |
| Cooling-loss-to-crossing time | Time from recorded cooling loss to the first valid temperature strictly outside configured limits. |
| Inventory exposure estimate | Estimated refrigerator failure probability multiplied by estimated current inventory value. Not historical loss or audited cost. |

### Further reading

- [NIST constant-rate repairable-system estimation](https://www.itl.nist.gov/div898/handbook/apr/section4/apr451.htm)
- [NIST exponential reliability and CDF](https://www.itl.nist.gov/div898/handbook/apr/section1/apr161.htm)
- [NIST proportion confidence intervals](https://www.itl.nist.gov/div898/handbook/prc/section2/prc241.htm)
- [21 CFR 640.11 — red blood cell storage](https://www.ecfr.gov/current/title-21/chapter-I/subchapter-F/part-640/subpart-B/section-640.11)
