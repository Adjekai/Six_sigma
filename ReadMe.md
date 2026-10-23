# BloodWatch

BloodWatch is a Python and FastAPI dashboard for blood-storage data.

Team members: Audrey Sakcey, Isabelle Seidenberg, Jasmine Tamous, Ameera El'Amin-White, Jonathan Engle

## Run the dashboard

Python 3.12–3.15 is required.

| Action | macOS | Windows PowerShell |
|---|---|---|
| Install | `python3 scripts/project.py setup` | `py scripts\project.py setup` |
| Run | `python3 scripts/project.py run` | `py scripts\project.py run` |
| Test | `python3 scripts/project.py test` | `py scripts\project.py test` |
| Regenerate data | `python3 scripts/project.py data` | `py scripts\project.py data` |

Open <http://127.0.0.1:8000>. Press `Ctrl+C` in the same terminal to stop the server.

## Live temperature feed

Start the dashboard, then run the bundled simulator in another terminal:

```sh
python scripts/stream_temperature.py --interval 15
```

It sends one simulated reading per refrigerator every 15 seconds. The dashboard reloads automatically every 15 seconds. Simulator values are synthetic; they are not sensor measurements.

Real sensor software can send readings to `POST /api/readings` as JSON:

```json
{
	"refrigerator_id": "R1",
	"timestamp_utc": "2026-10-22T12:00:00Z",
	"temperature_c": 4.2,
	"reading_valid": true,
	"source": "logger-01"
}
```

The refrigerator ID must already exist in the equipment dataset. Timestamps must include a timezone; invalid readings should use `"temperature_c": null` and `"reading_valid": false`. Readings are saved in `data/live_readings.sqlite3` and merged with the sample history. Set `BLOODWATCH_LIVE_DB` to use a different SQLite file. The API currently binds to localhost and has no sensor authentication; do not expose it to a network until authentication and transport security are configured.

## Dataset modes

BloodWatch uses three related CSV datasets as its equipment and history baseline:

- `data/blood_temperature.csv` contains temperature readings.
- `data/refrigerator_failures.csv` contains refrigerator identity, operating exposure, inventory, and mechanical events.
- `data/generator_failures.csv` contains blackout demands and generator start outcomes.

The dashboard opens in **Live data** mode. It uses the three CSV datasets and overlays readings received at `POST /api/readings` from the SQLite live feed. The bundled `scripts/stream_temperature.py` producer is simulated; use a real logger adapter to send actual readings.

The Data mode selector also offers three reproducible synthetic scenarios: Stable conditions, Degrading refrigerator, and Blackout with failed generator. These scenarios are generated from the same three CSV datasets and are clearly labeled synthetic. They do not use or overwrite live SQLite readings. Return to **Live data** to see the sensor feed.

## Baseline datasets

The dashboard reads these three CSV files from `data/`. They provide sample history and equipment context; Live mode can add incoming sensor readings without changing the CSVs.

| File | What it contains |
|---|---|
| `blood_temperature.csv` | Timestamped temperature readings for each refrigerator, plus validity and related-event fields |
| `refrigerator_failures.csv` | Refrigerator operating periods, mechanical failures, baseline periods, and current inventory snapshots |
| `generator_failures.csv` | Blackout demands and backup-generator start outcomes |

All timestamps are UTC. Blank fields mean unknown or not applicable; zero is an observed zero. IDs connect records across files. One generator start is one demand even when its failure affects several refrigerators. The 1–6 °C range is the default storage specification used by the demo, not a biological spoilage threshold.

The scenario selector creates three reproducible synthetic demonstrations from these same files. It does not require separate scenario folders or replace Live sensor readings.

## 1. Temperature

The dashboard shows the latest temperature, mean, range, sample standard deviation, and selected history for one refrigerator. The file contains the normal baseline, the latest 24-hour history, and a short 15-minute reading sequence through every older cooling interruption.

### `blood_temperature.csv`

Fifteen-minute readings. Real data would come from calibrated temperature loggers and the monitoring-quality system.

| Variable | Meaning |
|---|---|
| `timestamp_utc` | Reading time |
| `refrigerator_id` | Refrigerator measured |
| `temperature_c` | Recorded temperature in °C; blank if missing |
| `reading_valid` | Whether the reading passed validation |

Invalid readings are not replaced with zero. Readings exactly at 1 °C or 6 °C are within range.

## 2. Cooling loss to out-of-range temperature

The dashboard measures from cooling loss to the first valid reading strictly outside 1–6 °C.

Cooling-loss timing comes from failure records in `refrigerator_failures.csv` and `generator_failures.csv`; there is no separate cooling-incidents CSV.

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

The result is an observed storage-limit crossing, not a spoilage time. Cooling restoration and return to the storage range are separate events.

## 3. Failure risk

The dashboard separates refrigerator mechanical failures from backup-generator start failures.

### `refrigerator_failures.csv`

Equipment identity and operating exposure. Real sources would be the asset register, maintenance system, and runtime meter.

| Variable | Meaning |
|---|---|
| `equipment_id` | Refrigerator identifier |
| `site_id` | Site identifier |
| `equipment_type` | Equipment category; currently `refrigerator` |
| `model_group` | Refrigerators pooled into one reliability estimate |
| `generator_id` | Shared backup generator |
| `observation_start_utc` | Exposure-period start |
| `observation_end_utc` | Exposure-period end |
| `mechanical_operating_hours` | Mechanical-failure exposure denominator |

### `generator_failures.csv`

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

These values are calculated from the failure-risk files; they are not additional collected variables.

| Metric | Calculation |
|---|---|
| Failure rate `λ` | Mechanical failures ÷ mechanical operating hours |
| Reliability `R(t)` | `exp(−λt)` |
| Failure probability `F(t)` | `1 − R(t)` |
| Hazard `h(t)` | `λ` under the constant-rate model |
| MTBF | `1 ÷ λ`; unavailable when no failures are observed |
| Generator failed-start rate | Failed starts ÷ blackout demands with known outcomes |
| Generator uncertainty | 95% Wilson interval for the failed-start rate |

Zero observed failures do not prove zero future risk.

## 5. Process analysis

These values are calculated from valid rows in `temperatures.csv`. Pre-incident readings form the baseline when an incident appears in the selected window; otherwise the selected window is the exploratory baseline.

| Metric | Meaning |
|---|---|
| Mean | Average temperature |
| Sample standard deviation | Spread of individual readings |
| Standard error | Sample standard deviation ÷ square root of the reading count |
| Control limits | Individuals-chart limits estimated from moving ranges |
| Control signal | Reading outside the estimated control limits |
| Cp / Cpk | Potential and centered capability using within-process variation |
| Pp / Ppk | Overall performance using variation across the selected window |

Control limits describe observed behavior. The 1–6 °C limits describe the storage requirement.

## Sources

- [NIST constant-rate repairable-system estimation](https://www.itl.nist.gov/div898/handbook/apr/section4/apr451.htm)
- [NIST exponential reliability and CDF](https://www.itl.nist.gov/div898/handbook/apr/section1/apr161.htm)
- [NIST proportion confidence intervals](https://www.itl.nist.gov/div898/handbook/prc/section2/prc241.htm)
- [21 CFR 640.11 — red blood cell storage](https://www.ecfr.gov/current/title-21/chapter-I/subchapter-F/part-640/subpart-B/section-640.11)
