PRAGMA journal_mode = WAL;
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS source_snapshots (
  id INTEGER PRIMARY KEY,
  source TEXT NOT NULL,
  forum_id INTEGER NOT NULL,
  captured_at TEXT NOT NULL,
  path TEXT,
  note TEXT
);

CREATE TABLE IF NOT EXISTS threads (
  id INTEGER PRIMARY KEY,
  source TEXT NOT NULL,
  forum_id INTEGER NOT NULL,
  thread_id INTEGER NOT NULL,
  url TEXT NOT NULL,
  title TEXT NOT NULL,
  thread_category_id INTEGER,
  thread_trade_type TEXT,
  reply_count INTEGER,
  author TEXT,
  created_at TEXT,
  snapshot_id INTEGER,
  UNIQUE(source, thread_id),
  FOREIGN KEY(snapshot_id) REFERENCES source_snapshots(id)
);

CREATE TABLE IF NOT EXISTS posts (
  id INTEGER PRIMARY KEY,
  source TEXT NOT NULL,
  thread_id INTEGER NOT NULL,
  post_id INTEGER,
  author TEXT,
  posted_at TEXT,
  body_text TEXT NOT NULL,
  snapshot_id INTEGER,
  UNIQUE(source, post_id),
  FOREIGN KEY(snapshot_id) REFERENCES source_snapshots(id)
);

CREATE TABLE IF NOT EXISTS observed_prices (
  id INTEGER PRIMARY KEY,
  source TEXT NOT NULL,
  market_key TEXT NOT NULL,
  forum_id INTEGER NOT NULL,
  thread_id INTEGER,
  post_id INTEGER,
  source_kind TEXT NOT NULL,      -- title|post|manual
  signal_kind TEXT NOT NULL,      -- bin|sold|co|ask
  thread_category_id INTEGER,     -- forum category c=2/3/4/5 when known
  thread_trade_type TEXT,         -- ft|iso|service|pc|unknown
  canonical_item_id TEXT NOT NULL,
  variant_key TEXT NOT NULL,
  price_fg REAL NOT NULL,
  confidence REAL NOT NULL,
  observed_at TEXT,
  source_url TEXT,
  raw_excerpt TEXT
);

CREATE INDEX IF NOT EXISTS idx_threads_forum ON threads(source, forum_id);
CREATE INDEX IF NOT EXISTS idx_obs_variant ON observed_prices(variant_key);
CREATE INDEX IF NOT EXISTS idx_obs_market_variant ON observed_prices(market_key, variant_key);
CREATE INDEX IF NOT EXISTS idx_obs_time ON observed_prices(observed_at);

CREATE TABLE IF NOT EXISTS price_estimates (
  id INTEGER PRIMARY KEY,
  market_key TEXT NOT NULL,
  variant_key TEXT NOT NULL,
  estimate_fg REAL NOT NULL,
  range_low_fg REAL NOT NULL,
  range_high_fg REAL NOT NULL,
  confidence TEXT NOT NULL,
  sample_count INTEGER NOT NULL,
  updated_at TEXT NOT NULL,
  UNIQUE(market_key, variant_key)
);
