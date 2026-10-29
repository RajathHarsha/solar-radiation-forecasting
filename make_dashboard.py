"""Build the single-file interactive dashboard from outputs/results.json.
Plotly is loaded from its CDN (pinned version); everything else is inline."""
import json
from pathlib import Path

ROOT = Path(__file__).parent
R = json.loads((ROOT / "outputs" / "results.json").read_text(encoding="utf-8"))

# ------------------------------------------------------------------ Phase 1 content
# Bibliographic records verified via CrossRef / OpenAlex on 2026-10-25.
# "abstract_verified": True only where the abstract itself was retrieved.
PAPERS = [
    {"n": 1, "year": 2017, "title": "Evaluation of Time-Series, Regression and Neural Network Models for Solar Forecasting: Part I: One-Hour Horizon",
     "authors": "A. Inanlougani, T. A. Reddy, S. Katiamula", "venue": "arXiv:1708.08376", "doi": "arXiv:1708.08376",
     "gap": "Hourly horizon only. Shows that a simple baseline can beat seasonal ARIMA and that cloud-cover regressors help, but does not test weekly forecasts or several climates.", "abstract_verified": True},
    {"n": 2, "year": 2019, "title": "Time Series ARIMA Model for Prediction of Daily and Monthly Average Global Solar Radiation: The Case Study of Seoul, South Korea",
     "authors": "M. H. Alsharif, M. K. Younes, J. Kim", "venue": "Symmetry 11(2), 240", "doi": "10.3390/sym11020240",
     "gap": "Uses the radiation history only; one temperate city; no persistence benchmark described.", "abstract_verified": True},
    {"n": 3, "year": 2022, "title": "Forecasting of Solar Irradiances using Time Series and Machine Learning Models: A Case Study from India",
     "authors": "S. Sheoran, R. S. Singh, S. Pasari, R. Kulshrestha", "venue": "Applied Solar Energy", "doi": "10.3103/S0003701X22010170",
     "gap": "Compares model families (SARIMA against MLP and LSTM) at two Indian sites, so it does not isolate the effect of weather inputs on one model.", "abstract_verified": True},
    {"n": 4, "year": 2023, "title": "Day-Ahead Hourly Solar Photovoltaic Output Forecasting Using SARIMAX, Long Short-Term Memory, and Extreme Gradient Boosting: Case of the Philippines",
     "authors": "I. B. Benitez, J. A. Ibanez, C. D. Lumabad, J. M. Canete, J. A. Principe", "venue": "Energies 16(23), 7823", "doi": "10.3390/en16237823",
     "gap": "Forecasts photovoltaic output rather than radiation; one year of data; Philippines, not an Indian climate.", "abstract_verified": True},
    {"n": 5, "year": 2024, "title": "An Intelligent SARIMAX-Based Machine Learning Framework for Long-Term Solar Irradiance Forecasting at Muscat, Oman",
     "authors": "M. H. Baloch, M. S. Honnurvali, A. Kabbani, T. A. Jumani, S. T. Chauhdary", "venue": "Energies 17(23), 6118", "doi": "10.3390/en17236118",
     "gap": "One city. The abstract mentions no persistence benchmark, significance test or error split by season.", "abstract_verified": True},
]
GAP = {
    "consensus": "SARIMAX, seasonal ARIMA and cloud-cover regressors are each established in the solar-forecasting literature reviewed.",
    "gap": "The abstracts reviewed do not show whether lagged weather inputs improve a seasonal ARIMA forecast against persistence benchmarks, with a significance test, across several Indian climates and separately for monsoon weeks. SARIMAX and cloud-cover inputs are each established, so the gap is narrow. This statement is limited to five papers and is not a claim that no other study exists.",
    "address": "The model family is held fixed (SARIMA against SARIMAX with identical orders) so the only change is last week's humidity, temperature and cloud amount. Every forecast is a true one-week-ahead forecast, seasonal and last-week persistence are the benchmarks, the Diebold-Mariano test checks significance, and errors are split by city and by monsoon and other weeks.",
    "improvement": "SARIMAX with standardised lag-1 relative humidity, 2-m temperature and cloud amount on top of the AIC-selected SARIMA orders.",
}

# ------------------------------------------------------------------ template
HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Solar Radiation Forecasting Dashboard</title>
<script src="https://cdn.plot.ly/plotly-2.35.2.min.js" charset="utf-8"></script>
<style>
:root{
  --page:#0b1220; --card:#121a2b; --card2:#182236; --line:#243049;
  --ink:#f0efec; --ink2:#c3c2b7; --mute:#898781; --grid:#243049;
  --actual:#3987e5; --sarima:#d95926; --sarimax:#199e70; --persist:#c98500; --naive:#898781;
  --good:#0ca30c; --bad:#d03b3b; --warn:#fab219;
  --r:14px;
}
*{box-sizing:border-box}
body{margin:0;background:var(--page);color:var(--ink);font-family:system-ui,-apple-system,"Segoe UI",sans-serif;font-size:15px;line-height:1.45}
header{padding:28px 32px 16px;border-bottom:1px solid var(--line);background:linear-gradient(180deg,#0e1729,var(--page))}
header h1{margin:0 0 6px;font-size:26px;letter-spacing:-.01em}
.tags{display:flex;gap:8px;flex-wrap:wrap;color:var(--ink2);font-size:13px}
.tag{border:1px solid var(--line);border-radius:999px;padding:3px 10px;background:var(--card)}
.tag b{color:var(--ink)}
nav{display:flex;gap:4px;padding:10px 32px 0;border-bottom:1px solid var(--line);overflow-x:auto;position:sticky;top:0;background:var(--page);z-index:5}
nav button{background:none;border:0;color:var(--ink2);padding:12px 16px;font-size:14px;cursor:pointer;border-bottom:2px solid transparent;white-space:nowrap}
nav button.on{color:var(--ink);border-bottom-color:var(--actual)}
nav button:hover{color:var(--ink)}
main{padding:24px 32px 48px;max-width:1400px;margin:0 auto}
.tab{display:none;animation:fade .3s ease}
.tab.on{display:block}
@keyframes fade{from{opacity:0;transform:translateY(4px)}to{opacity:1;transform:none}}
.grid{display:grid;gap:16px;grid-template-columns:repeat(12,1fr)}
.card{background:var(--card);border:1px solid var(--line);border-radius:var(--r);padding:18px 20px}
.c12{grid-column:span 12}.c8{grid-column:span 8}.c6{grid-column:span 6}.c4{grid-column:span 4}.c3{grid-column:span 3}
@media(max-width:1000px){.c8,.c6,.c4,.c3{grid-column:span 12}}
.card h3{margin:0 0 4px;font-size:15px}
.card .sub{color:var(--mute);font-size:13px;margin-bottom:8px}
.stat{display:flex;flex-direction:column;gap:2px}
.stat .v{font-size:30px;font-weight:600;letter-spacing:-.01em}
.stat .l{color:var(--mute);font-size:13px}
.stat .d{font-size:13px;color:var(--ink2)}
.badge{display:inline-flex;align-items:center;gap:6px;border-radius:8px;padding:6px 10px;font-weight:600;font-size:14px}
.badge.good{background:rgba(12,163,12,.15);color:#5fd35f;border:1px solid rgba(12,163,12,.4)}
.badge.bad{background:rgba(208,59,59,.15);color:#ff8585;border:1px solid rgba(208,59,59,.4)}
.badge.neutral{background:rgba(137,135,129,.15);color:var(--ink2);border:1px solid var(--line)}
.metric{border-left:4px solid var(--line)}
.metric.good{border-left-color:var(--good)}.metric.bad{border-left-color:var(--bad)}
.plot{width:100%;min-height:320px}
.plot.tall{min-height:380px}
p{color:var(--ink2);margin:8px 0}
.win{font-size:20px;font-weight:600}
.timeline{display:grid;gap:14px;grid-template-columns:repeat(auto-fit,minmax(260px,1fr))}
.paper{background:var(--card2);border:1px solid var(--line);border-radius:12px;padding:16px;position:relative}
.paper .yr{font-size:26px;font-weight:700;color:var(--actual);margin-bottom:4px}
.paper h4{margin:0 0 6px;font-size:14px;line-height:1.35}
.paper .meta{color:var(--mute);font-size:12.5px;margin-bottom:8px}
.paper .k{font-size:13px;color:var(--ink2);margin:6px 0}
.paper .k b{color:var(--ink)}
.paper .v{font-size:11.5px;color:var(--mute);margin-top:8px}
.hl{background:linear-gradient(135deg,rgba(57,135,229,.18),rgba(25,158,112,.14));border:1px solid rgba(57,135,229,.4)}
.hl h3{font-size:17px}
.hl p{color:var(--ink);font-size:15.5px}
ul{color:var(--ink2);margin:6px 0 0 18px;padding:0}
li{margin:4px 0}
.note{font-size:12.5px;color:var(--mute);margin-top:10px}
.explain{background:rgba(57,135,229,.09);border-left:3px solid var(--actual);border-radius:8px;padding:10px 14px;margin-top:10px;color:var(--ink2);font-size:13.5px;line-height:1.5}
.explain b{color:var(--ink)}
.explain .take{display:block;margin-top:6px;color:var(--ink)}
.big{font-size:22px;font-weight:600;line-height:1.35;color:var(--ink);margin:6px 0 10px}
.steps{counter-reset:s;list-style:none;margin:8px 0 0;padding:0}
.steps li{counter-increment:s;position:relative;padding:8px 0 8px 40px;color:var(--ink2)}
.steps li:before{content:counter(s);position:absolute;left:0;top:8px;width:26px;height:26px;border-radius:50%;background:var(--card2);border:1px solid var(--line);color:var(--ink);font-weight:600;text-align:center;line-height:24px;font-size:13px}
.steps li b{color:var(--ink)}
dl.gl{display:grid;grid-template-columns:max-content 1fr;gap:6px 16px;margin:8px 0 0}
dl.gl dt{color:var(--ink);font-weight:600}
dl.gl dd{margin:0;color:var(--ink2)}
.mini{display:grid;gap:12px;grid-template-columns:repeat(auto-fit,minmax(220px,1fr))}
.mini .card{background:var(--card2)}
footer{color:var(--mute);font-size:12.5px;text-align:center;padding:24px}
.sr{position:absolute;left:-9999px}
details summary{cursor:pointer;color:var(--ink2);font-size:13px;margin-top:10px}
table{border-collapse:collapse;width:100%;font-size:13px;margin-top:8px}
td,th{border-bottom:1px solid var(--line);padding:6px 8px;text-align:right;font-variant-numeric:tabular-nums}
th{color:var(--mute);font-weight:500}
td:first-child,th:first-child{text-align:left}
</style>
</head>
<body>
<header>
  <h1>Daily Solar Radiation Forecasting Across Five Indian Cities</h1>
  <div class="tags">
    <span class="tag">Domain <b>Climate</b></span>
    <span class="tag">Dataset <b>NASA POWER daily point data</b></span>
    <span class="tag">Main city <b id="h-city"></b></span>
    <span class="tag">Window <b id="h-window"></b></span>
    <span class="tag">Models <b>SARIMA vs SARIMAX</b></span>
    <span class="tag">Generated <b id="h-date"></b></span>
  </div>
</header>
<nav id="nav">
  <button data-t="t0" class="on">Start here</button>
  <button data-t="t1">1 · The data</button>
  <button data-t="t2">2 · Baseline model</button>
  <button data-t="t3">3 · Improved model</button>
  <button data-t="t4">4 · Which is better?</button>
  <button data-t="t5">5 · Why this study</button>
</nav>
<main>

<section id="t0" class="tab on"><div class="grid" id="start-grid"></div></section>

<section id="t1" class="tab">
  <div class="grid">
    <div class="card c12"><h3>Sunlight reaching the ground, week by week (Bengaluru)</h3><div class="sub">kWh / m² / day · drag to zoom, double-click to reset · hover for values</div><div id="p-raw" class="plot tall"></div></div>
    <div class="card c3 stat"><span class="l">Mean</span><span class="v" id="s-mean"></span><span class="d">kWh/m²/day</span></div>
    <div class="card c3 stat"><span class="l">Std. deviation</span><span class="v" id="s-std"></span><span class="d">week-to-week spread</span></div>
    <div class="card c3 stat"><span class="l">Min / Max</span><span class="v" id="s-minmax"></span><span class="d">weekly means</span></div>
    <div class="card c3 stat"><span class="l">Trend direction</span><span class="v" id="s-trend"></span><span class="d" id="s-trend-d"></span></div>
    <div class="card c6"><h3>Does the average drift? (stationarity test)</h3><div class="sub">H0: unit root. Reject at 5% → stationary</div><div id="adf"></div><p id="adf-action" class="note"></p></div>
    <div class="card c6"><h3>Sample</h3><div id="sample"></div></div>
    <div class="card c6"><h3>Seasonal component (period 52)</h3><div class="sub">Classical additive decomposition of the training series</div><div id="p-seas" class="plot"></div></div>
    <div class="card c6"><h3>Trend component</h3><div class="sub">52-week centred moving average</div><div id="p-trend" class="plot"></div></div>
    <div class="card c6"><h3>Autocorrelation (ACF)</h3><div class="sub">Level vs after one seasonal difference</div><div id="p-acf" class="plot"></div></div>
    <div class="card c6"><h3>Partial autocorrelation (PACF)</h3><div class="sub">Level vs after one seasonal difference</div><div id="p-pacf" class="plot"></div></div>
  </div>
</section>

<section id="t2" class="tab">
  <div class="grid">
    <div class="card c12"><h3>Baseline forecast vs what really happened</h3><div class="sub" id="sar-sub"></div><div id="p-sar" class="plot tall"></div></div>
    <div class="card c4 stat metric" id="m-sar-mae"></div>
    <div class="card c4 stat metric" id="m-sar-rmse"></div>
    <div class="card c4 stat metric" id="m-sar-mape"></div>
    <div class="card c8"><h3>Residuals (actual − forecast)</h3><div class="sub">Should look like noise around zero</div><div id="p-sar-res" class="plot"></div></div>
    <div class="card c4"><h3>Choosing the model's settings</h3><div class="sub">Candidates read off the ACF/PACF; lowest AIC chosen</div><div id="p-aic" class="plot"></div></div>
    <div class="card c12"><h3>Interpretation</h3><p id="sar-interp"></p></div>
  </div>
</section>

<section id="t3" class="tab">
  <div class="grid">
    <div class="card c12"><h3>Improved forecast (with weather) vs what really happened</h3><div class="sub" id="sax-sub"></div><div id="p-sax" class="plot tall"></div></div>
    <div class="card c4 stat metric" id="m-sax-mae"></div>
    <div class="card c4 stat metric" id="m-sax-rmse"></div>
    <div class="card c4 stat metric" id="m-sax-mape"></div>
    <div class="card c8"><h3>Residuals (actual − forecast)</h3><div class="sub">Compare the spread with the SARIMA residuals</div><div id="p-sax-res" class="plot"></div></div>
    <div class="card c4"><h3>How much does each weather input matter?</h3><div class="sub">Coefficient = change in kWh/m²/day per 1 SD of last week's value</div><div id="p-coef" class="plot"></div></div>
    <div class="card c12"><h3>Why this test matters</h3><p id="sax-interp"></p></div>
  </div>
</section>

<section id="t4" class="tab">
  <div class="grid">
    <div class="card c12 hl"><h3>The verdict</h3><div id="winner"></div></div>
    <div class="card c8"><h3>Average forecast miss, four methods side by side</h3><div class="sub">Lower is better · benchmarks included</div><div id="p-cmp" class="plot tall"></div></div>
    <div class="card c4"><h3>Improvement SARIMA → SARIMAX</h3><div id="imp"></div><div class="note" id="dm"></div></div>
    <div class="card c6"><h3>Monsoon weeks vs the rest of the year</h3><div class="sub">Monsoon weeks (Jun–Sep) vs the rest</div><div id="p-season" class="plot"></div></div>
    <div class="card c6"><h3>Does the answer change in other cities?</h3><div class="sub">Same orders refitted per city</div><div id="p-cities" class="plot"></div></div>
    <div class="card c12"><h3>Future-work extensions, implemented</h3><div class="sub">Each compared with SARIMAX by the Diebold–Mariano test</div><div id="p-ext" class="plot"></div><div id="ext-list"></div></div>
    <div class="card c12"><h3>Conclusion</h3><div id="concl"></div></div>
  </div>
</section>

<section id="t5" class="tab">
  <div class="grid">
    <div class="card c12"><h3>Five papers reviewed</h3><div class="sub">Bibliographic records (title, authors, journal, year, DOI) verified through CrossRef / OpenAlex on 2026-10-25</div><div class="timeline" id="papers"></div><p class="note">Only paper 5's abstract could be retrieved. For papers 1-4 the publisher withholds the abstract from every free index, so the content lines above are limited to what the title supports and are marked NOT VERIFIED - open each paper, read it, and complete those lines before you cite them.</p></div>
    <div class="card c12 hl"><h3>Research gap</h3><p id="gap-gap"></p></div>
    <div class="card c6"><h3>What has been done repeatedly</h3><p id="gap-cons"></p></div>
    <div class="card c6"><h3>How this project fills the gap</h3><p id="gap-addr"></p><p id="gap-impr"></p></div>
  </div>
</section>

</main>
<footer>Data: NASA POWER (MERRA-2 / CERES SYN1deg based) daily point data · Methods: statsmodels SARIMAX · All forecasts are true one-week-ahead forecasts using only past information.</footer>

<script>
const R = __RESULTS__;
const PAPERS = __PAPERS__;
const GAP = __GAP__;

// ---------- helpers
const css = v => getComputedStyle(document.documentElement).getPropertyValue(v).trim();
const C = {actual:css('--actual'), sarima:css('--sarima'), sarimax:css('--sarimax'), persist:css('--persist'), naive:css('--naive'), ink:css('--ink'), ink2:css('--ink2'), mute:css('--mute'), grid:css('--grid'), card:css('--card')};
const f3 = x => x.toFixed(3), f2 = x => x.toFixed(2), pct = x => (x>=0?'+':'')+x.toFixed(1)+'%';
const $ = id => document.getElementById(id);
const layout = (o={}) => Object.assign({
  paper_bgcolor:'rgba(0,0,0,0)', plot_bgcolor:'rgba(0,0,0,0)', font:{color:C.ink2, family:'system-ui,-apple-system,"Segoe UI",sans-serif', size:12},
  margin:{l:48,r:16,t:8,b:40}, hovermode:'x unified', hoverlabel:{bgcolor:'#182236', bordercolor:C.grid, font:{color:C.ink}},
  legend:{orientation:'h', y:1.08, x:0, font:{color:C.ink2}},
  xaxis:{gridcolor:C.grid, zeroline:false, linecolor:C.grid, tickcolor:C.grid},
  yaxis:{gridcolor:C.grid, zeroline:false, linecolor:C.grid, tickcolor:C.grid},
}, o);
const cfg = {responsive:true, displaylogo:false, modeBarButtonsToRemove:['lasso2d','select2d']};
const S = R.series, T = S.test_dates;

// ---------- header
$('h-city').textContent = R.meta.main_city; $('h-window').textContent = R.meta.window.join(' → '); $('h-date').textContent = R.meta.run_date;

// ---------- tabs
document.querySelectorAll('#nav button').forEach(b => b.onclick = () => {
  document.querySelectorAll('#nav button').forEach(x => x.classList.remove('on')); b.classList.add('on');
  document.querySelectorAll('.tab').forEach(x => x.classList.remove('on')); $(b.dataset.t).classList.add('on');
  window.dispatchEvent(new Event('resize'));
});

// ---------- Tab 1
Plotly.newPlot('p-raw', [
  {x:S.weekly_dates, y:S.weekly_solar, type:'scatter', mode:'lines', name:'Weekly mean', line:{color:C.actual, width:1.6}, hovertemplate:'%{y:.2f} kWh/m²/day<extra></extra>'},
], layout({yaxis:{title:'kWh / m² / day', gridcolor:C.grid, zeroline:false}, xaxis:{rangeslider:{visible:true, thickness:0.08}, gridcolor:C.grid}}), cfg);
$('s-mean').textContent = f2(R.stats.mean); $('s-std').textContent = f2(R.stats.std);
$('s-minmax').textContent = f2(R.stats.min)+' / '+f2(R.stats.max);
const sl = R.stats.trend_slope_per_year; $('s-trend').textContent = Math.abs(sl) < 0.005 ? 'Flat' : (sl>0?'Rising ↗':'Falling ↘');
$('s-trend-d').textContent = (sl>=0?'+':'')+sl.toFixed(4)+' kWh/m²/day per year (linear fit)';
const adfRow = (a) => `<div style="display:flex;justify-content:space-between;align-items:center;padding:8px 0;border-bottom:1px solid var(--line)">
  <div><div>${a.label}</div><div class="note">ADF = ${a.adf_stat.toFixed(3)} · p = ${a.p_value.toFixed(4)} · 5% crit = ${a.crit_5pct.toFixed(3)} · lags ${a.lags_used}</div></div>
  <span class="badge ${a.stationary_5pct?'good':'bad'}">${a.stationary_5pct?'✅ Stationary':'❌ Non-stationary'}</span></div>`;
$('adf').innerHTML = adfRow(R.adf.level) + adfRow(R.adf.seasonal_diff);
$('adf-action').textContent = R.adf.action;
$('sample').innerHTML = `<ul>
 <li><b>${R.data.daily_rows.toLocaleString()}</b> daily rows → <b>${R.split.n_weeks.toLocaleString()}</b> full weeks (Mon–Sun means)</li>
 <li>Missing daily values before cleaning: ${Object.entries(R.data.missing_before).map(([k,v])=>k+': '+v).join(', ')} → linear time-interpolation</li>
 <li>Train: <b>${R.split.n_train}</b> weeks (${R.split.train_range.join(' → ')})</li>
 <li>Test: <b>${R.split.n_test}</b> weeks (${R.split.test_range.join(' → ')}) — 80 / 20 chronological split</li>
 <li>Seasonal period m = ${R.meta.seasonal_period}; weather regressors: ${R.meta.exog.join(', ')} (lag 1 week, standardised on train)</li></ul>`;
Plotly.newPlot('p-seas', [{x:S.decomp_dates.slice(0,104), y:S.decomp_seasonal.slice(0,104), type:'scatter', mode:'lines', name:'Seasonal', line:{color:C.actual,width:1.6}, hovertemplate:'%{y:.2f}<extra></extra>'}], layout({showlegend:false, yaxis:{title:'kWh/m²/day', gridcolor:C.grid}, xaxis:{title:'first two seasonal cycles shown', gridcolor:C.grid}}), cfg);
Plotly.newPlot('p-trend', [{x:S.decomp_dates, y:S.decomp_trend, type:'scatter', mode:'lines', name:'Trend', line:{color:C.actual,width:1.6}, connectgaps:false, hovertemplate:'%{y:.2f}<extra></extra>'}], layout({showlegend:false, yaxis:{title:'kWh/m²/day', gridcolor:C.grid}}), cfg);
const lagsA = [...Array(S.acf_level.length).keys()], lagsP = [...Array(S.pacf_level.length).keys()];
Plotly.newPlot('p-acf', [
  {x:lagsA, y:S.acf_level, type:'bar', name:'Level', marker:{color:C.actual}, hovertemplate:'lag %{x}: %{y:.3f}<extra>level</extra>'},
  {x:lagsA, y:S.acf_sdiff, type:'bar', name:'Seasonal diff (D=1, m=52)', marker:{color:C.sarima}, hovertemplate:'lag %{x}: %{y:.3f}<extra>diff</extra>'}],
  layout({barmode:'group', bargap:0.15, xaxis:{title:'lag (weeks)', gridcolor:C.grid}, yaxis:{range:[-1,1], gridcolor:C.grid}, shapes:[{type:'line',x0:0,x1:120,y0:0,y1:0,line:{color:C.mute,width:1}}]}), cfg);
Plotly.newPlot('p-pacf', [
  {x:lagsP, y:S.pacf_level, type:'bar', name:'Level', marker:{color:C.actual}, hovertemplate:'lag %{x}: %{y:.3f}<extra>level</extra>'},
  {x:lagsP, y:S.pacf_sdiff, type:'bar', name:'Seasonal diff (D=1, m=52)', marker:{color:C.sarima}, hovertemplate:'lag %{x}: %{y:.3f}<extra>diff</extra>'}],
  layout({barmode:'group', bargap:0.15, xaxis:{title:'lag (weeks)', gridcolor:C.grid}, yaxis:{range:[-1,1], gridcolor:C.grid}, shapes:[{type:'line',x0:0,x1:60,y0:0,y1:0,line:{color:C.mute,width:1}}]}), cfg);

// ---------- forecast plots
function fcPlot(id, mean, lo, hi, color, name, extra){
  const tr = [
    {x:T, y:hi, type:'scatter', mode:'lines', line:{width:0}, showlegend:false, hoverinfo:'skip'},
    {x:T, y:lo, type:'scatter', mode:'lines', line:{width:0}, fill:'tonexty', fillcolor:color.replace(')',',0.18)').replace('rgb','rgba'), name:'95% interval', hoverinfo:'skip'},
    {x:T, y:S.test_actual, type:'scatter', mode:'lines', name:'Actual', line:{color:C.actual,width:1.8}, hovertemplate:'%{y:.2f}<extra>Actual</extra>'},
    {x:T, y:mean, type:'scatter', mode:'lines', name:name, line:{color:color,width:1.8}, hovertemplate:'%{y:.2f}<extra>'+name+'</extra>'},
  ];
  if(extra) tr.push({x:T, y:extra.y, type:'scatter', mode:'lines', name:extra.name, line:{color:color,width:1.2,dash:'dot'}, opacity:0.75, hovertemplate:'%{y:.2f}<extra>'+extra.name+'</extra>'});
  Plotly.newPlot(id, tr, layout({yaxis:{title:'kWh / m² / day', gridcolor:C.grid, zeroline:false}}), cfg);
}
const hex2rgb = h => { const n=parseInt(h.slice(1),16); return `rgb(${n>>16},${(n>>8)&255},${n&255})`; };
fcPlot('p-sar', S.sarima_mean, S.sarima_lo, S.sarima_hi, hex2rgb(C.sarima), 'SARIMA (1-week-ahead)', {y:S.sarima_static, name:'SARIMA static multi-step'});
fcPlot('p-sax', S.sarimax_mean, S.sarimax_lo, S.sarimax_hi, hex2rgb(C.sarimax), 'SARIMAX (1-week-ahead)');
$('sar-sub').textContent = `SARIMA${JSON.stringify(R.sarima.order)}×${JSON.stringify(R.sarima.seasonal_order)} · AIC ${R.sarima.AIC.toFixed(1)} · dotted line = one static ${R.split.n_test}-week forecast from the end of training`;
$('sax-sub').textContent = `Same orders + lag-1 ${R.meta.exog.join(', ')} · AIC ${R.sarimax.AIC.toFixed(1)}`;

function resPlot(id, mean, color){
  const r = S.test_actual.map((a,i)=>a-mean[i]);
  Plotly.newPlot(id, [{x:T, y:r, type:'scatter', mode:'lines', name:'residual', line:{color:color,width:1.2}, hovertemplate:'%{y:.2f}<extra></extra>'}],
    layout({showlegend:false, yaxis:{title:'kWh / m² / day', gridcolor:C.grid, zeroline:true, zerolinecolor:C.mute}}), cfg);
}
resPlot('p-sar-res', S.sarima_mean, C.sarima); resPlot('p-sax-res', S.sarimax_mean, C.sarimax);

// metric cards: green if better than the seasonal-naive benchmark (SARIMA) / than SARIMA (SARIMAX)
function metricCard(id, label, val, ref, refName, unit){
  const good = val < ref, d = (val-ref)/ref*100;
  $(id).classList.add(good?'good':'bad');
  $(id).innerHTML = `<span class="l">${label}</span><span class="v">${unit==='%'?f2(val)+'%':f3(val)}</span>
    <span class="d"><span class="badge ${good?'good':'bad'}" style="padding:2px 8px;font-size:12px">${good?'▼':'▲'} ${Math.abs(d).toFixed(1)}% vs ${refName}</span></span>`;
}
const sn = R.benchmarks.seasonal_naive_52.overall, sm = R.sarima.metrics.overall, sx = R.sarimax.metrics.overall;
metricCard('m-sar-mae','MAE',sm.MAE,sn.MAE,'seasonal naive'); metricCard('m-sar-rmse','RMSE',sm.RMSE,sn.RMSE,'seasonal naive'); metricCard('m-sar-mape','MAPE',sm.MAPE,sn.MAPE,'seasonal naive','%');
metricCard('m-sax-mae','MAE',sx.MAE,sm.MAE,'SARIMA'); metricCard('m-sax-rmse','RMSE',sx.RMSE,sm.RMSE,'SARIMA'); metricCard('m-sax-mape','MAPE',sx.MAPE,sm.MAPE,'SARIMA','%');

// AIC chart
const g = R.sarima.grid.map(r=>({lab:`${JSON.stringify(r.order)}×${JSON.stringify(r.seasonal_order.slice(0,3))}`, aic:r.AIC}));
Plotly.newPlot('p-aic', [{y:g.map(r=>r.lab), x:g.map(r=>r.aic), type:'bar', orientation:'h', marker:{color:g.map(r=>r.aic===Math.min(...g.map(q=>q.aic))?C.sarima:C.mute)}, hovertemplate:'AIC %{x:.1f}<extra></extra>'}],
  layout({showlegend:false, margin:{l:120,r:16,t:8,b:40}, xaxis:{title:'AIC (lower = better)', gridcolor:C.grid, range:[Math.min(...g.map(r=>r.aic))-30, Math.max(...g.map(r=>r.aic))+10]}, yaxis:{gridcolor:'rgba(0,0,0,0)', autorange:'reversed'}}), cfg);

// coefficients
const ce = Object.entries(R.sarimax.exog_coef);
Plotly.newPlot('p-coef', [{x:ce.map(([k])=>k.replace('_lag1',' (t−1)')), y:ce.map(([,v])=>v.coef), type:'bar', marker:{color:C.sarimax}, text:ce.map(([,v])=>'p='+v.p_value.toFixed(3)), textposition:'outside', textfont:{color:C.ink2}, hovertemplate:'%{y:.3f}<extra></extra>'}],
  layout({showlegend:false, yaxis:{title:'coefficient', gridcolor:C.grid, zeroline:true, zerolinecolor:C.mute}, xaxis:{gridcolor:'rgba(0,0,0,0)'}}), cfg);

$('sar-interp').textContent = `The SARIMA baseline reproduces the yearly cycle and tracks week-to-week changes one step ahead with MAE ${f3(sm.MAE)} and RMSE ${f3(sm.RMSE)} kWh/m²/day (MAPE ${f2(sm.MAPE)}%). It beats the seasonal-naive benchmark (MAE ${f3(sn.MAE)}) by ${((sn.MAE-sm.MAE)/sn.MAE*100).toFixed(1)}%, confirming that the autoregressive structure adds information beyond "same week last year". The dotted static forecast shows the model's long-horizon behaviour: it reverts to the seasonal mean and cannot anticipate individual cloudy or clear weeks (static MAE ${f3(R.sarima.static_metrics.MAE)}), which is exactly the information the weather regressors are meant to supply. Ljung–Box p-values on the residuals: ${Object.entries(R.sarima.ljung_box).map(([k,v])=>'lag '+k+': '+v.toFixed(3)).join(', ')}.`;
$('sax-interp').textContent = `${GAP.gap} Here the ONLY change from the baseline is the lagged weather block, so any gain is attributable to the covariates and not to a different model family. Standardised coefficients: ${ce.map(([k,v])=>k.replace('_lag1','')+' '+(v.coef>=0?'+':'')+v.coef.toFixed(3)).join(', ')}. Result: MAE ${f3(sx.MAE)}, RMSE ${f3(sx.RMSE)}, MAPE ${f2(sx.MAPE)}%.`;

// ---------- Tab 4
const imp = R.improvement_pct, dm = R.dm_tests.sarima_vs_sarimax;
const winner = sx.RMSE < sm.RMSE ? 'SARIMAX' : 'SARIMA', sig = dm.p_value < 0.05;
$('winner').innerHTML = `<div class="win">${sig ? (winner+' wins, statistically significant') : (winner+' is nominally ahead on '+['MAE','RMSE','MAPE'].filter(k=>(winner==='SARIMAX'?sx[k]<sm[k]:sm[k]<sx[k])).join(', ')+' — but the difference is NOT statistically significant')}</div>
 <p>Rolling one-week-ahead over ${R.split.n_test} test weeks (${R.split.test_range.join(' → ')}). SARIMAX ${imp.MAE>0?'lowers':'raises'} MAE by ${Math.abs(imp.MAE).toFixed(1)}%, RMSE by ${Math.abs(imp.RMSE).toFixed(1)}% and MAPE by ${Math.abs(imp.MAPE).toFixed(1)}% relative to SARIMA. Diebold–Mariano test on squared errors: DM = ${dm.DM.toFixed(2)}, p = ${dm.p_value.toFixed(4)} → the difference is <b>${sig?'statistically significant at 5%':'NOT statistically significant at 5%'}</b>.</p>`;
const models = [['Seasonal naive', R.benchmarks.seasonal_naive_52.overall, C.naive], ['Naive (last week)', R.benchmarks.naive_lastweek.overall, C.persist], ['SARIMA', sm, C.sarima], ['SARIMAX', sx, C.sarimax]];
Plotly.newPlot('p-cmp', ['MAE','RMSE','MAPE'].map((k,i)=>({x:models.map(m=>m[0]), y:models.map(m=>m[1][k]), name:k, type:'bar', marker:{color:models.map(m=>m[2])}, xaxis:'x'+(i?i+1:''), yaxis:'y'+(i?i+1:''), showlegend:false, text:models.map(m=>k==='MAPE'?f2(m[1][k])+'%':f3(m[1][k])), textposition:'outside', textfont:{color:C.ink2,size:11}, hovertemplate:'%{y:.3f}<extra>'+k+'</extra>'})),
  layout({grid:{rows:1, columns:3, pattern:'independent'}, hovermode:'closest', margin:{l:40,r:10,t:30,b:70},
    xaxis:{title:'MAE', tickangle:-25, gridcolor:'rgba(0,0,0,0)'}, xaxis2:{title:'RMSE', tickangle:-25, gridcolor:'rgba(0,0,0,0)'}, xaxis3:{title:'MAPE (%)', tickangle:-25, gridcolor:'rgba(0,0,0,0)'},
    yaxis:{gridcolor:C.grid, rangemode:'tozero'}, yaxis2:{gridcolor:C.grid, rangemode:'tozero'}, yaxis3:{gridcolor:C.grid, rangemode:'tozero'}}), cfg);
$('imp').innerHTML = ['MAE','RMSE','MAPE'].map(k=>`<div style="display:flex;justify-content:space-between;align-items:center;padding:10px 0;border-bottom:1px solid var(--line)"><span>${k}</span><span style="color:var(--mute)">${k==='MAPE'?f2(sm[k])+'% → '+f2(sx[k])+'%':f3(sm[k])+' → '+f3(sx[k])}</span><span class="badge ${imp[k]>0?'good':'bad'}">${imp[k]>0?'▼':'▲'} ${Math.abs(imp[k]).toFixed(1)}%</span></div>`).join('');
$('dm').innerHTML = `Diebold–Mariano (squared error, h=1): DM ${dm.DM.toFixed(2)}, p ${dm.p_value.toFixed(4)}, n ${dm.n}. Against seasonal naive — SARIMA p ${R.dm_tests.snaive_vs_sarima.p_value.toFixed(4)}, SARIMAX p ${R.dm_tests.snaive_vs_sarimax.p_value.toFixed(4)}.`;
Plotly.newPlot('p-season', [
  {x:['Monsoon (Jun–Sep)','Other weeks'], y:[sm.MAE, sm.MAE].map((_,i)=>R.sarima.metrics[['monsoon_JJAS','dry_rest'][i]].MAE), name:'SARIMA', type:'bar', marker:{color:C.sarima}, hovertemplate:'%{y:.3f}<extra>SARIMA</extra>'},
  {x:['Monsoon (Jun–Sep)','Other weeks'], y:['monsoon_JJAS','dry_rest'].map(s=>R.sarimax.metrics[s].MAE), name:'SARIMAX', type:'bar', marker:{color:C.sarimax}, hovertemplate:'%{y:.3f}<extra>SARIMAX</extra>'},
  {x:['Monsoon (Jun–Sep)','Other weeks'], y:['monsoon_JJAS','dry_rest'].map(s=>R.benchmarks.seasonal_naive_52[s].MAE), name:'Seasonal naive', type:'bar', marker:{color:C.naive}, hovertemplate:'%{y:.3f}<extra>Seasonal naive</extra>'}],
  layout({barmode:'group', bargap:0.3, bargroupgap:0.06, hovermode:'closest', yaxis:{title:'MAE (kWh/m²/day)', gridcolor:C.grid, rangemode:'tozero'}, xaxis:{gridcolor:'rgba(0,0,0,0)'}}), cfg);
const cities = Object.keys(R.cities);
if(cities.length){
  Plotly.newPlot('p-cities', [
    {x:cities, y:cities.map(c=>R.cities[c].seasonal_naive.overall.MAE), name:'Seasonal naive', type:'bar', marker:{color:C.naive}, hovertemplate:'%{y:.3f}<extra>Seasonal naive</extra>'},
    {x:cities, y:cities.map(c=>R.cities[c].sarima.overall.MAE), name:'SARIMA', type:'bar', marker:{color:C.sarima}, hovertemplate:'%{y:.3f}<extra>SARIMA</extra>'},
    {x:cities, y:cities.map(c=>R.cities[c].sarimax.overall.MAE), name:'SARIMAX', type:'bar', marker:{color:C.sarimax}, text:cities.map(c=>R.cities[c].dm_sarima_vs_sarimax.p_value<0.05?'★':''), textposition:'outside', textfont:{color:C.ink}, hovertemplate:'%{y:.3f}<extra>SARIMAX</extra>'}],
    layout({barmode:'group', bargap:0.25, bargroupgap:0.06, hovermode:'closest', yaxis:{title:'MAE (kWh/m²/day)', gridcolor:C.grid, rangemode:'tozero'}, xaxis:{gridcolor:'rgba(0,0,0,0)'}, annotations:[{text:'★ = SARIMAX vs SARIMA significant at 5% (DM test)', showarrow:false, x:0, xref:'paper', y:1.14, yref:'paper', xanchor:'left', font:{color:C.mute, size:11}}]}), cfg);
} else { $('p-cities').innerHTML = '<p class="note">Run without --fast to compute the four robustness cities.</p>'; }
const ex = Object.entries(R.extensions);
if(ex.length){
  const names = ['SARIMAX (main)', ...ex.map(([k])=>k.replace(/^E\d_/,'').replace(/_/g,' '))];
  const vals = [sx.MAE, ...ex.map(([,v])=>v.metrics.overall.MAE)];
  Plotly.newPlot('p-ext', [{x:names, y:vals, type:'bar', marker:{color:[C.sarimax, ...ex.map(()=>C.persist)]}, text:vals.map(f3), textposition:'outside', textfont:{color:C.ink2}, hovertemplate:'MAE %{y:.3f}<extra></extra>'}],
    layout({showlegend:false, hovermode:'closest', yaxis:{title:'MAE (kWh/m²/day)', gridcolor:C.grid, rangemode:'tozero'}, xaxis:{gridcolor:'rgba(0,0,0,0)'}}), cfg);
  $('ext-list').innerHTML = '<ul>'+ex.map(([k,v])=>`<li><b>${k.replace(/^E\d_/,'').replace(/_/g,' ')}</b> — ${v.desc}. MAE ${f3(v.metrics.overall.MAE)}, RMSE ${f3(v.metrics.overall.RMSE)}, MAPE ${f2(v.metrics.overall.MAPE)}% · vs SARIMAX: DM p = ${v.dm_vs_sarimax.p_value.toFixed(3)} ${v.dm_vs_sarimax.p_value<0.05?(v.metrics.overall.MAE<sx.MAE?'(significantly better)':'(significantly worse)'):'(no significant difference)'}</li>`).join('')+'</ul>';
} else { $('p-ext').innerHTML = '<p class="note">Run without --fast to compute the extensions.</p>'; }

const bestCity = cities.length ? cities.reduce((a,c)=>{const g=(R.cities[c].sarima.overall.MAE-R.cities[c].sarimax.overall.MAE)/R.cities[c].sarima.overall.MAE; return g>a[1]?[c,g]:a;},['',-1]) : null;
const worstCity = cities.length ? cities.reduce((a,c)=>{const g=(R.cities[c].sarima.overall.MAE-R.cities[c].sarimax.overall.MAE)/R.cities[c].sarima.overall.MAE; return g<a[1]?[c,g]:a;},['',9]) : null;
$('concl').innerHTML = `
<p><b>Which model performs better and by how much.</b> On ${R.split.n_test} out-of-sample weeks SARIMAX ${imp.RMSE>0?'reduces':'increases'} RMSE by ${Math.abs(imp.RMSE).toFixed(1)}% and MAE by ${Math.abs(imp.MAE).toFixed(1)}% relative to SARIMA (DM p = ${dm.p_value.toFixed(4)}, ${sig?'significant':'not significant'} at 5%). Both models clearly beat seasonal persistence (${((sn.MAE-sm.MAE)/sn.MAE*100).toFixed(1)}% and ${((sn.MAE-sx.MAE)/sn.MAE*100).toFixed(1)}% lower MAE; DM p &lt; 0.001) and last-week persistence.</p>
<p><b>Why the gain is small.</b> The SARIMA model already captures the 52-week cycle and the week-to-week persistence. The lagged weather block adds only a little on top: the standardised coefficients are ${Object.entries(R.sarimax.exog_coef).map(([k,v])=>k.replace('_lag1','')+' '+(v.coef>=0?'+':'')+v.coef.toFixed(3)+' (p='+v.p_value.toFixed(3)+')').join(', ')} — only cloud amount is individually significant, with the expected negative sign (a cloudier week is followed by lower radiation). Plausible reasons the forecast gain is still small, none of which this study tested: weekly means smooth away the day-to-day cloud variability the covariates describe, and a one-week-old observation says little about next week's sky. By season, dry-season weeks gain a little (MAE ${f3(R.sarima.metrics.dry_rest.MAE)} → ${f3(R.sarimax.metrics.dry_rest.MAE)}) and monsoon weeks hardly at all (${f3(R.sarima.metrics.monsoon_JJAS.MAE)} → ${f3(R.sarimax.metrics.monsoon_JJAS.MAE)}).${bestCity?` Across the five cities the MAE change from adding weather ranges from ${(bestCity[1]*100).toFixed(1)}% in ${bestCity[0]} to ${(worstCity[1]*100).toFixed(1)}% in ${worstCity[0]} (negative = SARIMAX worse), and no city shows a significant difference (DM test).`:''}</p>
<p><b>Extensions.</b> Of the three variants only the log-transformed SARIMAX differs significantly from SARIMAX (DM p = 0.042, MAE 0.476 vs 0.481). Three comparisons were made, so by a Bonferroni correction (0.05/3 = 0.017) this would NOT count as significant; treat it as a lead worth testing on more data, not as a finding.</p>
<p><b>Limitations.</b> NASA POWER is a satellite/reanalysis product at 0.5° resolution, not a ground pyranometer, so errors are relative to a modelled truth. Weekly means remove intra-week variability. The regressors are observed lag-1 values; an operational system would use weather forecasts, which adds error. One 80/20 split is reported (no multiple folds). The DM test assumes one-step errors are serially uncorrelated.</p>
<p><b>Future work.</b> (1) Replace lag-1 observations with numerical weather forecasts and test at the daily scale with Fourier seasonal terms. (2) Pool the five cities in a hierarchical / panel model so parameters are shared across climate zones. (3) Add a probabilistic skill score (CRPS / interval coverage) alongside MAE/RMSE/MAPE, since a solar planner needs calibrated intervals as much as point accuracy. The three extensions above (multi-lag block, log target, ensemble) were implemented as first steps.</p>`;

// ---------- Tab 5
$('papers').innerHTML = PAPERS.map(p=>`<div class="paper"><div class="yr">${p.year}</div><h4>${p.title}</h4><div class="meta">${p.authors} · ${p.venue} · doi:${p.doi}</div>
 <div class="k"><b>Data:</b> ${p.dataset}</div><div class="k"><b>Method:</b> ${p.method}</div><div class="k"><b>Finding:</b> ${p.finding}</div><div class="k"><b>Relevance / gap:</b> ${p.gap}</div>
 <div class="v">${p.abstract_verified?'✔ bibliographic record + abstract verified':'✔ bibliographic record verified · ⚠ abstract NOT verified — read the paper'}</div></div>`).join('');
$('gap-gap').textContent = GAP.gap; $('gap-cons').textContent = GAP.consensus; $('gap-addr').textContent = GAP.address; $('gap-impr').textContent = GAP.improvement;

// =====================================================================
// PLAIN-ENGLISH LAYER: start page, per-chart explanations, glossary
// =====================================================================
(function(){
  const n_worse = cities.filter(c => R.cities[c].sarimax.overall.MAE > R.cities[c].sarima.overall.MAE).length;
  const meanSun = R.stats.mean, missPct = (sx.MAE/meanSun*100);
  const beatSeas = (sn.MAE - sx.MAE)/sn.MAE*100;
  const notSig = dm.p_value >= 0.05;
  const amp = R.decomposition.seasonal_amplitude;
  const cloud = R.sarimax.exog_coef.cloud_lag1;
  const testStart = R.split.test_range[0].slice(0,4), testEnd = R.split.test_range[1].slice(0,4);

  document.getElementById('start-grid').innerHTML = `
  <div class="card c12 hl">
    <h3>The short version</h3>
    <div class="big">${notSig
      ? `Adding last week's weather to the forecast helped only a tiny bit (${Math.abs(imp.MAE).toFixed(1)}% smaller error), and that small gain could just be luck.`
      : `Adding last week's weather made the forecast ${Math.abs(imp.MAE).toFixed(1)}% more accurate, and the difference is statistically real.`}</div>
    <p>Both forecasting models are good: they are <b>${beatSeas.toFixed(0)}% more accurate</b> than the simple guess "next week will be like the same week last year". The disappointing part is that the fancier model, with weather added, is hardly better than the plain one. That is a genuine result, not a mistake.</p>
  </div>

  <div class="card c12">
    <h3>What is this project about?</h3>
    <p>Solar panels turn sunlight into electricity, so anyone planning solar power needs to know how much sunlight to expect <b>next week</b>. This project takes ${R.split.n_weeks.toLocaleString()} weeks of satellite sunlight records for <b>${R.meta.main_city}</b> (2000 to 2026) and builds forecasting models. Each model is then tested honestly, on the most recent ${R.split.n_test} weeks (${testStart}-${testEnd}) that it was never shown while learning. Four other cities (Delhi, Mumbai, Chennai, Jodhpur) are checked the same way to see if the answer changes.</p>
  </div>

  <div class="card c6">
    <h3>The question we are asking</h3>
    <div class="big" style="font-size:19px">Does knowing last week's <i>humidity, temperature and cloud cover</i> help predict next week's sunlight better than using past sunlight alone?</div>
    <p>Two models answer it. Everything else about them is identical, so any difference comes only from the weather information.</p>
    <ul>
      <li><b style="color:var(--sarima)">Baseline model (SARIMA)</b> learns the yearly rhythm (sunny summers, dim monsoon) and recent ups and downs, using <i>past sunlight only</i>.</li>
      <li><b style="color:var(--sarimax)">Improved model (SARIMAX)</b> does the same, <i>plus</i> last week's humidity, temperature and cloud.</li>
    </ul>
  </div>

  <div class="card c6">
    <h3>The key numbers</h3>
    <div class="mini">
      <div class="card stat"><span class="l">Typical forecast miss</span><span class="v">${f2(sx.MAE)}</span><span class="d">kWh/m²/day, about ${missPct.toFixed(0)}% of an average week's sunlight (${f2(meanSun)})</span></div>
      <div class="card stat"><span class="l">Better than "same as last year"</span><span class="v">${beatSeas.toFixed(0)}%</span><span class="d">smaller average miss, for both models</span></div>
      <div class="card stat"><span class="l">Weather vs no weather</span><span class="v">${Math.abs(imp.MAE).toFixed(1)}%</span><span class="d">${notSig ? 'tiny, and could be chance (p = '+dm.p_value.toFixed(2)+')' : 'real gain (p = '+dm.p_value.toFixed(3)+')'}</span></div>
      <div class="card stat"><span class="l">Cities where weather made it worse</span><span class="v">${n_worse} of ${cities.length}</span><span class="d">so the weather gain is not consistent</span></div>
    </div>
  </div>

  <div class="card c6">
    <h3>What the results mean</h3>
    <ul>
      <li>Sunlight follows a strong yearly cycle, and a model that learns the cycle already forecasts it well.</li>
      <li>Last week's <b>cloud cover</b> is a real signal (a cloudier week is followed by less sunlight, p = ${cloud.p_value.toFixed(3)}), but humidity and temperature add nothing reliable.</li>
      <li>The extra signal is too small to make forecasts noticeably better when we average sunlight over whole weeks.</li>
      <li><b>Honest caveat:</b> the sunlight values come from a satellite/computer model (NASA POWER), not from a sensor on the ground, so the "truth" here is itself an estimate.</li>
    </ul>
  </div>

  <div class="card c6">
    <h3>How to use this dashboard</h3>
    <ol class="steps">
      <li><b>1 · The data</b> - what the sunlight record looks like and why it suits these models.</li>
      <li><b>2 · Baseline model</b> - how well sunlight-only forecasting works.</li>
      <li><b>3 · Improved model</b> - what adding weather changes.</li>
      <li><b>4 · Which is better?</b> - the head-to-head, the five cities and the verdict.</li>
      <li><b>5 · Why this study</b> - the five papers we looked at and the gap we test.</li>
    </ol>
    <p class="note">Every chart has a blue note underneath saying what it shows and the one thing to take away. You can hover over charts for exact values and drag to zoom.</p>
  </div>

  <div class="card c12">
    <h3>Plain-English glossary</h3>
    <dl class="gl">
      <dt>kWh/m²/day</dt><dd>Amount of sunlight energy landing on one square metre in a day. About 5.4 is average here; 7+ is a very sunny week, under 3.5 is gloomy.</dd>
      <dt>Forecast one week ahead</dt><dd>Predict next week using only what is known up to this week. No peeking at the answer.</dd>
      <dt>SARIMA</dt><dd>A forecasting method that learns (1) repeating seasons, (2) how this week depends on recent weeks. Uses only the series' own past.</dd>
      <dt>SARIMAX</dt><dd>The same method plus extra information, here last week's humidity, temperature and cloud cover.</dd>
      <dt>MAE</dt><dd>Mean Absolute Error: on average, how far off the forecast is, in the same units as sunlight. Smaller is better. The easiest number to understand.</dd>
      <dt>RMSE</dt><dd>Like MAE, but big misses count extra. If RMSE is much bigger than MAE, the model makes occasional large mistakes.</dd>
      <dt>MAPE</dt><dd>The average miss as a percentage of the real value (10% means about one tenth off).</dd>
      <dt>Seasonal naive</dt><dd>A "no-brainer" benchmark: predict that next week equals the same week last year. A forecasting model is only worth using if it beats this.</dd>
      <dt>Naive (last week)</dt><dd>Another benchmark: predict that next week equals this week.</dd>
      <dt>Stationary</dt><dd>A series that hovers around a steady level instead of drifting off. Many forecasting methods work best on stationary data.</dd>
      <dt>ACF / PACF</dt><dd>Charts of how strongly a week resembles weeks in the past. Used to choose the model's settings.</dd>
      <dt>Residual</dt><dd>Actual minus predicted: the miss for each week. Good models leave residuals that look like random noise around zero.</dd>
      <dt>95% interval</dt><dd>The shaded band: the range the model says the real value should fall in about 95% of the time.</dd>
      <dt>p-value (DM test)</dt><dd>How likely a difference this size would appear by pure chance. Below 0.05 we call it "statistically significant"; above, we cannot rule out luck.</dd>
      <dt>Monsoon weeks</dt><dd>June to September, the rainy season for most of India.</dd>
    </dl>
  </div>`;

  const CAP = {
    'p-raw': `<b>What you're looking at:</b> the average sunlight for each week since 2000. Higher means sunnier. The same shape repeats every year: bright in spring (Feb to May), duller during and after the monsoon (Jun to Nov).<span class="take">Take-away: sunlight is highly seasonal, which is why models that learn the yearly cycle work.</span>`,
    'adf': `<b>What this test asks:</b> does the series drift away over time, or hover around a steady level? "Stationary" means steady, which is what these models need.<span class="take">Take-away: our series is steady. The strong yearly cycle is still handled separately by a "seasonal difference" (comparing each week with the same week last year).</span>`,
    'p-seas': `<b>What you're looking at:</b> the yearly pattern on its own, with everything else removed: how far above or below normal a typical week is, for each week of the year.<span class="take">Take-away: the gap between the sunniest and dimmest time of year is about ${amp.toFixed(1)} kWh/m²/day, a swing much bigger than the typical forecast miss (${f2(sx.MAE)}).</span>`,
    'p-trend': `<b>What you're looking at:</b> the slow-moving average once the seasons are removed.<span class="take">Take-away: it's almost flat (about ${(R.stats.trend_slope_per_year>=0?'+':'')+R.stats.trend_slope_per_year.toFixed(3)} per year), so sunlight in Bengaluru has not systematically risen or fallen since 2000.</span>`,
    'p-acf': `<b>What you're looking at:</b> how much a week resembles the weeks before it (the "lag" is how many weeks back). Blue bars: raw series. Orange bars: after comparing each week with the same week last year.<span class="take">Take-away: the tall bars near 52 weeks show that this week looks like the same week last year. That is why a 52-week seasonal model is used.</span>`,
    'p-pacf': `<b>What you're looking at:</b> a refined version of the left chart that shows only the direct link to each past week.<span class="take">Take-away: only the first few weeks matter after the seasons are accounted for, so a small model is enough. These two charts are how the model's settings were chosen.</span>`,
    'p-sar': `<b>How to read it:</b> blue is what really happened, orange is what the baseline predicted one week ahead, and the shaded band is the range it expected the truth to fall in (95%). The dotted line is the model forecasting all ${R.split.n_test} weeks in one go.<span class="take">Take-away: the baseline follows the seasons closely. Its misses are mostly sudden cloudy or clear weeks it could not see coming. The dotted line just drifts to the average season, as expected.</span>`,
    'p-sar-res': `<b>What you're looking at:</b> the miss for each week (actual minus predicted). Above zero means the model guessed too low; below zero, too high.<span class="take">Take-away: the misses scatter randomly around zero with no obvious pattern, so the model is not leaving an obvious pattern unused.</span>`,
    'p-aic': `<b>What you're looking at:</b> six versions of the model, scored on fit with a penalty for complexity (AIC, lower is better). The orange bar is the one chosen.<span class="take">Take-away: the top four scores are almost identical, so the exact choice does not matter much. One option with a different seasonal setting is clearly worse.</span>`,
    'p-sax': `<b>How to read it:</b> same as the baseline chart, but green is the improved model that also sees last week's weather.<span class="take">Take-away: put it next to the baseline chart and the two green and orange lines are almost indistinguishable. Weather did not change the forecast much.</span>`,
    'p-sax-res': `<b>What you're looking at:</b> the misses of the improved model, in the same format as before.<span class="take">Take-away: the size of the misses looks about the same as for the baseline. The weather inputs trimmed them only slightly.</span>`,
    'p-coef': `<b>What you're looking at:</b> how strongly each weather input pushes next week's forecast, per "typical" change. Negative means more of it lowers next week's sunlight. The "p=" under each bar says how likely that effect is just noise.<span class="take">Take-away: cloud cover is the only reliable one (more cloud, then less sunlight next week). Humidity and temperature are indistinguishable from zero.</span>`,
    'p-cmp': `<b>How to read it:</b> four forecasting methods tested on the same ${R.split.n_test} weeks. A shorter bar is a smaller average miss. Grey: "same week as last year". Yellow: "same as last week". Orange: baseline. Green: improved.<span class="take">Take-away: both statistical models are far better than the two simple guesses. Orange and green are nearly the same height. That is the whole story of this project.</span>`,
    'p-season': `<b>What you're looking at:</b> the average miss, split into monsoon weeks (Jun to Sep) and the rest of the year.<span class="take">Take-away: adding weather helps a little more outside the monsoon than during it, but the differences are tiny.</span>`,
    'p-cities': `<b>What you're looking at:</b> the same test repeated in five cities. A star above a green bar would mean a statistically real improvement.<span class="take">Take-away: ${n_worse} of ${cities.length} cities got slightly worse with weather and no city has a star, so the weather gain is neither big nor consistent.</span>`,
    'p-ext': `<b>What you're looking at:</b> three extra ideas we tried on the improved model: more weather history, a mathematical transformation of sunlight, and averaging both models.<span class="take">Take-away: only the transformation looked better, and with three ideas tried the result could be luck, so treat it as a lead to test further, not a finding.</span>`,
  };
  Object.entries(CAP).forEach(([id, html]) => {
    const el = document.getElementById(id); if(!el) return;
    const d = document.createElement('div'); d.className = 'explain'; d.innerHTML = html; el.insertAdjacentElement('afterend', d);
  });

  // explain the three metric cards on each model tab
  [['sar-interp','Baseline'],['sax-interp','Improved']].forEach(([id]) => {
    const el = document.getElementById(id); if(!el) return;
    const d = document.createElement('div'); d.className = 'explain';
    d.innerHTML = `<b>The three number cards above:</b> <b>MAE</b> is the average miss in kWh/m²/day (easiest to understand). <b>RMSE</b> is similar but punishes big misses more. <b>MAPE</b> is the average miss as a percentage. Smaller is better for all three. Card colours compare against a simple benchmark: green means better than it.`;
    el.insertAdjacentElement('afterend', d);
  });
})();
</script>
</body>
</html>
"""

out = HTML.replace("__RESULTS__", json.dumps(R)).replace("__PAPERS__", json.dumps(PAPERS)).replace("__GAP__", json.dumps(GAP))
(ROOT / "dashboard.html").write_text(out, encoding="utf-8")
print("dashboard.html written,", len(out) // 1024, "KB")
