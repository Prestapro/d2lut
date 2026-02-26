#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sqlite3
import subprocess
from pathlib import Path


STYLE = """
:root {
  --bg: #0a1117; --panel: #101922; --line: #223041; --text: #dce7f4; --muted: #92a6be;
  --green: #86efac; --yellow: #fde68a; --red: #fca5a5; --blue: #93c5fd;
}
body { margin:0; padding:16px; background: radial-gradient(circle at 10% -10%, #172230, var(--bg)); color:var(--text); font:14px/1.35 ui-monospace,SFMono-Regular,Menlo,Consolas,monospace; }
.wrap { width:100%; max-width:none; margin:0 auto; }
.bar { display:grid; gap:8px; grid-template-columns:repeat(auto-fit,minmax(150px,1fr)); background:rgba(16,25,34,.9); border:1px solid var(--line); border-radius:12px; padding:10px; position:sticky; top:0; z-index:5; }
input,select { background:#0c141c; color:var(--text); border:1px solid var(--line); border-radius:8px; padding:8px 10px; }
.meta { color:var(--muted); margin:8px 2px 10px; }
table { width:100%; border-collapse:collapse; background:var(--panel); border:1px solid var(--line); }
thead th { position:sticky; top:56px; background:#586573; color:var(--text); border-bottom:1px solid var(--line); text-align:left; padding:10px; cursor:pointer; }
td { padding:8px 10px; border-bottom:1px solid rgba(34,48,65,.55); vertical-align:top; }
tbody tr:hover { background: rgba(147,197,253,.06); }
.num { text-align:right; white-space:nowrap; }
.muted { color:var(--muted); }
.pill { display:inline-block; padding:2px 7px; border-radius:999px; border:1px solid var(--line); font-size:12px; }
.stack > div { margin:0 0 2px 0; }
.empty { color:var(--muted); padding:18px 10px; }
a { color: var(--blue); text-decoration:none; }
a:hover { text-decoration:underline; }
@media (max-width:980px) { thead th { top:108px; } }
"""


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Export full Maxroll D2 Planner item variants into HTML (with optional market overlay)")
    p.add_argument("--db", default="data/cache/d2lut.db")
    p.add_argument("--planner-dir", default="data/raw/maxroll/d2planner")
    p.add_argument("--market-key", default="d2r_sc_ladder")
    p.add_argument("--out", default="data/cache/d2planner_all_items_table.html")
    return p.parse_args()


def _latest_data_module(root: Path) -> Path:
    files = sorted(root.glob("data.min-*.js"))
    if not files:
        raise FileNotFoundError(f"Missing data.min-*.js in {root}")
    return max(files, key=lambda p: p.stat().st_mtime)


def _extract_planner_rows(root: Path) -> list[dict]:
    data_js = _latest_data_module(root)
    node = rf'''
const path = require('node:path');
const {{ pathToFileURL }} = require('node:url');
(async()=>{{
  const mod = await import(pathToFileURL(path.resolve({json.dumps(str(data_js))})).href);
  const d = mod.default;
  const rows = [];
  const tierOf = (x) => {{
    if (!x || !x.code) return "";
    if (x.normcode && x.code === x.normcode) return "normal";
    if (x.ubercode && x.code === x.ubercode) return "exceptional";
    if (x.ultracode && x.code === x.ultracode) return "elite";
    return "";
  }};
  const rangeSummary = (x, prefix='prop', minp='min', maxp='max') => {{
    const out=[];
    for (let i=1;i<=12;i++) {{
      const p = x[`${{prefix}}${{i}}`] ?? x[`a${{prefix}}${{i}}a`] ?? x[`a${{prefix}}${{i}}`];
      if (!p) continue;
      let mn = x[`${{minp}}${{i}}`] ?? x[`a${{minp}}${{i}}a`] ?? x[`a${{minp}}${{i}}`];
      let mx = x[`${{maxp}}${{i}}`] ?? x[`a${{maxp}}${{i}}a`] ?? x[`a${{maxp}}${{i}}`];
      if (mn != null && mx != null && String(mn)!==String(mx)) out.push(`${{p}}:${{mn}}-${{mx}}`);
      else if (mn != null) out.push(`${{p}}:${{mn}}`);
      else if (mx != null) out.push(`${{p}}:${{mx}}`);
      else out.push(String(p));
      if (out.length>=8) break;
    }}
    return out.join(' | ');
  }};
  const baseByCode = Object.assign({{}}, d.armor||{{}}, d.weapons||{{}}, d.misc||{{}});

  for (const [code,x] of Object.entries(d.armor||{{}})) rows.push({{ planner_group:'armor', planner_key:code, name:x.name||code, code:x.code||code, req_lvl:x.levelreq ?? null, base_tier:tierOf(x), item_type:x.type||'', sockets:x.gemsockets ?? null, ranges:[`class:armor`, x.gemsockets!=null?`sockets:0-${{x.gemsockets}}`:'' ].filter(Boolean).join(' | '), quality:'base' }});
  for (const [code,x] of Object.entries(d.weapons||{{}})) rows.push({{ planner_group:'weapon', planner_key:code, name:x.name||code, code:x.code||code, req_lvl:x.levelreq ?? null, base_tier:tierOf(x), item_type:x.type||'', sockets:x.gemsockets ?? null, ranges:[`class:weapon`, x.gemsockets!=null?`sockets:0-${{x.gemsockets}}`:'' ].filter(Boolean).join(' | '), quality:'base' }});
  for (const [code,x] of Object.entries(d.misc||{{}})) rows.push({{ planner_group:'misc', planner_key:code, name:x.name||code, code:x.code||code, req_lvl:x.levelreq ?? null, base_tier:tierOf(x), item_type:x.type||'', sockets:x.gemsockets ?? null, ranges:[x.type?`type:${{x.type}}`:'', x.gemsockets!=null&&x.gemsockets>0?`sockets:0-${{x.gemsockets}}`:'' ].filter(Boolean).join(' | '), quality:'misc' }});

  for (const [k,x] of Object.entries(d.uniqueItems||{{}})) {{
    const base = baseByCode[x.code] || null;
    rows.push({{
      planner_group:'unique', planner_key:k, name:x.index||k, code:x.code||'', req_lvl:x.lvlreq ?? null,
      base_tier:tierOf(base||x), item_type:(base&&base.type)||'', sockets:(base&&base.gemsockets) ?? null,
      ranges: rangeSummary(x), quality:'unique'
    }});
  }}
  for (const [k,x] of Object.entries(d.setItems||{{}})) {{
    const code = x.item || x.code || '';
    const base = baseByCode[code] || null;
    rows.push({{
      planner_group:'set', planner_key:k, name:x.index||k, code:code, req_lvl:x.lvlreq ?? null,
      base_tier:tierOf(base||x), item_type:(base&&base.type)||'', sockets:(base&&base.gemsockets) ?? null,
      ranges: rangeSummary(x), quality:'set'
    }});
  }}
  for (const [k,x] of Object.entries(d.runewords||{{}})) {{
    const runes=[]; for (let i=1;i<=6;i++) if (x[`rune${{i}}`]) runes.push(x[`rune${{i}}`]);
    const props=[]; for (let t=1;t<=3;t++) for (let i=1;i<=6;i++) {{ const c=x[`t${{t}}code${{i}}`]; if(!c) continue; const mn=x[`t${{t}}min${{i}}`]; const mx=x[`t${{t}}max${{i}}`]; if (mn!=null && mx!=null && String(mn)!==String(mx)) props.push(`${{c}}:${{mn}}-${{mx}}`); else if (mn!=null) props.push(`${{c}}:${{mn}}`); else if (mx!=null) props.push(`${{c}}:${{mx}}`); else props.push(String(c)); if (props.length>=8) break; }}
    rows.push({{ planner_group:'runeword', planner_key:k, name:x.name||k, code:'', req_lvl:null, base_tier:'', item_type:[x.itype1,x.itype2,x.itype3].filter(Boolean).join(','), sockets:null, ranges:[runes.length?`runes:${{runes.join('+')}}`:'', ...props.slice(0,6)].filter(Boolean).join(' | '), quality:'runeword' }});
  }}

  console.log(JSON.stringify(rows));
}})().catch(e=>{{ console.error(e); process.exit(1); }});
'''
    proc = subprocess.run(["node", "-e", node], capture_output=True, text=True, check=True)
    return json.loads(proc.stdout)


def _market_maps(conn: sqlite3.Connection, market_key: str):
    conn.row_factory = sqlite3.Row
    canon_by_base = {r[0]: r[1] for r in conn.execute("select source_key, canonical_item_id from catalog_items where source_table='catalog_bases'")}
    canon_by_unique = {r[0]: r[1] for r in conn.execute("select source_key, canonical_item_id from catalog_items where source_table='catalog_uniques'")}
    canon_by_set = {r[0]: r[1] for r in conn.execute("select source_key, canonical_item_id from catalog_items where source_table='catalog_sets'")}
    obs = {
        r[0]: dict(obs_count=int(r[1] or 0), max_fg=float(r[2]) if r[2] is not None else None, max_bin_fg=float(r[3]) if r[3] is not None else None)
        for r in conn.execute(
            "select canonical_item_id,count(*),max(price_fg),max(case when signal_kind='bin' then price_fg end) from observed_prices where market_key=? group by canonical_item_id",
            (market_key,),
        )
    }
    pe = {
        r[0]: dict(est_fg=float(r[1]) if r[1] is not None else None, range_high=float(r[2]) if r[2] is not None else None)
        for r in conn.execute("select variant_key, estimate_fg, range_high_fg from price_estimates where market_key=?", (market_key,))
    }
    return canon_by_base, canon_by_unique, canon_by_set, obs, pe


def _attach_market(rows: list[dict], conn: sqlite3.Connection, market_key: str) -> list[dict]:
    canon_by_base, canon_by_unique, canon_by_set, obs_by_canon, pe_by_variant = _market_maps(conn, market_key)
    out=[]
    for r in rows:
      canon = ''
      if r['planner_group'] in {'armor','weapon','misc'} and r.get('code'):
        canon = canon_by_base.get(r['code'], '')
      elif r['planner_group']=='unique':
        canon = canon_by_unique.get(r['name'], '')
      elif r['planner_group']=='set':
        canon = canon_by_set.get(r['name'], '')
      # runes misc special-case from names
      if not canon and r['planner_group']=='misc':
        nm=(r.get('name') or '').lower()
        if nm.endswith(' rune'):
          canon='rune:'+nm.replace(' rune','').replace(' ','_')
      obs = obs_by_canon.get(canon, {}) if canon else {}
      sell = obs.get('max_bin_fg') or obs.get('max_fg')
      est = None
      # direct estimate via canonical-derived common variant fallback is not reliable here; leave blank for now except runes
      if canon and canon in pe_by_variant:
        est = pe_by_variant[canon].get('est_fg')
      r2=dict(r)
      r2['canonical_item_id']=canon
      r2['obs_count']=int(obs.get('obs_count') or 0)
      r2['sell_fg']=sell
      r2['estimate_fg']=est
      r2['has_market']=bool(obs)
      out.append(r2)
    return out


def _html(rows: list[dict], market_key: str) -> str:
    payload=json.dumps(rows, ensure_ascii=False)
    return f'''<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>D2 Planner All Variants</title><style>{STYLE}</style></head><body><div class="wrap"><div class="bar">
<input id="q" type="search" placeholder="Search planner item / code / canonical">
<input id="modQ" type="search" placeholder="Filter by modifier/range (dmg%, res-all, runes:...)">
<select id="mode"><option value="all">All planner variants</option><option value="market">Market-covered only</option><option value="no_market">No market data only</option></select>
<select id="group"><option value="">All groups</option></select>
<select id="tier"><option value="">All base tiers</option><option value="normal">normal</option><option value="exceptional">exceptional</option><option value="elite">elite</option></select>
<select id="sort"><option value="sell_desc">Sell FG high → low</option><option value="name_asc">Name A → Z</option><option value="req_desc">Req high → low</option><option value="group_asc">Group A → Z</option></select>
<a href="d2planner_modifiers_table.html" class="pill" title="Open D2 Planner modifiers (prefix/suffix/automagic/properties/itemStatCost)">Modifiers</a>
<a href="d2planner_amulet_magic_combos.html" class="pill" title="Open full magic amulet prefix/suffix combinations">Amulet Combos</a>
</div><div class="meta" id="meta"></div><table><thead><tr>
<th data-key="name">Name</th><th data-key="planner_group">Group</th><th data-key="quality">Quality</th><th data-key="code">Code</th><th data-key="item_type">Type</th><th data-key="base_tier">Base Tier</th><th data-key="req_lvl" class="num">Req</th><th data-key="ranges">Ranges</th><th data-key="canonical_item_id">Canonical</th><th data-key="estimate_fg" class="num">Estimate FG</th><th data-key="sell_fg" class="num">Sell FG</th><th data-key="obs_count" class="num">Obs</th>
</tr></thead><tbody id="rows"></tbody></table></div>
<script>
const DATA={payload};
const state={{q:'',modQ:'',mode:'all',group:'',tier:'',sort:'sell_desc'}}; const $=(id)=>document.getElementById(id); const tbody=$("rows"), meta=$("meta");
const esc=(s)=>String(s??'').replace(/[&<>\"]/g,c=>({{"&":"&amp;","<":"&lt;",">":"&gt;",'\"':"&quot;"}}[c]));
const n=(v)=>v==null||v===''?'-':Math.round(Number(v));
function headerBase(k){{return {{name:'name',planner_group:'group',req_lvl:'req',sell_fg:'sell',obs_count:'obs'}}[k]||'';}}
function toggleHeaderSort(k){{const b=headerBase(k); if(!b) return; state.sort=(state.sort===`${{b}}_desc`)?`${{b}}_asc`:(state.sort===`${{b}}_asc`?`${{b}}_desc`:(b==='name'||b==='group'?`${{b}}_asc`:`${{b}}_desc`)); render();}}
function sortRows(rows){{ return rows.sort((a,b)=>{{ switch(state.sort){{ case 'name_asc': return String(a.name||'').localeCompare(String(b.name||'')); case 'name_desc': return String(b.name||'').localeCompare(String(a.name||'')); case 'group_asc': return String(a.planner_group||'').localeCompare(String(b.planner_group||''))||String(a.name||'').localeCompare(String(b.name||'')); case 'group_desc': return String(b.planner_group||'').localeCompare(String(a.planner_group||''))||String(a.name||'').localeCompare(String(b.name||'')); case 'req_desc': return Number(b.req_lvl||-1)-Number(a.req_lvl||-1)||Number(b.sell_fg||0)-Number(a.sell_fg||0); case 'req_asc': return Number(a.req_lvl||999)-Number(b.req_lvl||999)||Number(b.sell_fg||0)-Number(a.sell_fg||0); case 'obs_desc': return Number(b.obs_count||0)-Number(a.obs_count||0)||Number(b.sell_fg||0)-Number(a.sell_fg||0); case 'obs_asc': return Number(a.obs_count||0)-Number(b.obs_count||0)||Number(b.sell_fg||0)-Number(a.sell_fg||0); case 'sell_asc': return Number(a.sell_fg||0)-Number(b.sell_fg||0)||String(a.name||'').localeCompare(String(b.name||'')); case 'sell_desc': default: return Number(b.sell_fg||0)-Number(a.sell_fg||0)||Number(b.obs_count||0)-Number(a.obs_count||0); }} }}); }}
function filterRows(rows){{ const q=state.q.trim().toLowerCase(); const modQ=state.modQ.trim().toLowerCase(); return rows.filter(r=>{{ if(state.mode==='market' && !r.has_market) return false; if(state.mode==='no_market' && r.has_market) return false; if(state.group && String(r.planner_group||'')!==state.group) return false; if(state.tier && String(r.base_tier||'')!==state.tier) return false; if(modQ && !String(r.ranges||'').toLowerCase().includes(modQ)) return false; if(!q) return true; const hay=[r.name,r.planner_group,r.quality,r.code,r.item_type,r.base_tier,r.canonical_item_id,r.ranges].join(' ').toLowerCase(); return hay.includes(q); }}); }}
function render(){{ const rows=sortRows(filterRows(DATA)); const market=DATA.filter(r=>r.has_market).length; meta.textContent=`Planner variants: ${{DATA.length}} | market-covered: ${{market}} | showing: ${{rows.length}} | market=${market_key}`; if(!rows.length){{tbody.innerHTML='<tr><td class="empty" colspan="12">No rows match filters.</td></tr>'; return;}} tbody.innerHTML=rows.map(r=>`<tr><td>${{esc(r.name)}}</td><td>${{esc(r.planner_group)}}</td><td>${{esc(r.quality)}}</td><td class="muted">${{esc(r.code||'')}}</td><td class="muted">${{esc(r.item_type||'')}}</td><td>${{r.base_tier?`<span class="pill">${{esc(r.base_tier)}}</span>`:'<span class="muted">-</span>'}}</td><td class="num">${{r.req_lvl==null?'-':n(r.req_lvl)}}</td><td class="muted">${{esc(r.ranges||'')}}</td><td class="muted">${{esc(r.canonical_item_id||'')}}</td><td class="num">${{r.estimate_fg==null?'-':`${{n(r.estimate_fg)}} fg`}}</td><td class="num">${{r.sell_fg==null?'-':`${{n(r.sell_fg)}} fg`}}</td><td class="num">${{n(r.obs_count||0)}}</td></tr>`).join(''); }}
$('q').addEventListener('input',e=>{{state.q=e.target.value; render();}}); $('modQ').addEventListener('input',e=>{{state.modQ=e.target.value; render();}}); $('mode').addEventListener('change',e=>{{state.mode=e.target.value; render();}}); $('group').addEventListener('change',e=>{{state.group=e.target.value; render();}}); $('tier').addEventListener('change',e=>{{state.tier=e.target.value; render();}}); $('sort').addEventListener('change',e=>{{state.sort=e.target.value; render();}}); document.querySelectorAll('thead th[data-key]').forEach(th=>th.addEventListener('click',()=>toggleHeaderSort(th.dataset.key||'')));
(function initGroups(){{ const vals=[...new Set(DATA.map(r=>String(r.planner_group||'')).filter(Boolean))].sort(); const sel=$('group'); for(const v of vals){{ const o=document.createElement('option'); o.value=v; o.textContent=v; sel.appendChild(o); }} }})();
render();
</script></body></html>'''


def main() -> int:
    args = parse_args()
    root = Path(args.planner_dir)
    rows = _extract_planner_rows(root)
    conn = sqlite3.connect(args.db)
    try:
        rows = _attach_market(rows, conn, args.market_key)
    finally:
        conn.close()
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(_html(rows, args.market_key), encoding='utf-8')
    market_cov = sum(1 for r in rows if r.get('has_market'))
    print(f"exported planner_variants={len(rows)} market_covered={market_cov} out={out}")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
