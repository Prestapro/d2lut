#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import sqlite3
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path


TOKEN_RE = re.compile(r"[a-z0-9@+#/%'-]+")
STOPWORDS = {
    "ft", "iso", "pc", "service", "services", "need", "for", "and", "or", "the", "w", "with", "of",
    "in", "my", "your", "new", "item", "items", "list", "random", "offer", "offers", "bin", "sold",
    "co", "res", "pc", "vs", "each", "x", "x2", "x3", "x4", "x5", "x10", "o", "wtb", "wts", "wtt",
    "up", "bump", "bumps", "still", "round", "here",
    "fg",
}
NOISE_PATTERNS = [
    re.compile(r"^\d+$"),
    re.compile(r"^\d+fg$"),
    re.compile(r"^[<>~]+$"),
]
CANONICAL_TOKEN_PARTS_EXCLUDE = {
    "unique", "set", "base", "rune", "misc", "key", "keyset", "token", "essence", "charm", "jewel"
}


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def norm_text(s: str) -> str:
    s = s.lower().replace("&amp;", "and").replace("’", "'")
    s = re.sub(r"\s+", " ", s).strip()
    return s


def norm_token(tok: str) -> str:
    t = tok.lower()
    t = t.replace("’", "'")
    t = t.strip("'")
    return t


def tokenize(text: str) -> list[str]:
    text = norm_text(text)
    toks = [norm_token(m.group(0)) for m in TOKEN_RE.finditer(text)]
    toks = [t for t in toks if t]
    return toks


def looks_noise(token: str) -> bool:
    if token in STOPWORDS:
        return True
    if len(token) <= 1:
        return True
    for rx in NOISE_PATTERNS:
        if rx.match(token):
            return True
    return False


def ngrams(tokens: list[str], n: int) -> list[tuple[str, ...]]:
    if len(tokens) < n:
        return []
    return [tuple(tokens[i : i + n]) for i in range(len(tokens) - n + 1)]


@dataclass
class Stat:
    count: int = 0
    thread_ids: set[int] = field(default_factory=set)
    fg_values: list[float] = field(default_factory=list)
    raw_samples: list[str] = field(default_factory=list)
    contexts: list[str] = field(default_factory=list)

    def add(self, *, thread_id: int | None, fg: float | None, raw: str, context: str) -> None:
        self.count += 1
        if thread_id:
            self.thread_ids.add(int(thread_id))
        if fg is not None:
            self.fg_values.append(float(fg))
        if raw and len(self.raw_samples) < 3 and raw not in self.raw_samples:
            self.raw_samples.append(raw)
        if context and len(self.contexts) < 3 and context not in self.contexts:
            self.contexts.append(context)


def load_known_terms(conn: sqlite3.Connection) -> set[str]:
    known: set[str] = set()
    # catalog aliases
    for (alias_norm,) in conn.execute("SELECT alias_norm FROM catalog_aliases"):
        known.add(alias_norm)
        known.update(alias_norm.split())
    # canonical item ids pieces
    for (cid,) in conn.execute("SELECT canonical_item_id FROM catalog_items"):
        if not cid:
            continue
        parts = re.split(r"[:_]", cid.lower())
        for p in parts:
            if p and p not in CANONICAL_TOKEN_PARTS_EXCLUDE:
                known.add(p)
    # manual slang aliases if table exists
    try:
        for (term_norm,) in conn.execute("SELECT term_norm FROM slang_aliases WHERE enabled=1"):
            known.add(term_norm)
            known.update(term_norm.split())
    except sqlite3.OperationalError:
        pass
    return known


def ensure_slang_schema(conn: sqlite3.Connection) -> None:
    schema_path = Path(__file__).resolve().parents[1] / "src" / "d2lut" / "catalog" / "slang_schema.sql"
    conn.executescript(schema_path.read_text(encoding="utf-8"))
    conn.commit()


def fetch_rows(
    conn: sqlite3.Connection, market_key: str, min_fg: float, max_fg: float | None, source_scope: str
) -> list[sqlite3.Row]:
    conn.row_factory = sqlite3.Row
    max_clause = " AND price_fg <= ? " if max_fg is not None else ""
    params: tuple[object, ...] | None = None
    if source_scope == "title":
        sql = """
            SELECT raw_excerpt AS text, thread_id, price_fg, source_kind
            FROM observed_prices
            WHERE market_key = ? AND price_fg >= ? AND source_kind = 'title' AND raw_excerpt IS NOT NULL
        """
        sql += max_clause
        params = (market_key, min_fg, max_fg) if max_fg is not None else (market_key, min_fg)
        return list(conn.execute(sql, params))
    if source_scope == "post":
        sql = """
            SELECT raw_excerpt AS text, thread_id, price_fg, source_kind
            FROM observed_prices
            WHERE market_key = ? AND price_fg >= ? AND source_kind = 'post' AND raw_excerpt IS NOT NULL
        """
        sql += max_clause
        params = (market_key, min_fg, max_fg) if max_fg is not None else (market_key, min_fg)
        return list(conn.execute(sql, params))
    sql = """
        SELECT raw_excerpt AS text, thread_id, price_fg, source_kind
        FROM observed_prices
        WHERE market_key = ? AND price_fg >= ? AND raw_excerpt IS NOT NULL
    """
    sql += max_clause
    params = (market_key, min_fg, max_fg) if max_fg is not None else (market_key, min_fg)
    return list(conn.execute(sql, params))


def extract_candidates(
    conn: sqlite3.Connection, *, market_key: str, min_fg: float, max_fg: float | None, source_scope: str, top_n: int
) -> dict[tuple[int, str], Stat]:
    rows = fetch_rows(conn, market_key, min_fg, max_fg, source_scope)
    known_terms = load_known_terms(conn)
    stats: dict[tuple[int, str], Stat] = defaultdict(Stat)

    for r in rows:
        text = (r["text"] or "").strip()
        if not text:
            continue
        thread_id = r["thread_id"]
        fg = r["price_fg"]
        tokens = tokenize(text)
        if not tokens:
            continue

        # unigram candidates
        for tok in tokens:
            if looks_noise(tok):
                continue
            if tok in known_terms:
                continue
            stats[(1, tok)].add(thread_id=thread_id, fg=fg, raw=tok, context=text[:160])

        # phrase candidates (2-grams, 3-grams): only if phrase contains unknown token
        for n in (2, 3):
            for gram in ngrams(tokens, n):
                if any(looks_noise(t) for t in gram):
                    continue
                phrase = " ".join(gram)
                if phrase in known_terms:
                    continue
                if all(t in known_terms for t in gram):
                    continue
                stats[(n, phrase)].add(thread_id=thread_id, fg=fg, raw=phrase, context=text[:160])

    # prune low-frequency noise
    filtered: dict[tuple[int, str], Stat] = {}
    for k, st in stats.items():
        n, term = k
        min_count = 2 if n == 1 else 2
        if st.count < min_count:
            continue
        filtered[k] = st

    # keep top_n by frequency (with slight boost for thread diversity)
    ranked = sorted(
        filtered.items(),
        key=lambda kv: (kv[1].count, len(kv[1].thread_ids)),
        reverse=True,
    )[: top_n * 3]  # keep broader set before DB upsert
    return dict(ranked)


def upsert_candidates(
    conn: sqlite3.Connection,
    *,
    candidates: dict[tuple[int, str], Stat],
    corpus: str,
    source_scope: str,
) -> int:
    now = utc_now_iso()
    n = 0
    for (gram_size, term_norm), st in candidates.items():
        fg_values = st.fg_values or []
        examples = [{"raw": raw, "context": ctx} for raw, ctx in zip(st.raw_samples or [term_norm], st.contexts or [""])]
        conn.execute(
            """
            INSERT INTO slang_candidates(
              term_norm, term_raw_sample, gram_size, corpus, source_scope, frequency, distinct_threads,
              min_fg, max_fg, avg_fg, examples_json, status, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'new', ?, ?)
            ON CONFLICT(term_norm, gram_size, corpus, source_scope) DO UPDATE SET
              term_raw_sample=excluded.term_raw_sample,
              frequency=excluded.frequency,
              distinct_threads=excluded.distinct_threads,
              min_fg=excluded.min_fg,
              max_fg=excluded.max_fg,
              avg_fg=excluded.avg_fg,
              examples_json=excluded.examples_json,
              updated_at=excluded.updated_at
            """,
            (
                term_norm,
                st.raw_samples[0] if st.raw_samples else term_norm,
                gram_size,
                corpus,
                source_scope,
                st.count,
                len(st.thread_ids),
                min(fg_values) if fg_values else None,
                max(fg_values) if fg_values else None,
                (sum(fg_values) / len(fg_values)) if fg_values else None,
                json.dumps(examples, ensure_ascii=True),
                now,
                now,
            ),
        )
        n += 1
    conn.commit()
    return n


def cmd_extract(args: argparse.Namespace) -> int:
    conn = sqlite3.connect(args.db)
    conn.row_factory = sqlite3.Row
    ensure_slang_schema(conn)

    if args.max_fg is not None:
        corpus = f"{args.market_key}_{int(args.min_fg)}to{int(args.max_fg)}"
    else:
        corpus = f"{args.market_key}_over{int(args.min_fg)}"
    total_upserts = 0

    scopes = [args.source_scope] if args.source_scope != "both" else ["title", "post"]
    for scope in scopes:
        conn.execute(
            "DELETE FROM slang_candidates WHERE corpus = ? AND source_scope = ?",
            (corpus, scope),
        )
        cands = extract_candidates(
            conn,
            market_key=args.market_key,
            min_fg=args.min_fg,
            max_fg=args.max_fg,
            source_scope=scope,
            top_n=args.limit,
        )
        # Narrow to requested limit after extraction
        ranked = sorted(cands.items(), key=lambda kv: (kv[1].count, len(kv[1].thread_ids)), reverse=True)[: args.limit]
        upsert_n = upsert_candidates(conn, candidates=dict(ranked), corpus=corpus, source_scope=scope)
        total_upserts += upsert_n
        print(f"scope={scope} candidates_upserted={upsert_n}")

    print(f"total_upserts={total_upserts} corpus={corpus}")
    conn.close()
    return 0


def cmd_list(args: argparse.Namespace) -> int:
    conn = sqlite3.connect(args.db)
    conn.row_factory = sqlite3.Row
    ensure_slang_schema(conn)
    if args.corpus:
        corpus = args.corpus
    elif args.max_fg is not None:
        corpus = f"{args.market_key}_{int(args.min_fg)}to{int(args.max_fg)}"
    else:
        corpus = f"{args.market_key}_over{int(args.min_fg)}"
    params: list[object] = [corpus]
    sql = """
      SELECT term_norm, term_raw_sample, gram_size, source_scope, frequency, distinct_threads, min_fg, max_fg, avg_fg, examples_json
      FROM slang_candidates
      WHERE corpus = ?
    """
    if args.source_scope != "both":
        sql += " AND source_scope = ?"
        params.append(args.source_scope)
    if args.gram_size:
        sql += " AND gram_size = ?"
        params.append(args.gram_size)
    sql += " ORDER BY frequency DESC, distinct_threads DESC, term_norm ASC LIMIT ?"
    params.append(args.limit)
    rows = conn.execute(sql, tuple(params)).fetchall()
    for r in rows:
        ex = json.loads(r["examples_json"] or "[]")
        ctx = ex[0]["context"] if ex else ""
        print(
            f"{r['source_scope']:<5} n{r['gram_size']} {r['frequency']:>4}x th={r['distinct_threads']:>3} "
            f"fg[{int(r['min_fg'] or 0)}-{int(r['max_fg'] or 0)}] term={r['term_norm']!r} | {ctx[:120]}"
        )
    conn.close()
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Extract d2jsp slang candidates from high-value observations")
    p.add_argument("--db", default="data/cache/d2lut.db")
    sp = p.add_subparsers(dest="cmd", required=True)

    p_ext = sp.add_parser("extract")
    p_ext.add_argument("--market-key", default="d2r_sc_ladder")
    p_ext.add_argument("--min-fg", type=float, default=300.0)
    p_ext.add_argument("--max-fg", type=float, default=None)
    p_ext.add_argument("--source-scope", choices=["title", "post", "both"], default="both")
    p_ext.add_argument("--limit", type=int, default=300)
    p_ext.set_defaults(func=cmd_extract)

    p_list = sp.add_parser("list")
    p_list.add_argument("--market-key", default="d2r_sc_ladder")
    p_list.add_argument("--min-fg", type=float, default=300.0)
    p_list.add_argument("--max-fg", type=float, default=None)
    p_list.add_argument("--corpus", default=None)
    p_list.add_argument("--source-scope", choices=["title", "post", "both"], default="both")
    p_list.add_argument("--gram-size", type=int, choices=[1, 2, 3], default=None)
    p_list.add_argument("--limit", type=int, default=100)
    p_list.set_defaults(func=cmd_list)
    return p


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
