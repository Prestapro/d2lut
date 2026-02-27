#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterable

from d2lut.models import ObservedPrice
from d2lut.normalize.d2jsp_market import (
    classify_thread_trade_type,
    is_bump_only_text,
    normalize_item_hint,
    parse_forum_threads_from_html,
    parse_observations_from_topic_html,
    parse_observations_from_threads,
)
from d2lut.pricing.engine import PricingEngine
from d2lut.storage.sqlite import D2LutDB


def row_to_observed(row: dict) -> ObservedPrice:
    sig = row["signal_kind"].lower()  # Normalize to lowercase
    value = float(row["price_fg"])
    trade_type = (row.get("thread_trade_type") or "unknown").lower()
    category_id = row.get("thread_category_id")
    trade_mul = 1.0
    if trade_type == "ft":
        trade_mul = 1.0
    elif trade_type == "iso":
        # ISO prices are demand-side signals: useful, but weaker than FT sale/listing.
        trade_mul = 0.8 if sig in {"bin", "sold"} else 0.7
    elif trade_type == "pc":
        trade_mul = 0.4
    elif trade_type == "service":
        trade_mul = 0.3
    elif trade_type == "unknown":
        trade_mul = 0.9
    # Category-aware weighting (light touch for now).
    item_id = str(row.get("canonical_item_id") or "")
    cat_mul = 1.0
    try:
        c = int(category_id) if category_id is not None else None
    except Exception:
        c = None
    if c == 2:  # Runes
        if item_id.startswith("rune:") or item_id.startswith("bundle:runes:"):
            cat_mul = 1.1
        elif item_id.startswith(("set:", "unique:", "base:")):
            cat_mul = 0.85
    elif c == 3:  # Charms
        if item_id.startswith("charm:"):
            cat_mul = 1.1
    elif c == 5:  # LLD
        # Keep LLD items from being down-weighted too much by generic heuristics.
        cat_mul = 1.05
    confidence = max(0.01, min(1.0, float(row.get("confidence", 0.0)) * trade_mul * cat_mul))
    return ObservedPrice(
        canonical_item_id=row["canonical_item_id"],
        variant_key=row["variant_key"],
        ask_fg=value if sig == "ask" else None,
        bin_fg=value if sig == "bin" else None,
        sold_fg=value if sig == "sold" else None,
        confidence=confidence,
        source_url=row.get("source_url", ""),
        thread_category_id=c,
    )


def filter_observations_by_price(rows: list[dict], min_fg: float | None, max_fg: float | None) -> list[dict]:
    if min_fg is None and max_fg is None:
        return rows
    out: list[dict] = []
    for row in rows:
        price = float(row["price_fg"])
        if min_fg is not None and price < min_fg:
            continue
        if max_fg is not None and price > max_fg:
            continue
        out.append(row)
    return out


def build_estimates(db: D2LutDB, market_key: str) -> int:
    rows = db.load_observations(market_key)
    obs = [row_to_observed(dict(r)) for r in rows]
    estimates = PricingEngine().build_index(obs)
    return db.replace_price_estimates(market_key, estimates)


def iter_input_files(path: str, pattern: str = "*.html", recursive: bool = False) -> list[Path]:
    p = Path(path)
    if p.is_file():
        return [p]
    if not p.exists():
        raise FileNotFoundError(path)
    finder = p.rglob if recursive else p.glob
    return sorted(x for x in finder(pattern) if x.is_file())


def infer_forum_category_id_from_path(path: str | Path) -> int | None:
    s = str(path)
    # Accept common snapshot names like forum_f271_c2_o25.html or query-like names.
    m = re.search(r"(?:^|[_?&])c(?:=)?(\d+)(?:[_&.]|$)", s)
    if not m:
        return None
    try:
        return int(m.group(1))
    except ValueError:
        return None


def load_thread_context(db: D2LutDB, thread_id: int | None) -> dict[str, object]:
    if not thread_id or thread_id <= 0:
        return {}
    row = db.conn.execute(
        "SELECT thread_trade_type, thread_category_id FROM threads WHERE source='d2jsp' AND thread_id=? LIMIT 1",
        (thread_id,),
    ).fetchone()
    return dict(row) if row else {}


_LIQUID_SINGLETON_PREFIXES = (
    "rune:",
    "bundle:runes:",
    "key:",
    "keyset:",
    "token:",
    "essence:",
    "gem:",
    "consumable:",
    "bundle:spirit_set",
    "bundle:insight_set",
    "bundle:organ_set",
    "bundle:craftset:",
    "bundle:map_reroll_runes",
)


def _is_probably_multi_item_title(title: str) -> bool:
    t = (title or "").lower()
    # common list separators / packs / "and more"
    if any(tok in t for tok in [",", " & ", " and ", " | ", " pack", " list", " + more", " etc"]):
        # avoid classifying rune bundles as multi-item "list" noise
        if not re.search(r"(?i)\b(?:jah|ber|sur|lo|ohm|vex|gul|ist|mal|um|pul|lem|fal|ko|lum|io|hel|dol|shael|sol|amn|thul|ort|ral|tal|ith|el)\s*[+/,&]\s*(?:jah|ber|sur|lo|ohm|vex|gul|ist|mal|um|pul|lem|fal|ko|lum|io|hel|dol|shael|sol|amn|thul|ort|ral|tal|ith|el)\b", t):
            return True
    # multiple explicit quantities / xN often imply bundles/lists
    if len(re.findall(r"\b\d+x\b", t)) >= 2:
        return True
    return False


def _recent_observation_count_for_variant(db: D2LutDB, market_key: str, variant_key: str, hours: int) -> int:
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
    row = db.conn.execute(
        """
        SELECT COUNT(*)
        FROM observed_prices
        WHERE market_key = ? AND variant_key = ? AND COALESCE(observed_at, '') >= ?
        """,
        (market_key, variant_key, cutoff),
    ).fetchone()
    return int(row[0]) if row else 0


def _is_liquid_singleton_variant(variant_key: str) -> bool:
    return any(variant_key.startswith(p) for p in _LIQUID_SINGLETON_PREFIXES)


def cmd_init_db(args: argparse.Namespace) -> int:
    db = D2LutDB(args.db)
    try:
        db.init_schema()
    finally:
        db.close()
    print(f"initialized db: {args.db}")
    return 0


def cmd_import_forum_html(args: argparse.Namespace) -> int:
    db = D2LutDB(args.db)
    db.init_schema()
    html_text = Path(args.html).read_text(encoding="utf-8", errors="ignore")
    if "Just a moment..." in html_text and "Cloudflare" in html_text:
        raise SystemExit(
            "Input HTML appears to be a Cloudflare challenge page. Save the actual forum HTML from a browser and retry."
        )

    snapshot_id = db.insert_snapshot("d2jsp", args.forum_id, args.html, note=args.note)
    threads = parse_forum_threads_from_html(html_text, forum_id=args.forum_id)
    category_id = infer_forum_category_id_from_path(args.html)
    if args.skip_zero_replies:
        threads = [t for t in threads if int(t.get("reply_count") or 0) > 0]
    for th in threads:
        th["snapshot_id"] = snapshot_id
        if category_id is not None:
            th["thread_category_id"] = category_id
        th.setdefault("created_at", datetime.now(timezone.utc).isoformat())

    n_threads = db.upsert_threads(threads)
    obs_rows = parse_observations_from_threads(threads, market_key=args.market_key)
    obs_rows = filter_observations_by_price(obs_rows, args.min_fg, args.max_fg)
    n_obs = db.insert_observed_prices(obs_rows)
    n_est = build_estimates(db, args.market_key)

    if args.export_json:
        out_path = Path(args.export_json)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        top = db.conn.execute(
            """
            SELECT variant_key, estimate_fg, range_low_fg, range_high_fg, confidence, sample_count, updated_at
            FROM price_estimates
            WHERE market_key = ?
            ORDER BY estimate_fg DESC, sample_count DESC
            """,
            (args.market_key,),
        ).fetchall()
        out_path.write_text(
            json.dumps([dict(r) for r in top], ensure_ascii=True, indent=2),
            encoding="utf-8",
        )

    print(
        f"imported threads={n_threads} observations={n_obs} estimates={n_est} "
        f"market={args.market_key} db={args.db}"
    )
    db.close()
    return 0


def _import_forum_html_into_db(
    db: D2LutDB,
    *,
    html_path: str,
    forum_id: int,
    market_key: str,
    note: str | None,
    min_fg: float | None,
    max_fg: float | None,
    skip_zero_replies: bool,
) -> tuple[int, int]:
    html_text = Path(html_path).read_text(encoding="utf-8", errors="ignore")
    if "Just a moment..." in html_text and "Cloudflare" in html_text:
        return (0, 0)

    snapshot_id = db.insert_snapshot("d2jsp", forum_id, html_path, note=note)
    threads = parse_forum_threads_from_html(html_text, forum_id=forum_id)
    category_id = infer_forum_category_id_from_path(html_path)
    if skip_zero_replies:
        threads = [t for t in threads if int(t.get("reply_count") or 0) > 0]
    for th in threads:
        th["snapshot_id"] = snapshot_id
        if category_id is not None:
            th["thread_category_id"] = category_id
        th.setdefault("created_at", datetime.now(timezone.utc).isoformat())

    n_threads = db.upsert_threads(threads)
    obs_rows = parse_observations_from_threads(threads, market_key=market_key)
    obs_rows = filter_observations_by_price(obs_rows, min_fg, max_fg)
    n_obs = db.insert_observed_prices(obs_rows)
    return (n_threads, n_obs)


def cmd_dump_topic_candidates(args: argparse.Namespace) -> int:
    db = D2LutDB(args.db)
    db.init_schema()
    sql = """
        SELECT DISTINCT t.thread_id, t.url, t.title, t.reply_count
        FROM threads t
        LEFT JOIN observed_prices o
          ON o.thread_id = t.thread_id AND o.market_key = ?
        WHERE t.source='d2jsp' AND t.forum_id = ?
    """
    params: list[object] = [args.market_key, args.forum_id]

    if args.skip_zero_replies:
        sql += " AND COALESCE(t.reply_count, 0) > 0"

    if args.max_fg is not None:
        sql += " AND (o.price_fg IS NULL OR o.price_fg <= ?)"
        params.append(args.max_fg)
    if args.min_fg is not None:
        sql += " AND (o.price_fg IS NULL OR o.price_fg >= ?)"
        params.append(args.min_fg)

    if args.only_priced_titles:
        sql += " AND o.id IS NOT NULL"

    if getattr(args, "prefer_recent", False):
        sql += " ORDER BY t.thread_id DESC, COALESCE(t.reply_count, 0) DESC LIMIT ?"
    else:
        sql += " ORDER BY COALESCE(t.reply_count, 0) DESC, t.thread_id DESC LIMIT ?"
    params.append(args.limit)

    rows = list(db.conn.execute(sql, tuple(params)).fetchall())

    if args.include_terms or args.exclude_terms:
        include_terms = [x.strip().lower() for x in (args.include_terms or "").split(",") if x.strip()]
        exclude_terms = [x.strip().lower() for x in (args.exclude_terms or "").split(",") if x.strip()]
        filtered = []
        for r in rows:
            title_l = (r["title"] or "").lower()
            if include_terms and not any(term in title_l for term in include_terms):
                continue
            if exclude_terms and any(term in title_l for term in exclude_terms):
                continue
            filtered.append(r)
        rows = filtered

    if args.skip_liquid_singletons:
        # Freshness matters more for liquid singleton commodities (Ber/Jah/keys/etc.).
        # Process newest threads first and keep only a small number of recent duplicates.
        rows = sorted(rows, key=lambda r: int(r["thread_id"] or 0), reverse=True)
        filtered = []
        skipped_singletons = 0
        kept_singletons_by_variant: dict[str, int] = {}
        for r in rows:
            title = str(r["title"] or "")
            if _is_probably_multi_item_title(title):
                filtered.append(r)
                continue
            hint = normalize_item_hint(title)
            if not hint:
                filtered.append(r)
                continue
            _canonical_item_id, variant_key = hint
            if not _is_liquid_singleton_variant(variant_key):
                filtered.append(r)
                continue
            recent_n = _recent_observation_count_for_variant(db, args.market_key, variant_key, args.singleton_recent_hours)
            kept_local = kept_singletons_by_variant.get(variant_key, 0)
            effective_recent_n = recent_n + kept_local
            if effective_recent_n >= args.singleton_min_recent_observations:
                skipped_singletons += 1
                continue
            kept_singletons_by_variant[variant_key] = kept_local + 1
            filtered.append(r)
        rows = filtered
        if not getattr(args, "quiet", False):
            print(
                f"# skip_liquid_singletons=on skipped={skipped_singletons} "
                f"recent_hours={args.singleton_recent_hours} min_recent_obs={args.singleton_min_recent_observations}"
            )

    if args.export_urls:
        out = Path(args.export_urls)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(
            "\n".join((r["url"] or "").replace("&amp;", "&") for r in rows if r["url"]) + ("\n" if rows else ""),
            encoding="utf-8",
        )

    for r in rows:
        print(f"{r['thread_id']}\t{r['reply_count'] or 0}\t{r['url']}\t{r['title']}")
    db.close()
    return 0


def cmd_import_forum_dir(args: argparse.Namespace) -> int:
    db = D2LutDB(args.db)
    db.init_schema()
    files = iter_input_files(args.path, pattern=args.pattern, recursive=args.recursive)
    total_files = total_threads = total_obs = skipped_cf = 0
    for fp in files:
        try:
            n_threads, n_obs = _import_forum_html_into_db(
                db,
                html_path=str(fp),
                forum_id=args.forum_id,
                market_key=args.market_key,
                note=args.note,
                min_fg=args.min_fg,
                max_fg=args.max_fg,
                skip_zero_replies=args.skip_zero_replies,
            )
        except Exception as e:
            print(f"error {fp}: {e}")
            continue
        total_files += 1
        total_threads += n_threads
        total_obs += n_obs
        if n_threads == 0 and n_obs == 0:
            txt = fp.read_text(encoding="utf-8", errors="ignore")
            if "Just a moment..." in txt and "Cloudflare" in txt:
                skipped_cf += 1
        if args.verbose:
            print(f"{fp.name}: threads={n_threads} obs={n_obs}")

    n_est = build_estimates(db, args.market_key)
    print(
        f"imported_forum_dir files={total_files} threads={total_threads} observations={total_obs} "
        f"estimates={n_est} skipped_cloudflare={skipped_cf} market={args.market_key} db={args.db}"
    )
    db.close()
    return 0


def cmd_import_topic_html(args: argparse.Namespace) -> int:
    db = D2LutDB(args.db)
    db.init_schema()
    html_text = Path(args.html).read_text(encoding="utf-8", errors="ignore")
    if "Just a moment..." in html_text and "Cloudflare" in html_text:
        raise SystemExit(
            "Input HTML appears to be a Cloudflare challenge page. Export the fully loaded topic page from Chrome and retry."
        )

    snapshot_id = db.insert_snapshot("d2jsp", args.forum_id, args.html, note=args.note)
    thread_row, post_rows, obs_rows = parse_observations_from_topic_html(
        html_text,
        forum_id=args.forum_id,
        market_key=args.market_key,
        source_url=args.source_url,
        observed_at=datetime.now(timezone.utc).isoformat(),
    )
    if args.skip_bump_only_topic and post_rows and is_bump_only_text(post_rows[0]["body_text"]):
        print("skipped topic import: bump-only text detected")
        db.close()
        return 0
    ctx = load_thread_context(db, thread_row.get("thread_id"))
    if ctx:
        thread_row["thread_trade_type"] = thread_row.get("thread_trade_type") or ctx.get("thread_trade_type")
        if ctx.get("thread_category_id") is not None:
            thread_row["thread_category_id"] = ctx.get("thread_category_id")
        for row in obs_rows:
            row.setdefault("thread_trade_type", thread_row.get("thread_trade_type"))
            if thread_row.get("thread_category_id") is not None:
                row["thread_category_id"] = thread_row.get("thread_category_id")
    thread_row["snapshot_id"] = snapshot_id
    db.upsert_threads([thread_row])
    db.upsert_posts(post_rows, snapshot_id=snapshot_id)
    obs_rows = filter_observations_by_price(obs_rows, args.min_fg, args.max_fg)
    n_obs = db.insert_observed_prices(obs_rows)
    n_est = build_estimates(db, args.market_key)
    print(
        f"imported topic thread_id={thread_row['thread_id']} posts={len(post_rows)} "
        f"observations={n_obs} estimates={n_est} market={args.market_key} db={args.db}"
    )
    db.close()
    return 0


def cmd_import_topic_text(args: argparse.Namespace) -> int:
    db = D2LutDB(args.db)
    db.init_schema()
    text = Path(args.text).read_text(encoding="utf-8", errors="ignore")
    if args.skip_bump_only_topic and is_bump_only_text(text):
        print("skipped topic text import: bump-only text detected")
        db.close()
        return 0
    snapshot_id = db.insert_snapshot("d2jsp", args.forum_id, args.text, note=args.note or "topic text import")

    # Reuse topic parser by wrapping text into simple HTML for title/body extraction is overkill; insert directly.
    thread_id = int(args.thread_id) if args.thread_id else -1
    title = args.title or f"topic {thread_id}" if thread_id > 0 else "topic text import"
    thread_row = {
        "source": "d2jsp",
        "forum_id": args.forum_id,
        "thread_id": thread_id,
        "url": args.source_url or (f"https://forums.d2jsp.org/topic.php?t={thread_id}" if thread_id > 0 else ""),
        "title": title,
        "thread_category_id": None,
        "thread_trade_type": classify_thread_trade_type(title),
        "snapshot_id": snapshot_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    db.upsert_threads([thread_row])
    db.upsert_posts(
        [
            {
                "source": "d2jsp",
                "thread_id": thread_id,
                "post_id": None,
                "body_text": text,
                "posted_at": datetime.now(timezone.utc).isoformat(),
            }
        ],
        snapshot_id=snapshot_id,
    )

    obs_rows: list[dict] = []
    from d2lut.normalize.d2jsp_market import observations_from_text  # local import to keep script imports tidy

    obs_rows.extend(
        observations_from_text(
            text=title,
            market_key=args.market_key,
            forum_id=args.forum_id,
            thread_id=thread_id if thread_id > 0 else None,
            post_id=None,
            source_kind="title",
            source_url=thread_row["url"],
            observed_at=thread_row["created_at"],
            thread_trade_type=thread_row["thread_trade_type"],
        )
    )
    for row in obs_rows:
        row.setdefault("thread_trade_type", thread_row["thread_trade_type"])
        row.setdefault("thread_category_id", thread_row.get("thread_category_id"))
    for line in text.splitlines():
        obs_rows.extend(
            observations_from_text(
                text=line.strip(),
                market_key=args.market_key,
                forum_id=args.forum_id,
                thread_id=thread_id if thread_id > 0 else None,
                post_id=None,
                source_kind="post",
                source_url=thread_row["url"],
                observed_at=thread_row["created_at"],
                thread_trade_type=thread_row["thread_trade_type"],
            )
        )
    obs_rows = filter_observations_by_price(obs_rows, args.min_fg, args.max_fg)
    n_obs = db.insert_observed_prices(obs_rows)
    n_est = build_estimates(db, args.market_key)
    print(
        f"imported topic text thread_id={thread_id} observations={n_obs} "
        f"estimates={n_est} market={args.market_key} db={args.db}"
    )
    db.close()
    return 0


def _import_topic_html_into_db(
    db: D2LutDB,
    *,
    html_path: str,
    forum_id: int,
    market_key: str,
    note: str | None,
    min_fg: float | None,
    max_fg: float | None,
    skip_bump_only_topic: bool,
) -> tuple[int, int, str]:
    html_text = Path(html_path).read_text(encoding="utf-8", errors="ignore")
    if "Just a moment..." in html_text and "Cloudflare" in html_text:
        return (0, 0, "cloudflare")

    snapshot_id = db.insert_snapshot("d2jsp", forum_id, html_path, note=note)
    thread_row, post_rows, obs_rows = parse_observations_from_topic_html(
        html_text,
        forum_id=forum_id,
        market_key=market_key,
        source_url=None,
        observed_at=datetime.now(timezone.utc).isoformat(),
    )
    if skip_bump_only_topic and post_rows and is_bump_only_text(post_rows[0]["body_text"]):
        return (0, 0, "bump")
    ctx = load_thread_context(db, thread_row.get("thread_id"))
    if ctx:
        thread_row["thread_trade_type"] = thread_row.get("thread_trade_type") or ctx.get("thread_trade_type")
        if ctx.get("thread_category_id") is not None:
            thread_row["thread_category_id"] = ctx.get("thread_category_id")
        for row in obs_rows:
            row.setdefault("thread_trade_type", thread_row.get("thread_trade_type"))
            if thread_row.get("thread_category_id") is not None:
                row["thread_category_id"] = thread_row.get("thread_category_id")

    thread_row["snapshot_id"] = snapshot_id
    db.upsert_threads([thread_row])
    db.upsert_posts(post_rows, snapshot_id=snapshot_id)
    obs_rows = filter_observations_by_price(obs_rows, min_fg, max_fg)
    n_obs = db.insert_observed_prices(obs_rows)
    return (1, n_obs, "ok")


def cmd_import_topic_dir(args: argparse.Namespace) -> int:
    db = D2LutDB(args.db)
    db.init_schema()
    files = iter_input_files(args.path, pattern=args.pattern, recursive=args.recursive)
    total_files = total_topics = total_obs = skipped_cf = skipped_bump = 0
    for fp in files:
        try:
            n_topics, n_obs, status = _import_topic_html_into_db(
                db,
                html_path=str(fp),
                forum_id=args.forum_id,
                market_key=args.market_key,
                note=args.note,
                min_fg=args.min_fg,
                max_fg=args.max_fg,
                skip_bump_only_topic=args.skip_bump_only_topic,
            )
        except Exception as e:
            print(f"error {fp}: {e}")
            continue
        total_files += 1
        total_topics += n_topics
        total_obs += n_obs
        if status == "cloudflare":
            skipped_cf += 1
        elif status == "bump":
            skipped_bump += 1
        if args.verbose:
            print(f"{fp.name}: topics={n_topics} obs={n_obs} status={status}")

    n_est = build_estimates(db, args.market_key)
    print(
        f"imported_topic_dir files={total_files} topics={total_topics} observations={total_obs} "
        f"estimates={n_est} skipped_cloudflare={skipped_cf} skipped_bump={skipped_bump} "
        f"market={args.market_key} db={args.db}"
    )
    db.close()
    return 0


def cmd_dump_top(args: argparse.Namespace) -> int:
    db = D2LutDB(args.db)
    db.init_schema()
    rows = db.conn.execute(
        """
        SELECT variant_key, estimate_fg, range_low_fg, range_high_fg, confidence, sample_count
        FROM price_estimates
        WHERE market_key = ?
        ORDER BY estimate_fg DESC, sample_count DESC
        LIMIT ?
        """,
        (args.market_key, args.limit),
    ).fetchall()
    for r in rows:
        print(
            f"{r['variant_key']:<40} ~{r['estimate_fg']:.0f} fg "
            f"[{r['range_low_fg']:.0f}-{r['range_high_fg']:.0f}] "
            f"{r['confidence']} n={r['sample_count']}"
        )
    db.close()
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="d2lut market db builder (d2jsp html snapshot -> sqlite)")
    p.add_argument("--db", default="data/cache/d2lut.db", help="SQLite path")

    sp = p.add_subparsers(dest="cmd", required=True)

    p_init = sp.add_parser("init-db")
    p_init.set_defaults(func=cmd_init_db)

    p_imp = sp.add_parser("import-forum-html")
    p_imp.add_argument("--html", required=True, help="Saved forum HTML snapshot")
    p_imp.add_argument("--forum-id", type=int, default=271)
    p_imp.add_argument("--market-key", default="d2r_sc_ladder")
    p_imp.add_argument("--note", default=None)
    p_imp.add_argument("--export-json", default="data/cache/price_index.json")
    p_imp.add_argument("--min-fg", type=float, default=None)
    p_imp.add_argument("--max-fg", type=float, default=None)
    p_imp.add_argument("--skip-zero-replies", action="store_true")
    p_imp.set_defaults(func=cmd_import_forum_html)

    p_topic = sp.add_parser("import-topic-html")
    p_topic.add_argument("--html", required=True, help="Saved topic.php HTML snapshot")
    p_topic.add_argument("--forum-id", type=int, default=271)
    p_topic.add_argument("--market-key", default="d2r_sc_ladder")
    p_topic.add_argument("--source-url", default=None, help="Original topic URL (optional)")
    p_topic.add_argument("--note", default=None)
    p_topic.add_argument("--min-fg", type=float, default=None)
    p_topic.add_argument("--max-fg", type=float, default=None)
    p_topic.add_argument("--skip-bump-only-topic", action="store_true")
    p_topic.set_defaults(func=cmd_import_topic_html)

    p_topic_txt = sp.add_parser("import-topic-text")
    p_topic_txt.add_argument("--text", required=True, help="Plain text file copied from topic post(s)")
    p_topic_txt.add_argument("--forum-id", type=int, default=271)
    p_topic_txt.add_argument("--market-key", default="d2r_sc_ladder")
    p_topic_txt.add_argument("--thread-id", type=int, default=None)
    p_topic_txt.add_argument("--title", default=None)
    p_topic_txt.add_argument("--source-url", default=None)
    p_topic_txt.add_argument("--note", default=None)
    p_topic_txt.add_argument("--min-fg", type=float, default=None)
    p_topic_txt.add_argument("--max-fg", type=float, default=None)
    p_topic_txt.add_argument("--skip-bump-only-topic", action="store_true")
    p_topic_txt.set_defaults(func=cmd_import_topic_text)

    p_top = sp.add_parser("dump-top")
    p_top.add_argument("--market-key", default="d2r_sc_ladder")
    p_top.add_argument("--limit", type=int, default=50)
    p_top.set_defaults(func=cmd_dump_top)

    p_forum_dir = sp.add_parser("import-forum-dir")
    p_forum_dir.add_argument("--path", required=True, help="Forum HTML snapshot file or directory")
    p_forum_dir.add_argument("--pattern", default="*.html")
    p_forum_dir.add_argument("--recursive", action="store_true")
    p_forum_dir.add_argument("--forum-id", type=int, default=271)
    p_forum_dir.add_argument("--market-key", default="d2r_sc_ladder")
    p_forum_dir.add_argument("--note", default=None)
    p_forum_dir.add_argument("--min-fg", type=float, default=None)
    p_forum_dir.add_argument("--max-fg", type=float, default=None)
    p_forum_dir.add_argument("--skip-zero-replies", action="store_true")
    p_forum_dir.add_argument("--verbose", action="store_true")
    p_forum_dir.set_defaults(func=cmd_import_forum_dir)

    p_topic_dir = sp.add_parser("import-topic-dir")
    p_topic_dir.add_argument("--path", required=True, help="Topic HTML snapshot file or directory")
    p_topic_dir.add_argument("--pattern", default="*.html")
    p_topic_dir.add_argument("--recursive", action="store_true")
    p_topic_dir.add_argument("--forum-id", type=int, default=271)
    p_topic_dir.add_argument("--market-key", default="d2r_sc_ladder")
    p_topic_dir.add_argument("--note", default=None)
    p_topic_dir.add_argument("--min-fg", type=float, default=None)
    p_topic_dir.add_argument("--max-fg", type=float, default=None)
    p_topic_dir.add_argument("--skip-bump-only-topic", action="store_true")
    p_topic_dir.add_argument("--verbose", action="store_true")
    p_topic_dir.set_defaults(func=cmd_import_topic_dir)

    p_cand = sp.add_parser("dump-topic-candidates")
    p_cand.add_argument("--market-key", default="d2r_sc_ladder")
    p_cand.add_argument("--forum-id", type=int, default=271)
    p_cand.add_argument("--limit", type=int, default=200)
    p_cand.add_argument("--skip-zero-replies", action="store_true")
    p_cand.add_argument("--prefer-recent", action="store_true", help="Sort candidates by newest threads first (recommended for fast-moving markets)")
    p_cand.add_argument("--only-priced-titles", action="store_true")
    p_cand.add_argument("--min-fg", type=float, default=None)
    p_cand.add_argument("--max-fg", type=float, default=None)
    p_cand.add_argument("--include-terms", default=None, help="CSV substrings to include in title")
    p_cand.add_argument("--exclude-terms", default=None, help="CSV substrings to exclude from title")
    p_cand.add_argument("--skip-liquid-singletons", action="store_true", help="Skip single-item liquid topics if enough recent observations already exist")
    p_cand.add_argument("--singleton-recent-hours", type=int, default=24, help="Freshness window for --skip-liquid-singletons")
    p_cand.add_argument("--singleton-min-recent-observations", type=int, default=5, help="Minimum recent observations to skip a liquid singleton topic")
    p_cand.add_argument("--export-urls", default=None, help="Write topic URLs (one per line) to file")
    p_cand.set_defaults(func=cmd_dump_topic_candidates)

    return p


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
