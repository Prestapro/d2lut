#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import re
import sqlite3
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


SOURCE_BASE_URL = "https://raw.githubusercontent.com/pinkufairy/D2R-Excel/master"
DATASETS = {
    "itemtypes": "itemtypes.txt",
    "weapons": "weapons.txt",
    "armor": "armor.txt",
    "misc": "misc.txt",
    "uniqueitems": "uniqueitems.txt",
    "setitems": "setitems.txt",
    "automagic": "automagic.txt",
    "magicprefix": "magicprefix.txt",
    "magicsuffix": "magicsuffix.txt",
    "rareprefix": "rareprefix.txt",
    "raresuffix": "raresuffix.txt",
}

RUNE_CODES = {
    "el","eld","tir","nef","eth","ith","tal","ral","ort","thul","amn","sol","shael","dol","hel","io",
    "lum","ko","fal","lem","pul","um","mal","ist","gul","vex","ohm","lo","sur","ber","jah","cham","zod"
}

CUSTOM_ALIASES = {
    "unique:hellfire_torch": ["torch", "unid torch", "torch unid", "hellfire torch"],
    "unique:annihilus": ["anni", "annihilus", "unid anni"],
    "token:absolution": ["token", "token of absolution", "respec token"],
    "keyset:3x3": ["3x3", "keyset", "key set", "3x3 keyset", "3x3 key set"],
    "key:terror": ["terror key", "key of terror", "tkey", "t key"],
    "key:hate": ["hate key", "key of hate", "hkey", "h key"],
    "key:destruction": ["destruction key", "key of destruction", "dkey", "d key"],
    "set:tal_rashas_fine-spun_cloth": ["tal belt", "tals belt", "tal rasha belt"],
    "set:tal_rashas_lidless_eye": ["tal orb", "tals orb", "tal weapon"],
    "set:tal_rashas_adjudication": ["tal ammy", "tals ammy", "tal amulet"],
    "set:tal_rashas_horadric_crest": ["tal mask", "tals mask"],
    "set:tal_rashas_guardianship": ["tal armor", "tals armor"],
    "unique:harlequin_crest": ["shako"],
    "unique:arachnid_mesh": ["arach", "arachs", "arach belt"],
    "unique:maras_kaleidoscope": ["maras", "mara"],
    "unique:highlords_wrath": ["highlords", "highlord"],
    "unique:stone_of_jordan": ["soj", "stone of jordan"],
    "unique:nagelring": ["nagel", "nagelring"],
    "unique:raven_frost": ["ravenfrost", "raven frost"],
    "unique:dwarf_star": ["dwarf star"],
    "unique:bul_kathos_wedding_band": ["bk ring", "bk wedding band"],
    "unique:thundergods_vigor": ["tgods", "thundergods"],
    "unique:nosferatus_coil": ["nosferatus coil"],
    "unique:wisp_projector": ["wisp projector", "wisp"],
    "unique:metalgrid": ["metalgrid"],
    "unique:the_oculus": ["occy", "oculus"],
    "unique:ormus_robes": ["ormus robes", "ormus"],
    "unique:tyraels_might": ["tyraels might", "tyraels"],
    "unique:windforce": ["windforce"],
    "unique:the_grandfather": ["grandfather"],
    "unique:leviathan": ["leviathan"],
    "unique:ravenlore": ["ravenlore"],
    "unique:vampire_gaze": ["vampire gaze", "vamp gaze"],
    "unique:snowclash": ["snowclash"],
    "unique:arkaines_valor": ["arkaines valor"],
    "unique:guardian_angel": ["guardian angel"],
    "unique:shaftstop": ["shaftstop"],
    "unique:duriels_shell": ["duriels shell"],
    "unique:buriza_do_kyanon": ["buriza", "buriza-do kyanon"],
    "unique:frostburn": ["frostburn"],
    "charm:skiller": ["skiller", "skill gc"],
    "charm:sunder": ["sunder charm", "sunder"],
    "unique:blade": ["spectral shard"],
    "unique:cap": ["biggins bonnet", "biggin bonnet"],
    "set:belt": ["hwanins blessing", "hwanin blessing", "hwanins belt", "hwanin belt"],
}


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def to_int(v: str | None) -> int | None:
    if v is None:
        return None
    s = str(v).strip()
    if s == "":
        return None
    try:
        return int(float(s))
    except ValueError:
        return None


def to_bool01(v: str | None) -> int:
    s = (v or "").strip()
    if s in {"1", "true", "True"}:
        return 1
    return 0


def norm_alias(text: str) -> str:
    s = text.lower()
    s = s.replace("&amp;", "and")
    s = s.replace("'", "")
    s = re.sub(r"[^a-z0-9+]+", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def fetch_file(url: str, out_path: Path, force: bool = False) -> None:
    if out_path.exists() and out_path.stat().st_size > 0 and not force:
        return
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with urllib.request.urlopen(url) as resp:
        data = resp.read()
    out_path.write_bytes(data)


def read_tsv(path: Path) -> list[dict[str, str]]:
    text = path.read_text(encoding="utf-8", errors="ignore")
    rows: list[dict[str, str]] = []
    reader = csv.DictReader(text.splitlines(), delimiter="\t")
    for row in reader:
        rows.append({k: (v or "") for k, v in row.items()})
    return rows


@dataclass(slots=True)
class CatalogDB:
    conn: sqlite3.Connection

    @classmethod
    def open(cls, path: str | Path) -> "CatalogDB":
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(p)
        conn.row_factory = sqlite3.Row
        return cls(conn)

    def close(self) -> None:
        self.conn.close()

    def init_schema(self) -> None:
        schema_path = Path(__file__).resolve().parents[1] / "src" / "d2lut" / "catalog" / "schema.sql"
        self.conn.executescript(schema_path.read_text(encoding="utf-8"))
        self.conn.commit()

    def begin_import_run(self, source_url: str) -> int:
        cur = self.conn.execute(
            "INSERT INTO catalog_import_runs(source_name, source_url, started_at) VALUES (?, ?, ?)",
            ("pinkufairy/D2R-Excel", source_url, utc_now_iso()),
        )
        self.conn.commit()
        return int(cur.lastrowid)

    def finish_import_run(self, run_id: int, notes: str | None = None) -> None:
        self.conn.execute(
            "UPDATE catalog_import_runs SET completed_at = ?, notes = ? WHERE id = ?",
            (utc_now_iso(), notes, run_id),
        )
        self.conn.commit()


def upsert_itemtypes(db: CatalogDB, rows: list[dict[str, str]]) -> int:
    n = 0
    for r in rows:
        code = (r.get("Code") or r.get("code") or "").strip()
        if not code:
            continue
        db.conn.execute(
            """
            INSERT INTO catalog_itemtypes(code,name,equiv1,equiv2,body,bodyloc1,bodyloc2,shoots,quiver,throwable,reload,reqlvl,class_raw,raw_json)
            VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            ON CONFLICT(code) DO UPDATE SET
              name=excluded.name, equiv1=excluded.equiv1, equiv2=excluded.equiv2, body=excluded.body,
              bodyloc1=excluded.bodyloc1, bodyloc2=excluded.bodyloc2, shoots=excluded.shoots, quiver=excluded.quiver,
              throwable=excluded.throwable, reload=excluded.reload, reqlvl=excluded.reqlvl, class_raw=excluded.class_raw,
              raw_json=excluded.raw_json
            """,
            (
                code,
                (r.get("ItemType") or r.get("ItemTypeName") or r.get("Name") or "").strip() or code,
                (r.get("Equiv1") or "").strip() or None,
                (r.get("Equiv2") or "").strip() or None,
                to_int(r.get("Body")),
                (r.get("BodyLoc1") or "").strip() or None,
                (r.get("BodyLoc2") or "").strip() or None,
                (r.get("Shoots") or "").strip() or None,
                (r.get("Quiver") or "").strip() or None,
                to_int(r.get("Throwable")) or 0,
                to_int(r.get("Reload")) or 0,
                to_int(r.get("ReqLvl")),
                (r.get("Class") or "").strip() or None,
                json.dumps(r, ensure_ascii=True),
            ),
        )
        n += 1
    db.conn.commit()
    return n


def upsert_bases(db: CatalogDB, rows: list[dict[str, str]], item_class: str) -> int:
    n = 0
    for r in rows:
        code = (r.get("code") or "").strip()
        name = (r.get("name") or "").strip()
        if not code or not name:
            continue
        db.conn.execute(
            """
            INSERT INTO catalog_bases(
              code, display_name, item_class, type_code, type2_code, level, levelreq, spawnable, stackable, gemsockets,
              invwidth, invheight, normcode, ubercode, ultracode, namestr, raw_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(code) DO UPDATE SET
              display_name=excluded.display_name, item_class=excluded.item_class, type_code=excluded.type_code, type2_code=excluded.type2_code,
              level=excluded.level, levelreq=excluded.levelreq, spawnable=excluded.spawnable, stackable=excluded.stackable,
              gemsockets=excluded.gemsockets, invwidth=excluded.invwidth, invheight=excluded.invheight,
              normcode=excluded.normcode, ubercode=excluded.ubercode, ultracode=excluded.ultracode, namestr=excluded.namestr, raw_json=excluded.raw_json
            """,
            (
                code,
                name,
                item_class,
                (r.get("type") or "").strip() or None,
                (r.get("type2") or "").strip() or None,
                to_int(r.get("level")),
                to_int(r.get("levelreq")),
                to_bool01(r.get("spawnable")),
                to_bool01(r.get("stackable")),
                to_int(r.get("gemsockets")),
                to_int(r.get("invwidth")),
                to_int(r.get("invheight")),
                (r.get("normcode") or "").strip() or None,
                (r.get("ubercode") or "").strip() or None,
                (r.get("ultracode") or "").strip() or None,
                (r.get("namestr") or "").strip() or None,
                json.dumps(r, ensure_ascii=True),
            ),
        )
        n += 1
    db.conn.commit()
    return n


def upsert_uniques(db: CatalogDB, rows: list[dict[str, str]]) -> int:
    n = 0
    for r in rows:
        idx = (r.get("index") or "").strip()
        name = (r.get("*ItemName") or idx).strip()
        if not idx:
            continue
        spawnable = to_bool01(r.get("spawnable"))
        enabled = 0 if to_bool01(r.get("disabled")) else 1
        db.conn.execute(
            """
            INSERT INTO catalog_uniques(unique_index, display_name, code, lvl, levelreq, rarity, spawnable, enabled, raw_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(unique_index) DO UPDATE SET
              display_name=excluded.display_name, code=excluded.code, lvl=excluded.lvl, levelreq=excluded.levelreq,
              rarity=excluded.rarity, spawnable=excluded.spawnable, enabled=excluded.enabled, raw_json=excluded.raw_json
            """,
            (
                idx,
                name,
                (r.get("code") or "").strip() or None,
                to_int(r.get("lvl")),
                to_int(r.get("lvl req")),
                to_int(r.get("rarity")),
                spawnable,
                enabled,
                json.dumps(r, ensure_ascii=True),
            ),
        )
        n += 1
    db.conn.commit()
    return n


def upsert_sets(db: CatalogDB, rows: list[dict[str, str]]) -> int:
    n = 0
    for r in rows:
        idx = (r.get("index") or "").strip()
        name = (r.get("*ItemName") or idx).strip()
        if not idx:
            continue
        db.conn.execute(
            """
            INSERT INTO catalog_sets(set_index, display_name, code, lvl, levelreq, rarity, spawnable, enabled, raw_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(set_index) DO UPDATE SET
              display_name=excluded.display_name, code=excluded.code, lvl=excluded.lvl, levelreq=excluded.levelreq,
              rarity=excluded.rarity, spawnable=excluded.spawnable, enabled=excluded.enabled, raw_json=excluded.raw_json
            """,
            (
                idx,
                name,
                (r.get("item") or r.get("code") or "").strip() or None,
                to_int(r.get("lvl")),
                to_int(r.get("lvl req")),
                to_int(r.get("rarity")),
                to_bool01(r.get("spawnable")),
                0 if to_bool01(r.get("disabled")) else 1,
                json.dumps(r, ensure_ascii=True),
            ),
        )
        n += 1
    db.conn.commit()
    return n


def _affix_mods(row: dict[str, str]) -> list[dict]:
    mods: list[dict] = []
    for i in range(1, 4):
        code = (row.get(f"mod{i}code") or "").strip()
        if not code:
            continue
        mods.append(
            {
                "code": code,
                "param": (row.get(f"mod{i}param") or "").strip() or None,
                "min": to_int(row.get(f"mod{i}min")),
                "max": to_int(row.get(f"mod{i}max")),
            }
        )
    return mods


def _affix_itemtypes(row: dict[str, str]) -> tuple[list[str], list[str]]:
    itypes = [(row.get(f"itype{i}") or "").strip() for i in range(1, 8)]
    etypes = [(row.get(f"etype{i}") or "").strip() for i in range(1, 6)]
    return ([x for x in itypes if x], [x for x in etypes if x])


def upsert_affixes(db: CatalogDB, rows: list[dict[str, str]], affix_kind: str) -> int:
    n = 0
    for r in rows:
        name = (r.get("Name") or r.get("name") or "").strip()
        if not name:
            continue
        itypes, etypes = _affix_itemtypes(r)
        affix_id = f"{affix_kind}:{name.lower()}"
        db.conn.execute(
            """
            INSERT INTO catalog_affixes(
              affix_id, affix_kind, affix_name, group_id, level, maxlevel, levelreq, frequency,
              classspecific, class_raw, transformcolor, itypes_json, etypes_json, mods_json, enabled, raw_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(affix_id) DO UPDATE SET
              affix_kind=excluded.affix_kind, affix_name=excluded.affix_name, group_id=excluded.group_id,
              level=excluded.level, maxlevel=excluded.maxlevel, levelreq=excluded.levelreq, frequency=excluded.frequency,
              classspecific=excluded.classspecific, class_raw=excluded.class_raw, transformcolor=excluded.transformcolor,
              itypes_json=excluded.itypes_json, etypes_json=excluded.etypes_json, mods_json=excluded.mods_json,
              enabled=excluded.enabled, raw_json=excluded.raw_json
            """,
            (
                affix_id,
                affix_kind,
                name,
                to_int(r.get("group")),
                to_int(r.get("level")),
                to_int(r.get("maxlevel")),
                to_int(r.get("levelreq")),
                to_int(r.get("frequency")),
                to_bool01(r.get("classspecific")),
                (r.get("class") or "").strip() or None,
                (r.get("transformcolor") or "").strip() or None,
                json.dumps(itypes, ensure_ascii=True),
                json.dumps(etypes, ensure_ascii=True),
                json.dumps(_affix_mods(r), ensure_ascii=True),
                1 if to_bool01(r.get("spawnable")) or (r.get("spawnable", "") == "") else 0,
                json.dumps(r, ensure_ascii=True),
            ),
        )
        n += 1
    db.conn.commit()
    return n


def clear_catalog_items_aliases(db: CatalogDB) -> None:
    db.conn.execute("DELETE FROM catalog_aliases")
    db.conn.execute("DELETE FROM catalog_items")
    db.conn.commit()


def insert_catalog_item(db: CatalogDB, row: tuple) -> None:
    db.conn.execute(
        """
        INSERT INTO catalog_items(
          canonical_item_id, display_name, category, quality_class, base_code, source_table, source_key, tradeable, enabled, metadata_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(canonical_item_id) DO UPDATE SET
          display_name=excluded.display_name, category=excluded.category, quality_class=excluded.quality_class,
          base_code=excluded.base_code, source_table=excluded.source_table, source_key=excluded.source_key,
          tradeable=excluded.tradeable, enabled=excluded.enabled, metadata_json=excluded.metadata_json
        """,
        row,
    )


def add_alias(db: CatalogDB, alias_raw: str, canonical_item_id: str, alias_type: str = "name", priority: int = 100, source: str = "catalog_seed") -> None:
    alias_norm = norm_alias(alias_raw)
    if not alias_norm:
        return
    db.conn.execute(
        """
        INSERT OR IGNORE INTO catalog_aliases(alias_norm, alias_raw, canonical_item_id, alias_type, priority, source)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (alias_norm, alias_raw, canonical_item_id, alias_type, priority, source),
    )


def classify_misc(row: sqlite3.Row) -> tuple[str, str]:
    name = (row["display_name"] or "").lower()
    code = (row["code"] or "").lower()
    type_code = (row["type_code"] or "").lower()

    if code in RUNE_CODES or type_code == "rune":
        return ("rune", "misc")
    if "key of terror" in name:
        return ("key", "misc")
    if "key of hate" in name:
        return ("key", "misc")
    if "key of destruction" in name:
        return ("key", "misc")
    if "token of absolution" in name:
        return ("token", "misc")
    if "essence" in name:
        return ("essence", "misc")
    if "grand charm" in name or "small charm" in name or "large charm" in name:
        return ("charm", "misc")
    if "jewel" in name:
        return ("jewel", "misc")
    return ("misc", "misc")


def slugify_item_name(name: str) -> str:
    s = name.lower()
    s = s.replace("&", " and ")
    s = s.replace("'", "")
    s = re.sub(r"[^a-z0-9]+", "_", s)
    s = re.sub(r"_+", "_", s).strip("_")
    return s


def build_catalog_items_and_aliases(db: CatalogDB) -> tuple[int, int]:
    clear_catalog_items_aliases(db)
    item_count = 0
    alias_count_before = db.conn.execute("SELECT COUNT(*) FROM catalog_aliases").fetchone()[0]

    # Bases
    for r in db.conn.execute("SELECT * FROM catalog_bases"):
        code = r["code"]
        name = r["display_name"]
        item_class = r["item_class"]
        if item_class == "misc":
            category, quality = classify_misc(r)
            if category == "rune":
                canonical = f"rune:{code.lower()}"
            elif category == "key":
                if "terror" in name.lower():
                    canonical = "key:terror"
                elif "hate" in name.lower():
                    canonical = "key:hate"
                elif "destruction" in name.lower():
                    canonical = "key:destruction"
                else:
                    canonical = f"key:{slugify_item_name(name)}"
            elif category == "token":
                canonical = "token:absolution"
            elif category == "essence":
                canonical = f"essence:{slugify_item_name(name)}"
            elif category == "charm":
                canonical = f"charm:{code.lower()}"
            elif category == "jewel":
                canonical = f"jewel:{code.lower()}"
            else:
                canonical = f"misc:{code.lower()}"
        else:
            canonical = f"base:{code.lower()}"
            category, quality = ("base", "base")

        insert_catalog_item(
            db,
            (
                canonical,
                name,
                category,
                quality,
                code,
                "catalog_bases",
                code,
                1,
                1,
                json.dumps({"item_class": item_class}, ensure_ascii=True),
            ),
        )
        item_count += 1
        add_alias(db, name, canonical, alias_type="name", priority=100)
        add_alias(db, code, canonical, alias_type="code", priority=200)

    # Uniques
    for r in db.conn.execute("SELECT * FROM catalog_uniques WHERE enabled = 1"):
        idx = r["unique_index"]
        name = r["display_name"]
        canonical = f"unique:{slugify_item_name(name)}"
        insert_catalog_item(
            db,
            (
                canonical,
                name,
                "unique",
                "unique",
                r["code"],
                "catalog_uniques",
                idx,
                1,
                1,
                json.dumps({"unique_index": idx}, ensure_ascii=True),
            ),
        )
        item_count += 1
        add_alias(db, name, canonical, alias_type="name", priority=100)
        if r["code"]:
            add_alias(db, r["code"], canonical, alias_type="code", priority=250)

    # Sets
    for r in db.conn.execute("SELECT * FROM catalog_sets WHERE enabled = 1"):
        idx = r["set_index"]
        name = r["display_name"]
        canonical = f"set:{slugify_item_name(name)}"
        insert_catalog_item(
            db,
            (
                canonical,
                name,
                "set",
                "set",
                r["code"],
                "catalog_sets",
                idx,
                1,
                1,
                json.dumps({"set_index": idx}, ensure_ascii=True),
            ),
        )
        item_count += 1
        add_alias(db, name, canonical, alias_type="name", priority=100)
        if r["code"]:
            add_alias(db, r["code"], canonical, alias_type="code", priority=250)

    # Manual aliases for d2jsp shorthand and aggregated keys
    # Aggregated 3x3 keyset canonical entity
    insert_catalog_item(
        db,
        (
            "keyset:3x3",
            "3x3 Key Set",
            "keyset",
            "misc",
            None,
            "manual",
            "keyset:3x3",
            1,
            1,
            json.dumps({}, ensure_ascii=True),
        ),
    )
    item_count += 1

    for canonical, aliases in CUSTOM_ALIASES.items():
        exists = db.conn.execute("SELECT 1 FROM catalog_items WHERE canonical_item_id = ?", (canonical,)).fetchone()
        if not exists:
            kind, _, rest = canonical.partition(":")
            if kind == "key":
                display = rest.title() + " Key"
                category = "key"
                quality = "misc"
            elif kind == "keyset":
                display = "3x3 Key Set"
                category = "keyset"
                quality = "misc"
            elif kind in {"unique", "set", "token"}:
                display = rest.replace("_", " ").title()
                category = kind
                quality = "misc" if kind == "token" else kind
            elif kind == "charm":
                display = rest.replace("_", " ").title()
                category = "charm"
                quality = "misc"
            else:
                # Skip broken manual alias mapping instead of crashing import.
                print(f"warn: missing canonical target for alias seed, skipping aliases for {canonical}")
                continue
            insert_catalog_item(
                db,
                (
                    canonical,
                    display,
                    category,
                    quality,
                    None,
                    "manual",
                    canonical,
                    1,
                    1,
                    json.dumps({"placeholder": True}, ensure_ascii=True),
                ),
            )
            item_count += 1
        for alias in aliases:
            add_alias(db, alias, canonical, alias_type="manual", priority=10, source="manual_d2jsp")

    db.conn.commit()
    alias_count_after = db.conn.execute("SELECT COUNT(*) FROM catalog_aliases").fetchone()[0]
    return (db.conn.execute("SELECT COUNT(*) FROM catalog_items").fetchone()[0], alias_count_after - alias_count_before)


def cmd_build(args: argparse.Namespace) -> int:
    download_dir = Path(args.download_dir)
    download_dir.mkdir(parents=True, exist_ok=True)

    if not args.no_download:
        for key, filename in DATASETS.items():
            url = f"{SOURCE_BASE_URL}/{filename}"
            fetch_file(url, download_dir / filename, force=args.force_download)
            print(f"fetched {filename}")

    db = CatalogDB.open(args.db)
    db.init_schema()
    run_id = db.begin_import_run(SOURCE_BASE_URL)

    counts: dict[str, int] = {}
    data = {k: read_tsv(download_dir / fn) for k, fn in DATASETS.items()}

    counts["itemtypes"] = upsert_itemtypes(db, data["itemtypes"])
    counts["weapons"] = upsert_bases(db, data["weapons"], item_class="weapon")
    counts["armor"] = upsert_bases(db, data["armor"], item_class="armor")
    counts["misc"] = upsert_bases(db, data["misc"], item_class="misc")
    counts["uniques"] = upsert_uniques(db, data["uniqueitems"])
    counts["sets"] = upsert_sets(db, data["setitems"])
    counts["automagic"] = upsert_affixes(db, data["automagic"], affix_kind="automagic")
    counts["prefixes"] = upsert_affixes(db, data["magicprefix"], affix_kind="prefix")
    counts["suffixes"] = upsert_affixes(db, data["magicsuffix"], affix_kind="suffix")
    counts["rareprefix"] = upsert_affixes(db, data["rareprefix"], affix_kind="rareprefix")
    counts["raresuffix"] = upsert_affixes(db, data["raresuffix"], affix_kind="raresuffix")
    catalog_items_count, _new_aliases = build_catalog_items_and_aliases(db)
    counts["catalog_items"] = catalog_items_count
    counts["catalog_aliases"] = db.conn.execute("SELECT COUNT(*) FROM catalog_aliases").fetchone()[0]
    counts["catalog_affixes"] = db.conn.execute("SELECT COUNT(*) FROM catalog_affixes").fetchone()[0]

    db.finish_import_run(run_id, notes=json.dumps(counts, ensure_ascii=True))
    db.close()

    for k in sorted(counts):
        print(f"{k}={counts[k]}")
    return 0


def cmd_lookup(args: argparse.Namespace) -> int:
    conn = sqlite3.connect(args.db)
    conn.row_factory = sqlite3.Row
    q = norm_alias(args.query)
    print(f"query_norm={q}")
    rows = conn.execute(
        """
        SELECT a.alias_raw, a.alias_norm, a.priority, a.alias_type, i.canonical_item_id, i.display_name, i.category, i.quality_class
        FROM catalog_aliases a
        JOIN catalog_items i ON i.canonical_item_id = a.canonical_item_id
        WHERE a.alias_norm = ?
        ORDER BY a.priority ASC, i.canonical_item_id ASC
        LIMIT 50
        """,
        (q,),
    ).fetchall()
    for r in rows:
        print(
            f"{r['canonical_item_id']:<40} {r['display_name']:<35} "
            f"{r['category']:<10} prio={r['priority']} alias={r['alias_raw']!r}"
        )
    if not rows:
        print("no exact alias match")
    conn.close()
    return 0


def cmd_affix_search(args: argparse.Namespace) -> int:
    conn = sqlite3.connect(args.db)
    conn.row_factory = sqlite3.Row
    pat = f"%{args.name.lower()}%"
    rows = conn.execute(
        """
        SELECT affix_id, affix_kind, affix_name, level, levelreq, group_id, mods_json
        FROM catalog_affixes
        WHERE lower(affix_name) LIKE ?
        ORDER BY affix_kind, affix_name
        LIMIT ?
        """,
        (pat, args.limit),
    ).fetchall()
    for r in rows:
        print(f"{r['affix_id']:<40} lvl={r['level'] or '-'} req={r['levelreq'] or '-'} group={r['group_id'] or '-'}")
    if not rows:
        print("no affixes found")
    conn.close()
    return 0


def cmd_type_search(args: argparse.Namespace) -> int:
    conn = sqlite3.connect(args.db)
    conn.row_factory = sqlite3.Row
    pat = f"%{args.name.lower()}%"
    rows = conn.execute(
        """
        SELECT code, COALESCE(name, code) AS display_name, equiv1, equiv2, reqlvl, class_raw
        FROM catalog_itemtypes
        WHERE lower(COALESCE(name,'')) LIKE ? OR lower(code) LIKE ?
        ORDER BY code
        LIMIT ?
        """,
        (pat, pat, args.limit),
    ).fetchall()
    for r in rows:
        print(
            f"{r['code']:<8} {r['display_name']:<28} "
            f"reqlvl={r['reqlvl'] if r['reqlvl'] is not None else '-'} "
            f"class={r['class_raw'] or '-'} equiv=({r['equiv1'] or '-'}|{r['equiv2'] or '-'})"
        )
    if not rows:
        print("no itemtypes found")
    conn.close()
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Build canonical D2R catalog DB (items, aliases, affixes)")
    p.add_argument("--db", default="data/cache/d2lut.db", help="SQLite DB path (can be same DB as market)")
    sp = p.add_subparsers(dest="cmd", required=True)

    p_build = sp.add_parser("build")
    p_build.add_argument("--download-dir", default="data/cache/d2r_excel")
    p_build.add_argument("--no-download", action="store_true")
    p_build.add_argument("--force-download", action="store_true")
    p_build.set_defaults(func=cmd_build)

    p_lookup = sp.add_parser("lookup")
    p_lookup.add_argument("query")
    p_lookup.set_defaults(func=cmd_lookup)

    p_affix = sp.add_parser("affix-search")
    p_affix.add_argument("name")
    p_affix.add_argument("--limit", type=int, default=50)
    p_affix.set_defaults(func=cmd_affix_search)

    p_type = sp.add_parser("type-search")
    p_type.add_argument("name")
    p_type.add_argument("--limit", type=int, default=50)
    p_type.set_defaults(func=cmd_type_search)
    return p


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
