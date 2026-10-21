# BloodWatch Dashboard

BloodWatch helps a blood-bank supervisor review refrigerator conditions, equipment failures, and synthetic inventory losses.

All displayed data are **synthetic demonstration data**. The dashboard does not decide whether blood is safe or should be discarded.

## Dashboard controls

- **Scenario:** switches between normal operation, a refrigerator breakdown, and a blackout with a failed generator start.
- **Refrigerator:** selects the refrigerator shown in the temperature chart.
- **Operating horizon:** selects how far ahead to estimate refrigerator failure probability.

## Conditions

This section shows what is happening with the equipment and inventory.

- Latest refrigerator temperature and timestamp.
- Whether the reading is within the configured 1–6 °C demonstration range.
- A 24-hour temperature chart.
- Missing or stale readings.
- Active cooling incidents.
- Current inventory value exposed to an interruption or unknown condition.

A temperature outside the limits means **review required**. It does not automatically mean that blood is spoiled.

## Reliability

This section shows estimates based on recorded synthetic event histories.

- Refrigerator mechanical failures and total operating hours.
- Estimated mechanical failure rate.
- Mean time between failures, or MTBF.
- Failure probability over the selected future operating horizon.
- Generator failed starts divided by known blackout demands.
- A 95% confidence interval for generator start-failure probability.
- Observed time to a temperature breach and cooling-recovery time.

MTBF is a long-run average, not a countdown to the next failure.

## Financial Impact

This section separates different kinds of financial information.

- **Actual historical loss:** recorded synthetic write-offs.
- **Inventory exposed:** current inventory affected by an interruption, breach, or unknown condition.
- **Expected annual mechanical loss:** planning estimate based on mechanical failure history.
- **Expected annual blackout loss:** planning estimate based on blackout frequency, failed starts, and recorded losses.
- **Loss by cause:** recorded losses separated into mechanical and blackout pathways.

Inventory exposed is not the same as inventory lost.

## Status labels

- **Within limits:** the latest valid reading is inside the configured range.
- **Review required:** an observed condition requires attention.
- **Unknown:** the available data are missing, stale, or insufficient.
- **Unavailable:** the requested statistic cannot be estimated from the available history.

## Analysis warnings

The warnings section explains limitations such as missing readings, incomplete outcomes, zero observed failures, or insufficient history. Unknown values are not silently replaced with zero.

## Start the dashboard

From the repository root, after setup:

```sh
python3 scripts/project.py run
```

On Windows PowerShell, use `py scripts\project.py run`.

Open <http://127.0.0.1:8000>.
