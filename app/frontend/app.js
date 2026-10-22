const root = document.querySelector('#root');
const state = { scenarios: [], scenario: 'normal', refrigeratorId: '', horizonDays: 30, windowHours: 6, data: null, error: '', busy: false, request: 0 };
const esc = value => String(value ?? '').replaceAll('&', '&amp;').replaceAll('<', '&lt;').replaceAll('>', '&gt;').replaceAll('"', '&quot;').replaceAll("'", '&#039;');
const num = (v, digits = 2) => v == null ? 'Not enough data' : Number(v).toLocaleString('en-US', {maximumFractionDigits: digits});
const pct = v => v == null ? 'Not enough data' : `${num(v * 100, 1)}%`;
const usd = v => v == null ? 'Not enough data' : new Intl.NumberFormat('en-US', {style:'currency',currency:'USD',maximumFractionDigits:0}).format(v);
const minutes = hours => hours == null ? 'Not enough data' : `${num(hours * 60, 0)} min`;
const clock = time => new Intl.DateTimeFormat('en-US', {timeZone:'UTC',hour:'2-digit',minute:'2-digit',hour12:false}).format(new Date(time));
const titleCase = value => String(value ?? '').toLowerCase().replace(/\b\w/g, letter => letter.toUpperCase());
const refrigeratorName = id => {
  const number = String(id ?? '').match(/(\d+)$/)?.[1];
  return number ? `Refrigerator ${number}` : `Refrigerator ${id}`;
};
const card = (label, value, note) => `<article class="metric-card"><span>${label}</span><strong>${value}</strong><small>${note}</small></article>`;
const sectionTitle = (n, title) => `<div class="question"><span class="question-number">${n}</span><h2>${title}</h2></div>`;

async function getJson(url) {
  const response = await fetch(url);
  const body = await response.json();
  if (!response.ok) throw new Error(body.detail || 'Could not load analysis.');
  return body;
}

function lineChart(points, {label, xLabel, yLabel, lower, upper, probability = false, marker = null}) {
  if (!points.length) return '<p class="empty">No recorded values to plot.</p>';
  const w=850, h=270, l=65, r=25, top=22, bottom=52;
  const valid=points.filter(p=>p.y!=null);
  if (!valid.length) return '<p class="empty">No valid values to plot.</p>';
  const xmin=Math.min(...points.map(p=>p.x)), xmax=Math.max(...points.map(p=>p.x));
  const ys=valid.map(p=>p.y).concat(lower==null?[]:[lower,upper]);
  const ymin=probability?0:Math.floor(Math.min(...ys)-0.4), ymax=probability?1:Math.ceil(Math.max(...ys)+0.4);
  const X=v=>l+(v-xmin)/(xmax-xmin||1)*(w-l-r), Y=v=>top+(ymax-v)/(ymax-ymin||1)*(h-top-bottom);
  let lines='';
  for(let i=0;i<=4;i++) {
    const v=ymin+(ymax-ymin)*i/4;
    lines+=`<line class="grid" x1="${l}" x2="${w-r}" y1="${Y(v)}" y2="${Y(v)}"/><text x="${l-10}" y="${Y(v)+4}" text-anchor="end">${probability?num(v*100,0)+'%':num(v,1)}</text>`;
  }
  for(let i=0;i<=3;i++) {
    const v=xmin+(xmax-xmin)*i/3;
    lines+=`<text x="${X(v)}" y="${h-28}" text-anchor="${i===3?'end':i===0?'start':'middle'}">${probability?num(v,1):clock(v)}</text>`;
  }
  let path='', pen=false;
  for(const p of points) {
    if(p.y==null) {pen=false; continue;}
    path+=`${pen?'L':'M'}${X(p.x)},${Y(p.y)} `; pen=true;
  }
  const band=lower==null?'':`<rect class="limit-band" x="${l}" y="${Y(upper)}" width="${w-l-r}" height="${Y(lower)-Y(upper)}"/>${[lower,upper].map(v=>`<line class="storage-line" x1="${l}" x2="${w-r}" y1="${Y(v)}" y2="${Y(v)}"/><text x="${w-r-4}" y="${Y(v)-5}" text-anchor="end">${v} °C limit</text>`).join('')}`;
  const event=marker==null||marker<xmin||marker>xmax?'':`<line class="event-line" x1="${X(marker)}" x2="${X(marker)}" y1="${top}" y2="${h-bottom}"/><text x="${Math.min(X(marker)+5,w-150)}" y="${top+12}">Cooling lost</text>`;
  return `<div class="chart-wrap"><svg viewBox="0 0 ${w} ${h}" role="img" aria-label="${esc(label)}"><title>${esc(label)}</title>${band}${lines}${event}<path d="${path}" class="temperature-line"/>${valid.length===1?`<circle cx="${X(valid[0].x)}" cy="${Y(valid[0].y)}" r="4" class="point"/>`:''}<text x="15" y="15">${esc(yLabel)}</text><text x="${w/2}" y="${h-4}" text-anchor="middle">${esc(xLabel)}</text></svg></div>`;
}

function overview(data) {
  const s=data.conditions.temperature_summary;
  const inventory=data.conditions.inventory_summary;
  const equipment=data.conditions.equipment;
  const fridge=data.reliability.selected_refrigerator_model;
  const generator=data.reliability.selected_generator;
  const incident=data.reliability.selected_breach_recovery;
  const detailed=incident.incidents;
  const latest=detailed.filter(row=>row.first_breach_utc).sort((a,b)=>a.cooling_loss_utc.localeCompare(b.cooling_loss_utc)).at(-1);
  const series=data.conditions.temperature_series.map(row=>({x:Date.parse(row.timestamp_utc),y:row.reading_valid?row.temperature_c:null})).sort((a,b)=>a.x-b.x);
  const shownIncident=detailed.filter(row=>Date.parse(row.cooling_loss_utc)>=series[0]?.x && Date.parse(row.cooling_loss_utc)<=series.at(-1)?.x).at(-1);
  const status=s.state==='within_limits'?'Within range':s.state==='unknown'?'Unknown':'Review required';
  const rows=detailed.map(row=>`<tr><td>${esc(row.incident_id)}</td><td>${row.breach_status==='breached'?minutes(row.observed_hours_to_breach_or_censoring):row.breach_status==='unknown'?'Temperature history missing':'No observed breach before follow-up ended'}</td><td>${minutes(row.recovery_hours)}</td></tr>`).join('');
  const zeroFailures=fridge.failures===0;
  const within=equipment.filter(row=>row.status==='within_limits').length;
  const review=equipment.filter(row=>row.status==='review_required').length;
  const unknown=equipment.filter(row=>row.status==='unknown').length;
  const site=data.selection.site_id||data.selection.available_sites[0];
  const inventoryRows=inventory.by_refrigerator.map(row=>`<tr><td><strong>${esc(refrigeratorName(row.refrigerator_id))}</strong><br><small>${esc(row.refrigerator_id)}</small></td><td>${num(row.bags_present,0)}</td><td>${row.lot_count}</td><td>${usd(row.inventory_value_usd)}</td></tr>`).join('');
  return `<section class="panel overview-panel"><h2>Overview</h2>
    <div class="metric-grid four">
      ${card('Inventory',`${num(inventory.bags_present,0)} bags`,`${inventory.lot_count} lots · ${usd(inventory.inventory_value_usd)}`)}
      ${card('Storage range',`${s.lower_limit_c}–${s.upper_limit_c} °C`,'Refrigerated blood')}
      ${card('Refrigerators',`${within} of ${equipment.length} within range`,review||unknown?`${review} need review · ${unknown} unknown`:'All refrigerators')}
      ${card('Currently viewing',esc(refrigeratorName(data.selection.refrigerator_id)),`ID ${esc(data.selection.refrigerator_id)} · ${esc(titleCase(site))} site`)}
    </div>
    <h3>Inventory by refrigerator</h3>
    <div class="table-wrap"><table><thead><tr><th>Refrigerator</th><th>Bags</th><th>Lots</th><th>Value</th></tr></thead><tbody>${inventoryRows}</tbody></table></div>
  </section>
  <section class="panel">${sectionTitle(1,'Temperature')}
    <div class="metric-grid three">
      ${card('Latest',s.latest_temperature_c==null?'Unknown':`${num(s.latest_temperature_c)} °C`,`${esc(status)} · ${s.latest_timestamp_utc?clock(s.latest_timestamp_utc)+' UTC':''}`)}
      ${card('Average',`${num(s.mean_c)} °C`,`${num(s.minimum_c)}–${num(s.maximum_c)} °C`)}
      ${card('Sample SD',s.standard_deviation_c==null?'Not enough data':`${num(s.standard_deviation_c)} °C`,`${s.valid_count} readings · ${s.missing_or_invalid_count} missing`)}
    </div>
    ${lineChart(series,{label:'Recorded temperature over time with 1–6 °C storage limits',xLabel:'Recorded time (UTC)',yLabel:'Temperature (°C)',lower:s.lower_limit_c,upper:s.upper_limit_c,marker:shownIncident?Date.parse(shownIncident.cooling_loss_utc):null})}
    <p class="source"><a href="https://www.law.cornell.edu/cfr/text/21/640.11" target="_blank" rel="noopener">1–6 °C storage reference</a></p>
  </section>
  <section class="panel">${sectionTitle(2,'Time to breach')}
    <div class="metric-grid two">
      ${card('Most recent breach',latest?minutes(latest.observed_hours_to_breach_or_censoring):'Not enough data',latest?esc(latest.incident_id):'No observed breach')}
      ${card('Average to breach',minutes(incident.mean_observed_hours_to_breach_breached_only),`${incident.breached_count} observed breaches`)}
    </div>
    <p class="plain-note">${incident.unbreached_censored_count} without breach · ${incident.unknown_count} missing histories</p>
    <details><summary>See incident times and recovery</summary>${rows?`<div class="table-wrap"><table><thead><tr><th>Incident</th><th>Time to observed breach</th><th>Cooling restored after</th></tr></thead><tbody>${rows}</tbody></table></div>`:'<p>No recorded incidents for this refrigerator.</p>'}<p class="plain-note">Restoring cooling and reaching the temperature limit are different events. These data show storage-limit crossings, not a measured time when blood becomes biologically unusable. Missing samples limit what can be inferred between readings.</p></details>
  </section>
  <section class="panel">${sectionTitle(3,'Failure risk')}
    <label class="inline-control" for="horizon">Operating period <select id="horizon">${[7,30,90].map(days=>`<option value="${days}"${days===state.horizonDays?' selected':''}>${days} days</option>`).join('')}</select></label>
    <div class="metric-grid two">
      ${card('Refrigerator failure',zeroFailures?'No failures observed':pct(fridge.failure_probability),`${fridge.failures} failures · ${num(fridge.exposure_hours,0)} hours · ${esc(fridge.model_group)}`)}
      ${card('Generator start failure',generator.failed_demands===0?'No failed starts observed':pct(generator.failed_start_probability),`${generator.failed_demands} failed · ${generator.known_demands} demands · ${esc(generator.generator_id)}`)}
    </div>
    ${zeroFailures?`<p class="plain-note">95% upper rate: ${num(fridge.rate_interval_95.upper,6)} per hour</p>`:lineChart(fridge.cdf.map(p=>({x:p.operating_hours/24,y:p.failure_probability})),{label:'Probability of a refrigerator mechanical failure by operating time',xLabel:'Future operating time (days)',yLabel:'Failure probability F(t)',probability:true})}
    <details><summary>Connect this to class: λ, R(t), F(t), hazard, and mean life</summary>
      <p><strong>Failure rate λ:</strong> ${num(fridge.rate_per_hour,6)} failures/hour = failures ÷ operating hours. The model assumes a constant rate.</p>
      <p><strong>Reliability:</strong> R(t) = exp(−λt), the probability of no mechanical failure through t operating hours. <strong>Failure CDF:</strong> F(t) = 1 − R(t), the probability of a failure by then.</p>
      <p><strong>Hazard:</strong> h(t) = λ in this model. <strong>Mean time between equipment failures:</strong> 1/λ = ${num(fridge.mtbf_hours,0)} hours. It describes repairable refrigerators; it is not the blood's time to a temperature breach.</p>
      <p><strong>Generator:</strong> failed starts ÷ known demands. Its 95% interval is ${pct(generator.wilson_interval_95.lower)}–${pct(generator.wilson_interval_95.upper)}. Zero failed starts in a small sample does not establish perfect reliability.</p>
    </details>
  </section>
  <details class="panel"><summary>Other class tools: stability, capability, and uncertainty</summary>
    <dl><div><dt>Mean and standard deviation</dt><dd>The typical temperature and spread of individual readings; shown above.</dd></div><div><dt>Standard error</dt><dd>Uncertainty in an estimated mean. It does not describe individual blood temperatures; s/√n requires an appropriate independence assumption.</dd></div><div><dt>Control charts</dt><dd>Detect changes from a reviewed normal baseline. Common-cause variation is normal process variation; a breakdown is a potential special cause. The chart above is a temperature history with storage limits, not a control chart.</dd></div><div><dt>Cp/Cpk and Pp/Ppk</dt><dd>Compare process spread and centering with 1–6 °C specifications. Cp/Cpk need a defensible within-process estimate and stability; Pp/Ppk summarize overall performance. We do not calculate capability by mixing normal readings and a known breakdown.</dd></div></dl>
    <p class="plain-note">A next course-focused addition is one baseline control chart, followed by capability once its assumptions are supported. Control limits describe the process; storage limits describe the product requirement.</p>
  </details>
  <details class="panel"><summary>Financial impact</summary><div class="metric-grid two">${card('Inventory exposed',usd(data.financial.inventory_exposed_usd),'Current scenario')}${card('Recorded loss',usd(data.financial.actual_historical_loss_usd),'Synthetic history')}</div></details>
  ${data.warnings.length?`<details class="warnings"><summary>Data limitations (${data.warnings.length})</summary><ul>${data.warnings.map(w=>`<li>${esc(w.message)}</li>`).join('')}</ul></details>`:''}`;
}

function render() {
  const data=state.data;
  const fridgeOptions=(data?.selection.available_refrigerators||[]).map(id=>`<option value="${esc(id)}"${id===(state.refrigeratorId||data?.selection.refrigerator_id)?' selected':''}>${esc(refrigeratorName(id))} (${esc(id)})</option>`).join('');
  root.innerHTML=`<main><header class="masthead"><div><p class="eyebrow">Storage · response · reliability</p><h1>BloodWatch</h1></div><span class="synthetic">SYNTHETIC CLASS DEMO</span></header>
    <section class="controls" aria-label="Dashboard controls"><label>Choose a scenario<select id="scenario" ${state.busy?'disabled':''}>${state.scenarios.map(s=>`<option value="${esc(s.id)}"${s.id===state.scenario?' selected':''}>${esc(s.name)}</option>`).join('')}</select></label><label>Refrigerator<select id="refrigerator" ${state.busy?'disabled':''}>${fridgeOptions}</select></label><label>Temperature history<select id="window" ${state.busy?'disabled':''}>${[6,24].map(v=>`<option value="${v}"${v===state.windowHours?' selected':''}>Last ${v} hours</option>`).join('')}</select></label></section>
    <div aria-live="polite">${state.error?`<p class="error" role="alert">${esc(state.error)}</p>`:state.busy?'<p class="loading">Updating analysis…</p>':data?`<p class="context">${esc(data.scenario.name)} · ${esc(data.scenario.reference_time_utc)}</p>${overview(data)}`:'<p class="loading">Loading dashboard…</p>'}</div>
    <footer>Synthetic educational data. Storage breaches require review.</footer></main>`;
  root.querySelector('#scenario').addEventListener('change',e=>{state.scenario=e.target.value;state.refrigeratorId='';loadDashboard();});
  root.querySelector('#refrigerator').addEventListener('change',e=>{state.refrigeratorId=e.target.value;loadDashboard();});
  root.querySelector('#window').addEventListener('change',e=>{state.windowHours=Number(e.target.value);loadDashboard();});
  root.querySelector('#horizon')?.addEventListener('change',e=>{state.horizonDays=Number(e.target.value);loadDashboard();});
}

async function loadDashboard() {
  const request=++state.request;
  state.busy=true; state.error=''; render();
  const params=new URLSearchParams({scenario:state.scenario,horizon_operating_days:String(state.horizonDays),temperature_window_hours:String(state.windowHours)});
  if(state.refrigeratorId) params.set('refrigerator_id',state.refrigeratorId);
  try {const data=await getJson(`/api/dashboard?${params}`); if(request!==state.request)return;state.data=data;}
  catch(error){if(request!==state.request)return;state.error=error.message;}
  state.busy=false;render();
}
async function start() {
  try {state.scenarios=(await getJson('/api/scenarios')).scenarios;await loadDashboard();}
  catch(error){state.error=error.message;state.busy=false;render();}
}
start();
