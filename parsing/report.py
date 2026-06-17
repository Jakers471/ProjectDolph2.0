"""Generate a self-contained interactive HTML signal report.

Writes a single .html file next to the JSONL — open it in any browser.

Tabs:
  Signals      — filter/sort/expand every parsed signal
  Equity Curve — cumulative PnL chart from paper-trading positions
  Order Book   — full chronological trade log with position lifecycle

Usage (standalone):
    python parsing/report.py Grizzlies
    python parsing/report.py Grizzlies <run_id>
"""
import json
import sys
from collections import Counter
from pathlib import Path
from datetime import datetime

PROJECT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT))


ACTION_COLORS = {
    "ENTRY":  "#22c55e",
    "TRIM":   "#22d3ee",
    "EXIT":   "#facc15",
    "ADD":    "#60a5fa",
    "UNSURE": "#fb923c",
    "NOISE":  "#6b7280",
}


def _esc(s: str) -> str:
    return (str(s).replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;").replace('"', "&quot;").replace("'", "&#39;"))


def generate(trader: str, signals: list, run_id: str,
             equity_data: dict | None = None,
             order_book: list | None = None) -> str:
    total        = len(signals)
    action_counts = Counter(s.action for s in signals)
    symbol_counts = Counter(s.symbol for s in signals if s.symbol)
    rows_json    = json.dumps([s.to_dict() for s in signals], ensure_ascii=False)
    eq_json      = json.dumps(equity_data or {"labels": [], "equity": [], "trades": [], "starting_balance": 7000})
    ob_json      = json.dumps(order_book or [])

    # ---- Stats cards ----------------------------------------------------------
    stats_cards = ""
    for action, color in ACTION_COLORS.items():
        n   = action_counts.get(action, 0)
        pct = n / total * 100 if total else 0
        stats_cards += f"""
        <div class="stat-card" onclick="filterAction('{action}')" style="border-left:4px solid {color}">
          <div class="stat-action" style="color:{color}">{action}</div>
          <div class="stat-count">{n}</div>
          <div class="stat-pct">{pct:.1f}%</div>
        </div>"""

    # ---- Symbol pills ---------------------------------------------------------
    symbol_pills = ""
    for sym, n in symbol_counts.most_common(12):
        symbol_pills += f'<span class="sym-pill" onclick="filterSymbol(\'{_esc(sym)}\')">{_esc(sym)} <span class="sym-n">{n}</span></span>'

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>ProjectDolph2.0 &mdash; {_esc(trader)} Signals</title>
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
body{{background:#0f1117;color:#e2e8f0;font-family:'Segoe UI',system-ui,sans-serif;font-size:14px}}
a{{color:#60a5fa}}

/* Header */
.header{{background:#1a1f2e;border-bottom:1px solid #2d3748;padding:16px 24px;display:flex;justify-content:space-between;align-items:center}}
.header h1{{font-size:18px;font-weight:700;color:#e2e8f0}}
.header .meta{{color:#94a3b8;font-size:12px}}

/* Tabs */
.tab-bar{{background:#111827;border-bottom:1px solid #1e293b;padding:0 24px;display:flex;gap:0}}
.tab-btn{{padding:12px 20px;font-size:13px;font-weight:600;color:#6b7280;border:none;background:none;cursor:pointer;border-bottom:2px solid transparent;transition:color .15s}}
.tab-btn:hover{{color:#cbd5e1}}
.tab-btn.active{{color:#e2e8f0;border-bottom-color:#60a5fa}}
.tab-panel{{display:none}}
.tab-panel.active{{display:block}}

/* Stats */
.stats-row{{display:flex;gap:12px;padding:16px 24px;flex-wrap:wrap}}
.stat-card{{background:#1a1f2e;border-radius:8px;padding:12px 18px;cursor:pointer;transition:background .15s;min-width:100px}}
.stat-card:hover{{background:#252d3d}}
.stat-card.active{{background:#252d3d;outline:1px solid #4b5563}}
.stat-action{{font-size:11px;font-weight:700;letter-spacing:.05em}}
.stat-count{{font-size:24px;font-weight:700;color:#f1f5f9;line-height:1.2}}
.stat-pct{{font-size:12px;color:#94a3b8}}

/* Symbol pills */
.symbols-row{{padding:0 24px 12px;display:flex;flex-wrap:wrap;gap:6px}}
.sym-pill{{background:#1e293b;border:1px solid #334155;border-radius:20px;padding:3px 10px;cursor:pointer;font-size:12px;font-weight:600;transition:background .15s}}
.sym-pill:hover{{background:#334155}}
.sym-pill.active{{background:#3b4f6e;border-color:#60a5fa}}
.sym-n{{color:#94a3b8;font-weight:400}}

/* Filters */
.filters{{padding:10px 24px 14px;display:flex;gap:12px;align-items:center;flex-wrap:wrap;background:#0f1117;border-bottom:1px solid #1e293b}}
.filter-label{{color:#94a3b8;font-size:12px;white-space:nowrap}}
.search-box{{background:#1a1f2e;border:1px solid #334155;border-radius:6px;color:#e2e8f0;padding:5px 10px;font-size:13px;width:200px;outline:none}}
.search-box:focus{{border-color:#60a5fa}}
.conf-slider{{width:120px;accent-color:#60a5fa}}
.conf-val{{color:#94a3b8;font-size:12px;min-width:28px}}
.clear-btn{{background:#374151;border:none;border-radius:6px;color:#d1d5db;padding:5px 12px;cursor:pointer;font-size:12px}}
.clear-btn:hover{{background:#4b5563}}
.result-count{{color:#94a3b8;font-size:12px;margin-left:auto}}

/* Table */
.table-wrap{{overflow-x:auto;padding:0 24px 40px}}
table{{width:100%;border-collapse:collapse}}
thead tr{{border-bottom:1px solid #1e293b}}
th{{padding:10px 8px;text-align:left;color:#94a3b8;font-size:11px;font-weight:600;letter-spacing:.05em;white-space:nowrap;cursor:pointer;user-select:none}}
th:hover{{color:#cbd5e1}}
th .sort-arrow{{opacity:.4;margin-left:4px}}
th.sorted .sort-arrow{{opacity:1}}
tbody tr{{border-bottom:1px solid #1a1f2e;cursor:pointer;transition:background .1s}}
tbody tr:hover{{background:#1a1f2e}}
tbody tr.expanded{{background:#1a1f2e}}
td{{padding:9px 8px;vertical-align:top}}
.action-badge{{display:inline-block;padding:2px 8px;border-radius:4px;font-size:11px;font-weight:700;letter-spacing:.05em}}
.conf-bar-wrap{{width:60px}}
.conf-bar-bg{{background:#1e293b;border-radius:3px;height:6px}}
.conf-bar-fill{{height:6px;border-radius:3px}}
.msg-preview{{color:#94a3b8;font-size:12px;max-width:340px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}}
.expand-row{{display:none}}
.expand-row.open{{display:table-row}}
.expand-cell{{padding:0 8px 16px 32px}}
.raw-msg{{background:#1e293b;border-radius:6px;padding:12px 16px;font-family:monospace;font-size:12px;color:#cbd5e1;white-space:pre-wrap;word-break:break-word;border-left:3px solid #334155;max-width:900px}}
.signal-fields{{display:flex;flex-wrap:wrap;gap:8px;margin-top:10px}}
.field-chip{{background:#0f1117;border:1px solid #334155;border-radius:4px;padding:3px 10px;font-size:11px}}
.field-chip span{{color:#94a3b8;margin-right:4px}}
.unsure-reasons{{margin-top:8px;color:#fb923c;font-size:12px}}
.empty{{text-align:center;padding:60px;color:#4b5563}}

/* Equity tab */
.eq-section{{padding:24px}}
.eq-empty{{color:#6b7280;text-align:center;padding:60px;font-size:14px}}
.eq-charts{{display:grid;grid-template-columns:1fr;gap:24px;margin-bottom:28px}}
.eq-chart-box{{background:#1a1f2e;border-radius:10px;padding:20px}}
.eq-chart-title{{font-size:13px;font-weight:600;color:#94a3b8;margin-bottom:14px;letter-spacing:.04em}}
canvas{{display:block;width:100%!important}}
.eq-summary{{display:flex;gap:20px;flex-wrap:wrap;margin-bottom:20px}}
.eq-kpi{{background:#1a1f2e;border-radius:8px;padding:14px 20px;min-width:140px}}
.eq-kpi-label{{font-size:11px;color:#6b7280;letter-spacing:.05em;margin-bottom:4px}}
.eq-kpi-val{{font-size:22px;font-weight:700}}
.eq-trade-table{{background:#1a1f2e;border-radius:10px;overflow:hidden}}
.eq-trade-table table{{width:100%;border-collapse:collapse}}
.eq-trade-table th{{background:#111827;padding:10px 12px;text-align:left;font-size:11px;color:#6b7280;font-weight:600;letter-spacing:.05em}}
.eq-trade-table td{{padding:9px 12px;border-bottom:1px solid #111827;font-size:13px}}
.pnl-pos{{color:#22c55e;font-weight:600}}
.pnl-neg{{color:#ef4444;font-weight:600}}

/* Order Book tab */
.ob-section{{padding:24px}}
.ob-empty{{color:#6b7280;text-align:center;padding:60px}}
.ob-summary{{display:flex;gap:16px;flex-wrap:wrap;margin-bottom:20px}}
.ob-kpi{{background:#1a1f2e;border-radius:8px;padding:12px 18px;min-width:120px}}
.ob-kpi-label{{font-size:11px;color:#6b7280;letter-spacing:.05em;margin-bottom:4px}}
.ob-kpi-val{{font-size:20px;font-weight:700;color:#e2e8f0}}
.ob-filters{{display:flex;gap:10px;align-items:center;margin-bottom:16px;flex-wrap:wrap}}
.ob-search{{background:#1a1f2e;border:1px solid #334155;border-radius:6px;color:#e2e8f0;padding:5px 10px;font-size:13px;width:200px;outline:none}}
.ob-search:focus{{border-color:#60a5fa}}
.ob-pill{{background:#1e293b;border:1px solid #334155;border-radius:16px;padding:3px 10px;font-size:12px;cursor:pointer;font-weight:600}}
.ob-pill:hover,.ob-pill.active{{background:#3b4f6e;border-color:#60a5fa}}
/* Position group cards */
.pos-group{{background:#1a1f2e;border:1px solid #1e293b;border-radius:10px;margin-bottom:16px;overflow:hidden}}
.pos-group.has-concurrent{{border-color:#facc1533}}
.pos-header{{display:flex;align-items:center;gap:12px;padding:14px 18px;cursor:pointer;user-select:none;transition:background .15s}}
.pos-header:hover{{background:#252d3d}}
.pos-symbol{{font-size:17px;font-weight:800;color:#f1f5f9;min-width:60px}}
.pos-meta{{display:flex;flex-direction:column;gap:2px;flex:1}}
.pos-meta-row{{display:flex;gap:10px;align-items:center;flex-wrap:wrap}}
.pos-label{{font-size:11px;color:#6b7280;letter-spacing:.04em}}
.pos-val{{font-size:12px;color:#cbd5e1}}
.pos-pnl{{font-size:18px;font-weight:700;min-width:90px;text-align:right}}
.pos-pnl.pos{{color:#22c55e}}
.pos-pnl.neg{{color:#ef4444}}
.pos-pnl.zero{{color:#6b7280}}
.pos-chevron{{color:#6b7280;font-size:14px;transition:transform .2s;margin-left:8px}}
.pos-group.open .pos-chevron{{transform:rotate(90deg)}}
/* Size bar */
.size-bar-wrap{{display:flex;align-items:center;gap:6px}}
.size-bar-bg{{background:#0f1117;border-radius:4px;height:6px;width:80px;overflow:hidden}}
.size-bar-fill{{height:6px;border-radius:4px;background:#60a5fa;transition:width .3s}}
.size-pct{{font-size:11px;color:#94a3b8;min-width:36px}}
/* Status badges */
.ob-tag{{display:inline-block;padding:2px 7px;border-radius:4px;font-size:10px;font-weight:700;letter-spacing:.04em}}
.ob-tag-open{{background:#22c55e22;color:#22c55e;border:1px solid #22c55e44}}
.ob-tag-closed{{background:#37415122;color:#9ca3af;border:1px solid #37415166}}
.ob-tag-partial{{background:#facc1522;color:#facc15;border:1px solid #facc1544}}
.ob-tag-dry{{background:#60a5fa11;color:#60a5fa88;border:1px solid #60a5fa22}}
.ob-tag-concurrent{{background:#fb923c22;color:#fb923c;border:1px solid #fb923c44;font-size:9px}}
/* Trade rows inside a position */
.pos-trades{{display:none;border-top:1px solid #111827}}
.pos-group.open .pos-trades{{display:block}}
.trade-table{{width:100%;border-collapse:collapse}}
.trade-table th{{background:#111827;padding:8px 14px;text-align:left;font-size:10px;color:#4b5563;font-weight:600;letter-spacing:.06em}}
.trade-table td{{padding:9px 14px;font-size:12px;border-bottom:1px solid #0f1117;vertical-align:middle}}
.trade-table tr:last-child td{{border-bottom:none}}
.trade-table tr:hover td{{background:#111827}}
.ob-action{{display:inline-block;padding:2px 7px;border-radius:3px;font-size:11px;font-weight:700;letter-spacing:.04em}}
.ob-buy{{background:#22c55e22;color:#22c55e}}
.ob-sell{{background:#ef444422;color:#ef4444}}
.ob-add{{background:#60a5fa22;color:#60a5fa}}
.ob-sell_short{{background:#fb923c22;color:#fb923c}}
.ob-buy_cover{{background:#a78bfa22;color:#a78bfa}}
.trade-size-flow{{display:flex;align-items:center;gap:5px;font-size:11px;color:#6b7280;white-space:nowrap}}
.trade-size-arrow{{color:#374151}}
/* Debug console */
.debug-toggle{{position:fixed;bottom:20px;right:20px;background:#1a1f2e;border:1px solid #334155;border-radius:8px;padding:8px 14px;cursor:pointer;font-size:12px;color:#6b7280;z-index:1000}}
.debug-toggle:hover{{color:#cbd5e1;border-color:#60a5fa}}
.debug-panel{{display:none;position:fixed;bottom:60px;right:20px;width:540px;max-height:60vh;background:#0f1117;border:1px solid #374151;border-radius:10px;z-index:999;overflow:hidden;flex-direction:column}}
.debug-panel.open{{display:flex}}
.debug-header{{background:#1a1f2e;padding:10px 16px;font-size:12px;font-weight:600;color:#94a3b8;border-bottom:1px solid #1e293b;display:flex;justify-content:space-between}}
.debug-body{{overflow-y:auto;padding:14px 16px;font-family:monospace;font-size:11px;color:#6b7280;white-space:pre-wrap;word-break:break-all;flex:1}}
.debug-section{{margin-bottom:14px}}
.debug-section-title{{color:#60a5fa;font-weight:600;margin-bottom:6px}}
.debug-field{{display:flex;gap:8px;margin-bottom:3px}}
.debug-key{{color:#94a3b8;min-width:160px}}
.debug-val{{color:#e2e8f0}}
.debug-warn{{color:#fb923c}}
.debug-ok{{color:#22c55e}}
</style>
</head>
<body>

<div class="header">
  <h1>ProjectDolph2.0 &mdash; {_esc(trader)} Signals</h1>
  <div class="meta">Run: {_esc(run_id)} &nbsp;|&nbsp; {total} messages</div>
</div>

<div class="tab-bar">
  <button class="tab-btn active" onclick="switchTab('signals',this)">Signals</button>
  <button class="tab-btn" onclick="switchTab('equity',this)">Equity Curve</button>
  <button class="tab-btn" onclick="switchTab('orderbook',this)">Order Book</button>
</div>

<!-- ===== SIGNALS TAB ===== -->
<div class="tab-panel active" id="tab-signals">

<div class="stats-row" id="statsRow">
{stats_cards}
  <div class="stat-card" onclick="filterAction(null)" id="allCard" style="border-left:4px solid #475569">
    <div class="stat-action" style="color:#94a3b8">ALL</div>
    <div class="stat-count">{total}</div>
    <div class="stat-pct">100%</div>
  </div>
</div>

<div class="symbols-row" id="symbolsRow">
  <span class="filter-label" style="line-height:24px">Symbols:</span>
  {symbol_pills}
</div>

<div class="filters">
  <span class="filter-label">Search:</span>
  <input class="search-box" id="searchBox" placeholder="symbol or message..." oninput="applyFilters()">
  <span class="filter-label">Min conf:</span>
  <input type="range" class="conf-slider" id="confSlider" min="0" max="1" step="0.05" value="0" oninput="updateConf()">
  <span class="conf-val" id="confVal">0.0</span>
  <button class="clear-btn" onclick="clearFilters()">Clear</button>
  <span class="result-count" id="resultCount"></span>
</div>

<div class="table-wrap">
<table id="sigTable">
<thead>
  <tr>
    <th onclick="sortBy('timestamp')" data-col="timestamp">Time <span class="sort-arrow">&#9660;</span></th>
    <th onclick="sortBy('action')" data-col="action">Action <span class="sort-arrow">&#9660;</span></th>
    <th onclick="sortBy('symbol')" data-col="symbol">Symbol <span class="sort-arrow">&#9660;</span></th>
    <th onclick="sortBy('asset_type')" data-col="asset_type">Asset <span class="sort-arrow">&#9660;</span></th>
    <th onclick="sortBy('side')" data-col="side">Side <span class="sort-arrow">&#9660;</span></th>
    <th onclick="sortBy('entry_price')" data-col="entry_price">Entry <span class="sort-arrow">&#9660;</span></th>
    <th>Targets</th>
    <th onclick="sortBy('stop')" data-col="stop">Stop <span class="sort-arrow">&#9660;</span></th>
    <th>Size</th>
    <th onclick="sortBy('confidence')" data-col="confidence">Conf <span class="sort-arrow">&#9660;</span></th>
    <th>Message</th>
  </tr>
</thead>
<tbody id="tableBody"></tbody>
</table>
<div class="empty" id="emptyState" style="display:none">No signals match current filters.</div>
</div>

</div><!-- /tab-signals -->

<!-- ===== EQUITY TAB ===== -->
<div class="tab-panel" id="tab-equity">
<div class="eq-section" id="equitySection"></div>
</div>

<!-- ===== ORDER BOOK TAB ===== -->
<div class="tab-panel" id="tab-orderbook">
<div class="ob-section" id="obSection"></div>
</div>

<!-- Debug console — fixed overlay, visible on all tabs -->
<button class="debug-toggle" id="debugToggle" onclick="toggleDebug()">&#128270; Debug</button>
<div class="debug-panel" id="debugPanel">
  <div class="debug-header">
    <span>Debug Console — Data &amp; Calculations</span>
    <span style="cursor:pointer;color:#6b7280" onclick="toggleDebug()">&#x2715;</span>
  </div>
  <div class="debug-body"></div>
</div>

<script>
const SIGNALS = {rows_json};
const ACTION_COLORS = {json.dumps(ACTION_COLORS)};
const EQ_DATA = {eq_json};
const OB_DATA = {ob_json};

// ---- Tab switching ----------------------------------------------------------
function switchTab(name, btn) {{
  document.querySelectorAll('.tab-panel').forEach(p => p.classList.remove('active'));
  document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
  document.getElementById('tab-' + name).classList.add('active');
  btn.classList.add('active');
  if (name === 'equity')     renderEquity();
  if (name === 'orderbook')  renderOrderBook();
}}

// ---- Signals tab ------------------------------------------------------------
let activeAction = null;
let activeSymbol = null;
let sortCol = 'timestamp';
let sortAsc = false;

function confColor(c) {{
  if (c >= 0.75) return '#22c55e';
  if (c >= 0.50) return '#facc15';
  return '#f87171';
}}

function fmtTime(ts) {{
  if (!ts) return '';
  return ts.replace('T',' ').substring(0,16);
}}

function fmtTargets(arr) {{
  if (!arr || !arr.length) return '';
  return arr.slice(0,3).join(', ') + (arr.length > 3 ? '...' : '');
}}

function render() {{
  const search  = document.getElementById('searchBox').value.toLowerCase();
  const minConf = parseFloat(document.getElementById('confSlider').value);

  let filtered = SIGNALS.filter(s => {{
    if (activeAction && s.action !== activeAction) return false;
    if (activeSymbol && (s.symbol||'').toUpperCase() !== activeSymbol) return false;
    if (s.confidence < minConf) return false;
    if (search) {{
      const hay = ((s.symbol||'')+' '+(s.raw_content||'')).toLowerCase();
      if (!hay.includes(search)) return false;
    }}
    return true;
  }});

  filtered.sort((a,b) => {{
    let av=a[sortCol], bv=b[sortCol];
    if (av==null) av=''; if (bv==null) bv='';
    if (typeof av==='string') av=av.toLowerCase();
    if (typeof bv==='string') bv=bv.toLowerCase();
    if (av<bv) return sortAsc?-1:1;
    if (av>bv) return sortAsc?1:-1;
    return 0;
  }});

  document.getElementById('resultCount').textContent = filtered.length+' signals';
  document.getElementById('emptyState').style.display = filtered.length===0?'block':'none';

  const tbody = document.getElementById('tableBody');
  tbody.innerHTML='';

  filtered.forEach((s,i) => {{
    const color  = ACTION_COLORS[s.action]||'#6b7280';
    const cConf  = confColor(s.confidence);
    const barW   = Math.round(s.confidence*60);
    const preview= (s.raw_content||'').replace(/\\n/g,' ').substring(0,80);

    const tr = document.createElement('tr');
    tr.onclick = () => toggleExpand(i, s);
    tr.innerHTML = `
      <td style="color:#94a3b8;font-size:12px;white-space:nowrap">${{fmtTime(s.timestamp)}}</td>
      <td><span class="action-badge" style="background:${{color}}22;color:${{color}}">${{s.action}}</span></td>
      <td style="font-weight:700">${{s.symbol||''}}</td>
      <td style="color:#94a3b8;font-size:12px">${{s.asset_type||''}}</td>
      <td style="color:#94a3b8;font-size:12px">${{s.side||''}}</td>
      <td style="font-family:monospace">${{s.entry_price!=null?s.entry_price:''}}</td>
      <td style="font-family:monospace;font-size:12px;color:#94a3b8">${{fmtTargets(s.targets)}}</td>
      <td style="font-family:monospace">${{s.stop!=null?s.stop:''}}</td>
      <td style="font-size:12px;color:#94a3b8">${{s.size_hint||''}}</td>
      <td>
        <div class="conf-bar-wrap">
          <div style="font-size:11px;color:${{cConf}};margin-bottom:2px">${{s.confidence.toFixed(2)}}</div>
          <div class="conf-bar-bg"><div class="conf-bar-fill" style="width:${{barW}}px;background:${{cConf}}"></div></div>
        </div>
      </td>
      <td class="msg-preview">${{preview.replace(/</g,'&lt;')}}</td>`;

    const expandTr = document.createElement('tr');
    expandTr.className='expand-row';
    expandTr.id='exp-'+i;
    const fields=[];
    if (s.entry_price!=null) fields.push(['entry',s.entry_price]);
    if (s.targets&&s.targets.length) fields.push(['targets',s.targets.join(', ')]);
    if (s.stop!=null) fields.push(['stop',s.stop]);
    if (s.size_hint) fields.push(['size',s.size_hint]);
    if (s.source_message_id) fields.push(['msg_id',s.source_message_id]);
    const fieldHtml=fields.map(([k,v])=>`<div class="field-chip"><span>${{k}}</span>${{v}}</div>`).join('');
    const reasonsHtml=s.unsure_reasons&&s.unsure_reasons.length
      ?`<div class="unsure-reasons">Flagged: ${{s.unsure_reasons.join(', ')}}</div>`:'';
    expandTr.innerHTML=`<td colspan="11" class="expand-cell">
      <div class="raw-msg">${{(s.raw_content||'').replace(/</g,'&lt;')}}</div>
      <div class="signal-fields">${{fieldHtml}}</div>${{reasonsHtml}}</td>`;
    tbody.appendChild(tr);
    tbody.appendChild(expandTr);
  }});
}}

function toggleExpand(i) {{
  const el=document.getElementById('exp-'+i);
  if (!el) return;
  const isOpen=el.classList.contains('open');
  document.querySelectorAll('.expand-row.open').forEach(r=>r.classList.remove('open'));
  if (!isOpen) el.classList.add('open');
}}

function filterAction(action) {{
  activeAction=(activeAction===action)?null:action;
  document.querySelectorAll('.stat-card').forEach(c=>c.classList.remove('active'));
  if (activeAction) {{
    document.querySelectorAll('.stat-card').forEach(c=>{{
      const a=c.querySelector('.stat-action');
      if (a&&a.textContent===activeAction) c.classList.add('active');
    }});
  }}
  render();
}}

function filterSymbol(sym) {{
  activeSymbol=(activeSymbol===sym)?null:sym;
  document.querySelectorAll('.sym-pill').forEach(p=>p.classList.remove('active'));
  if (activeSymbol) {{
    document.querySelectorAll('.sym-pill').forEach(p=>{{
      if (p.textContent.trim().startsWith(sym)) p.classList.add('active');
    }});
  }}
  render();
}}

function applyFilters(){{render();}}
function updateConf(){{
  const v=parseFloat(document.getElementById('confSlider').value);
  document.getElementById('confVal').textContent=v.toFixed(1);
  render();
}}
function clearFilters(){{
  activeAction=null; activeSymbol=null;
  document.querySelectorAll('.stat-card,.sym-pill').forEach(e=>e.classList.remove('active'));
  document.getElementById('searchBox').value='';
  document.getElementById('confSlider').value=0;
  document.getElementById('confVal').textContent='0.0';
  render();
}}
function sortBy(col){{
  if (sortCol===col){{sortAsc=!sortAsc;}}
  else{{sortCol=col;sortAsc=true;}}
  document.querySelectorAll('th').forEach(th=>th.classList.remove('sorted'));
  const th=document.querySelector(`th[data-col="${{col}}"]`);
  if (th) th.classList.add('sorted');
  render();
}}

// ---- Equity tab -------------------------------------------------------------
let equityRendered = false;

function renderEquity() {{
  if (equityRendered) return;
  equityRendered = true;
  const sec   = document.getElementById('equitySection');
  const eq    = EQ_DATA;
  const start = eq.starting_balance || 7000;

  if (!eq.trades || eq.trades.length === 0) {{
    sec.innerHTML = '<div class="eq-empty">No closed trades yet.<br>Run <code>python dev.py --paper {_esc(trader)} --save</code> to simulate the pipeline and regenerate this report.</div>';
    return;
  }}

  const trades      = eq.trades;
  const finalBal    = eq.equity[eq.equity.length-1] || start;
  const totalPnl    = finalBal - start;
  const totalPct    = (totalPnl / start * 100);
  const wins        = trades.filter(t=>t.pnl>0).length;
  const losses      = trades.filter(t=>t.pnl<0).length;
  const winRate     = trades.length ? (wins/trades.length*100) : 0;
  const avgWin      = wins   ? trades.filter(t=>t.pnl>0).reduce((s,t)=>s+t.pnl,0)/wins   : 0;
  const avgLoss     = losses ? trades.filter(t=>t.pnl<0).reduce((s,t)=>s+t.pnl,0)/losses : 0;
  const maxDd       = _maxDrawdown(eq.equity, start);

  function kpi(label, val, color) {{
    return `<div class="eq-kpi"><div class="eq-kpi-label">${{label}}</div>
      <div class="eq-kpi-val" style="color:${{color}}">${{val}}</div></div>`;
  }}
  function fmt$(v) {{ return '$'+(Math.abs(v)<1000?v.toFixed(2):v.toFixed(0)); }}

  const balColor = totalPnl >= 0 ? '#22c55e' : '#ef4444';
  const summary  = `<div class="eq-summary">
    ${{kpi('Balance', fmt$(finalBal), balColor)}}
    ${{kpi('Return', (totalPct>=0?'+':'')+totalPct.toFixed(2)+'%', balColor)}}
    ${{kpi('Total PnL', (totalPnl>=0?'+':'')+fmt$(totalPnl), balColor)}}
    ${{kpi('Trades', trades.length, '#e2e8f0')}}
    ${{kpi('Win Rate', winRate.toFixed(1)+'%', winRate>=50?'#22c55e':'#fb923c')}}
    ${{kpi('Avg Win', '+'+fmt$(avgWin), '#22c55e')}}
    ${{kpi('Avg Loss', fmt$(avgLoss), '#ef4444')}}
    ${{kpi('Max DD', '-'+fmt$(maxDd), '#ef4444')}}
  </div>`;

  const tradeRows = trades.map((t,i) => {{
    const pc   = t.pnl>0?'pnl-pos':t.pnl<0?'pnl-neg':'';
    const sign = t.pnl>=0?'+':'';
    const pct  = (t.entry && t.exit) ? ((t.exit-t.entry)/t.entry*100*(t.side==='SHORT'?-1:1)) : null;
    const pctStr = pct!=null ? ` (${{(pct>=0?'+':'')+pct.toFixed(2)}}%)` : '';
    return `<tr>
      <td style="color:#6b7280;font-size:12px">${{(t.timestamp||'').substring(0,10)}}</td>
      <td style="font-weight:700">${{t.symbol||''}}</td>
      <td style="color:#94a3b8">${{t.side||''}}</td>
      <td style="font-family:monospace;font-size:12px">${{t.entry!=null?t.entry:'—'}}</td>
      <td style="font-family:monospace;font-size:12px">${{t.exit!=null?t.exit:'—'}}</td>
      <td class="${{pc}}">${{sign+fmt$(t.pnl)}}${{pctStr}}</td>
      <td style="font-family:monospace;font-size:12px;color:#94a3b8">${{fmt$(t.balance)}}</td>
    </tr>`;
  }}).join('');

  sec.innerHTML = `
    ${{summary}}
    <div class="eq-charts">
      <div class="eq-chart-box">
        <div class="eq-chart-title">ACCOUNT BALANCE  <span style="color:#6b7280;font-size:11px">(starting ${{start.toLocaleString()}})</span></div>
        <canvas id="equityCanvas" height="220"></canvas>
      </div>
      <div class="eq-chart-box">
        <div class="eq-chart-title">PER-TRADE PnL ($)</div>
        <canvas id="barsCanvas" height="140"></canvas>
      </div>
    </div>
    <div class="eq-trade-table">
      <table>
        <thead><tr><th>Date</th><th>Symbol</th><th>Side</th><th>Entry</th><th>Exit</th><th>PnL ($)</th><th>Balance</th></tr></thead>
        <tbody>${{tradeRows}}</tbody>
      </table>
    </div>`;

  const allBalances = [start, ...eq.equity];
  const allLabels   = ['start', ...eq.labels];
  requestAnimationFrame(() => {{
    drawLineChart('equityCanvas', allLabels, allBalances, start);
    drawBarChart('barsCanvas', eq.labels, trades.map(t=>t.pnl));
  }});
}}

function _maxDrawdown(balances, start) {{
  let peak = start, maxDd = 0;
  for (const b of [start, ...balances]) {{
    if (b > peak) peak = b;
    const dd = peak - b;
    if (dd > maxDd) maxDd = dd;
  }}
  return maxDd;
}}

function drawLineChart(canvasId, labels, values, baseline) {{
  const canvas = document.getElementById(canvasId);
  if (!canvas) return;
  const dpr = window.devicePixelRatio || 1;
  const W   = canvas.offsetWidth;
  const H   = canvas.offsetHeight || 220;
  canvas.width  = W * dpr;
  canvas.height = H * dpr;
  const ctx = canvas.getContext('2d');
  ctx.scale(dpr, dpr);

  const pad = {{top:20, right:20, bottom:28, left:72}};
  const w   = W - pad.left - pad.right;
  const h   = H - pad.top  - pad.bottom;

  const minV  = Math.min(baseline, ...values);
  const maxV  = Math.max(baseline, ...values);
  const range = maxV - minV || 1;
  const pad5  = range * 0.05;
  const lo    = minV - pad5;
  const hi    = maxV + pad5;
  const span  = hi - lo;

  function xp(i) {{ return pad.left + (i / (values.length - 1 || 1)) * w; }}
  function yp(v) {{ return pad.top  + h - ((v - lo) / span) * h; }}

  // Baseline (starting balance) dashed line
  ctx.strokeStyle = '#4b5563';
  ctx.lineWidth   = 1;
  ctx.setLineDash([4, 4]);
  ctx.beginPath();
  ctx.moveTo(pad.left, yp(baseline));
  ctx.lineTo(pad.left + w, yp(baseline));
  ctx.stroke();
  ctx.setLineDash([]);

  // Fill between line and baseline
  const aboveColor = '#22c55e';
  const belowColor = '#ef4444';
  const lineColor  = values[values.length-1] >= baseline ? aboveColor : belowColor;

  ctx.beginPath();
  ctx.moveTo(xp(0), yp(values[0]));
  values.forEach((v, i) => ctx.lineTo(xp(i), yp(v)));
  ctx.lineTo(xp(values.length - 1), yp(baseline));
  ctx.lineTo(xp(0), yp(baseline));
  ctx.closePath();
  const grad = ctx.createLinearGradient(0, pad.top, 0, pad.top + h);
  grad.addColorStop(0, lineColor + '55');
  grad.addColorStop(1, lineColor + '08');
  ctx.fillStyle = grad;
  ctx.fill();

  // Equity line
  ctx.beginPath();
  ctx.moveTo(xp(0), yp(values[0]));
  values.forEach((v, i) => ctx.lineTo(xp(i), yp(v)));
  ctx.strokeStyle = lineColor;
  ctx.lineWidth   = 2;
  ctx.stroke();

  // Dot on each trade
  values.forEach((v, i) => {{
    ctx.beginPath();
    ctx.arc(xp(i), yp(v), 3, 0, Math.PI * 2);
    ctx.fillStyle = v >= baseline ? aboveColor : belowColor;
    ctx.fill();
  }});

  // Y axis labels ($)
  ctx.fillStyle  = '#6b7280';
  ctx.font       = '11px monospace';
  ctx.textAlign  = 'right';
  const yTicks   = 5;
  for (let t = 0; t <= yTicks; t++) {{
    const v   = lo + (span * t / yTicks);
    const y   = yp(v);
    const lbl = v >= 1000 ? '$' + (v/1000).toFixed(1) + 'k' : '$' + v.toFixed(0);
    ctx.fillText(lbl, pad.left - 6, y + 4);
    ctx.strokeStyle = '#1f2937';
    ctx.lineWidth   = 0.5;
    ctx.beginPath();
    ctx.moveTo(pad.left, y);
    ctx.lineTo(pad.left + w, y);
    ctx.stroke();
  }}

  // X labels (sampled)
  ctx.fillStyle  = '#6b7280';
  ctx.textAlign  = 'center';
  const step = Math.max(1, Math.floor(labels.length / 6));
  labels.forEach((l, i) => {{
    if (i % step === 0) ctx.fillText(l, xp(i), H - 6);
  }});
}}

function drawBarChart(canvasId, labels, values) {{
  const canvas = document.getElementById(canvasId);
  if (!canvas) return;
  const dpr = window.devicePixelRatio || 1;
  const W = canvas.offsetWidth;
  const H = canvas.offsetHeight || 140;
  canvas.width  = W * dpr;
  canvas.height = H * dpr;
  const ctx = canvas.getContext('2d');
  ctx.scale(dpr, dpr);

  const pad = {{top:10, right:20, bottom:28, left:60}};
  const w = W - pad.left - pad.right;
  const h = H - pad.top  - pad.bottom;

  const minV = Math.min(0, ...values);
  const maxV = Math.max(0, ...values);
  const range = maxV - minV || 1;

  function yp(v) {{ return pad.top + h - ((v - minV) / range) * h; }}
  const y0  = yp(0);
  const barW = Math.max(2, w / values.length - 2);

  // Zero line
  ctx.strokeStyle = '#374151';
  ctx.lineWidth = 1;
  ctx.setLineDash([3,3]);
  ctx.beginPath();
  ctx.moveTo(pad.left, y0);
  ctx.lineTo(pad.left + w, y0);
  ctx.stroke();
  ctx.setLineDash([]);

  values.forEach((v, i) => {{
    const x   = pad.left + (i / values.length) * w + (w/values.length - barW)/2;
    const top = yp(v);
    ctx.fillStyle = v >= 0 ? '#22c55e' : '#ef4444';
    ctx.fillRect(x, Math.min(top, y0), barW, Math.abs(top - y0));
  }});

  ctx.fillStyle = '#6b7280';
  ctx.font = '11px monospace';
  ctx.textAlign = 'right';
  [minV, maxV].forEach(v => ctx.fillText(v.toFixed(2), pad.left-6, yp(v)+4));
}}

// ---- Order Book tab ---------------------------------------------------------
let obRendered = false;
let obSymFilter = null;

function renderOrderBook() {{
  if (obRendered) return;
  obRendered = true;
  _buildOB();
  _buildDebug();
}}

function _buildOB() {{
  const sec = document.getElementById('obSection');
  if (!OB_DATA || OB_DATA.length === 0) {{
    sec.innerHTML = '<div class="ob-empty">No trades yet.<br>Run <code>python dev.py --paper {_esc(trader)} --save</code></div>';
    return;
  }}

  // Summary KPIs
  const totalPos    = OB_DATA.length;
  const openPos     = OB_DATA.filter(p => p.status === 'open').length;
  const partialPos  = OB_DATA.filter(p => p.status === 'partial').length;
  const closedPos   = OB_DATA.filter(p => p.status === 'closed').length;
  const allTrades   = OB_DATA.flatMap(p => p.trades || []);
  const totalPnl    = OB_DATA.reduce((s,p) => s + (p.total_pnl||0), 0);
  const syms        = [...new Set(OB_DATA.map(p => p.symbol).filter(Boolean))].sort();

  function kpi(label, val, color) {{
    return `<div class="ob-kpi"><div class="ob-kpi-label">${{label}}</div><div class="ob-kpi-val" style="color:${{color||'#e2e8f0'}}">${{val}}</div></div>`;
  }}
  function fmt$(v) {{ return (v>=0?'+':'')+v.toFixed(2); }}

  const pnlColor = totalPnl > 0 ? '#22c55e' : totalPnl < 0 ? '#ef4444' : '#6b7280';
  const summary = `<div class="ob-summary">
    ${{kpi('Positions', totalPos)}}
    ${{kpi('Open', openPos, '#22c55e')}}
    ${{kpi('Partial', partialPos, '#facc15')}}
    ${{kpi('Closed', closedPos, '#6b7280')}}
    ${{kpi('Total Trades', allTrades.length)}}
    ${{kpi('Realized P&L', '$'+fmt$(totalPnl), pnlColor)}}
  </div>`;

  const symPills = syms.map(s =>
    `<span class="ob-pill" id="obpill-${{s}}" onclick="obFilterSym('${{s}}')">${{s}}</span>`
  ).join('');

  const filterBar = `<div class="ob-filters">
    <input class="ob-search" id="obSearch" placeholder="search symbol / status..." oninput="_renderPositions()">
    ${{symPills}}
    <span style="color:#6b7280;font-size:12px;margin-left:auto" id="obCount"></span>
  </div>`;

  sec.innerHTML = summary + filterBar + `<div id="obPositions"></div>`;
  _renderPositions();
}}

function obFilterSym(sym) {{
  obSymFilter = (obSymFilter === sym) ? null : sym;
  document.querySelectorAll('.ob-pill').forEach(p => p.classList.remove('active'));
  if (obSymFilter) {{
    const el = document.getElementById('obpill-' + obSymFilter);
    if (el) el.classList.add('active');
  }}
  _renderPositions();
}}

function _renderPositions() {{
  const q    = (document.getElementById('obSearch')?.value || '').toLowerCase();
  const wrap = document.getElementById('obPositions');
  if (!wrap) return;

  const filtered = OB_DATA.filter(p => {{
    if (obSymFilter && p.symbol !== obSymFilter) return false;
    if (q && !(
      (p.symbol||'').toLowerCase().includes(q) ||
      (p.status||'').toLowerCase().includes(q) ||
      (p.asset_type||'').toLowerCase().includes(q) ||
      (p.side||'').toLowerCase().includes(q)
    )) return false;
    return true;
  }});

  const countEl = document.getElementById('obCount');
  if (countEl) countEl.textContent = filtered.length + ' position' + (filtered.length!==1?'s':'');

  wrap.innerHTML = filtered.map(pos => _posCard(pos)).join('');
}}

function _posCard(pos) {{
  const statusCls = `ob-tag-${{pos.status||'open'}}`;
  const pnl       = pos.total_pnl || 0;
  const pnlCls    = pnl > 0 ? 'pos' : pnl < 0 ? 'neg' : 'zero';
  const pnlStr    = (pnl>=0?'+':'') + '$' + Math.abs(pnl).toFixed(4);
  const remPct    = pos.remaining_pct ?? 100;
  const orig      = pos.original_qty || 0;
  const remaining = pos.remaining ?? orig;
  const hasConcurrent = pos.concurrent_symbols && pos.concurrent_symbols.length > 0;

  // Size bar
  const sizeBar = `<div class="size-bar-wrap">
    <div class="size-bar-bg"><div class="size-bar-fill" style="width:${{remPct}}%"></div></div>
    <span class="size-pct">${{remPct}}%</span>
  </div>`;

  // Concurrent positions flag
  const concurrentTag = hasConcurrent
    ? `<span class="ob-tag ob-tag-concurrent" title="Concurrent open positions: ${{pos.concurrent_symbols.join(', ')}}">
        &#9650; ${{pos.concurrent_symbols.join('+')}}</span>`
    : '';

  // Trade rows
  const tradeRows = (pos.trades || []).map(tr => {{
    const acMap  = {{'BUY':'ob-buy','SELL':'ob-sell','ADD':'ob-add','SELL_SHORT':'ob-sell_short','BUY_COVER':'ob-buy_cover'}};
    const ac     = acMap[tr.action] || 'ob-add';
    const tpnl   = tr.trade_pnl || 0;
    const isOpen = tr.action==='BUY' || tr.action==='ADD' || tr.action==='SELL_SHORT';
    const tpnlHtml = isOpen
      ? '<span style="color:#374151">—</span>'
      : `<span class="${{tpnl>=0?'pnl-pos':'pnl-neg'}}">${{tpnl>=0?'+':''}}${{tpnl.toFixed(4)}}</span>`;
    const after  = tr.size_after_pct ?? (tr.close_fraction > 0 ? Math.round((1-tr.close_fraction)*100) : 100);
    const before = tr.action==='BUY'?0:(tr.action==='ADD'?after:after + Math.round(tr.close_fraction*100));
    const sizeFlow = tr.action==='BUY'
      ? `<span class="trade-size-flow">0% <span class="trade-size-arrow">→</span> 100%</span>`
      : tr.action==='ADD'
      ? `<span class="trade-size-flow" title="ADD increases position">${{after}}% <span class="trade-size-arrow">↑</span></span>`
      : `<span class="trade-size-flow">${{before}}% <span class="trade-size-arrow">→</span> ${{after}}% left</span>`;
    const dryTag = tr.dry_run ? '<span class="ob-tag ob-tag-dry" style="margin-left:4px">DRY</span>' : '';
    const closeInfo = tr.close_fraction > 0
      ? `<span style="color:#6b7280;font-size:10px;margin-left:6px">${{Math.round(tr.close_fraction*100)}}% close</span>` : '';
    return `<tr>
      <td style="color:#374151;font-size:10px;padding-left:18px">#${{tr.trade_id}}</td>
      <td style="color:#6b7280;font-size:11px;white-space:nowrap">${{(tr.time||'').substring(0,16).replace('T',' ')}}</td>
      <td><span class="ob-action ${{ac}}">${{tr.action}}</span>${{closeInfo}}${{dryTag}}</td>
      <td style="font-family:monospace;font-size:12px">${{tr.price!=null?tr.price:'—'}}</td>
      <td style="font-family:monospace;font-size:12px;color:#94a3b8">${{tr.quantity!=null?'$'+tr.quantity.toFixed(0):'—'}}</td>
      <td>${{tpnlHtml}}</td>
      <td>${{sizeFlow}}</td>
      <td style="font-size:11px;color:#6b7280">${{tr.trade_status||''}}</td>
    </tr>`;
  }}).join('');

  const tradesSection = pos.trades && pos.trades.length > 0 ? `
    <div class="pos-trades">
      <table class="trade-table">
        <thead><tr>
          <th style="padding-left:18px">#TRADE</th>
          <th>TIMESTAMP</th><th>ACTION</th><th>PRICE</th>
          <th>NOTIONAL</th><th>TRADE P&amp;L</th><th>SIZE FLOW</th><th>STATUS</th>
        </tr></thead>
        <tbody>${{tradeRows}}</tbody>
      </table>
    </div>` : '';

  return `<div class="pos-group${{hasConcurrent?' has-concurrent':''}}" id="pos-${{pos.position_id}}">
    <div class="pos-header" onclick="togglePos(${{pos.position_id}})">
      <div class="pos-symbol">${{pos.symbol||'?'}}</div>
      <div class="pos-meta">
        <div class="pos-meta-row">
          <span class="ob-tag ${{statusCls}}">${{(pos.status||'open').toUpperCase()}}</span>
          <span class="pos-label">Type:</span><span class="pos-val">${{pos.asset_type||'—'}}</span>
          <span class="pos-label">Side:</span><span class="pos-val">${{pos.side||'—'}}</span>
          <span class="pos-label">Entry:</span><span class="pos-val" style="font-family:monospace">${{pos.entry_price!=null?pos.entry_price:'—'}}</span>
          ${{concurrentTag}}
        </div>
        <div class="pos-meta-row" style="margin-top:4px">
          <span class="pos-label">Opened:</span><span class="pos-val">${{(pos.opened_at||'').substring(0,10)}}</span>
          ${{pos.closed_at?`<span class="pos-label">Closed:</span><span class="pos-val">${{pos.closed_at.substring(0,10)}}</span>`:''}}
          <span class="pos-label">Remaining:</span>${{sizeBar}}
          <span class="pos-label" style="margin-left:8px">Trades:</span><span class="pos-val">${{(pos.trades||[]).length}}</span>
        </div>
      </div>
      <div class="pos-pnl ${{pnlCls}}">${{pnlStr}}</div>
      <span class="pos-chevron">&#9654;</span>
    </div>
    ${{tradesSection}}
  </div>`;
}}

function togglePos(pid) {{
  const el = document.getElementById('pos-' + pid);
  if (el) el.classList.toggle('open');
}}

// ---- Debug console ----------------------------------------------------------
function _buildDebug() {{
  const btn = document.getElementById('debugToggle');
  const panel = document.getElementById('debugPanel');
  if (!btn || !panel) return;

  const positions  = OB_DATA || [];
  const allTrades  = positions.flatMap(p => p.trades || []);
  const startBal   = (typeof EQ_DATA !== 'undefined' && EQ_DATA.starting_balance) || 7000;
  const eqTrades   = (typeof EQ_DATA !== 'undefined' && EQ_DATA.trades) || [];

  // Field-level diagnostics
  const zeroPnl    = allTrades.filter(t => t.trade_pnl === 0 && t.action === 'SELL');
  const missingPrice = allTrades.filter(t => t.price == null);
  const nullEntry  = positions.filter(p => p.entry_price == null);

  let html = '';

  html += `<div class="debug-section">`;
  html += `<div class="debug-section-title">DATA LOADED</div>`;
  html += `<div class="debug-field"><span class="debug-key">Source:</span><span class="debug-val">OB_DATA (positions w/ nested trades)</span></div>`;
  html += `<div class="debug-field"><span class="debug-key">Positions:</span><span class="debug-val">${{positions.length}}</span></div>`;
  html += `<div class="debug-field"><span class="debug-key">Total trades:</span><span class="debug-val">${{allTrades.length}}</span></div>`;
  html += `<div class="debug-field"><span class="debug-key">Equity snapshots:</span><span class="debug-val">${{eqTrades.length}}</span></div>`;
  html += `<div class="debug-field"><span class="debug-key">Starting balance:</span><span class="debug-val">$${{startBal}}</span></div>`;
  html += `</div>`;

  html += `<div class="debug-section">`;
  html += `<div class="debug-section-title">P&L CALCULATION</div>`;
  html += `<div class="debug-field"><span class="debug-key">Formula:</span><span class="debug-val">notional × close_frac × (exit−entry)/entry × side_mult</span></div>`;
  html += `<div class="debug-field"><span class="debug-key">TRIM close_fraction:</span><span class="debug-val">0.50 (50% of remaining)</span></div>`;
  html += `<div class="debug-field"><span class="debug-key">EXIT close_fraction:</span><span class="debug-val">1.00 (100% of remaining)</span></div>`;
  html += `<div class="debug-field"><span class="debug-key">BUY/ADD trade_pnl:</span><span class="debug-val">0.00 (no realized PnL on open)</span></div>`;
  html += `<div class="debug-field"><span class="debug-key">pos.total_pnl:</span><span class="debug-val">cumulative sum of all trade_pnl events for this position</span></div>`;
  html += `</div>`;

  html += `<div class="debug-section">`;
  html += `<div class="debug-section-title">ZERO / NULL DIAGNOSTICS</div>`;
  if (zeroPnl.length === 0) {{
    html += `<div class="debug-field"><span class="debug-ok">✓ No SELL trades with zero P&L</span></div>`;
  }} else {{
    html += `<div class="debug-warn">⚠ ${{zeroPnl.length}} SELL trade(s) with $0.00 P&L — likely exit_price fell back to entry_price (break-even). Check if the signal had a parsed price.</div>`;
    zeroPnl.slice(0,5).forEach(t => {{
      html += `<div class="debug-field" style="padding-left:12px"><span class="debug-key">Trade #${{t.trade_id}} (${{t.time||'?'}})</span><span class="debug-val">price=${{t.price}} qty=${{t.quantity}}</span></div>`;
    }});
  }}
  if (missingPrice.length > 0) {{
    html += `<div class="debug-warn" style="margin-top:6px">⚠ ${{missingPrice.length}} trade(s) with null price — signal had no parsed entry_price</div>`;
  }} else {{
    html += `<div class="debug-field"><span class="debug-ok">✓ All trades have a price</span></div>`;
  }}
  if (nullEntry.length > 0) {{
    html += `<div class="debug-warn" style="margin-top:6px">⚠ ${{nullEntry.length}} position(s) with null entry_price: ${{nullEntry.map(p=>p.symbol).join(', ')}}</div>`;
  }} else {{
    html += `<div class="debug-field"><span class="debug-ok">✓ All positions have an entry_price</span></div>`;
  }}
  html += `</div>`;

  html += `<div class="debug-section">`;
  html += `<div class="debug-section-title">SIZE TRACKING</div>`;
  positions.forEach(p => {{
    const flow = (p.trades||[]).map(t => {{
      const after = t.size_after_pct ?? '?';
      return `${{t.action}}→${{after}}%`;
    }}).join(' ');
    const remStr = `remaining=${{p.remaining_pct}}% ($$${{(p.remaining||0).toFixed(0)}} of $$${{(p.original_qty||0).toFixed(0)}})`;
    html += `<div class="debug-field"><span class="debug-key">Pos#${{p.position_id}} ${{p.symbol}}</span><span class="debug-val">${{flow}} | ${{remStr}}</span></div>`;
  }});
  html += `</div>`;

  html += `<div class="debug-section">`;
  html += `<div class="debug-section-title">RAW OB_DATA (first 3 positions)</div>`;
  html += `<span style="color:#374151;white-space:pre-wrap">${{JSON.stringify(OB_DATA.slice(0,3), null, 2)}}</span>`;
  html += `</div>`;

  panel.querySelector('.debug-body').innerHTML = html;
}}

function toggleDebug() {{
  document.getElementById('debugPanel').classList.toggle('open');
}}

// Init
render();
_buildDebug();  // always populate debug console, button visible on all tabs
</script>
</body>
</html>"""
    return html


def write_report(trader: str, signals: list, run_id: str,
                 equity_data: dict | None = None,
                 order_book: list | None = None) -> Path:
    out_dir = PROJECT / "data" / trader / "signals"
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / f"{run_id}.html"
    out.write_text(generate(trader, signals, run_id, equity_data, order_book), encoding="utf-8")
    return out


if __name__ == "__main__":
    args = sys.argv[1:]
    trader    = args[0] if args else "Grizzlies"
    run_id_arg = args[1] if len(args) > 1 else None

    signals_dir = PROJECT / "data" / trader / "signals"
    if run_id_arg:
        jsonl = signals_dir / f"{run_id_arg}.jsonl"
    else:
        files = sorted(signals_dir.glob("*.jsonl")) if signals_dir.exists() else []
        jsonl = files[-1] if files else None

    if jsonl and jsonl.exists():
        import json as _json

        raw = [_json.loads(l) for l in jsonl.read_text(encoding="utf-8").splitlines() if l.strip()]

        class _S:
            def __init__(self, d):
                self.__dict__.update(d)
            def to_dict(self):
                return self.__dict__

        signals = [_S(r) for r in raw]
        rid = jsonl.stem
    else:
        print(f"No signals JSONL found for {trader} -- parsing corpus now...")
        from parsing.parser import parse_corpus
        signals = parse_corpus(trader)
        rid = datetime.now().strftime("%Y%m%dT%H%M%S")

    out = write_report(trader, signals, rid)
    print(f"wrote {out}")
