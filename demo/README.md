# BloodWatch demonstration

## Start

After installing dependencies with `make setup`, run:

```sh
make run
```

Open <http://127.0.0.1:8000>.

## Walkthrough

1. Select **Normal / resilient**. Conditions should be within limits, generator failures should be 0, and recorded historical loss should be $0.
2. Select **Refrigerator breakdown**. The temperature plot contains a planted excursion; reliability shows 2 mechanical failures over 20,000 operating hours, and financial impact shows $7,500 of recorded synthetic loss.
3. Set the operating horizon to 30 days. Confirm that the displayed probability is labeled as future operating time, not equipment age or calendar countdown.
4. Select **Blackout / failed backup**. Reliability should show 2 failed starts over 20 known blackout demands, or 10%. The incident table summarizes three affected refrigerators without counting three generator demands.
5. Open **Financial impact**. Compare actual historical loss, current exposed value, and annual expected values; they have different meanings and periods.
6. Expand **Analysis warnings**. Missing historical temperature windows and incomplete failed-blackout outcomes should remain visible.

## Expected known answers

- Mechanical rate: `2 / 20,000 = 0.0001/hour`.
- MTBF: `1 / 0.0001 = 10,000 hours`.
- `F(1,000 operating hours) = 1 - exp(-0.0001 × 1,000) ≈ 0.0951626`.
- Generator failed-start probability: `2 / 20 = 0.10`.
- Financial hand-check test: `4 × 0.10 × 0.25 × $20,000 = $2,000/year`.

Every scenario and financial outcome is synthetic.
