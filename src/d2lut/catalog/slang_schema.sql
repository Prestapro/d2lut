PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS slang_aliases (
  id INTEGER PRIMARY KEY,
  term_norm TEXT NOT NULL,
  term_raw TEXT NOT NULL,
  term_type TEXT NOT NULL,             -- item_alias|base_alias|stat_alias|trade_term|noise|unknown
  canonical_item_id TEXT NOT NULL DEFAULT '', -- empty for non-item terms
  replacement_text TEXT NOT NULL DEFAULT '',  -- normalized textual expansion (e.g. "giant thresher")
  confidence REAL NOT NULL DEFAULT 0.5,
  source TEXT NOT NULL DEFAULT 'manual',
  notes TEXT,
  enabled INTEGER NOT NULL DEFAULT 1,
  UNIQUE(term_norm, canonical_item_id, replacement_text)
);

CREATE INDEX IF NOT EXISTS idx_slang_aliases_term ON slang_aliases(term_norm, enabled);

CREATE TABLE IF NOT EXISTS slang_candidates (
  id INTEGER PRIMARY KEY,
  term_norm TEXT NOT NULL,
  term_raw_sample TEXT NOT NULL,
  gram_size INTEGER NOT NULL,          -- 1/2/3
  corpus TEXT NOT NULL,                -- titles_over300, posts_over300, etc.
  source_scope TEXT NOT NULL,          -- title|post|mixed
  frequency INTEGER NOT NULL,
  distinct_threads INTEGER NOT NULL DEFAULT 0,
  min_fg REAL,
  max_fg REAL,
  avg_fg REAL,
  examples_json TEXT,
  status TEXT NOT NULL DEFAULT 'new',  -- new|reviewed|mapped|ignored
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  UNIQUE(term_norm, gram_size, corpus, source_scope)
);

CREATE INDEX IF NOT EXISTS idx_slang_candidates_freq ON slang_candidates(corpus, source_scope, frequency DESC);
