const root = document.querySelector("#root");
const money = new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", maximumFractionDigits: 0 });
const number = new Intl.NumberFormat("en-US", { maximumFractionDigits: 3 });

const state = {
  scenarios: [],
  scenario: "normal",
  refrigeratorId: "",
  horizonDays: 30,
  tab: "conditions",
  data: null,
  error: "",
};

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function formatMoney(value) {
  return value === null || value === undefined ? "Unavailable" : money.format(value);
}

function formatPercent(value) {
  return value === null || value === undefined ? "Unavailable" : `${(value * 100).toFixed(1)}%`;
}

function formatNumber(value, suffix = "") {
  return value === null || value === undefined ? "Unavailable" : `${number.format(value)}${suffix}`;
}

function stateBadge(value) {
  const safeValue = escapeHtml(value);
  return `<span class="state state--${safeValue}">${safeValue.replaceAll("_", " ")}</span>`;
}

function metricCard(label, value, note) {
  return `<article class="metric-card"><span>${label}</span><strong>${value}</strong><small>${note}</small></article>`;
}

async function getJson(url, fallbackMessage) {
  const response = await fetch(url);
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new Error(body.detail || fallbackMessage);
  }
  return response.json();
}

function temperatureChart(series, lower = 1, upper = 6) {
  const valid = series.filter((row) => row.reading_valid && row.temperature_c !== null);
  if (!valid.length) return '<p class="empty">No valid readings in this window.</p>';

  const width = 820;
  const height = 260;
  const inset = 34;
  const y = (value) => height - inset - ((value - 0) / 8) * (height - inset * 2);
  const x = (index) => inset + (index / Math.max(valid.length - 1, 1)) * (width - inset * 2);
  const points = valid.map((row, index) => `${x(index)},${y(row.temperature_c)}`).join(" ");
  const grid = [0, 2, 4, 6, 8].map((tick) => `
    <g><line x1="${inset}" x2="${width - inset}" y1="${y(tick)}" y2="${y(tick)}" class="grid" />
    <text x="2" y="${y(tick) + 4}">${tick} °C</text></g>`).join("");
  const circles = valid.map((row, index) => {
    const breached = row.temperature_c < lower || row.temperature_c > upper;
    return `<circle cx="${x(index)}" cy="${y(row.temperature_c)}" r="3.5" class="point${breached ? " breach" : ""}" />`;
  }).join("");

  return `<div class="chart-wrap">
    <svg viewBox="0 0 ${width} ${height}" role="img" aria-label="Refrigerator temperature with configured storage limits">
      <rect x="${inset}" y="${y(upper)}" width="${width - 2 * inset}" height="${y(lower) - y(upper)}" class="limit-band" />
      ${grid}<polyline points="${points}" class="temperature-line" />${circles}
    </svg>
    <p class="chart-note">Shaded area: configured 1–6 °C demonstration range. Equality is in range.</p>
  </div>`;
}

function conditions(data) {
  const summary = data.conditions.temperature_summary;
  const equipment = data.conditions.equipment.map((row) => `<tr>
    <td><strong>${escapeHtml(row.equipment_id)}</strong><br><small>${escapeHtml(row.site_id)} · ${escapeHtml(row.generator_id)}</small></td>
    <td>${stateBadge(row.status)}</td><td>${formatNumber(row.latest_temperature_c, " °C")}</td>
    <td>${escapeHtml(row.incident_status.replaceAll("_", " "))}</td><td>${escapeHtml(row.alert_reasons.join("; "))}</td>
  </tr>`).join("");
  return `<section class="metric-grid">
      ${metricCard("Latest temperature", formatNumber(summary.latest_temperature_c, " °C"), escapeHtml(summary.latest_timestamp_utc || "No valid reading"))}
      ${metricCard("Current condition", stateBadge(summary.state), `Freshness: ${formatNumber(summary.freshness_minutes, " min")}`)}
      ${metricCard("Inventory exposed", formatMoney(data.conditions.inventory_exposed_usd), "Current affected unique lots")}
      ${metricCard("Window readings", summary.valid_count, `${summary.missing_or_invalid_count} missing or invalid`)}
    </section>
    <section class="panel"><div class="panel-heading"><div><p class="eyebrow">Selected refrigerator</p><h2>${escapeHtml(data.selection.refrigerator_id)} temperature</h2></div>${stateBadge(summary.state)}</div>
      ${temperatureChart(data.conditions.temperature_series, summary.lower_limit_c, summary.upper_limit_c)}
      <p class="explanation">A breach means review is required. It does not automatically mean that blood is spoiled or should be written off.</p>
    </section>
    <section class="panel"><div class="panel-heading"><div><p class="eyebrow">Current conditions</p><h2>Equipment</h2></div></div>
      <div class="table-wrap"><table><thead><tr><th>Equipment</th><th>Status</th><th>Latest</th><th>Incident</th><th>Reason</th></tr></thead><tbody>${equipment}</tbody></table></div>
    </section>`;
}

function reliability(data) {
  const refrigerator = data.reliability.refrigerators[0];
  const generator = data.reliability.generators[0];
  const breach = data.reliability.breach_recovery;
  return `<section class="metric-grid">
      ${metricCard("Mechanical failure rate", formatNumber(refrigerator.rate_per_hour, " / hour"), `${refrigerator.failures} failures / ${number.format(refrigerator.exposure_hours)} operating hours`)}
      ${metricCard("MTBF", formatNumber(refrigerator.mtbf_hours, " hours"), "Not a countdown to the next failure")}
      ${metricCard(`${data.selection.horizon_operating_days}-day operating risk`, formatPercent(refrigerator.failure_probability), `${number.format(refrigerator.horizon_hours)} future operating hours`)}
      ${metricCard("Generator failed-start risk", formatPercent(generator.failed_start_probability), `${generator.failed_demands} failed / ${generator.known_demands} known demands`)}
    </section>
    <section class="two-column">
      <article class="panel"><p class="eyebrow">Refrigerators · ${escapeHtml(refrigerator.model_group)}</p><h2>Constant-rate occurrence model</h2><dl>
        <div><dt>95% rate interval</dt><dd>${formatNumber(refrigerator.rate_interval_95.lower)}–${formatNumber(refrigerator.rate_interval_95.upper)} / hour</dd></div>
        <div><dt>Reliability over horizon</dt><dd>${formatPercent(refrigerator.reliability)}</dd></div><div><dt>Equipment in pool</dt><dd>${refrigerator.equipment_count}</dd></div>
      </dl><p class="explanation">Assumes a constant occurrence rate and independent mechanical failures. Blackout interruptions are excluded from operating exposure.</p></article>
      <article class="panel"><p class="eyebrow">Generator · ${escapeHtml(generator.generator_id)}</p><h2>Failure to start on demand</h2><dl>
        <div><dt>Wilson 95% interval</dt><dd>${formatPercent(generator.wilson_interval_95.lower)}–${formatPercent(generator.wilson_interval_95.upper)}</dd></div>
        <div><dt>Successful demands</dt><dd>${generator.successful_demands}</dd></div><div><dt>Unknown outcomes</dt><dd>${generator.unknown_demands}</dd></div>
      </dl><p class="explanation">The denominator is blackout demands, not refrigerator operating hours or temperature rows.</p></article>
    </section>
    <section class="panel"><p class="eyebrow">Cooling incidents</p><h2>Breach and recovery</h2><div class="metric-grid metric-grid--inside">
      ${metricCard("Breached incidents", breach.breached_count, "First observed reading strictly outside limits")}
      ${metricCard("Unbreached / censored", breach.unbreached_censored_count, "Recovery or observation ended first")}
      ${metricCard("Mean observed breach time", formatNumber(breach.mean_observed_hours_to_breach_breached_only, " hours"), "Breached incidents only")}
      ${metricCard("Median recovery time", formatNumber(breach.median_recovery_hours, " hours"), `${breach.unresolved_incident_count} unresolved incidents`)}
    </div></section>`;
}

function lossBars(rows) {
  if (!rows.length) return '<p class="empty">No recorded simulated write-offs.</p>';
  const maximum = Math.max(...rows.map((row) => row.loss_usd), 1);
  return `<div class="loss-bars">${rows.map((row) => `<div class="loss-row"><span>${escapeHtml(row.cause)}</span><div><i style="width:${(row.loss_usd / maximum) * 100}%"></i></div><strong>${formatMoney(row.loss_usd)}</strong></div>`).join("")}</div>`;
}

function financial(data) {
  const value = data.financial;
  return `<section class="metric-grid">
      ${metricCard("Actual historical loss", formatMoney(value.actual_historical_loss_usd), "Recorded synthetic write-offs")}
      ${metricCard("Inventory exposed now", formatMoney(value.inventory_exposed_usd), "Not a predicted write-off")}
      ${metricCard("Expected annual mechanical loss", formatMoney(value.expected_annual_mechanical_loss_usd), `${number.format(value.annual_operating_hours_assumption)} assumed operating hours/year`)}
      ${metricCard("Expected annual blackout loss", formatMoney(value.expected_annual_blackout_loss_usd), "Estimated from demand and outcome histories")}
    </section><section class="two-column">
      <article class="panel"><p class="eyebrow">Recorded outcomes</p><h2>Loss by cause</h2>${lossBars(value.loss_by_cause)}</article>
      <article class="panel"><p class="eyebrow">Blackout estimate factors</p><h2>What creates the annual estimate</h2><dl>
        <div><dt>Blackouts / site-year</dt><dd>${formatNumber(value.blackouts_per_year)}</dd></div>
        <div><dt>P(failed start | blackout)</dt><dd>${formatPercent(value.blackout_factors.failed_start_probability)}</dd></div>
        <div><dt>P(loss | failed start)</dt><dd>${formatPercent(value.blackout_factors.loss_probability_given_failed_start)}</dd></div>
        <div><dt>Mean loss | positive loss</dt><dd>${formatMoney(value.blackout_factors.mean_loss_given_loss_usd)}</dd></div>
      </dl></article></section>
    <p class="explanation">Expected values are planning estimates. Unknown outcomes are excluded and reported as warnings; they are not treated as zero.</p>`;
}

function render() {
  const data = state.data;
  const scenarioOptions = state.scenarios.map((row) => `<option value="${escapeHtml(row.id)}"${row.id === state.scenario ? " selected" : ""}>${escapeHtml(row.name)}</option>`).join("");
  const refrigerators = data?.selection.available_refrigerators || [];
  const selectedRefrigerator = state.refrigeratorId || data?.selection.refrigerator_id || "";
  const refrigeratorOptions = refrigerators.map((id) => `<option value="${escapeHtml(id)}"${id === selectedRefrigerator ? " selected" : ""}>${escapeHtml(id)}</option>`).join("");
  const error = state.error ? `<section class="error">${stateBadge("unknown")}<div><strong>Dashboard unavailable</strong><p>${escapeHtml(state.error)}</p></div></section>` : "";
  const loading = !state.error && !data ? '<p class="loading">Loading dashboard…</p>' : "";
  let dashboard = "";
  if (data && !state.error) {
    const content = state.tab === "conditions" ? conditions(data) : state.tab === "reliability" ? reliability(data) : financial(data);
    const warnings = data.warnings.length ? `<details class="warnings"><summary>Analysis warnings (${data.warnings.length})</summary><ul>${data.warnings.map((item) => `<li><strong>${escapeHtml(item.code)}</strong>: ${escapeHtml(item.message)}</li>`).join("")}</ul></details>` : "";
    dashboard = `<section class="scenario-banner"><div><strong>${escapeHtml(data.scenario.name)}</strong><p>${escapeHtml(data.scenario.description)}</p></div><small>Reference time: ${escapeHtml(data.scenario.reference_time_utc)}</small></section>
      <nav class="tabs" aria-label="Dashboard sections">${[["conditions", "Conditions"], ["reliability", "Reliability"], ["financial", "Financial impact"]].map(([id, label]) => `<button data-tab="${id}" class="${state.tab === id ? "active" : ""}">${label}</button>`).join("")}</nav>
      ${content}${warnings}`;
  }

  root.innerHTML = `<main><header class="masthead"><div><p class="eyebrow">Regional blood-bank operations</p><h1>BloodWatch</h1><p>Supply conditions, equipment reliability, and recorded synthetic losses.</p></div><span class="synthetic">SYNTHETIC DATA</span></header>
    <section class="controls" aria-label="Dashboard controls">
      <label>Scenario<select id="scenario">${scenarioOptions}</select></label>
      <label>Refrigerator<select id="refrigerator">${refrigeratorOptions}</select></label>
      <label>Operating horizon<select id="horizon">${[7, 30, 90].map((days) => `<option value="${days}"${days === state.horizonDays ? " selected" : ""}>${days} days</option>`).join("")}</select></label>
    </section>${error}${loading}${dashboard}
    <footer>Prototype decision support only. A temperature breach requires review and does not automatically establish biological viability, spoilage, or financial write-off.</footer></main>`;

  document.querySelector("#scenario").addEventListener("change", (event) => {
    state.scenario = event.target.value;
    state.refrigeratorId = "";
    loadDashboard();
  });
  document.querySelector("#refrigerator").addEventListener("change", (event) => {
    state.refrigeratorId = event.target.value;
    loadDashboard();
  });
  document.querySelector("#horizon").addEventListener("change", (event) => {
    state.horizonDays = Number(event.target.value);
    loadDashboard();
  });
  document.querySelectorAll("[data-tab]").forEach((button) => button.addEventListener("click", () => {
    state.tab = button.dataset.tab;
    render();
  }));
}

async function loadDashboard() {
  state.error = "";
  render();
  const parameters = new URLSearchParams({
    scenario: state.scenario,
    horizon_operating_days: String(state.horizonDays),
    temperature_window_hours: "24",
  });
  if (state.refrigeratorId) parameters.set("refrigerator_id", state.refrigeratorId);
  try {
    state.data = await getJson(`/api/dashboard?${parameters}`, "Could not load dashboard data");
  } catch (error) {
    state.error = error.message;
  }
  render();
}

async function start() {
  try {
    const result = await getJson("/api/scenarios", "Could not load scenarios");
    state.scenarios = result.scenarios;
  } catch (error) {
    state.error = error.message;
  }
  await loadDashboard();
}

start();
