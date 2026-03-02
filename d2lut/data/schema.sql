-- D2LUT Database Schema
-- Version: 1.0.0
-- SQLite compatible

-- =============================================================================
-- Core Tables
-- =============================================================================

-- Item catalog with D2R codes
CREATE TABLE IF NOT EXISTS catalog_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    variant_key TEXT NOT NULL UNIQUE,
    d2r_code TEXT NOT NULL,
    display_name TEXT NOT NULL,
    category TEXT NOT NULL,
    subcategory TEXT,
    base_type TEXT,
    is_tradable BOOLEAN DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_catalog_variant ON catalog_items(variant_key);
CREATE INDEX IF NOT EXISTS idx_catalog_category ON catalog_items(category);
CREATE INDEX IF NOT EXISTS idx_catalog_d2r_code ON catalog_items(d2r_code);

-- Slang/alias mapping
CREATE TABLE IF NOT EXISTS slang_aliases (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    alias TEXT NOT NULL UNIQUE,
    canonical TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_slang_alias ON slang_aliases(alias);

-- =============================================================================
-- Price Data Tables
-- =============================================================================

-- Raw price observations from scraping
CREATE TABLE IF NOT EXISTS observed_prices (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    variant_key TEXT NOT NULL,
    price_fg REAL NOT NULL CHECK (price_fg > 0),
    signal_kind TEXT NOT NULL DEFAULT 'bin',
    confidence REAL NOT NULL DEFAULT 0.5 CHECK (confidence >= 0 AND confidence <= 1),
    
    -- Source tracking
    topic_id INTEGER,
    post_id INTEGER,
    author TEXT,
    forum_id INTEGER DEFAULT 271,
    
    -- Raw data
    raw_text TEXT,
    
    -- Timestamps
    observed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    FOREIGN KEY (variant_key) REFERENCES catalog_items(variant_key)
);

CREATE INDEX IF NOT EXISTS idx_observed_variant ON observed_prices(variant_key);
CREATE INDEX IF NOT EXISTS idx_observed_price ON observed_prices(price_fg);
CREATE INDEX IF NOT EXISTS idx_observed_date ON observed_prices(observed_at);
CREATE INDEX IF NOT EXISTS idx_observed_signal ON observed_prices(signal_kind);

-- Aggregated price estimates
CREATE TABLE IF NOT EXISTS price_estimates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    variant_key TEXT NOT NULL UNIQUE,
    price_fg REAL NOT NULL CHECK (price_fg > 0),
    confidence REAL NOT NULL DEFAULT 0.5,
    
    -- Statistics
    observation_count INTEGER DEFAULT 0,
    min_price REAL,
    max_price REAL,
    std_dev REAL,
    
    -- Price tier
    price_tier TEXT DEFAULT 'LOW',
    
    -- Timestamps
    first_observed TIMESTAMP,
    last_observed TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    FOREIGN KEY (variant_key) REFERENCES catalog_items(variant_key)
);

CREATE INDEX IF NOT EXISTS idx_estimates_price ON price_estimates(price_fg);
CREATE INDEX IF NOT EXISTS idx_estimates_tier ON price_estimates(price_tier);

-- =============================================================================
-- Legacy Schema Support (for backwards compatibility)
-- =============================================================================

-- Alternative table names that might be expected
CREATE TABLE IF NOT EXISTS items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    variant_key TEXT NOT NULL UNIQUE,
    price REAL DEFAULT 0,
    category TEXT DEFAULT 'misc',
    d2r_code TEXT,
    display_name TEXT,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS price_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    variant_key TEXT NOT NULL,
    price REAL NOT NULL,
    source TEXT,
    recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_history_variant ON price_history(variant_key);

-- =============================================================================
-- Scan Metadata
-- =============================================================================

CREATE TABLE IF NOT EXISTS scan_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    forum_id INTEGER DEFAULT 271,
    pages_scanned INTEGER DEFAULT 0,
    posts_processed INTEGER DEFAULT 0,
    observations_created INTEGER DEFAULT 0,
    errors_count INTEGER DEFAULT 0,
    started_at TIMESTAMP,
    finished_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- =============================================================================
-- Views
-- =============================================================================

-- Active price view (most recent estimate per item)
CREATE VIEW IF NOT EXISTS v_active_prices AS
SELECT 
    ci.variant_key,
    ci.d2r_code,
    ci.display_name,
    ci.category,
    pe.price_fg,
    pe.confidence,
    pe.price_tier,
    pe.observation_count,
    pe.last_observed
FROM catalog_items ci
LEFT JOIN price_estimates pe ON ci.variant_key = pe.variant_key
WHERE pe.price_fg IS NOT NULL AND pe.price_fg > 0
ORDER BY pe.price_fg DESC;

-- Recent observations view
CREATE VIEW IF NOT EXISTS v_recent_observations AS
SELECT 
    op.variant_key,
    ci.display_name,
    op.price_fg,
    op.signal_kind,
    op.confidence,
    op.topic_id,
    op.author,
    op.observed_at
FROM observed_prices op
LEFT JOIN catalog_items ci ON op.variant_key = ci.variant_key
ORDER BY op.observed_at DESC
LIMIT 1000;

-- =============================================================================
-- Triggers
-- =============================================================================

-- Update timestamp on catalog_items
CREATE TRIGGER IF NOT EXISTS trg_catalog_updated
AFTER UPDATE ON catalog_items
BEGIN
    UPDATE catalog_items SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
END;

-- Auto-create price_estimate when observations are added
CREATE TRIGGER IF NOT EXISTS trg_update_estimate
AFTER INSERT ON observed_prices
BEGIN
    INSERT OR REPLACE INTO price_estimates (
        variant_key, price_fg, confidence, observation_count,
        min_price, max_price, first_observed, last_observed, updated_at
    )
    SELECT 
        NEW.variant_key,
        AVG(price_fg),
        AVG(confidence),
        COUNT(*),
        MIN(price_fg),
        MAX(price_fg),
        MIN(observed_at),
        MAX(observed_at),
        CURRENT_TIMESTAMP
    FROM observed_prices
    WHERE variant_key = NEW.variant_key;
END;
