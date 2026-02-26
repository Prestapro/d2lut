#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import urllib.parse
import re
import subprocess
from pathlib import Path
from html import unescape

STYLE = """
:root { --bg:#0a1117; --panel:#101922; --line:#223041; --text:#dce7f4; --muted:#92a6be; --blue:#93c5fd; }
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
    p = argparse.ArgumentParser(description="Export full D2 Planner magic amulet prefix/suffix combinations into HTML")
    p.add_argument("--planner-dir", default="data/raw/maxroll/d2planner")
    p.add_argument("--property-table-html", default="data/cache/property_price_table.html")
    p.add_argument("--out", default="data/cache/d2planner_amulet_magic_combos.html")
    return p.parse_args()


def _latest_data_module(root: Path) -> Path:
    files = sorted(root.glob("data.min-*.js"))
    if not files:
        raise FileNotFoundError(f"Missing data.min-*.js in {root}")
    return max(files, key=lambda p: p.stat().st_mtime)


def _extract_amulet_affixes(root: Path) -> dict:
    data_js = _latest_data_module(root)
    node = rf'''
const path = require('node:path');
const {{ pathToFileURL }} = require('node:url');
(async()=>{{
  const mod = await import(pathToFileURL(path.resolve({json.dumps(str(data_js))})).href);
  const d = mod.default;
  const forceSingleToRange = (s) => {{
    // Make fixed rolls explicit for classifier/debug UX: dex:3 -> dex:3-3, skilltab(6):3 -> skilltab(6):3-3
    return String(s || '').replace(/:((-?\d+))(?!\s*-\s*-?\d)(?=$|\s*\|)/g, ':$1-$1');
  }};
  const normalizePattern = (s) => {{
    let out = String(s || '');
    out = out.replace(/\b(skilltab)\([^)]*\):(\d+(?:-\d+)?)\b/g, (m,k,r)=>`class_skill_tree:+${{r}}`);
    out = out.replace(/\b(allskills)\([^)]*\):(\d+(?:-\d+)?)\b/g, (m,k,r)=>`allskills:+${{r}}`);
    out = out.replace(/\b(?:cast\d+|cast-skill|gethit-skill|hit-skill|att-skill|kill-skill|death-skill|levelup-skill)\([^)]*\):[^|]+/g, 'chance_to_cast');
    out = out.replace(/\b(?:cast\d+):[^|]+/g, 'chance_to_cast');
    out = out.replace(/\bcharged\([^)]*\):[^|]+/g, 'charges');
    out = out.replace(/\([^)]*\)/g, '(*)');
    out = out.replace(/:(-?\d+(?:-\d+)?)\b/g, ':#');
    out = out.replace(/\s*\|\s*/g, ' | ').replace(/\s+/g, ' ').trim();
    return out;
  }};
      const affixSummary = (x) => {{
        const out=[];
        for (let i=1;i<=12;i++) {{
          const c = x[`mod${{i}}code`]; if (!c) continue;
          const p = x[`mod${{i}}param`]; const mn=x[`mod${{i}}min`]; const mx=x[`mod${{i}}max`];
          let s=String(c); if (p!=null) s += `(${{p}})`;
          // Always show explicit min-max so classifier/debug workflows can see fixed rolls as 3-3, not just 3.
          if (mn!=null && mx!=null) s += `:${{mn}}-${{mx}}`;
          else if (mn!=null) s += `:${{mn}}-${{mn}}`;
          else if (mx!=null) s += `:${{mx}}-${{mx}}`;
          out.push(s); if (out.length>=8) break;
        }}
      return forceSingleToRange(out.join(' | '));
  }};
  const typeList = (x) => {{
    const it=[]; for (let i=1;i<=7;i++) if (x[`itype${{i}}`]) it.push(String(x[`itype${{i}}`]));
    return it;
  }};
  const pick = (obj, fam) => Object.entries(obj||{{}})
    .filter(([k,x]) => typeList(x||{{}}).includes('amul'))
    .map(([key,x]) => {{
      const mods = affixSummary(x||{{}});
      return {{
        family: fam,
        key,
        name: x?.name || key,
        level: x?.level ?? null,
        req_lvl: x?.levelreq ?? x?.lvlreq ?? null,
        group: x?.group ?? null,
        mod_codes: mods,
        mod_pattern: normalizePattern(mods),
      }};
    }});
  const out = {{
    prefixes: pick(d.magicPrefix, 'magicPrefix'),
    suffixes: pick(d.magicSuffix, 'magicSuffix')
  }};
  console.log(JSON.stringify(out));
}})().catch(e=>{{ console.error(e); process.exit(1); }});
'''
    proc = subprocess.run(["node", "-e", node], capture_output=True, text=True, check=True)
    return json.loads(proc.stdout)


def _combine(prefixes: list[dict], suffixes: list[dict]) -> list[dict]:
    rows: list[dict] = []
    base = "Amulet"
    # base only row for reference
    rows.append({
        "kind": "base_only",
        "display_name": base,
        "prefix_name": "",
        "suffix_name": "",
        "prefix_pattern": "",
        "suffix_pattern": "",
        "combined_pattern": "",
        "pattern_key": "",
        "prefix_mods": "",
        "suffix_mods": "",
        "dup_count": 1,
        "req_lvl": 0,
        "prefix_level": None,
        "suffix_level": None,
    })
    for p in prefixes:
        rows.append({
            "kind": "prefix_only",
            "display_name": f"{p['name']} {base}",
            "prefix_name": p["name"], "suffix_name": "",
            "prefix_pattern": p.get("mod_pattern", ""), "suffix_pattern": "",
            "combined_pattern": p.get("mod_codes", ""),
            "pattern_key": p.get("mod_pattern", ""),
            "prefix_mods": p.get("mod_codes", ""), "suffix_mods": "",
            "dup_count": 1,
            "req_lvl": p.get("req_lvl"), "prefix_level": p.get("level"), "suffix_level": None,
        })
    for s in suffixes:
        rows.append({
            "kind": "suffix_only",
            "display_name": f"{base} {s['name']}",
            "prefix_name": "", "suffix_name": s["name"],
            "prefix_pattern": "", "suffix_pattern": s.get("mod_pattern", ""),
            "combined_pattern": s.get("mod_codes", ""),
            "pattern_key": s.get("mod_pattern", ""),
            "prefix_mods": "", "suffix_mods": s.get("mod_codes", ""),
            "dup_count": 1,
            "req_lvl": s.get("req_lvl"), "prefix_level": None, "suffix_level": s.get("level"),
        })
    for p in prefixes:
        for s in suffixes:
            reqs = [x for x in [p.get("req_lvl"), s.get("req_lvl")] if x is not None]
            rows.append({
                "kind": "prefix_suffix",
                "display_name": f"{p['name']} {base} {s['name']}",
                "prefix_name": p["name"], "suffix_name": s["name"],
                "prefix_pattern": p.get("mod_pattern", ""), "suffix_pattern": s.get("mod_pattern", ""),
                "combined_pattern": " + ".join([x for x in [p.get('mod_codes',''), s.get('mod_codes','')] if x]),
                "pattern_key": " + ".join([x for x in [p.get('mod_pattern',''), s.get('mod_pattern','')] if x]),
                "prefix_mods": p.get("mod_codes", ""), "suffix_mods": s.get("mod_codes", ""),
                "dup_count": 1,
                "req_lvl": max(reqs) if reqs else None,
                "prefix_level": p.get("level"), "suffix_level": s.get("level"),
            })
    dedup: dict[tuple, dict] = {}
    for r in rows:
        key = (
            r["kind"],
            r["display_name"],
            r.get("req_lvl"),
            r.get("prefix_name", ""),
            r.get("suffix_name", ""),
            r.get("prefix_mods", ""),
            r.get("suffix_mods", ""),
        )
        if key in dedup:
            dedup[key]["dup_count"] = int(dedup[key].get("dup_count", 1)) + 1
        else:
            dedup[key] = r
    return list(dedup.values())


def _score_from_pattern(pattern: str) -> int | None:
    p = (pattern or "").lower()
    if not p:
        return None
    score = 0
    matched = False

    def has(x: str) -> bool:
        return x in p
    def max_roll(code_pat: str) -> int | None:
        # code_pat like "str", "dex", "hp", "res-all"
        m = re.search(rf"{re.escape(code_pat)}(?:\(\d+\))?:(-?\d+)-(-?\d+)", p)
        if not m:
            return None
        return max(int(m.group(1)), int(m.group(2)))

    # Core amulet value drivers (coarse heuristic; not market price)
    if has("class_skill_tree:+3") or has("class_skill_tree:+3-3"):
        score += 800
        matched = True
    elif has("class_skill_tree:+2") or has("class_skill_tree:+2-2"):
        score += 350
        matched = True
    elif has("class_skill_tree:+1") or has("class_skill_tree:+1-1"):
        score += 120
        matched = True

    if has("allskills:+1") or has("allskills:+1-1"):
        score += 600
        matched = True
    elif has("allskills:+2") or has("allskills:+2-2"):
        score += 1400
        matched = True

    # Resist / FCR / stats
    if has("res-all"):
        score += 250
        matched = True
        m = re.search(r"res-all\(\*\):(\d+)-(\d+)", p)
        if m:
            score += int(m.group(2)) * 4
    if has("cast:#") or has("fcr:#"):
        score += 350
        matched = True
    if has("chance_to_cast"):
        score += 40
        matched = True
    if has("charges"):
        score += 30
        matched = True
        if "charged(54)" in p:  # teleport charges family
            score += 180

    # Life/mana/stats
    # Scale by actual roll range (prevents +5 life looking like top-tier).
    scaled_specs = [
        ("str", 6.0),      # +30 str ~= +180
        ("dex", 5.0),      # +20 dex ~= +100
        ("vit", 6.0),
        ("enr", 3.0),
        ("hp", 4.0),       # +5 life = +20, +30 life = +120
        ("mana", 2.0),
        ("regen", 12.0),   # small numeric domain
        ("mag%", 5.0),
        ("att", 1.0),
    ]
    for code, mult in scaled_specs:
        v = max_roll(code)
        if v is not None:
            score += int(max(v, 0) * mult)
            matched = True

    # Res single
    for code in ["res-fire", "res-cold", "res-ltng", "res-pois"]:
        v = max_roll(code)
        if v is not None:
            score += int(max(v, 0) * 2.0)
            matched = True

    # Penalize low-signal utility clutter when no skills present
    if not any(x in p for x in ["class_skill_tree", "allskills"]):
        if any(x in p for x in ["stam:#", "light:#", "thorns:#", "gold%:#", "red-dmg:#"]):
            score -= 40

    if not matched:
        return None
    return max(score, 0)


def _attach_fg_estimates(rows: list[dict]) -> list[dict]:
    for r in rows:
        est = _score_from_pattern(str(r.get("combined_pattern") or r.get("pattern_key") or ""))
        if est is None:
            est2 = _score_from_pattern(str(r.get("pattern_key") or ""))
            if est2 is None:
                r["fg_est"] = None
                r["fg_basis"] = "unknown"
            else:
                r["fg_est"] = est2
                r["fg_basis"] = "heuristic-pattern"
        else:
            r["fg_est"] = est
            r["fg_basis"] = "heuristic"
    return rows


SKILLTAB_TAGS: dict[int, tuple[str, list[str]]] = {
    0: ("amazon_bow", ["bow", "bowa", "ama"]),
    1: ("amazon_passive", ["passive", "passives", "ama"]),
    2: ("amazon_java", ["java", "jav", "zon", "ama"]),
    3: ("sorc_fire", ["fire", "fireskills", "sorc", "warlock"]),
    4: ("sorc_light", ["light", "lightning", "lightsorc", "sorc", "warlock"]),
    5: ("sorc_cold", ["cold", "coldsorc", "sorc", "warlock"]),
    6: ("necro_curses", ["curses", "curse", "necro", "nec"]),
    7: ("necro_pnb", ["pnb", "poison", "bone", "necro", "nec"]),
    8: ("necro_summon", ["summon", "summoning", "summon nec", "necro", "nec"]),
    9: ("pal_combat", ["pcomb", "combat", "pal", "pala"]),
    10: ("pal_offensive", ["off aura", "offensive auras", "pala", "pal"]),
    11: ("pal_defensive", ["def aura", "defensive auras", "pala", "pal"]),
    12: ("barb_combat", ["bcombat", "barb combat", "barb"]),
    13: ("barb_masteries", ["masteries", "barb mastery", "barb"]),
    14: ("barb_warcries", ["wc", "warcries", "war cries", "barb"]),
    15: ("druid_summon", ["druid summon", "summon druid", "druid"]),
    16: ("druid_shape", ["shape", "shapeshift", "druid"]),
    17: ("druid_elemental", ["ele", "elemental", "druid"]),
    18: ("assassin_traps", ["traps", "trap", "sin", "assa", "assassin"]),
    19: ("assassin_shadow", ["shadow", "shadows", "sin", "assa", "assassin"]),
    20: ("assassin_martial", ["ma", "martial", "martial arts", "sin", "assa", "assassin"]),
}


def _d2jsp_tags_for_amulet_combo(row: dict) -> str:
    if row.get("kind") == "base_only":
        return "amulet, amu, ammy"
    text = " ".join(
        str(row.get(k, "")) for k in ("display_name", "combined_pattern", "pattern_key", "prefix_mods", "suffix_mods")
    ).lower()
    tags: list[str] = ["amu", "ammy"]
    seen: set[str] = set()

    def add(tag: str) -> None:
        t = tag.strip().lower()
        if not t or t in seen:
            return
        seen.add(t)
        tags.append(t)

    # skilltab -> common d2jsp shorthand
    for m in re.finditer(r"skilltab\((\d+)\):(-?\d+)-(-?\d+)", text):
        tab = int(m.group(1))
        hi = max(int(m.group(2)), int(m.group(3)))
        meta = SKILLTAB_TAGS.get(tab)
        if meta:
            _, aliases = meta
            for alias in aliases:
                if hi > 0:
                    add(f"{hi} {alias} amu")
            # compact ultra-common forms
            if aliases and hi > 0:
                add(f"+{hi} {aliases[0]}")

    # all skills
    m = re.search(r"allskills\(\d+\):(-?\d+)-(-?\d+)", text)
    if m:
        hi = max(int(m.group(1)), int(m.group(2)))
        add(f"{hi} all skills amu")
        add(f"+{hi} allskills ammy")

    # common desirable amulet mods
    if "cast1:" in text or "fcr:" in text or "cast:#" in text:
        add("fcr amu")
    if "str:" in text:
        add("str amu")
    if "dex:" in text:
        add("dex amu")
    if "res-all" in text:
        add("@ amu")
        add("all res amu")
    if "res-fire:" in text:
        add("fire res amu")
    if "res-cold:" in text:
        add("cold res amu")
    if "res-ltng:" in text:
        add("light res amu")
    if "res-pois:" in text:
        add("poison res amu")
    if "hp:" in text or "hp/lvl" in text:
        add("life amu")
    if "mana:" in text or "mana/lvl" in text:
        add("mana amu")
    if "chance_to_cast" in text:
        add("ctc amu")
    if "charges" in text:
        add("charges amu")
    if "charged(54)" in text:
        add("tele amu")
        add("teleport charges amu")

    # raw suffix/prefix hints can still help
    pn = str(row.get("prefix_name", "")).strip()
    sn = str(row.get("suffix_name", "")).strip()
    if pn:
        add(pn)
    if sn:
        add(sn)
    return " | ".join(tags[:12])


def _d2jsp_search_queries_for_amulet_combo(row: dict, tags: str) -> list[dict]:
    text = " ".join(str(row.get(k, "")) for k in ("combined_pattern", "pattern_key", "prefix_mods", "suffix_mods")).lower()
    queries: list[dict] = []
    seen: set[str] = set()

    def add_query(label: str, qtxt: str) -> None:
        q = " ".join(qtxt.strip().split())
        if not q:
            return
        key = q.lower()
        if key in seen:
            return
        seen.add(key)
        queries.append({"label": label, "query": q, "url": "https://forums.d2jsp.org/search.php?c=8&r=1"})

    # Primary skill-tree query (d2jsp-style)
    skill_query = None
    for m in re.finditer(r"skilltab\((\d+)\):(-?\d+)-(-?\d+)", text):
        tab = int(m.group(1))
        hi = max(int(m.group(2)), int(m.group(3)))
        meta = SKILLTAB_TAGS.get(tab)
        if not meta or hi <= 0:
            continue
        _, aliases = meta
        # prefer shortest common market alias
        alias = None
        for cand in aliases:
            if cand in {"curses", "pnb", "warcries", "ele", "traps", "shadow", "ma", "combat", "passive", "java", "bow", "cold", "fire", "light"}:
                alias = cand
                break
        if alias is None:
            alias = aliases[0]
        skill_query = f"{hi} {alias} amu"
        break

    # Secondary affix/mod tag for 2-attribute searches
    second = None
    second_map = [
        ("fcr", ["fcr", "cast1:"]),
        ("str", ["str:"]),
        ("dex", ["dex:"]),
        ("life", ["hp:"]),
        ("mana", ["mana:"]),
        ("all res", ["res-all"]),
        ("fire res", ["res-fire:"]),
        ("cold res", ["res-cold:"]),
        ("light res", ["res-ltng:"]),
        ("poison res", ["res-pois:"]),
        ("charges", ["charges", "charged("]),
        ("ctc", ["chance_to_cast"]),
    ]
    for label, keys in second_map:
        if any(k in text for k in keys):
            second = label
            break

    if skill_query and second:
        add_query("combo", f"{skill_query} {second}")
    if skill_query:
        add_query(skill_query, skill_query)

    # Add a few strong fallback tags (non-generic, non-duplicate aliases)
    generic = {"amu", "ammy", "amulet"}
    for t in [x.strip() for x in tags.split("|") if x.strip()]:
        tl = t.lower()
        if tl in generic:
            continue
        if tl.startswith("+3 ") or tl.startswith("+2 ") or tl.startswith("+1 "):
            continue  # covered by skill query
        add_query(t, t if any(x in tl for x in ("amu", "ammy", "amulet")) else f"{t} amu")
        if len(queries) >= 5:
            break
    return queries


def _attach_d2jsp_search(rows: list[dict]) -> list[dict]:
    for r in rows:
        tags = _d2jsp_tags_for_amulet_combo(r)
        r["d2jsp_tags"] = tags
        queries = _d2jsp_search_queries_for_amulet_combo(r, tags)
        r["d2jsp_search_queries"] = queries
        r["d2jsp_search_url"] = queries[0]["url"] if queries else None
    return rows


def _load_property_table_rows(path: Path) -> list[dict]:
    if not path.exists():
        return []
    s = path.read_text(encoding="utf-8")
    m = re.search(r"const DATA = (\[.*?\]);\s*\n\s*const state", s, re.S)
    if not m:
        return []
    return json.loads(unescape(m.group(1)))


def _property_amulet_market_anchors(path: Path) -> dict[str, dict]:
    rows = _load_property_table_rows(path)
    anchors: dict[str, dict] = {}
    for r in rows:
        sig = str(r.get("signature", "")).lower()
        ex = str(r.get("example_excerpt", "")).lower()
        hay = " ".join([
            sig, ex,
            str(r.get("name_display", "")).lower(),
            str(r.get("type_l1", "")).lower(),
            str(r.get("type_l2", "")).lower(),
            str(r.get("type_l3", "")).lower(),
        ])
        if "amu" not in hay and "amulet" not in hay and "ammy" not in hay:
            continue
        # Very conservative anchors from current market table (real rows only).
        if "paladin_skills" in sig and "amulet" in sig:
            anchors["paladin_skills_amulet"] = {
                "median_fg": r.get("median_fg"),
                "max_fg": r.get("max_fg"),
                "basis": "property_table:paladin_skills_amulet",
                "source": r.get("last_source_url") or "",
            }
    return anchors


def _attach_market_fg(rows: list[dict], property_table_html: Path) -> list[dict]:
    anchors = _property_amulet_market_anchors(property_table_html)
    pal_tabs = {9, 10, 11}
    for r in rows:
        r["fg_market"] = None
        r["fg_market_basis"] = "unknown"
        pattern = str(r.get("combined_pattern", "")).lower()
        # Match +3 paladin tree amulet combos to current observed market anchor where available.
        m = re.search(r"skilltab\((\d+)\):(-?\d+)-(-?\d+)", pattern)
        if m:
            tab = int(m.group(1))
            hi = max(int(m.group(2)), int(m.group(3)))
            if tab in pal_tabs and hi >= 3 and "paladin_skills_amulet" in anchors:
                a = anchors["paladin_skills_amulet"]
                r["fg_market"] = a.get("median_fg")
                r["fg_market_basis"] = a.get("basis", "market")
        # FG Best = only real market-backed value (user-facing "actual d2jsp present").
        if r["fg_market"] is not None:
            r["fg_best"] = r["fg_market"]
            r["fg_best_basis"] = "market"
        else:
            r["fg_best"] = None
            r["fg_best_basis"] = "unknown"
    return rows


def _html(rows: list[dict]) -> str:
    payload = json.dumps(rows, ensure_ascii=False)
    return f'''<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>D2 Planner Magic Amulet Combos</title><style>{STYLE}</style></head><body><div class="wrap"><div class="bar">
<input id="q" type="search" placeholder="Search combo / prefix / suffix / pattern">
<select id="kind"><option value="">All kinds</option><option value="base_only">base_only</option><option value="prefix_only">prefix_only</option><option value="suffix_only">suffix_only</option><option value="prefix_suffix">prefix_suffix</option></select>
<select id="req"><option value="">Any req</option><option value="l9">req <= 9</option><option value="l30">req <= 30</option><option value="has_req">has req</option></select>
<select id="sort"><option value="name_asc">Name A → Z</option><option value="req_desc">Req high → low</option><option value="pattern_asc">Pattern A → Z</option></select>
<a href="d2planner_modifiers_table.html" class="pill">Modifiers</a>
<a href="d2planner_all_items_table.html" class="pill">Items</a>
</div><div class="meta" id="meta"></div><table><thead><tr>
<th data-key="display_name">Name</th><th data-key="kind">Kind</th><th data-key="req_lvl" class="num">Req</th><th data-key="fg_best" class="num">FG Best</th><th data-key="fg_best_basis">FG Best Basis</th><th data-key="fg_market" class="num">FG Market</th><th data-key="fg_est" class="num">FG Heuristic</th><th data-key="combined_pattern">Pattern</th><th data-key="pattern_key">Pattern Key</th><th data-key="d2jsp_tags">d2jsp Tags</th><th data-key="dup_count" class="num">Dup</th><th data-key="prefix_name">Prefix</th><th data-key="suffix_name">Suffix</th><th data-key="prefix_mods">Prefix Mods</th><th data-key="suffix_mods">Suffix Mods</th>
</tr></thead><tbody id="rows"></tbody></table></div>
<script>
const DATA={payload}; const state={{q:'', kind:'', req:'', sort:'name_asc'}}; const $=(id)=>document.getElementById(id); const tbody=$('rows'), meta=$('meta');
const esc=(s)=>String(s??'').replace(/[&<>\"]/g,c=>({{"&":"&amp;","<":"&lt;",">":"&gt;",'\"':"&quot;"}}[c])); const n=(v)=>v==null||v===''?'-':Math.round(Number(v));
function headerBase(k){{return {{display_name:'name', req_lvl:'req', fg_best:'best', fg_best_basis:'bestbasis', fg_market:'market', fg_est:'fg', fg_basis:'basis', combined_pattern:'pattern', pattern_key:'pkey', d2jsp_tags:'tags', dup_count:'dup', kind:'kind'}}[k]||'';}}
function toggleHeaderSort(k){{const b=headerBase(k); if(!b) return; const cur=String(state.sort||''); state.sort=(cur===`${{b}}_desc`)?`${{b}}_asc`:(cur===`${{b}}_asc`?`${{b}}_desc`:(b==='name'||b==='pattern'||b==='kind'?`${{b}}_asc`:`${{b}}_desc`)); render();}}
function sortRows(rows){{return rows.sort((a,b)=>{{switch(state.sort){{case 'best_desc': return Number(b.fg_best??-1)-Number(a.fg_best??-1)||String(a.display_name||'').localeCompare(String(b.display_name||'')); case 'best_asc': return Number(a.fg_best??1e9)-Number(b.fg_best??1e9)||String(a.display_name||'').localeCompare(String(b.display_name||'')); case 'market_desc': return Number(b.fg_market??-1)-Number(a.fg_market??-1)||String(a.display_name||'').localeCompare(String(b.display_name||'')); case 'market_asc': return Number(a.fg_market??1e9)-Number(b.fg_market??1e9)||String(a.display_name||'').localeCompare(String(b.display_name||'')); case 'fg_desc': return Number(b.fg_est??-1)-Number(a.fg_est??-1)||String(a.display_name||'').localeCompare(String(b.display_name||'')); case 'fg_asc': return Number(a.fg_est??1e9)-Number(b.fg_est??1e9)||String(a.display_name||'').localeCompare(String(b.display_name||'')); case 'req_desc': return Number(b.req_lvl??-1)-Number(a.req_lvl??-1)||String(a.display_name||'').localeCompare(String(b.display_name||'')); case 'req_asc': return Number(a.req_lvl??999)-Number(b.req_lvl??999)||String(a.display_name||'').localeCompare(String(b.display_name||'')); case 'bestbasis_asc': return String(a.fg_best_basis||'').localeCompare(String(b.fg_best_basis||''))||String(a.display_name||'').localeCompare(String(b.display_name||'')); case 'bestbasis_desc': return String(b.fg_best_basis||'').localeCompare(String(a.fg_best_basis||''))||String(a.display_name||'').localeCompare(String(b.display_name||'')); case 'pattern_asc': return String(a.combined_pattern||'').localeCompare(String(b.combined_pattern||''))||String(a.display_name||'').localeCompare(String(b.display_name||'')); case 'pattern_desc': return String(b.combined_pattern||'').localeCompare(String(a.combined_pattern||''))||String(a.display_name||'').localeCompare(String(b.display_name||'')); case 'pkey_asc': return String(a.pattern_key||'').localeCompare(String(b.pattern_key||''))||String(a.display_name||'').localeCompare(String(b.display_name||'')); case 'pkey_desc': return String(b.pattern_key||'').localeCompare(String(a.pattern_key||''))||String(a.display_name||'').localeCompare(String(b.display_name||'')); case 'tags_asc': return String(a.d2jsp_tags||'').localeCompare(String(b.d2jsp_tags||''))||String(a.display_name||'').localeCompare(String(b.display_name||'')); case 'tags_desc': return String(b.d2jsp_tags||'').localeCompare(String(a.d2jsp_tags||''))||String(a.display_name||'').localeCompare(String(b.display_name||'')); case 'dup_desc': return Number(b.dup_count||1)-Number(a.dup_count||1)||String(a.display_name||'').localeCompare(String(b.display_name||'')); case 'dup_asc': return Number(a.dup_count||1)-Number(b.dup_count||1)||String(a.display_name||'').localeCompare(String(b.display_name||'')); case 'kind_asc': return String(a.kind||'').localeCompare(String(b.kind||''))||String(a.display_name||'').localeCompare(String(b.display_name||'')); case 'kind_desc': return String(b.kind||'').localeCompare(String(a.kind||''))||String(a.display_name||'').localeCompare(String(b.display_name||'')); case 'name_desc': return String(b.display_name||'').localeCompare(String(a.display_name||'')); case 'name_asc': default: return String(a.display_name||'').localeCompare(String(b.display_name||'')); }} }});}}
function filterRows(rows){{ const q=state.q.trim().toLowerCase(); return rows.filter(r=>{{ if(state.kind && String(r.kind||'')!==state.kind) return false; if(state.req==='l9' && !(r.req_lvl!=null && Number(r.req_lvl)<=9)) return false; if(state.req==='l30' && !(r.req_lvl!=null && Number(r.req_lvl)<=30)) return false; if(state.req==='has_req' && r.req_lvl==null) return false; if(!q) return true; const hay=[r.display_name,r.kind,r.combined_pattern,r.pattern_key,r.d2jsp_tags,r.prefix_name,r.suffix_name,r.prefix_mods,r.suffix_mods].join(' ').toLowerCase(); return hay.includes(q); }}); }}
function render(){{ const rows=sortRows(filterRows(DATA)); const prefSuf=DATA.filter(r=>r.kind==='prefix_suffix').length; const knownFg=DATA.filter(r=>r.fg_est!=null).length; const knownMarket=DATA.filter(r=>r.fg_market!=null).length; meta.textContent=`Magic amulet combos: ${{DATA.length}} | full prefix+suffix combos: ${{prefSuf}} | heuristic FG known: ${{knownFg}} | market FG known: ${{knownMarket}} | showing: ${{rows.length}}`; if(!rows.length){{tbody.innerHTML='<tr><td class="empty" colspan="15">No rows match filters.</td></tr>'; return;}} tbody.innerHTML=rows.map(r=>`<tr><td>${{esc(r.display_name)}}</td><td><span class="pill">${{esc(r.kind)}}</span></td><td class="num">${{n(r.req_lvl)}}</td><td class="num">${{r.fg_best==null?'unknown':n(r.fg_best)}}</td><td class="muted">${{esc(r.fg_best_basis||'unknown')}}</td><td class="num">${{r.fg_market==null?'unknown':n(r.fg_market)}}</td><td class="num">${{r.fg_est==null?'unknown':n(r.fg_est)}}</td><td>${{esc(r.combined_pattern||'')}}</td><td class="muted">${{esc(r.pattern_key||'')}}</td><td class="muted">${{esc(r.d2jsp_tags||'')}}</td><td class="num">${{n(r.dup_count||1)}}</td><td>${{esc(r.prefix_name||'')}}</td><td>${{esc(r.suffix_name||'')}}</td><td class="muted">${{esc(r.prefix_mods||'')}}</td><td class="muted">${{esc(r.suffix_mods||'')}}</td></tr>`).join(''); }}
$('q').addEventListener('input',e=>{{state.q=e.target.value; render();}}); $('kind').addEventListener('change',e=>{{state.kind=e.target.value; render();}}); $('req').addEventListener('change',e=>{{state.req=e.target.value; render();}}); $('sort').addEventListener('change',e=>{{state.sort=e.target.value; render();}}); document.querySelectorAll('thead th[data-key]').forEach(th=>th.addEventListener('click',()=>toggleHeaderSort(th.dataset.key||''))); render();
</script></body></html>'''


def main() -> int:
    args = parse_args()
    data = _extract_amulet_affixes(Path(args.planner_dir))
    rows = _attach_market_fg(
        _attach_d2jsp_search(_attach_fg_estimates(_combine(data['prefixes'], data['suffixes']))),
        Path(args.property_table_html),
    )
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(_html(rows), encoding='utf-8')
    print(f"exported amulet_prefixes={len(data['prefixes'])} amulet_suffixes={len(data['suffixes'])} combos={len(rows)} out={out}")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
