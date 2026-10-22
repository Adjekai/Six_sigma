# BloodWatch: three questions from class

The one-page overview shows synthetic data and asks:

1. Is the temperature within the refrigerated-red-cell storage range (1–6 °C)?
2. How long after cooling loss was the first storage-limit breach observed?
3. How likely is an equipment failure over the selected future operating time, and how often has the generator failed on a blackout demand?

Choose a scenario, refrigerator, and 6- or 24-hour temperature window. The operating-horizon control belongs to the refrigerator probability section. Temperature plots use real UTC timestamps, label the axes/limits, and mark cooling loss when the incident lies in the displayed window. Missing readings break the plotted line.

Temperature statistics include mean, min/max, and sample SD. The spread reflects the full chosen window, including a breakdown if present. It is not a standard error or stable-baseline capability estimate.

The breach-time section uses only incidents for the selected refrigerator. A first crossing in the demo is not a biological spoilage threshold or a safe response deadline. Missing histories and incidents with no observed breach remain visible. Repeated refrigerators within one blackout do not establish independent future breach trials.

The probability section labels refrigerator estimates as pooled model-group results. It shows the refrigerator failure CDF and generator failed starts per known demand, with formulas and uncertainty in expandable explanations. Zero observed failures are not displayed as established zero risk.

Process analysis includes standard error, an individuals control chart, Cp/Cpk, and Pp/Ppk. When an incident starts inside the selected window, pre-incident readings form the baseline; otherwise the selected window is used as an exploratory baseline. Control limits describe observed behavior, while 1–6 °C remains the storage requirement.

Inventory exposure and recorded losses remain expandable and are explicitly scoped to the scenario site. More detailed financial outputs remain in the API.

Run from the repository root after setup:

```sh
python3 scripts/project.py run
```

Open http://127.0.0.1:8000. FastAPI serves the frontend and `/api/dashboard`; all statistical computations remain in Python.
