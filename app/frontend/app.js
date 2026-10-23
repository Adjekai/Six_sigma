const root = document.querySelector('#root');
const state = { mode: 'live', refrigeratorId: '', availableRefrigerators: [], horizonDays: 30, windowHours: 6, data: null, error: '', busy: false, request: 0 };
const esc = value => String(value ?? '').replaceAll('&', '&amp;').replaceAll('<', '&lt;').replaceAll('>', '&gt;').replaceAll('"', '&quot;').replaceAll("'", '&#039;');
const num = (v, digits = 2) => v == null ? 'Not enough data' : Number(v).toLocaleString('en-US', {maximumFractionDigits: digits});
const pct = v => v == null ? 'Not enough data' : `${num(v * 100, 1)}%`;
const usd = v => v == null ? 'Not enough data' : new Intl.NumberFormat('en-US', {style:'currency',currency:'USD',maximumFractionDigits:0}).format(v);
const minutes = hours => hours == null ? 'Not enough data' : `${num(hours * 60, 0)} min`;
const clock = time => new Intl.DateTimeFormat('en-US', {timeZone:'UTC',hour:'2-digit',minute:'2-digit',hour12:false}).format(new Date(time));
const timestamp = time => new Intl.DateTimeFormat('en-US', {timeZone:'UTC',month:'short',day:'numeric',hour:'2-digit',minute:'2-digit',hour12:false}).format(new Date(time))+' UTC';
const currentTimestamp = () => new Intl.DateTimeFormat('en-US', {month:'long',day:'numeric',year:'numeric',hour:'numeric',minute:'2-digit',second:'2-digit',hour12:true,timeZoneName:'short'}).format(new Date());
const refrigeratorName = id => {
  const number = String(id ?? '').match(/(\d+)$/)?.[1];
  return number ? `Refrigerator ${number}` : `Refrigerator ${id}`;
};
const refrigeratorCode = id => {
  const number = String(id ?? '').match(/(\d+)$/)?.[1];
  return number ? `R${number}` : String(id ?? '');
};
const card = (label, value, note) => `<article class="metric-card"><span>${label}</span><strong>${value}</strong><small>${note}</small></article>`;
const sectionTitle = (n, title) => `<div class="question"><span class="question-number">${n}</span><h2>${title}</h2></div>`;

async function getJson(url) {
  const response = await fetch(url);
  const body = await response.json();
  if (!response.ok) throw new Error(body.detail || 'Could not load analysis.');
  return body;
}

function lineChart(points, {label, xLabel, yLabel, lower, upper, probability = false, markers = [], center = null, limitText = 'limit'}) {
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
  const band=lower==null?'':`<rect class="limit-band" x="${l}" y="${Y(upper)}" width="${w-l-r}" height="${Y(lower)-Y(upper)}"/>${[lower,upper].map(v=>`<line class="storage-line" x1="${l}" x2="${w-r}" y1="${Y(v)}" y2="${Y(v)}"/><text x="${w-r-4}" y="${Y(v)-5}" text-anchor="end">${num(v)} °C ${limitText}</text>`).join('')}`;
  const centerLine=center==null?'':`<line class="center-line" x1="${l}" x2="${w-r}" y1="${Y(center)}" y2="${Y(center)}"/><text x="${w-r-4}" y="${Y(center)-5}" text-anchor="end">${num(center)} °C center</text>`;
  const events=markers.filter(event=>event.x>=xmin&&event.x<=xmax).map((event,index)=>`<line class="event-line" x1="${X(event.x)}" x2="${X(event.x)}" y1="${top}" y2="${h-bottom}"/><text x="${Math.min(X(event.x)+5,w-175)}" y="${top+12+index%2*14}">${esc(event.label)}</text>`).join('');
  return `<div class="chart-wrap"><svg viewBox="0 0 ${w} ${h}" role="img" aria-label="${esc(label)}"><title>${esc(label)}</title>${band}${lines}${centerLine}${events}<path d="${path}" class="temperature-line"/>${valid.length===1?`<circle cx="${X(valid[0].x)}" cy="${Y(valid[0].y)}" r="4" class="point"/>`:''}<text x="15" y="15">${esc(yLabel)}</text><text x="${w/2}" y="${h-4}" text-anchor="middle">${esc(xLabel)}</text></svg></div>`;
}

function overview(data) {
  const s=data.conditions.temperature_summary;
  const process=data.conditions.process_analysis;
  const inventory=data.conditions.inventory_summary;
  const riskForecasts=data.conditions.risk_forecasts;
  const equipment=data.conditions.equipment;
  const fridge=data.reliability.selected_refrigerator_model;
  const generator=data.reliability.selected_generator;
  const incident=data.reliability.selected_breach_recovery;
  const detailed=incident.incidents;
  const latest=detailed.filter(row=>row.first_breach_utc).sort((a,b)=>a.cooling_loss_utc.localeCompare(b.cooling_loss_utc)).at(-1);
  const series=data.conditions.temperature_series.map(row=>({x:Date.parse(row.timestamp_utc),y:row.reading_valid?row.temperature_c:null})).sort((a,b)=>a.x-b.x);
  const visibleIncidents=detailed.filter(row=>Date.parse(row.cooling_loss_utc)>=series[0]?.x && Date.parse(row.cooling_loss_utc)<=series.at(-1)?.x);
  const coolingMarkers=visibleIncidents.map(row=>({x:Date.parse(row.cooling_loss_utc),label:row.cause==='mechanical'?`${row.incident_id}: refrigerator failure`:`${row.incident_id}: generator start failure`}));
  const status=s.state==='within_limits'?'Within range':s.state==='unknown'?'Reading unavailable':'Review required';
  const rows=detailed.map(row=>`<tr><td><strong>${row.cause==='mechanical'?'Refrigerator mechanical failure':'Backup generator failed to start'}</strong><br><small>Event ${esc(row.incident_id)}</small></td><td>${row.breach_status==='breached'?minutes(row.observed_hours_to_breach_or_censoring):row.breach_status==='unknown'?'No matching temperature readings':'No reading outside 1–6 °C before recovery'}</td><td>${minutes(row.recovery_hours)}</td></tr>`).join('');
  const zeroFailures=fridge.failures===0;
  const missingBreachValue='No out-of-range reading';
  const missingBreachNote='No observed out-of-range time';
  const within=equipment.filter(row=>row.status==='within_limits').length;
  const review=equipment.filter(row=>row.status==='review_required').length;
  const unknown=equipment.filter(row=>row.status==='unknown').length;
  const fullestInventory=Math.max(...inventory.by_refrigerator.map(row=>row.bags_present),1);
  const inventoryRows=inventory.by_refrigerator.map(row=>`<tr><td><strong>${esc(refrigeratorName(row.refrigerator_id))}</strong><br><small>${esc(refrigeratorCode(row.refrigerator_id))}</small></td><td><div class="blood-level" title="${num(row.bags_present,0)} bags; relative to the fullest refrigerator"><span class="blood-level-fill" style="width:${row.bags_present/fullestInventory*100}%"></span><strong>${num(row.bags_present,0)} bags</strong></div></td><td>${row.lot_count}</td><td>${usd(row.inventory_value_usd)}</td></tr>`).join('');
  const riskRows=riskForecasts.map(row=>{
    const signal=row.status==='approaching_limit'?`Limit projected in ${minutes(row.predicted_minutes_to_limit/60)}`:row.status==='currently_out_of_range'?'Currently outside range':row.status==='within_limits'?'No crossing projected':row.status==='insufficient_data'?'Collecting trend data':'Sensor data stale';
    const current=row.current_temperature_c==null?'Unknown':`${num(row.current_temperature_c)} °C`;
    const projected=row.projected_temperature_c==null?'Unavailable':`${num(row.projected_temperature_c)} °C`;
    return `<tr><td data-label="Unit"><strong>${esc(refrigeratorName(row.refrigerator_id))}</strong></td><td data-label="Signal"><span class="risk-signal risk-signal--${esc(row.status)}">${esc(signal)}</span></td><td data-label="Now → projected">${current} → ${projected}</td><td data-label="Inventory at risk">${usd(row.inventory_value_usd)} · ${num(row.inventory_bags,0)} bags</td></tr>`;
  }).join('');
  const flaggedForecasts=riskForecasts.filter(row=>['approaching_limit','currently_out_of_range'].includes(row.status)).length;
  const generatorRisk=data.reliability.selected_generator;
  const generatorRiskText=generatorRisk.failed_start_probability==null?'Not enough known blackout demands':`${pct(generatorRisk.failed_start_probability)} estimated per blackout`;
  const generatorInterval=generatorRisk.wilson_interval_95.lower==null?'uncertainty unavailable':`95% interval ${pct(generatorRisk.wilson_interval_95.lower)}–${pct(generatorRisk.wilson_interval_95.upper)}`;
  const overviewPanel=`<section class="ops-summary" aria-label="Supply status">
    <div class="summary-heading"><div><p class="eyebrow">Regional blood storage</p><h2>Supply status</h2></div><span class="live-indicator"><i></i>${num(data.dataset.live_reading_count,0)} live readings · updates every 15 s</span></div>
    <div class="summary-strip">
      <div><span>Inventory</span><strong>${num(inventory.bags_present,0)} bags</strong><small>${inventory.lot_count} lots · ${usd(inventory.inventory_value_usd)}</small></div>
      <div><span>Refrigerators</span><strong>${within} / ${equipment.length} in range</strong><small>${review} review · ${unknown} unknown</small></div>
      <div><span>Selected unit</span><strong>${num(s.latest_temperature_c)} °C</strong><small>${esc(status)} · ${s.latest_timestamp_utc?clock(s.latest_timestamp_utc)+' UTC':'No recent reading'}</small></div>
      <div><span>Storage requirement</span><strong>${s.lower_limit_c}–${s.upper_limit_c} °C</strong><small>For refrigerated blood</small></div>
    </div>
    <div class="risk-watch"><div><h3>Risk watch</h3><p>${flaggedForecasts} temperature warning${flaggedForecasts===1?'':'s'} · next 60 minutes</p></div><div class="table-wrap"><table><thead><tr><th>Unit</th><th>Signal</th><th>Now → projected</th><th>Inventory at risk</th></tr></thead><tbody>${riskRows}</tbody></table></div></div>
    <p class="generator-summary"><strong>Backup ${esc(generatorRisk.generator_id)}:</strong> ${esc(generatorRiskText)} · ${esc(generatorInterval)} · supports ${num(inventory.bags_present,0)} bags (${usd(inventory.inventory_value_usd)}). Historical estimate, not a live condition alert.</p>
    <details id="inventory-details" class="secondary-details"><summary>Inventory by refrigerator</summary><div class="table-wrap"><table><thead><tr><th>Refrigerator</th><th>Relative stock</th><th>Lots</th><th>Value</th></tr></thead><tbody>${inventoryRows}</tbody></table></div></details>
  </section>`;
  const sections=`<section class="panel temperature-panel"><div class="temperature-heading"><div><p class="eyebrow">Selected refrigerator</p><h2>${esc(refrigeratorName(state.refrigeratorId||data.selection.refrigerator_id))}</h2></div><span class="condition-tag condition-tag--${esc(s.state)}">${esc(status)}</span></div>
    <div class="metric-grid three">
      ${card('Latest',s.latest_temperature_c==null?'Unknown':`${num(s.latest_temperature_c)} °C`,`${esc(status)} · ${s.latest_timestamp_utc?clock(s.latest_timestamp_utc)+' UTC':''}`)}
      ${card('Average',`${num(s.mean_c)} °C`,`${num(s.minimum_c)}–${num(s.maximum_c)} °C`)}
      ${card('Sample standard deviation',s.standard_deviation_c==null?'Not enough data':`${num(s.standard_deviation_c)} °C`,'Variation among valid readings')}
    </div>
    ${lineChart(series,{label:'Recorded temperature over time with 1–6 °C storage limits and cooling-loss events',xLabel:'Recorded time (UTC)',yLabel:'Temperature (°C)',lower:s.lower_limit_c,upper:s.upper_limit_c,markers:coolingMarkers})}
    <p class="source"><a href="https://www.law.cornell.edu/cfr/text/21/640.11" target="_blank" rel="noopener">1–6 °C storage reference</a> · latest data ${esc(timestamp(data.dataset.reference_time_utc))}</p>
  </section>
  <details id="incidents-details" class="analysis-details"><summary><span>Cooling interruptions</span><small>${detailed.length} recorded · ${incident.breached_count} storage-range crossings</small></summary><section class="details-content">
    <p class="plain-note">For each interruption, BloodWatch records when cooling stopped, when temperature first moved outside 1–6 °C, and when cooling was restored.</p>
    <div class="breach-definition"><span>Cooling lost</span><strong aria-hidden="true">→</strong><span>First reading outside 1–6 °C</span><strong aria-hidden="true">→</strong><span>Cooling restored</span></div>
    <div class="metric-grid two">
      ${card('Most recent limit crossing',latest?minutes(latest.observed_hours_to_breach_or_censoring):missingBreachValue,latest?`${latest.cause==='mechanical'?'Refrigerator failure':'Generator start failure'} · ${esc(latest.incident_id)}`:missingBreachNote)}
      ${card('Average limit-crossing time',incident.mean_observed_hours_to_breach_breached_only==null?missingBreachValue:minutes(incident.mean_observed_hours_to_breach_breached_only),incident.breached_count?`Across ${incident.breached_count} interruptions that crossed the storage range`:missingBreachNote)}
    </div>
    <p class="plain-note">${detailed.length} recorded interruptions · ${incident.breached_count} crossed 1–6 °C · ${incident.unbreached_censored_count} stayed within range until recovery · ${incident.unknown_count} lack matching temperature readings</p>
    <details id="incident-timing-details"><summary>See every interruption and recovery time</summary>${rows?`<div class="table-wrap"><table><thead><tr><th>Interruption</th><th>Cooling loss to first reading outside 1–6 °C</th><th>Cooling loss to restoration</th></tr></thead><tbody>${rows}</tbody></table></div>`:'<p>No recorded cooling interruptions for this refrigerator.</p>'}<p class="plain-note">A limit crossing is an observed storage-temperature event, not a measurement of when blood becomes biologically unusable.</p></details>
  </section></details>
  <details id="reliability-details" class="analysis-details"><summary><span>Equipment failure risk</span><small>${num(fridge.failures,0)} refrigerator failures · ${generator.failed_demands} failed generator starts</small></summary><section class="details-content"><section class="panel">${sectionTitle(3,'Failure risk')}
    <div class="metric-grid four">
      ${card('Refrigerator mechanical failures',num(fridge.failures,0),`${num(fridge.exposure_hours,0)} observed operating hours · blackouts excluded`)}
      ${card('Refrigerator failure probability',zeroFailures?'No failures observed':pct(fridge.failure_probability),`Within the selected ${state.horizonDays}-day forecast period`)}
      ${card('Generator failed starts',`${generator.failed_demands} of ${generator.known_demands}`,`${generator.successful_demands} successful starts · ${generator.unknown_demands} unknown excluded`)}
      ${card('Generator failed-start probability',pct(generator.failed_start_probability),'Failed starts ÷ known blackout demands')}
    </div>
    ${zeroFailures?`<p class="plain-note">95% upper rate: ${num(fridge.rate_interval_95.upper,6)} per hour</p>`:lineChart(fridge.cdf.map(p=>({x:p.operating_hours/24,y:p.failure_probability})),{label:'Probability of a refrigerator mechanical failure by operating time',xLabel:'Future operating time (days)',yLabel:'Failure probability F(t)',probability:true})}
  </section>
  <section class="panel">${sectionTitle(4,'Reliability metrics')}
    <div class="metric-grid three">
      ${card('Failure rate λ',`${num(fridge.rate_per_hour,6)} / hour`,'Failures ÷ operating hours')}
      ${card('Reliability R(t)',pct(fridge.reliability),`No failure through ${state.horizonDays} days`)}
      ${card('Failure probability F(t)',pct(fridge.failure_probability),`Failure within ${state.horizonDays} days`)}
      ${card('Hazard h(t)',`${num(fridge.rate_per_hour,6)} / hour`,'Constant-rate model')}
      ${card('MTBF',fridge.mtbf_hours==null?'Unavailable':`${num(fridge.mtbf_hours,0)} hours`,fridge.mtbf_hours==null?'No mechanical failures observed':'Mean time between failures')}
      ${card('Backup generator uncertainty',`${pct(generator.wilson_interval_95.lower)}–${pct(generator.wilson_interval_95.upper)}`,'95% failed-start interval')}
    </div>
  </section></section></details>
  <details id="process-details" class="analysis-details"><summary><span>Process analysis</span><small>${process.capability_status==='estimated'?'Capability estimate available':'Limited baseline data'}</small></summary><section class="details-content"><section class="panel">${sectionTitle(5,'Process analysis')}
    <div class="metric-grid three">
      ${card('Standard error',process.standard_error_c==null?'Unavailable':`${num(process.standard_error_c,3)} °C`,'s ÷ √n')}
      ${card('Control limits',process.lower_control_limit_c==null?'Unavailable':`${num(process.lower_control_limit_c)}–${num(process.upper_control_limit_c)} °C`,`${process.baseline_count} fixed normal-baseline readings`)}
      ${card('Control signals',process.out_of_control_count==null?'Unavailable':num(process.out_of_control_count,0),'Points outside control limits')}
      ${card('Cp',num(process.cp),'Potential capability')}
      ${card('Cpk',num(process.cpk),'Centered capability')}
      ${card('Pp / Ppk',`${num(process.pp)} / ${num(process.ppk)}`,'Overall performance')}
    </div>
    ${process.lower_control_limit_c==null?'':lineChart(series,{label:'Individuals control chart with cooling-loss events',xLabel:'Recorded time (UTC)',yLabel:'Temperature (°C)',lower:process.lower_control_limit_c,upper:process.upper_control_limit_c,center:process.center_line_c,limitText:'control limit',markers:coolingMarkers})}
    <p class="plain-note">Control limits: fixed normal behavior · Storage specifications: ${s.lower_limit_c}–${s.upper_limit_c} °C</p>
    <p class="plain-note">${esc(process.capability_explanation)}</p>
  </section></section></details>
  `;
  return {overviewPanel,sections};
}

function scenarioPanel(scenario) {
  const alarm=scenario.observed_alarm;
  if(!alarm) return `<section class="scenario-result"><div><p class="eyebrow">Synthetic dataset scenario</p><h2>${esc(scenario.label)}</h2><p>${esc(scenario.description)}</p></div><span class="scenario-state">No observed alarm</span></section>`;
  const cause=scenario.id==='degrading_refrigerator'?'Refrigerator cooling failure':'Backup generator failed to start';
  const outage=alarm.outage_duration_hours==null?'':`<span>Outage <strong>${num(alarm.outage_duration_hours)} h</strong></span>`;
  return `<section class="scenario-result scenario-result--alert"><div class="scenario-copy"><p class="eyebrow">Synthetic dataset scenario</p><h2>${esc(scenario.label)}</h2><p>${esc(scenario.description)}</p></div><div class="scenario-outcome"><strong>Observed storage alarm</strong><span>${esc(refrigeratorName(alarm.refrigerator_id))} · ${esc(cause)}</span></div><div class="scenario-stats"><span>First limit crossing<strong>${minutes(alarm.hours_to_first_breach)}</strong></span><span>Recovery<strong>${alarm.recovery_hours==null?'Not observed':`${num(alarm.recovery_hours)} h`}</strong></span><span>Inventory exposed<strong>${usd(alarm.affected_inventory_value_usd)}</strong></span>${outage}</div></section>`;
}

function render() {
  const openDetails=[...root.querySelectorAll('details[open]')].map(item=>item.id);
  const data=state.data;
  const content=data?overview(data):null;
  const selectedRefrigerator=state.refrigeratorId||data?.selection.refrigerator_id||'';
  const fridgeOptions=state.availableRefrigerators.length
    ? state.availableRefrigerators.map(id=>`<option value="${esc(id)}"${id===selectedRefrigerator?' selected':''}>${esc(refrigeratorName(id))} (${esc(refrigeratorCode(id))})</option>`).join('')
    : `<option value="">${state.error?'Refrigerators unavailable':'Loading refrigerators…'}</option>`;
  root.innerHTML=`<main><header class="masthead"><div><p class="eyebrow">Storage · response · reliability</p><h1>BloodWatch</h1></div></header>
    <section class="controls" aria-label="Dashboard controls"><label>Data mode<select id="mode" ${state.busy?'disabled':''}><option value="live"${state.mode==='live'?' selected':''}>Live data</option><option value="stable"${state.mode==='stable'?' selected':''}>Demo · Stable conditions</option><option value="degrading_refrigerator"${state.mode==='degrading_refrigerator'?' selected':''}>Demo · Degrading refrigerator</option><option value="blackout_failed_generator"${state.mode==='blackout_failed_generator'?' selected':''}>Demo · Blackout and generator failure</option></select></label><label>Refrigerator<select id="refrigerator" ${state.busy?'disabled':''}>${fridgeOptions}</select></label><label>Temperature history<select id="window" ${state.busy?'disabled':''}>${[6,24].map(v=>`<option value="${v}"${v===state.windowHours?' selected':''}>Last ${v} hours</option>`).join('')}</select></label><label>Operating period<select id="horizon" ${state.busy?'disabled':''}>${[7,30,90].map(days=>`<option value="${days}"${days===state.horizonDays?' selected':''}>${days} days</option>`).join('')}</select></label></section>
    ${state.mode==='live'?'<p class="mode-note">Live mode combines the three CSV history datasets with incoming sensor readings.</p>':data?.scenario?scenarioPanel(data.scenario):''}
    ${content?.overviewPanel||''}
    <div aria-live="polite">${state.error?`<p class="error" role="alert">${esc(state.error)}</p>`:content?`<p class="context">Current time: <span id="current-time">${esc(currentTimestamp())}</span>${state.busy?' · Refreshing':''}</p>${content.sections}`:'<p class="loading">Loading dashboard…</p>'}</div>
    <footer>Synthetic educational data. Storage breaches require review.</footer></main>`;
  for(const id of openDetails) {
    const element=document.getElementById(id);
    if(element) element.open=true;
  }
  root.querySelector('#mode').addEventListener('change',e=>{state.mode=e.target.value;loadDashboard();});
  root.querySelector('#refrigerator').addEventListener('change',e=>{state.refrigeratorId=e.target.value;loadDashboard();});
  root.querySelector('#window').addEventListener('change',e=>{state.windowHours=Number(e.target.value);loadDashboard();});
  root.querySelector('#horizon')?.addEventListener('change',e=>{state.horizonDays=Number(e.target.value);loadDashboard();});
}

async function loadDashboard() {
  const request=++state.request;
  state.busy=true; state.error=''; render();
  const params=new URLSearchParams({horizon_operating_days:String(state.horizonDays),temperature_window_hours:String(state.windowHours)});
  if(state.mode!=='live') params.set('scenario',state.mode);
  if(state.refrigeratorId) params.set('refrigerator_id',state.refrigeratorId);
  try {const data=await getJson(`/api/dashboard?${params}`); if(request!==state.request)return;state.data=data;state.availableRefrigerators=data.selection.available_refrigerators;state.refrigeratorId=data.selection.refrigerator_id;}
  catch(error){if(request!==state.request)return;state.error=error.message;}
  state.busy=false;render();
}
async function start() {
  try {await loadDashboard();}
  catch(error){state.error=error.message;state.busy=false;render();}
}
start();
setInterval(() => {
  const display=document.querySelector('#current-time');
  if(display) display.textContent=currentTimestamp();
},1000);
setInterval(() => {
  if(!state.busy) loadDashboard();
},15000);
