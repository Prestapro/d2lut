#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
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
.empty { color:var(--muted); padding:18px 10px; }
a { color: var(--blue); text-decoration:none; } a:hover { text-decoration:underline; }
"""


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Export Maxroll D2 Planner modifiers into HTML")
    p.add_argument("--planner-dir", default="data/raw/maxroll/d2planner")
    p.add_argument("--out", default="data/cache/d2planner_modifiers_table.html")
    return p.parse_args()


def _latest_data_module(root: Path) -> Path:
    files = sorted(root.glob("data.min-*.js"))
    if not files:
        raise FileNotFoundError(f"Missing data.min-*.js in {root}")
    return max(files, key=lambda p: p.stat().st_mtime)


def _extract_rows(root: Path) -> list[dict]:
    data_js = _latest_data_module(root)
    node = rf'''
const path = require('node:path');
const {{ pathToFileURL }} = require('node:url');
(async()=>{{
  const mod = await import(pathToFileURL(path.resolve({json.dumps(str(data_js))})).href);
  const d = mod.default;
  const rows = [];
  const normalizePattern = (s) => {{
    let out = String(s || '');
    out = out.replace(/\b(skilltab)\([^)]*\):(\d+(?:-\d+)?)\b/g, (m, k, r) => `class_skill_tree:+${{r}}`);
    out = out.replace(/\b(allskills)\([^)]*\):(\d+(?:-\d+)?)\b/g, (m, k, r) => `allskills:+${{r}}`);
    out = out.replace(/\b(?:cast\d+|cast-skill|gethit-skill|hit-skill|att-skill|kill-skill|death-skill|levelup-skill)\([^)]*\):[^|]+/g, 'chance_to_cast');
    out = out.replace(/\b(?:cast\d+):[^|]+/g, 'chance_to_cast');
    out = out.replace(/\bcharged\([^)]*\):[^|]+/g, 'charges');
    out = out.replace(/\([^)]*\)/g, '(*)');
    out = out.replace(/:(-?\d+(?:-\d+)?)\b/g, ':#');
    out = out.replace(/\s*\|\s*/g, ' | ').replace(/\s+/g, ' ').trim();
    return out;
  }};
  const modSummary = (x, codePrefix='mod') => {{
    const out=[];
    for (let i=1;i<=12;i++) {{
      const code = x[`${{codePrefix}}${{i}}code`] ?? x[`mod${{i}}code`] ?? x[`t1code${{i}}`];
      if (!code) continue;
      const param = x[`mod${{i}}param`];
      const mn = x[`mod${{i}}min`];
      const mx = x[`mod${{i}}max`];
      let s = String(code);
      if (param != null) s += `(${{param}})`;
      if (mn != null && mx != null && String(mn)!==String(mx)) s += `:${{mn}}-${{mx}}`;
      else if (mn != null) s += `:${{mn}}`;
      else if (mx != null) s += `:${{mx}}`;
      out.push(s);
      if (out.length >= 8) break;
    }}
    return out.join(' | ');
  }};
  const affixSummary = (x) => {{
    const out=[];
    for (let i=1;i<=12;i++) {{
      const c = x[`mod${{i}}code`]; if (!c) continue;
      const p = x[`mod${{i}}param`]; const mn=x[`mod${{i}}min`]; const mx=x[`mod${{i}}max`];
      let s=String(c); if (p!=null) s += `(${{p}})`;
      if (mn!=null && mx!=null && String(mn)!==String(mx)) s += `:${{mn}}-${{mx}}`;
      else if (mn!=null) s += `:${{mn}}`; else if (mx!=null) s += `:${{mx}}`;
      out.push(s); if (out.length>=8) break;
    }}
    return out.join(' | ');
  }};
  const typeLists = (x) => {{
    const it=[], et=[];
    for (let i=1;i<=7;i++) {{ if (x[`itype${{i}}`]) it.push(String(x[`itype${{i}}`])); if (x[`etype${{i}}`]) et.push(String(x[`etype${{i}}`])); }}
    return [it.join(','), et.join(',')];
  }};

  const families = [
    ['magicPrefix', d.magicPrefix||{{}}],
    ['magicSuffix', d.magicSuffix||{{}}],
    ['autoMagic', d.autoMagic||{{}}],
    ['rarePrefix', d.rarePrefix||{{}}],
    ['rareSuffix', d.rareSuffix||{{}}],
    ['uniqueMods', d.uniqueMods||{{}}],
  ];
  for (const [fam, obj] of families) {{
    for (const [key, x] of Object.entries(obj)) {{
      const [itypes, etypes] = typeLists(x||{{}});
      const mods = affixSummary(x||{{}});
      rows.push({{
        family: fam,
        key,
        name: x?.name || x?.index || key,
        level: x?.level ?? null,
        req_lvl: x?.levelreq ?? x?.lvlreq ?? null,
        group: x?.group ?? null,
        rare: x?.rare ?? null,
        item_types: itypes,
        exclude_types: etypes,
        mod_codes: mods,
        mod_pattern: normalizePattern(mods),
        is_amulet_magic: /(^|,)amul($|,)/.test(itypes) && (fam === 'magicPrefix' || fam === 'magicSuffix' || fam === 'autoMagic'),
        desc: '',
      }});
    }}
  }}

  for (const [key, x] of Object.entries(d.properties||{{}})) {{
    const stats=[];
    for (let i=1;i<=7;i++) {{ if (x[`stat${{i}}`]) stats.push(String(x[`stat${{i}}`])); }}
    rows.push({{
      family:'properties', key, name:key, level:null, req_lvl:null, group:null, rare:null,
      item_types:'', exclude_types:'', mod_codes:stats.join(' | '), mod_pattern: normalizePattern(stats.join(' | ')), is_amulet_magic:false, desc:[x.func1!=null?`func1:${{x.func1}}`:'', x.func2!=null?`func2:${{x.func2}}`:''].filter(Boolean).join(' | ')
    }});
  }}

  for (const [key, x] of Object.entries(d.itemStatCost||{{}})) {{
    rows.push({{
      family:'itemStatCost', key, name:key, level:null, req_lvl:null, group:null, rare:null,
      item_types:'', exclude_types:'', mod_codes:[x.descstrpos||'', x.descstrneg||'', x.descstr2||''].filter(Boolean).join(' | '), mod_pattern:'', is_amulet_magic:false,
      desc:[x.id!=null?`id:${{x.id}}`:'', x.descfunc!=null?`descfunc:${{x.descfunc}}`:'', x.descpriority!=null?`prio:${{x.descpriority}}`:''].filter(Boolean).join(' | ')
    }});
  }}

  console.log(JSON.stringify(rows));
}})().catch(e=>{{ console.error(e); process.exit(1); }});
'''
    proc = subprocess.run(["node", "-e", node], capture_output=True, text=True, check=True)
    return json.loads(proc.stdout)


def _html(rows: list[dict]) -> str:
    payload = json.dumps(rows, ensure_ascii=False)
    return f'''<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>D2 Planner Modifiers</title><style>{STYLE}</style></head><body><div class="wrap"><div class="bar">
<input id="q" type="search" placeholder="Search modifier / code / stat / text">
<select id="scope"><option value="">All modifiers</option><option value="amulet_magic">Amulet magic affixes</option></select>
<select id="family"><option value="">All families</option></select>
<select id="tier"><option value="">Any levelreq</option><option value="l9">req <= 9</option><option value="l30">req <= 30</option><option value="has_req">has req</option><option value="no_req">no req</option></select>
<select id="sort"><option value="family_name">Family + Name</option><option value="pattern_asc">Pattern A → Z</option><option value="req_desc">Req high → low</option><option value="lvl_desc">Level high → low</option><option value="name_asc">Name A → Z</option></select>
<a href="d2planner_all_items_table.html" class="pill" title="Back to planner item variants">Items</a>
<a href="d2planner_amulet_magic_combos.html" class="pill" title="Open full magic amulet prefix/suffix combinations">Amulet Combos</a>
</div><div class="meta" id="meta"></div><table><thead><tr>
<th data-key="family">Family</th><th data-key="name">Name</th><th data-key="mod_pattern">Pattern</th><th data-key="key">Key</th><th data-key="level" class="num">Level</th><th data-key="req_lvl" class="num">Req</th><th data-key="group" class="num">Group</th><th data-key="item_types">Item Types</th><th data-key="exclude_types">Exclude Types</th><th data-key="mod_codes">Mods / Stats</th><th data-key="desc">Desc</th>
</tr></thead><tbody id="rows"></tbody></table></div>
<script>
const DATA={payload}; const state={{q:'', scope:'', family:'', tier:'', sort:'family_name'}}; const $=(id)=>document.getElementById(id); const tbody=$('rows'), meta=$('meta');
const esc=(s)=>String(s??'').replace(/[&<>\"]/g,c=>({{"&":"&amp;","<":"&lt;",">":"&gt;",'\"':"&quot;"}}[c]));
const n=(v)=>v==null||v===''?'-':Math.round(Number(v));
function headerBase(k){{ return {{family:'family',name:'name',mod_pattern:'pattern',level:'lvl',req_lvl:'req'}}[k]||''; }}
function toggleHeaderSort(k){{ const b=headerBase(k); if(!b) return; const cur=String(state.sort||''); state.sort=(cur===`${{b}}_desc`)?`${{b}}_asc`:(cur===`${{b}}_asc`?`${{b}}_desc`:(b==='name'||b==='family'?`${{b}}_asc`:`${{b}}_desc`)); render(); }}
function sortRows(rows){{ return rows.sort((a,b)=>{{ switch(state.sort){{ case 'pattern_asc': return String(a.mod_pattern||'').localeCompare(String(b.mod_pattern||''))||String(a.name||'').localeCompare(String(b.name||'')); case 'pattern_desc': return String(b.mod_pattern||'').localeCompare(String(a.mod_pattern||''))||String(a.name||'').localeCompare(String(b.name||'')); case 'req_desc': return Number(b.req_lvl??-1)-Number(a.req_lvl??-1)||String(a.family).localeCompare(String(b.family)); case 'req_asc': return Number(a.req_lvl??999)-Number(b.req_lvl??999)||String(a.family).localeCompare(String(b.family)); case 'lvl_desc': return Number(b.level??-1)-Number(a.level??-1)||String(a.family).localeCompare(String(b.family)); case 'lvl_asc': return Number(a.level??999)-Number(b.level??999)||String(a.family).localeCompare(String(b.family)); case 'name_desc': return String(b.name||'').localeCompare(String(a.name||'')); case 'name_asc': return String(a.name||'').localeCompare(String(b.name||'')); case 'family_desc': return String(b.family||'').localeCompare(String(a.family||''))||String(a.name||'').localeCompare(String(b.name||'')); case 'family_asc': return String(a.family||'').localeCompare(String(b.family||''))||String(a.name||'').localeCompare(String(b.name||'')); case 'family_name': default: return String(a.family||'').localeCompare(String(b.family||''))||String(a.name||'').localeCompare(String(b.name||'')); }} }}); }}
function filterRows(rows){{ const q=state.q.trim().toLowerCase(); return rows.filter(r=>{{ if(state.scope==='amulet_magic' && !r.is_amulet_magic) return false; if(state.family && String(r.family||'')!==state.family) return false; if(state.tier==='l9' && !(r.req_lvl!=null && Number(r.req_lvl)<=9)) return false; if(state.tier==='l30' && !(r.req_lvl!=null && Number(r.req_lvl)<=30)) return false; if(state.tier==='has_req' && r.req_lvl==null) return false; if(state.tier==='no_req' && r.req_lvl!=null) return false; if(!q) return true; const hay=[r.family,r.name,r.key,r.mod_pattern,r.item_types,r.exclude_types,r.mod_codes,r.desc].join(' ').toLowerCase(); return hay.includes(q); }}); }}
function render(){{ const rows=sortRows(filterRows(DATA)); const amu=DATA.filter(r=>r.is_amulet_magic).length; meta.textContent=`Modifiers rows: ${{DATA.length}} | amulet magic affixes: ${{amu}} | showing: ${{rows.length}}`; if(!rows.length){{ tbody.innerHTML='<tr><td class="empty" colspan="11">No rows match filters.</td></tr>'; return; }} tbody.innerHTML=rows.map(r=>`<tr><td><span class="pill">${{esc(r.family)}}</span></td><td>${{esc(r.name)}}</td><td>${{esc(r.mod_pattern||'')}}</td><td class="muted">${{esc(r.key)}}</td><td class="num">${{n(r.level)}}</td><td class="num">${{n(r.req_lvl)}}</td><td class="num">${{n(r.group)}}</td><td class="muted">${{esc(r.item_types||'')}}</td><td class="muted">${{esc(r.exclude_types||'')}}</td><td>${{esc(r.mod_codes||'')}}</td><td class="muted">${{esc(r.desc||'')}}</td></tr>`).join(''); }}
$('q').addEventListener('input', e=>{{state.q=e.target.value; render();}}); $('scope').addEventListener('change', e=>{{state.scope=e.target.value; render();}}); $('family').addEventListener('change', e=>{{state.family=e.target.value; render();}}); $('tier').addEventListener('change', e=>{{state.tier=e.target.value; render();}}); $('sort').addEventListener('change', e=>{{state.sort=e.target.value; render();}});
document.querySelectorAll('thead th[data-key]').forEach(th=>th.addEventListener('click',()=>toggleHeaderSort(th.dataset.key||'')));
(function initFamilies(){{ const vals=[...new Set(DATA.map(r=>String(r.family||'')).filter(Boolean))].sort(); const sel=$('family'); for (const v of vals) {{ const o=document.createElement('option'); o.value=v; o.textContent=v; sel.appendChild(o); }} }})();
render();
</script></body></html>'''


def main() -> int:
    args = parse_args()
    rows = _extract_rows(Path(args.planner_dir))
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(_html(rows), encoding='utf-8')
    print(f"exported modifier_rows={len(rows)} out={out}")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
