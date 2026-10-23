const root = document.querySelector('#root');
const state = { scenario: 'stable', refrigeratorId: '', availableRefrigerators: [], horizonDays: 30, windowHours: 6, data: null, error: '', busy: false, request: 0 };
const esc = value => String(value ?? '').replaceAll('&', '&amp;').replaceAll('<', '&lt;').replaceAll('>', '&gt;').replaceAll('"', '&quot;').replaceAll("'", '&#039;');
const num = (v, digits = 2) => v == null ? 'Not enough data' : Number(v).toLocaleString('en-US', {maximumFractionDigits: digits});
const pct = v => v == null ? 'Not enough data' : `${num(v * 100, 1)}%`;
const usd = v => v == null ? 'Not enough data' : new Intl.NumberFormat('en-US', {style:'currency',currency:'USD',maximumFractionDigits:0}).format(v);
const minutes = hours => hours == null ? 'Not enough data' : `${num(hours * 60, 0)} min`;
const clock = time => new Intl.DateTimeFormat('en-US', {timeZone:'UTC',hour:'2-digit',minute:'2-digit',hour12:false}).format(new Date(time));
const fullTimestamp = time => new Intl.DateTimeFormat('en-US', {timeZone:'UTC',year:'numeric',month:'long',day:'numeric',hour:'numeric',minute:'2-digit',second:'2-digit',hour12:true,timeZoneName:'short'}).format(new Date(time));
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
  const equipment=data.conditions.equipment;
  const fridge=data.reliability.selected_refrigerator_model;
  const generator=data.reliability.selected_generator;
  const incident=data.reliability.selected_breach_recovery;
  const detailed=incident.incidents;
  const latest=detailed.filter(row=>row.first_breach_utc).sort((a,b)=>a.cooling_loss_utc.localeCompare(b.cooling_loss_utc)).at(-1);
  const series=data.conditions.temperature_series.map(row=>({x:Date.parse(row.timestamp_utc),y:row.reading_valid?row.temperature_c:null})).sort((a,b)=>a.x-b.x);
  const visibleIncidents=detailed.filter(row=>Date.parse(row.cooling_loss_utc)>=series[0]?.x && Date.parse(row.cooling_loss_utc)<=series.at(-1)?.x);
  const coolingMarkers=visibleIncidents.map(row=>({x:Date.parse(row.cooling_loss_utc),label:row.cause==='mechanical'?`${row.incident_id}: refrigerator failure`:`${row.incident_id}: generator start failure`}));
  const status=s.state==='within_limits'?'Within range':s.state==='unknown'?'Unknown':'Review required';
  const rows=detailed.map(row=>`<tr><td><strong>${row.cause==='mechanical'?'Refrigerator mechanical failure':'Backup generator failed to start'}</strong><br><small>Event ${esc(row.incident_id)}</small></td><td>${row.breach_status==='breached'?minutes(row.observed_hours_to_breach_or_censoring):row.breach_status==='unknown'?'No matching temperature readings':'No reading outside 1–6 °C before recovery'}</td><td>${minutes(row.recovery_hours)}</td></tr>`).join('');
  const missingBreachValue='No out-of-range reading';
  const missingBreachNote='No observed out-of-range time';
  const within=equipment.filter(row=>row.status==='within_limits').length;
  const review=equipment.filter(row=>row.status==='review_required').length;
  const unknown=equipment.filter(row=>row.status==='unknown').length;
  const fullestInventory=Math.max(...inventory.by_refrigerator.map(row=>row.bags_present),1);
  const inventoryRows=inventory.by_refrigerator.map(row=>`<tr><td><strong>${esc(refrigeratorName(row.refrigerator_id))}</strong><br><small>${esc(refrigeratorCode(row.refrigerator_id))}</small></td><td><div class="blood-level" title="${num(row.bags_present,0)} bags; relative to the fullest refrigerator"><span class="blood-level-fill" style="width:${row.bags_present/fullestInventory*100}%"></span><strong>${num(row.bags_present,0)} bags</strong></div></td><td>${row.lot_count}</td><td>${usd(row.inventory_value_usd)}</td></tr>`).join('');
  const overviewPanel=`<section class="panel overview-panel"><h2>Overview</h2>
    <div class="metric-grid four">
      ${card('Inventory',`${num(inventory.bags_present,0)} bags`,`${inventory.lot_count} lots · ${usd(inventory.inventory_value_usd)}`)}
      ${card('Storage range',`${s.lower_limit_c}–${s.upper_limit_c} °C`,'Refrigerated blood')}
      ${card('Refrigerators',`${within} of ${equipment.length} within range`,review||unknown?`${review} need review · ${unknown} unknown`:'All refrigerators')}
      ${card('Backup power',`${data.reliability.generators.length} backup generator`,`Supports all ${equipment.length} refrigerators`)}
    </div>
    <h3>Inventory by refrigerator</h3>
    <div class="table-wrap"><table><thead><tr><th>Refrigerator</th><th>Relative inventory</th><th>Lots</th><th>Value</th></tr></thead><tbody>${inventoryRows}</tbody></table></div>
  </section>`;
  const sections=`<section class="panel">${sectionTitle(1,'Temperature')}
    <div class="metric-grid three">
      ${card('Latest temperature reading',s.latest_temperature_c==null?'Unknown':`${num(s.latest_temperature_c)} °C`,`${esc(status)} · ${s.latest_timestamp_utc?fullTimestamp(s.latest_timestamp_utc):'timestamp unavailable'}`)}
      ${card('Average',`${num(s.mean_c)} °C`,`${num(s.minimum_c)}–${num(s.maximum_c)} °C`)}
      ${card('Sample standard deviation',s.standard_deviation_c==null?'Not enough data':`${num(s.standard_deviation_c)} °C`,'Variation among valid readings')}
    </div>
    ${lineChart(series,{label:'Recorded temperature over time with 1–6 °C storage limits and cooling-loss events',xLabel:'Recorded time (UTC)',yLabel:'Temperature (°C)',lower:s.lower_limit_c,upper:s.upper_limit_c,markers:coolingMarkers})}
    <p class="source"><a href="https://www.law.cornell.edu/cfr/text/21/640.11" target="_blank" rel="noopener">1–6 °C storage reference</a></p>
  </section>
  <section class="panel">${sectionTitle(2,'Cooling interruptions')}
    <div class="metric-grid two">
      ${card('Most recent limit crossing',latest?minutes(latest.observed_hours_to_breach_or_censoring):missingBreachValue,latest?`${latest.cause==='mechanical'?'Refrigerator failure':'Generator start failure'} · ${esc(latest.incident_id)}`:missingBreachNote)}
      ${card('Average limit-crossing time',incident.mean_observed_hours_to_breach_breached_only==null?missingBreachValue:minutes(incident.mean_observed_hours_to_breach_breached_only),incident.breached_count?`Across ${incident.breached_count} interruptions that crossed the storage range`:missingBreachNote)}
    </div>
    <p class="plain-note">${detailed.length} interruptions recorded: ${incident.breached_count} crossed 1–6 °C; ${incident.unbreached_censored_count} recovered before a crossing; ${incident.unknown_count} lack readings. These are observed temperatures, not a product viability or disposition decision.</p>
    <details><summary>Interruption evidence and recovery times</summary>${rows?`<div class="table-wrap"><table><thead><tr><th>Interruption</th><th>Cooling loss to first reading outside 1–6 °C</th><th>Cooling loss to restoration</th></tr></thead><tbody>${rows}</tbody></table></div>`:'<p>No recorded cooling interruptions for this refrigerator.</p>'}</details>
  </section>
  <section class="panel reliability-summary"><h2>Reliability summary</h2>
    <div class="metric-grid two">
      ${card('Refrigerator failure probability',pct(fridge.failure_probability),`Model estimate over ${state.horizonDays} days`)}
      ${card('Generator failed-start probability',pct(generator.failed_start_probability),`${generator.failed_demands} failed of ${generator.known_demands} known starts`)}
    </div>
    <p class="plain-note">Statistical estimates from synthetic history; observed alarms are summarized above.</p>
  </section>
  <details class="methods-details"><summary>Methods and details</summary><div class="methods-content">
    <h2>Reliability metrics</h2>
    <div class="metric-grid three">
      ${card('Mechanical failures / exposure',`${num(fridge.failures,0)} / ${num(fridge.exposure_hours,0)} h`,'Observed refrigerator failures ÷ operating hours')}
      ${card('Failure rate / hazard',`${num(fridge.rate_per_hour,6)} / hour`,'Constant-rate model')}
      ${card('MTBF',fridge.mtbf_hours==null?'Unavailable':`${num(fridge.mtbf_hours,0)} hours`,fridge.mtbf_hours==null?'No mechanical failures observed':'Mean time between failures')}
      ${card('Successful / failed starts',`${generator.successful_demands} / ${generator.failed_demands}`,`${generator.unknown_demands} unknown excluded`)}
      ${card('Generator uncertainty interval',`${pct(generator.wilson_interval_95.lower)}–${pct(generator.wilson_interval_95.upper)}`,'95% failed-start interval')}
      ${card('95% failure-rate interval',`${num(fridge.rate_interval_95.lower,6)}–${num(fridge.rate_interval_95.upper,6)} / hour`,'Model uncertainty range')}
    </div>
    <h2>Temperature process diagnostics</h2>
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
  </div></details>
  ${data.warnings.length?`<details class="warnings"><summary>Data limitations (${data.warnings.length})</summary><ul>${data.warnings.map(w=>`<li>${esc(w.message)}</li>`).join('')}</ul></details>`:''}`;
  return {overviewPanel,sections};
}

function scenarioPanel(scenario) {
  const alarm=scenario.observed_alarm;
  if(!alarm) return `<section class="scenario-result" aria-live="polite"><strong>${esc(scenario.label)} · Synthetic demo data</strong><p>${esc(scenario.description)}</p><p class="plain-note">No observed alarm. Temperatures remain within 1–6 °C and power is steady.</p></section>`;
  const recovery=alarm.recovery_hours==null?'Not observed':`${num(alarm.recovery_hours)} hours`;
  const excursion=alarm.excursion_duration_hours==null?'Not observed':`${num(alarm.excursion_duration_hours)} hours`;
  const alarmText=scenario.id==='degrading_refrigerator'
    ? `Observed temperature excursion · ${refrigeratorName(alarm.refrigerator_id)} marked for review`
    : `Observed temperature alarm during failed generator start · ${refrigeratorName(alarm.refrigerator_id)} marked for review`;
  const outage=alarm.outage_duration_hours==null?'':`<div><dt>Blackout duration</dt><dd>${num(alarm.outage_duration_hours)} hours</dd></div>`;
  return `<section class="scenario-result scenario-result--review" aria-live="polite"><strong>${esc(scenario.label)} · Synthetic demo data</strong><p>${esc(scenario.description)}</p><h2>${esc(alarmText)}</h2><dl>${outage}<div><dt>Time to first reading outside 1–6 °C</dt><dd>${minutes(alarm.hours_to_first_breach)}</dd></div><div><dt>Observed excursion duration</dt><dd>${esc(excursion)}</dd></div><div><dt>Cooling recovery time</dt><dd>${esc(recovery)}</dd></div><div><dt>Affected inventory value</dt><dd>${usd(alarm.affected_inventory_value_usd)}</dd></div></dl><p class="plain-note">This is an observed demo event. Statistical risk estimates appear separately below; this dashboard does not make product-disposition decisions.</p></section>`;
}

function render() {
  const data=state.data;
  const content=data?overview(data):null;
  const selectedRefrigerator=state.refrigeratorId||data?.selection.refrigerator_id||'';
  const fridgeOptions=state.availableRefrigerators.length
    ? state.availableRefrigerators.map(id=>`<option value="${esc(id)}"${id===selectedRefrigerator?' selected':''}>${esc(refrigeratorName(id))} (${esc(refrigeratorCode(id))})</option>`).join('')
    : `<option value="">${state.error?'Refrigerators unavailable':'Loading refrigerators…'}</option>`;
  const scenarioOptions=[['stable','Stable'],['degrading_refrigerator','Degrading Refrigerator'],['blackout_failed_generator','Blackout with Failed Generator']];
  root.innerHTML=`<main><header class="masthead"><div><p class="eyebrow">Storage · response · reliability</p><h1>BloodWatch</h1></div></header>
    <section class="controls" aria-label="Dashboard controls"><label>Demo scenario<select id="scenario" ${state.busy?'disabled':''}>${scenarioOptions.map(([id,label])=>`<option value="${id}"${id===state.scenario?' selected':''}>${label}</option>`).join('')}</select></label><label>Refrigerator<select id="refrigerator" ${state.busy?'disabled':''}>${fridgeOptions}</select></label><label>Temperature history<select id="window" ${state.busy?'disabled':''}>${[6,24].map(v=>`<option value="${v}"${v===state.windowHours?' selected':''}>Last ${v} hours</option>`).join('')}</select></label><label>Operating period<select id="horizon" ${state.busy?'disabled':''}>${[7,30,90].map(days=>`<option value="${days}"${days===state.horizonDays?' selected':''}>${days} days</option>`).join('')}</select></label></section>
    ${data?.scenario?scenarioPanel(data.scenario):''}
    ${data?`<p class="dataset-time"><strong>Synthetic dataset reference time:</strong> ${fullTimestamp(data.dataset.reference_time_utc)} <span>Demo data timestamp; it is not the computer's current time.</span></p>`:''}
    ${content?.overviewPanel||''}
    <div aria-live="polite">${state.error?`<p class="error" role="alert">${esc(state.error)}</p>`:state.busy?'<p class="loading">Updating analysis…</p>':content?content.sections:'<p class="loading">Loading dashboard…</p>'}</div>
    <footer>Synthetic educational data. Storage breaches require review.</footer></main>`;
  root.querySelector('#refrigerator').addEventListener('change',e=>{state.refrigeratorId=e.target.value;loadDashboard();});
  root.querySelector('#scenario').addEventListener('change',e=>{state.scenario=e.target.value;loadDashboard();});
  root.querySelector('#window').addEventListener('change',e=>{state.windowHours=Number(e.target.value);loadDashboard();});
  root.querySelector('#horizon')?.addEventListener('change',e=>{state.horizonDays=Number(e.target.value);loadDashboard();});
}

async function loadDashboard() {
  const request=++state.request;
  state.busy=true; state.error=''; render();
  const params=new URLSearchParams({horizon_operating_days:String(state.horizonDays),temperature_window_hours:String(state.windowHours)});
  params.set('scenario',state.scenario);
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
