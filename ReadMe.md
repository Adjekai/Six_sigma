# BloodWatch

BloodWatch is a small React + FastAPI prototype for regional blood-bank supervisors. It separates current storage-condition evidence, equipment reliability estimates, and recorded synthetic financial outcomes so that every displayed number can be explained.

Team members: Audrey Sakcey, Isabelle Seidenberg, Jasmine Tamous, Ameera El'Amin-White, Jonathan EngleA

> All included data are synthetic. This prototype does not determine biological viability, clinical suitability, or whether blood must be discarded.

## What the first pass includes

The dashboard has three sections:

- **Conditions:** latest temperature, freshness, 24-hour chart, configured 1–6 °C demonstration limits, equipment status, and currently exposed inventory.
- **Reliability:** constant-rate mechanical failure estimates, MTBF, future operating-hour failure probability, failed generator starts per known blackout demand, Wilson interval, observed breach times, and recovery summaries.
- **Financial impact:** recorded simulated write-offs, currently exposed value, expected annual loss by mechanical and blackout pathways, and loss by cause.

Three reproducible scenarios demonstrate normal operation, a mechanical refrigerator breakdown, and a blackout with a failed backup start.

## Architecture

```text
data/scenarios/             generated related CSVs
scripts/generate_scenarios.py
                            reproducible data generator
app/bloodwatch/             plain Python analysis modules
app/qc.py                   public statistical interface
app/api.py                  FastAPI routes
app/frontend/               React/Vite dashboard
tests/                      statistical, scenario, and API checks
docs/interfaces.md          shared schema and JSON contract
```

The frontend does not calculate reliability or financial metrics. It only requests, formats, and plots API results.

## Local setup

Requirements:

- Python 3.11 or newer
- Node.js and npm
- `make`

Install the pinned dependencies:

```sh
make setup
```

## Run

After installation, one command builds the dashboard and starts FastAPI:

```sh
make run
```

Open <http://127.0.0.1:8000>. API documentation is available at <http://127.0.0.1:8000/docs>.

## Verify

```sh
make test
```

Regenerate the same synthetic datasets with:

```sh
make data
```

## Important definitions

- **Mechanical failure rate:** observed mechanical failures divided by mechanical operating hours. Blackout interruption is excluded from that exposure.
- **MTBF:** reciprocal of the estimated constant failure-occurrence rate. It is not a countdown.
- **Generator failed-start probability:** failed automatic starts divided by blackout demands with known outcomes. Temperature rows and affected refrigerators are not demands.
- **Time to storage-limit breach:** elapsed time from loss of effective cooling until the first recorded temperature strictly outside the configured range. It is limited by the logging interval.
- **Actual loss:** recorded synthetic write-offs only. A temperature breach alone does not create a loss.
- **Inventory exposed:** unique current inventory associated with a cooling interruption, breach, or unknown condition. It is not expected loss.

## Documentation

- [Shared interfaces](docs/interfaces.md)
- [Synthetic-data codebook](data/README.md)
- [Team branch handoff](docs/team-plan.md)
- [Demo walkthrough](demo/README.md)
- [Earlier project plan and scope-update notice](docs/BLOOD_BANK_PROJECT_PLAN.md)

## Sources

- [NIST constant-rate repairable-system estimation](https://www.itl.nist.gov/div898/handbook/apr/section4/apr451.htm)
- [NIST exponential reliability and CDF](https://www.itl.nist.gov/div898/handbook/apr/section1/apr161.htm)
- [NIST proportion confidence intervals](https://www.itl.nist.gov/div898/handbook/prc/section2/prc241.htm)
- [21 CFR 640.11 — red blood cell storage](https://www.ecfr.gov/current/title-21/chapter-I/subchapter-F/part-640/subpart-B/section-640.11)
