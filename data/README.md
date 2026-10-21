# BloodWatch synthetic-data codebook

All files under `data/scenarios/` are reproducible synthetic demonstrations. They contain no patient, donor, or facility data.

Regenerate them from the repository root with:

```sh
python3 scripts/generate_scenarios.py
```

## Relationships

- `equipment_exposure.equipment_id` → `temperatures.refrigerator_id`, `cooling_incidents.refrigerator_id`, and `inventory_outcomes.refrigerator_id`.
- `equipment_exposure.generator_id` → `blackout_demands.generator_id`.
- `cooling_incidents.incident_id` → `inventory_outcomes.incident_id` for historical outcomes.
- `cooling_incidents.blackout_id` → `blackout_demands.blackout_id`.
- One blackout may affect several refrigerators but remains one row and one generator demand.

## Variables

### Equipment and exposure

| Variable | Unit/type | Meaning | Real-world collection source |
|---|---|---|---|
| `equipment_id` | text | Refrigerator identifier | Asset-management register |
| `site_id` | text | Regional location | Asset-management register |
| `equipment_type` | category | Equipment category | Asset-management register |
| `model_group` | text | Explicitly comparable equipment pool | Manufacturer/model records plus engineering review |
| `generator_id` | text | Backup generator mapped to refrigerator | Electrical one-line/asset register |
| `observation_start_utc` | UTC timestamp | Exposure observation start | Maintenance/reliability system |
| `observation_end_utc` | UTC timestamp | Exposure observation end | Maintenance/reliability system |
| `mechanical_operating_hours` | hours | Effective mechanical operation excluding blackout interruption | Runtime meter or defensible operating log |

Zero-failure refrigerators remain in the exposure denominator.

### Temperatures

| Variable | Unit/type | Meaning | Real-world collection source |
|---|---|---|---|
| `timestamp_utc` | UTC timestamp | Logged reading time | Calibrated temperature logger |
| `refrigerator_id` | text | Refrigerator measured | Logger configuration |
| `temperature_c` | °C or blank | Recorded temperature | Calibrated temperature logger |
| `reading_valid` | boolean | Whether the reading passed validation | Monitoring/quality system |

Missing temperatures are never filled with zero or interpolated silently.

### Cooling incidents

| Variable | Unit/type | Meaning | Real-world collection source |
|---|---|---|---|
| `incident_id` | text | Unique cooling-loss event for one refrigerator | Incident/maintenance log |
| `refrigerator_id` | text | Affected refrigerator | Incident/maintenance log |
| `cause` | category | Mechanical failure, failed-start blackout, or brief blackout interruption | Root-cause review |
| `cooling_loss_utc` | UTC timestamp | Loss of effective cooling | Alarm/power/maintenance log |
| `observation_end_utc` | UTC timestamp | End of evidence used for breach analysis | Analysis record |
| `cooling_restored_utc` | UTC timestamp or blank | Restoration of effective cooling | Maintenance log |
| `blackout_id` | text or blank | Related blackout demand | Power-event log |

Recovery does not imply the temperature had already returned inside limits.

### Blackout demands

| Variable | Unit/type | Meaning | Real-world collection source |
|---|---|---|---|
| `blackout_id` | text | One site/generator demand | Power-event log |
| `site_id` | text | Affected site | Facilities log |
| `generator_id` | text | Generator demanded | Generator controller/event log |
| `start_utc` | UTC timestamp | Blackout start | Utility/transfer-switch log |
| `end_utc` | UTC timestamp | Blackout end | Utility/transfer-switch log |
| `auto_start_outcome` | category | `success`, `failure`, or `unknown` | Generator controller and incident review |

Scheduled tests are not mixed into the blackout-demand denominator.

### Inventory and outcomes

| Variable | Unit/type | Meaning | Real-world collection source |
|---|---|---|---|
| `record_type` | category | Current snapshot or historical incident outcome | Inventory/incident system |
| `as_of_utc` | UTC timestamp | Time represented | Inventory/incident system |
| `incident_id` | text or blank | Related historical incident | Incident system |
| `lot_id` | text | Lot key used for deduplication | Blood inventory system |
| `refrigerator_id` | text | Storage location | Blood inventory system |
| `bags_present` | bags | Bags exposed or stored | Blood inventory system |
| `value_per_bag_usd` | USD/bag or blank | Recorded demonstration value | Finance/inventory system |
| `bags_transferred` | bags or blank | Recorded transfer outcome | Incident review |
| `bags_written_off` | bags or blank | Confirmed simulated write-off | Incident/finance review |

Zero is an observed zero outcome. Blank means unknown.

## Scenario truth and planted events

### `normal`

- Temperatures remain within the configured range.
- Ten blackout demands all have successful automatic starts.
- A short successful-start interruption is restored before a breach.
- One older mechanical incident has a recorded zero loss.

### `refrigerator_breakdown`

- Two comparable refrigerators contribute 20,000 mechanical operating hours.
- Two mechanical failures yield a known rate of `0.0001/hour`.
- R-B1 warms above 6 °C, recovers, and has a simulated $7,500 write-off.
- R-B2 provides a completed zero-loss incident.

### `blackout_failed_backup`

- One current blackout affects three refrigerators but creates one generator demand.
- Historical records contain 2 failed starts in 20 known demands.
- Two refrigerators breach; one remains within limits before recovery.
- Inventory is transferred or explicitly written off.

## Generation assumptions

- Fixed seeds make every scenario reproducible.
- Mechanical event rates are treated as constant within each modeled group.
- Warming profiles are illustrative and are not validated biological or thermal-physics models.
- The permitted red-cell demonstration range is configurable; the initial value is 1–6 °C.
- Failure time of blood means first monitored reading strictly outside the range after cooling loss. It is not shelf life or biological viability.

Generation assumptions and planted truth live in each scenario's `metadata.json`; the analysis does not copy those values as estimates.
