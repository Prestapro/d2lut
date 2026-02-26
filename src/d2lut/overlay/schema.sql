-- Overlay system database schema extensions
-- Phase 1 (Core Overlay MVP) - minimal tables and indexes

PRAGMA foreign_keys = ON;

-- In-game item captures for training and validation
CREATE TABLE IF NOT EXISTS overlay_item_captures (
  id INTEGER PRIMARY KEY,
  captured_at TEXT NOT NULL,
  screenshot_path TEXT,
  tooltip_coords TEXT NOT NULL,  -- JSON array [x, y, width, height]
  raw_ocr_text TEXT,
  parsed_item_json TEXT,  -- JSON of ParsedItem
  matched_item_id TEXT,
  confidence REAL,
  user_verified_item_id TEXT,
  verified_at TEXT,
  FOREIGN KEY(matched_item_id) REFERENCES catalog_items(canonical_item_id)
);

CREATE INDEX IF NOT EXISTS idx_overlay_captures_time ON overlay_item_captures(captured_at DESC);
CREATE INDEX IF NOT EXISTS idx_overlay_captures_verified ON overlay_item_captures(user_verified_item_id);

-- Overlay configuration
CREATE TABLE IF NOT EXISTS overlay_config (
  id INTEGER PRIMARY KEY,
  config_key TEXT NOT NULL UNIQUE,
  config_value TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

-- Rule engine rules (configurable without code changes)
CREATE TABLE IF NOT EXISTS pricing_rules (
  rule_id TEXT PRIMARY KEY,
  rule_type TEXT NOT NULL,              -- lld, craft, affix, custom
  conditions_json TEXT NOT NULL,        -- JSON condition specification
  adjustment_type TEXT NOT NULL,        -- multiplier, flat, percentage
  adjustment_value REAL NOT NULL,
  priority INTEGER NOT NULL DEFAULT 0,
  enabled INTEGER NOT NULL DEFAULT 1
);

CREATE INDEX IF NOT EXISTS idx_pricing_rules_type ON pricing_rules(rule_type);
CREATE INDEX IF NOT EXISTS idx_pricing_rules_enabled ON pricing_rules(enabled);

-- Minimal market status view for local lookups
CREATE VIEW IF NOT EXISTS overlay_market_status AS
SELECT 
    pe.market_key,
    pe.variant_key,
    pe.estimate_fg AS median_price,
    pe.range_low_fg,
    pe.range_high_fg,
    pe.confidence,
    pe.sample_count,
    COUNT(DISTINCT op.thread_id) AS active_listings,
    MAX(op.observed_at) AS last_observed,
    CASE 
        WHEN pe.sample_count >= 10 THEN 'stable'
        WHEN pe.sample_count >= 5 THEN 'moderate'
        ELSE 'volatile'
    END AS market_stability
FROM price_estimates pe
LEFT JOIN observed_prices op ON pe.market_key = op.market_key AND pe.variant_key = op.variant_key
GROUP BY pe.market_key, pe.variant_key;

-- Refresh daemon metadata (Phase 4)
CREATE TABLE IF NOT EXISTS refresh_metadata (
    id INTEGER PRIMARY KEY,
    started_at TEXT NOT NULL,
    finished_at TEXT,
    success INTEGER NOT NULL DEFAULT 0,
    last_error TEXT,
    observations_before INTEGER,
    observations_after INTEGER,
    estimates_before INTEGER,
    estimates_after INTEGER,
    observations_delta INTEGER,
    estimates_delta INTEGER,
    trigger TEXT NOT NULL DEFAULT 'scheduled'
);

CREATE INDEX IF NOT EXISTS idx_refresh_metadata_finished
    ON refresh_metadata(finished_at DESC);

-- Price history for trend analysis (Phase 3)
CREATE TABLE IF NOT EXISTS price_history (
  id INTEGER PRIMARY KEY,
  market_key TEXT NOT NULL,
  variant_key TEXT NOT NULL,
  recorded_at TEXT NOT NULL,
  median_fg REAL NOT NULL,
  low_fg REAL NOT NULL,
  high_fg REAL NOT NULL,
  sample_count INTEGER NOT NULL,
  demand_score REAL,
  FOREIGN KEY(market_key, variant_key) REFERENCES price_estimates(market_key, variant_key)
);

CREATE INDEX IF NOT EXISTS idx_price_history_time ON price_history(recorded_at DESC, market_key, variant_key);

-- KPI snapshots for regression tracking (Phase 4, Task 32)
CREATE TABLE IF NOT EXISTS kpi_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    observed_prices INTEGER,
    variants INTEGER,
    canonical_items INTEGER,
    high_value_observations INTEGER,
    high_value_variants INTEGER,
    resolved_by_image_obs INTEGER,
    resolved_by_image_variants INTEGER,
    ocr_precision REAL,
    ocr_comparable_rows INTEGER,
    ocr_exact_match INTEGER,
    ocr_mismatch_count INTEGER
);
