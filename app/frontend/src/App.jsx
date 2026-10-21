import { useEffect, useState } from "react";
import { getDashboard, getScenarios } from "./api.js";
import MetricCard from "./components/MetricCard.jsx";
import TemperatureChart from "./components/TemperatureChart.jsx";

const money = new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", maximumFractionDigits: 0 });
const number = new Intl.NumberFormat("en-US", { maximumFractionDigits: 3 });

function formatMoney(value) {
  return value === null || value === undefined ? "Unavailable" : money.format(value);
}

function formatPercent(value) {
  return value === null || value === undefined ? "Unavailable" : `${(value * 100).toFixed(1)}%`;
}

function formatNumber(value, suffix = "") {
  return value === null || value === undefined ? "Unavailable" : `${number.format(value)}${suffix}`;
}

function State({ value }) {
  return <span className={`state state--${value}`}>{value.replaceAll("_", " ")}</span>;
}

function Conditions({ data }) {
  const summary = data.conditions.temperature_summary;
  return (
    <>
      <section className="metric-grid">
        <MetricCard label="Latest temperature" value={formatNumber(summary.latest_temperature_c, " °C")} note={summary.latest_timestamp_utc || "No valid reading"} />
        <MetricCard label="Current condition" value={<State value={summary.state} />} note={`Freshness: ${formatNumber(summary.freshness_minutes, " min")}`} />
        <MetricCard label="Inventory exposed" value={formatMoney(data.conditions.inventory_exposed_usd)} note="Current affected unique lots" />
        <MetricCard label="Window readings" value={summary.valid_count} note={`${summary.missing_or_invalid_count} missing or invalid`} />
      </section>

      <section className="panel">
        <div className="panel-heading">
          <div><p className="eyebrow">Selected refrigerator</p><h2>{data.selection.refrigerator_id} temperature</h2></div>
          <State value={summary.state} />
        </div>
        <TemperatureChart series={data.conditions.temperature_series} lower={summary.lower_limit_c} upper={summary.upper_limit_c} />
        <p className="explanation">A breach means review is required. It does not automatically mean that blood is spoiled or should be written off.</p>
      </section>

      <section className="panel">
        <div className="panel-heading"><div><p className="eyebrow">Current conditions</p><h2>Equipment</h2></div></div>
        <div className="table-wrap">
          <table>
            <thead><tr><th>Equipment</th><th>Status</th><th>Latest</th><th>Incident</th><th>Reason</th></tr></thead>
            <tbody>
              {data.conditions.equipment.map((row) => (
                <tr key={row.equipment_id}>
                  <td><strong>{row.equipment_id}</strong><br /><small>{row.site_id} · {row.generator_id}</small></td>
                  <td><State value={row.status} /></td>
                  <td>{formatNumber(row.latest_temperature_c, " °C")}</td>
                  <td>{row.incident_status.replaceAll("_", " ")}</td>
                  <td>{row.alert_reasons.join("; ")}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </>
  );
}

function Reliability({ data }) {
  const refrigerator = data.reliability.refrigerators[0];
  const generator = data.reliability.generators[0];
  const breach = data.reliability.breach_recovery;
  return (
    <>
      <section className="metric-grid">
        <MetricCard label="Mechanical failure rate" value={formatNumber(refrigerator.rate_per_hour, " / hour")} note={`${refrigerator.failures} failures / ${number.format(refrigerator.exposure_hours)} operating hours`} />
        <MetricCard label="MTBF" value={formatNumber(refrigerator.mtbf_hours, " hours")} note="Not a countdown to the next failure" />
        <MetricCard label={`${data.selection.horizon_operating_days}-day operating risk`} value={formatPercent(refrigerator.failure_probability)} note={`${number.format(refrigerator.horizon_hours)} future operating hours`} />
        <MetricCard label="Generator failed-start risk" value={formatPercent(generator.failed_start_probability)} note={`${generator.failed_demands} failed / ${generator.known_demands} known demands`} />
      </section>

      <section className="two-column">
        <article className="panel">
          <p className="eyebrow">Refrigerators · {refrigerator.model_group}</p>
          <h2>Constant-rate occurrence model</h2>
          <dl>
            <div><dt>95% rate interval</dt><dd>{formatNumber(refrigerator.rate_interval_95.lower)}–{formatNumber(refrigerator.rate_interval_95.upper)} / hour</dd></div>
            <div><dt>Reliability over horizon</dt><dd>{formatPercent(refrigerator.reliability)}</dd></div>
            <div><dt>Equipment in pool</dt><dd>{refrigerator.equipment_count}</dd></div>
          </dl>
          <p className="explanation">Assumes a constant occurrence rate and independent mechanical failures. Blackout interruptions are excluded from operating exposure.</p>
        </article>
        <article className="panel">
          <p className="eyebrow">Generator · {generator.generator_id}</p>
          <h2>Failure to start on demand</h2>
          <dl>
            <div><dt>Wilson 95% interval</dt><dd>{formatPercent(generator.wilson_interval_95.lower)}–{formatPercent(generator.wilson_interval_95.upper)}</dd></div>
            <div><dt>Successful demands</dt><dd>{generator.successful_demands}</dd></div>
            <div><dt>Unknown outcomes</dt><dd>{generator.unknown_demands}</dd></div>
          </dl>
          <p className="explanation">The denominator is blackout demands, not refrigerator operating hours or temperature rows.</p>
        </article>
      </section>

      <section className="panel">
        <p className="eyebrow">Cooling incidents</p>
        <h2>Breach and recovery</h2>
        <div className="metric-grid metric-grid--inside">
          <MetricCard label="Breached incidents" value={breach.breached_count} note="First observed reading strictly outside limits" />
          <MetricCard label="Unbreached / censored" value={breach.unbreached_censored_count} note="Recovery or observation ended first" />
          <MetricCard label="Mean observed breach time" value={formatNumber(breach.mean_observed_hours_to_breach_breached_only, " hours")} note="Breached incidents only" />
          <MetricCard label="Median recovery time" value={formatNumber(breach.median_recovery_hours, " hours")} note={`${breach.unresolved_incident_count} unresolved incidents`} />
        </div>
      </section>
    </>
  );
}

function LossBars({ rows }) {
  if (!rows.length) return <p className="empty">No recorded simulated write-offs.</p>;
  const maximum = Math.max(...rows.map((row) => row.loss_usd), 1);
  return (
    <div className="loss-bars">
      {rows.map((row) => (
        <div className="loss-row" key={row.cause}>
          <span>{row.cause}</span>
          <div><i style={{ width: `${(row.loss_usd / maximum) * 100}%` }} /></div>
          <strong>{formatMoney(row.loss_usd)}</strong>
        </div>
      ))}
    </div>
  );
}

function Financial({ data }) {
  const financial = data.financial;
  return (
    <>
      <section className="metric-grid">
        <MetricCard label="Actual historical loss" value={formatMoney(financial.actual_historical_loss_usd)} note="Recorded synthetic write-offs" />
        <MetricCard label="Inventory exposed now" value={formatMoney(financial.inventory_exposed_usd)} note="Not a predicted write-off" />
        <MetricCard label="Expected annual mechanical loss" value={formatMoney(financial.expected_annual_mechanical_loss_usd)} note={`${number.format(financial.annual_operating_hours_assumption)} assumed operating hours/year`} />
        <MetricCard label="Expected annual blackout loss" value={formatMoney(financial.expected_annual_blackout_loss_usd)} note="Estimated from demand and outcome histories" />
      </section>
      <section className="two-column">
        <article className="panel">
          <p className="eyebrow">Recorded outcomes</p>
          <h2>Loss by cause</h2>
          <LossBars rows={financial.loss_by_cause} />
        </article>
        <article className="panel">
          <p className="eyebrow">Blackout estimate factors</p>
          <h2>What creates the annual estimate</h2>
          <dl>
            <div><dt>Blackouts / site-year</dt><dd>{formatNumber(financial.blackouts_per_year)}</dd></div>
            <div><dt>P(failed start | blackout)</dt><dd>{formatPercent(financial.blackout_factors.failed_start_probability)}</dd></div>
            <div><dt>P(loss | failed start)</dt><dd>{formatPercent(financial.blackout_factors.loss_probability_given_failed_start)}</dd></div>
            <div><dt>Mean loss | positive loss</dt><dd>{formatMoney(financial.blackout_factors.mean_loss_given_loss_usd)}</dd></div>
          </dl>
        </article>
      </section>
      <p className="explanation">Expected values are planning estimates. Unknown outcomes are excluded and reported as warnings; they are not treated as zero.</p>
    </>
  );
}

export default function App() {
  const [scenarios, setScenarios] = useState([]);
  const [scenario, setScenario] = useState("normal");
  const [refrigeratorId, setRefrigeratorId] = useState("");
  const [horizonDays, setHorizonDays] = useState(30);
  const [tab, setTab] = useState("conditions");
  const [data, setData] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    getScenarios().then((result) => setScenarios(result.scenarios)).catch((requestError) => setError(requestError.message));
  }, []);

  useEffect(() => {
    let active = true;
    setError("");
    getDashboard({ scenario, refrigeratorId, horizonDays })
      .then((result) => { if (active) setData(result); })
      .catch((requestError) => { if (active) setError(requestError.message); });
    return () => { active = false; };
  }, [scenario, refrigeratorId, horizonDays]);

  function chooseScenario(event) {
    setRefrigeratorId("");
    setScenario(event.target.value);
  }

  return (
    <main>
      <header className="masthead">
        <div><p className="eyebrow">Regional blood-bank operations</p><h1>BloodWatch</h1><p>Supply conditions, equipment reliability, and recorded synthetic losses.</p></div>
        <span className="synthetic">SYNTHETIC DATA</span>
      </header>

      <section className="controls" aria-label="Dashboard controls">
        <label>Scenario<select value={scenario} onChange={chooseScenario}>{scenarios.map((row) => <option key={row.id} value={row.id}>{row.name}</option>)}</select></label>
        <label>Refrigerator<select value={refrigeratorId || data?.selection.refrigerator_id || ""} onChange={(event) => setRefrigeratorId(event.target.value)}>{data?.selection.available_refrigerators.map((id) => <option key={id} value={id}>{id}</option>)}</select></label>
        <label>Operating horizon<select value={horizonDays} onChange={(event) => setHorizonDays(Number(event.target.value))}><option value="7">7 days</option><option value="30">30 days</option><option value="90">90 days</option></select></label>
      </section>

      {error && <section className="error"><State value="unknown" /><div><strong>Dashboard unavailable</strong><p>{error}</p></div></section>}
      {!error && !data && <p className="loading">Loading dashboard…</p>}
      {data && !error && (
        <>
          <section className="scenario-banner"><div><strong>{data.scenario.name}</strong><p>{data.scenario.description}</p></div><small>Reference time: {data.scenario.reference_time_utc}</small></section>
          <nav className="tabs" aria-label="Dashboard sections">
            {[["conditions", "Conditions"], ["reliability", "Reliability"], ["financial", "Financial impact"]].map(([id, label]) => <button key={id} className={tab === id ? "active" : ""} onClick={() => setTab(id)}>{label}</button>)}
          </nav>
          {tab === "conditions" && <Conditions data={data} />}
          {tab === "reliability" && <Reliability data={data} />}
          {tab === "financial" && <Financial data={data} />}
          {data.warnings.length > 0 && <details className="warnings"><summary>Analysis warnings ({data.warnings.length})</summary><ul>{data.warnings.map((item, index) => <li key={`${item.code}-${index}`}><strong>{item.code}</strong>: {item.message}</li>)}</ul></details>}
        </>
      )}
      <footer>Prototype decision support only. A temperature breach requires review and does not automatically establish biological viability, spoilage, or financial write-off.</footer>
    </main>
  );
}
