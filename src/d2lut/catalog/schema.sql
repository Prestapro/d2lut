PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS catalog_import_runs (
  id INTEGER PRIMARY KEY,
  source_name TEXT NOT NULL,
  source_url TEXT,
  started_at TEXT NOT NULL,
  completed_at TEXT,
  notes TEXT
);

CREATE TABLE IF NOT EXISTS catalog_itemtypes (
  code TEXT PRIMARY KEY,
  name TEXT,
  equiv1 TEXT,
  equiv2 TEXT,
  body INTEGER,
  bodyloc1 TEXT,
  bodyloc2 TEXT,
  shoots TEXT,
  quiver TEXT,
  throwable INTEGER,
  reload INTEGER,
  reqlvl INTEGER,
  class_raw TEXT,
  raw_json TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS catalog_bases (
  code TEXT PRIMARY KEY,
  display_name TEXT NOT NULL,
  item_class TEXT NOT NULL,        -- weapon|armor|misc
  type_code TEXT,
  type2_code TEXT,
  level INTEGER,
  levelreq INTEGER,
  spawnable INTEGER,
  stackable INTEGER,
  gemsockets INTEGER,
  invwidth INTEGER,
  invheight INTEGER,
  normcode TEXT,
  ubercode TEXT,
  ultracode TEXT,
  namestr TEXT,
  raw_json TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS catalog_uniques (
  unique_index TEXT PRIMARY KEY,    -- uniqueitems.index
  display_name TEXT NOT NULL,
  code TEXT,
  lvl INTEGER,
  levelreq INTEGER,
  rarity INTEGER,
  spawnable INTEGER,
  enabled INTEGER,
  raw_json TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS catalog_sets (
  set_index TEXT PRIMARY KEY,       -- setitems.index
  display_name TEXT NOT NULL,
  code TEXT,
  lvl INTEGER,
  levelreq INTEGER,
  rarity INTEGER,
  spawnable INTEGER,
  enabled INTEGER,
  raw_json TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS catalog_affixes (
  affix_id TEXT PRIMARY KEY,        -- prefix:<name> / suffix:<name>
  affix_kind TEXT NOT NULL,         -- prefix|suffix
  affix_name TEXT NOT NULL,
  group_id INTEGER,
  level INTEGER,
  maxlevel INTEGER,
  levelreq INTEGER,
  frequency INTEGER,
  classspecific INTEGER,
  class_raw TEXT,
  transformcolor TEXT,
  itypes_json TEXT,
  etypes_json TEXT,
  mods_json TEXT,
  enabled INTEGER NOT NULL DEFAULT 1,
  raw_json TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS catalog_items (
  canonical_item_id TEXT PRIMARY KEY,
  display_name TEXT NOT NULL,
  category TEXT NOT NULL,          -- rune|base|unique|set|misc|consumable|key|token|essence|charm|jewel|...
  quality_class TEXT NOT NULL,     -- base|unique|set|misc
  base_code TEXT,
  source_table TEXT NOT NULL,      -- catalog_bases|catalog_uniques|catalog_sets|manual
  source_key TEXT,
  tradeable INTEGER NOT NULL DEFAULT 1,
  enabled INTEGER NOT NULL DEFAULT 1,
  metadata_json TEXT
);

CREATE TABLE IF NOT EXISTS catalog_aliases (
  id INTEGER PRIMARY KEY,
  alias_norm TEXT NOT NULL,
  alias_raw TEXT NOT NULL,
  canonical_item_id TEXT NOT NULL,
  alias_type TEXT NOT NULL DEFAULT 'name',  -- name|shorthand|code|manual
  priority INTEGER NOT NULL DEFAULT 100,
  source TEXT NOT NULL DEFAULT 'catalog_seed',
  UNIQUE(alias_norm, canonical_item_id),
  FOREIGN KEY(canonical_item_id) REFERENCES catalog_items(canonical_item_id)
);

CREATE INDEX IF NOT EXISTS idx_catalog_aliases_norm ON catalog_aliases(alias_norm, priority);
CREATE INDEX IF NOT EXISTS idx_catalog_items_category ON catalog_items(category, quality_class);

