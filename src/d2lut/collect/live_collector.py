"""Live Collector for automated d2jsp market data collection.

A comprehensive Playwright-based collector that:
- Runs as a background daemon
- Automatically navigates d2jsp forums
- Extracts price signals from trade posts
- Handles Cloudflare challenges
- Stores data in SQLite database
- Provides real-time updates via callback

This replaces the need for Tampermonkey userscript.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import random
import re
import sqlite3
import time
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Optional
from urllib.parse import parse_qs, urlparse

# Playwright imports with fallback
try:
    from playwright.async_api import async_playwright, Browser, Page, BrowserContext
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False
    async_playwright = None
    Browser = Page = BrowserContext = None


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

@dataclass
class CollectorConfig:
    """Configuration for the live collector."""
    
    # Target settings
    forum_id: int = 271  # D2R trading forum
    categories: list[int] = field(default_factory=lambda: [2, 3, 4, 5])  # Weapon, Charm, Rune, LLD
    
    # Timing
    scan_interval_seconds: float = 300.0  # 5 minutes between full scans
    page_delay_ms: tuple[int, int] = (800, 2000)  # Random delay range
    timeout_ms: int = 30000
    
    # Storage
    db_path: str = "data/cache/d2lut_live.db"
    state_path: str = "data/cache/collector_state.json"
    profile_dir: str = "data/cache/playwright-profile"
    
    # Browser
    headless: bool = False  # Non-headless for Cloudflare bypass
    browser_channel: str = "chrome"
    
    # Limits
    max_pages_per_scan: int = 50
    max_topics_per_page: int = 25
    max_retries: int = 3
    
    # Callbacks
    on_price_observed: Optional[Callable] = None
    on_scan_complete: Optional[Callable] = None
    on_error: Optional[Callable] = None


@dataclass
class CollectorState:
    """Persistent state for the collector."""
    
    last_scan_time: str = ""
    last_topic_id: int = 0
    pages_scanned: int = 0
    topics_processed: int = 0
    prices_observed: int = 0
    errors_count: int = 0
    is_running: bool = False
    
    def to_dict(self) -> dict:
        return {
            "last_scan_time": self.last_scan_time,
            "last_topic_id": self.last_topic_id,
            "pages_scanned": self.pages_scanned,
            "topics_processed": self.topics_processed,
            "prices_observed": self.prices_observed,
            "errors_count": self.errors_count,
            "is_running": self.is_running,
        }
    
    @classmethod
    def from_dict(cls, d: dict) -> "CollectorState":
        return cls(
            last_scan_time=d.get("last_scan_time", ""),
            last_topic_id=d.get("last_topic_id", 0),
            pages_scanned=d.get("pages_scanned", 0),
            topics_processed=d.get("topics_processed", 0),
            prices_observed=d.get("prices_observed", 0),
            errors_count=d.get("errors_count", 0),
            is_running=d.get("is_running", False),
        )


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class PriceObservation:
    """A single price observation from a forum post."""
    
    topic_id: int
    post_id: int
    variant_key: str  # e.g., "rune:jah", "unique:shako"
    item_name: str
    price_fg: float
    price_type: str  # "bin", "ask", "sold"
    category_id: int | None
    author: str
    timestamp: datetime
    raw_text: str = ""
    confidence: float = 0.5
    image_url: str | None = None
    
    def to_db_tuple(self) -> tuple:
        return (
            self.topic_id,
            self.post_id,
            self.variant_key,
            self.item_name,
            self.price_fg,
            self.price_type,
            self.category_id,
            self.author,
            self.timestamp.isoformat(),
            self.raw_text,
            self.confidence,
            self.image_url,
        )


@dataclass
class ScanResult:
    """Result of a single scan operation."""
    
    scan_time: datetime
    pages_scanned: int
    topics_processed: int
    prices_observed: int
    new_prices: int
    errors: list[str] = field(default_factory=list)
    observations: list[PriceObservation] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Price extraction patterns
# ---------------------------------------------------------------------------

# Price patterns in forum posts
PRICE_PATTERNS = [
    # BIN prices
    (r"(?:bin|b/o|buyout)[:\s]*(\d+(?:\.\d+)?)\s*(?:fg|forum\s*gold)", "bin"),
    (r"(\d+(?:\.\d+)?)\s*fg\s*(?:bin|b/o)", "bin"),
    
    # Sold prices (most reliable)
    (r"sold[:\s]*(?:@?\s*)?(\d+(?:\.\d+)?)\s*(?:fg)?", "sold"),
    (r"(\d+(?:\.\d+)?)\s*fg\s*sold", "sold"),
    
    # Asking prices
    (r"(?:asking|asking\s*price|c/o)[:\s]*(\d+(?:\.\d+)?)\s*(?:fg)?", "ask"),
    (r"(?:price|pc)[:\s]*(\d+(?:\.\d+)?)\s*(?:fg)?", "ask"),
    
    # Simple FG amounts in context
    (r"(\d+(?:\.\d+)?)\s*fg(?!\s*bin)", "ask"),
]

# Item name patterns
ITEM_PATTERNS = {
    # Runes
    "rune:jah": r"\bjah\b",
    "rune:ber": r"\bber\b",
    "rune:sur": r"\bsur\b",
    "rune:lo": r"\blo\b",
    "rune:ohm": r"\bohm\b",
    "rune:vex": r"\bvex\b",
    "rune:cham": r"\bcham\b",
    "rune:zod": r"\bzod\b",
    "rune:gul": r"\bgul\b",
    "rune:ist": r"\bist\b",
    "rune:mal": r"\bmal\b",
    "rune:um": r"\bum\b",
    "rune:pul": r"\bpul\b",
    "rune:lem": r"\blem\b",
    
    # High-value uniques
    "unique:shako": r"\bshakos?\b|\bharlequin\s*crest\b",
    "unique:arachnid_mesh": r"\barachs?\b|\barachnid\b",
    "unique:griffons_eye": r"\bgriffons?\b",
    "unique:deaths_fathom": r"\bfathoms?\b|\bdeaths?\s*fathom\b",
    "unique:hoz": r"\bhoz\b|\bherald\s*of\s*zakarum\b",
    "unique:soj": r"\bsoj\b|\bstone\s*of\s*jordan\b",
    "unique:bk": r"\bbk\s*(?:ring|wedding)?\b|\bbul[\'\-]?kathos\b",
    "unique:maras": r"\bmaras?\b|\bkaleidoscope\b",
    "unique:highlords": r"\bhighlords?\b|\bwrath\b",
    "unique:tal_ammy": r"\btal\s*(?:ammy|amulet)?\b|\badjudication\b",
    
    # Runewords
    "runeword:enigma": r"\benigma\b|\bnigma\b",
    "runeword:infinity": r"\binfinity\b|\binfi\b",
    "runeword:grief": r"\bgrief\b",
    "runeword:cta": r"\bcta\b|\bcall\s*to\s*arms\b",
    "runeword:spirit": r"\bspirit\s*(?:sword|shield|monarch)?\b",
    "runeword:insight": r"\binsight\b",
    "runeword:fortitude": r"\bforti?\b|\bfortitude\b",
    
    # Torches/Annihilus
    "torch": r"\btorch(?:es)?\b|\bhellfire\s*torch\b",
    "anni": r"\banni(?:hilus)?\b",
    
    # Charms
    "charm:skiller": r"\bskiller\b|\bgrand\s*charm\b|\bskiller\s*gc\b",
    "charm:sc": r"\bsc\b|\bsmall\s*charm\b|\b3/20/20\b|\b20/5\b",
    
    # Jewels
    "jewel:ias": r"\b40/15\b|\b15/15\b|\bias\s*jewel\b",
    
    # Bases
    "base:monarch": r"\bmonarch\b|\b4os\s*shield\b",
    "base:archon": r"\barchon\b|\bap\b",
    "base:phase": r"\bphase\s*blade\b|\bpb\b",
}


# ---------------------------------------------------------------------------
# Database schema
# ---------------------------------------------------------------------------

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS price_observations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    topic_id INTEGER NOT NULL,
    post_id INTEGER NOT NULL,
    variant_key TEXT NOT NULL,
    item_name TEXT NOT NULL,
    price_fg REAL NOT NULL,
    price_type TEXT NOT NULL,
    category_id INTEGER,
    author TEXT,
    observed_at TEXT NOT NULL,
    raw_text TEXT,
    confidence REAL DEFAULT 0.5,
    image_url TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(topic_id, post_id, variant_key)
);

CREATE INDEX IF NOT EXISTS idx_price_variant ON price_observations(variant_key);
CREATE INDEX IF NOT EXISTS idx_price_observed ON price_observations(observed_at);
CREATE INDEX IF NOT EXISTS idx_price_type ON price_observations(price_type);

CREATE TABLE IF NOT EXISTS scan_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    scan_time TEXT NOT NULL,
    pages_scanned INTEGER,
    topics_processed INTEGER,
    prices_observed INTEGER,
    new_prices INTEGER,
    errors TEXT
);

CREATE TABLE IF NOT EXISTS seen_topics (
    topic_id INTEGER PRIMARY KEY,
    last_seen TEXT NOT NULL
);
"""


# ---------------------------------------------------------------------------
# Live Collector
# ---------------------------------------------------------------------------

class LiveCollector:
    """Automated d2jsp market data collector using Playwright."""
    
    def __init__(self, config: CollectorConfig | None = None):
        self.config = config or CollectorConfig()
        self.state = CollectorState()
        self._browser: Browser | None = None
        self._context: BrowserContext | None = None
        self._page: Page | None = None
        self._running = False
        self._db_conn: sqlite3.Connection | None = None
        
        # Compile patterns
        self._price_patterns = [
            (re.compile(p, re.IGNORECASE), t) for p, t in PRICE_PATTERNS
        ]
        self._item_patterns = {
            k: re.compile(v, re.IGNORECASE) for k, v in ITEM_PATTERNS.items()
        }
    
    async def initialize(self) -> bool:
        """Initialize the collector - browser, database, state."""
        
        if not PLAYWRIGHT_AVAILABLE:
            raise RuntimeError("Playwright not installed. Run: pip install playwright && playwright install")
        
        # Load state
        state_path = Path(self.config.state_path)
        if state_path.exists():
            try:
                with open(state_path, "r") as f:
                    self.state = CollectorState.from_dict(json.load(f))
            except Exception:
                pass
        
        # Initialize database
        db_path = Path(self.config.db_path)
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self._db_conn = sqlite3.connect(str(db_path))
        self._db_conn.executescript(SCHEMA_SQL)
        self._db_conn.commit()
        
        # Launch browser
        try:
            playwright = await async_playwright().start()
            self._browser = await playwright.chromium.launch_persistent_context(
                user_data_dir=str(Path(self.config.profile_dir)),
                channel=self.config.browser_channel,
                headless=self.config.headless,
                viewport={"width": 1280, "height": 900},
                locale="en-US",
                timezone_id="America/New_York",
            )
            self._page = await self._browser.new_page()
            
            # Navigate to d2jsp to establish session
            await self._page.goto("https://forums.d2jsp.org/", timeout=self.config.timeout_ms)
            await asyncio.sleep(2)
            
            return True
            
        except Exception as e:
            if self.config.on_error:
                self.config.on_error(f"Browser init failed: {e}")
            return False
    
    async def run_daemon(self) -> None:
        """Run the collector as a daemon, scanning periodically."""
        
        if not await self.initialize():
            return
        
        self._running = True
        self.state.is_running = True
        self._save_state()
        
        try:
            while self._running:
                # Perform scan
                result = await self.scan_forum()
                
                # Store results
                await self._store_scan_result(result)
                
                # Callback
                if self.config.on_scan_complete:
                    self.config.on_scan_complete(result)
                
                # Wait for next scan
                await asyncio.sleep(self.config.scan_interval_seconds)
                
        finally:
            await self.shutdown()
    
    async def scan_forum(self) -> ScanResult:
        """Perform a single scan of the forum."""
        
        result = ScanResult(
            scan_time=datetime.now(timezone.utc),
            pages_scanned=0,
            topics_processed=0,
            prices_observed=0,
            new_prices=0,
        )
        
        if not self._page:
            result.errors.append("No browser page available")
            return result
        
        try:
            # Scan each category
            for category_id in self.config.categories:
                cat_result = await self._scan_category(category_id)
                result.pages_scanned += cat_result.pages_scanned
                result.topics_processed += cat_result.topics_processed
                result.prices_observed += cat_result.prices_observed
                result.new_prices += cat_result.new_prices
                result.observations.extend(cat_result.observations)
                result.errors.extend(cat_result.errors)
            
            # Update state
            self.state.last_scan_time = result.scan_time.isoformat()
            self.state.pages_scanned += result.pages_scanned
            self.state.topics_processed += result.topics_processed
            self.state.prices_observed += result.prices_observed
            self._save_state()
            
        except Exception as e:
            result.errors.append(str(e))
            self.state.errors_count += 1
            if self.config.on_error:
                self.config.on_error(str(e))
        
        return result
    
    async def _scan_category(self, category_id: int) -> ScanResult:
        """Scan a specific category."""
        
        result = ScanResult(
            scan_time=datetime.now(timezone.utc),
            pages_scanned=0,
            topics_processed=0,
            prices_observed=0,
            new_prices=0,
        )
        
        base_url = f"https://forums.d2jsp.org/forum.php?f={self.config.forum_id}&c={category_id}"
        
        for page_num in range(self.config.max_pages_per_scan):
            offset = page_num * 25
            url = f"{base_url}&o={offset}"
            
            # Retry logic for Cloudflare-blocked pages
            max_retries = 3
            for retry in range(max_retries):
                try:
                    await self._page.goto(url, timeout=self.config.timeout_ms)
                    await asyncio.sleep(random.uniform(*self.config.page_delay_ms) / 1000)
                    
                    # Check for Cloudflare - if detected, wait and retry same page
                    if await self._handle_cloudflare():
                        if retry < max_retries - 1:
                            await asyncio.sleep(5)  # Wait before retry
                            continue  # Retry same page
                        else:
                            result.errors.append(f"Page {page_num}: Cloudflare blocked after {max_retries} retries")
                            break  # Give up on this page, move to next
                    
                    # Successfully loaded page, break retry loop
                    break
                    
                except Exception as e:
                    if retry < max_retries - 1:
                        await asyncio.sleep(2)
                        continue
                    result.errors.append(f"Page {page_num}: {e}")
                    break
            else:
                # All retries exhausted
                continue
            
            try:
                # Extract topic links
                topic_ids = await self._extract_topic_ids()
                
                if not topic_ids:
                    break  # No more topics
                
                result.pages_scanned += 1
                
                # Process each topic
                for topic_id in topic_ids[:self.config.max_topics_per_page]:
                    if not self._running:
                        break
                    
                    # Skip already seen topics
                    if self._is_topic_seen(topic_id):
                        continue
                    
                    obs = await self._process_topic(topic_id, category_id)
                    if obs:
                        result.observations.extend(obs)
                        result.prices_observed += len(obs)
                        result.new_prices += len(obs)
                    
                    result.topics_processed += 1
                    self._mark_topic_seen(topic_id)
                
            except Exception as e:
                result.errors.append(f"Page {page_num}: {e}")
        
        return result
    
    async def _handle_cloudflare(self) -> bool:
        """Handle Cloudflare challenge if present. Returns True if handled."""
        
        title = await self._page.title()
        if "just a moment" in title.lower():
            # Wait for Cloudflare to resolve
            await asyncio.sleep(10)
            return True
        return False
    
    async def _extract_topic_ids(self) -> list[int]:
        """Extract topic IDs from forum listing page."""
        
        topic_ids = []
        
        try:
            # Find all topic links
            links = await self._page.query_selector_all('a[href*="topic.php?t="]')
            
            for link in links:
                href = await link.get_attribute("href")
                if href:
                    # Extract topic ID
                    match = re.search(r"t=(\d+)", href)
                    if match:
                        topic_ids.append(int(match.group(1)))
                        
        except Exception:
            pass
        
        return list(set(topic_ids))
    
    async def _process_topic(self, topic_id: int, category_id: int) -> list[PriceObservation]:
        """Process a single topic and extract price observations."""
        
        observations = []
        
        try:
            url = f"https://forums.d2jsp.org/topic.php?t={topic_id}"
            await self._page.goto(url, timeout=self.config.timeout_ms)
            await asyncio.sleep(random.uniform(0.5, 1.5))
            
            # Get page content
            content = await self._page.content()
            
            # Extract author
            author = ""
            try:
                author_elem = await self._page.query_selector(".username, .author a")
                if author_elem:
                    author = await author_elem.inner_text()
            except Exception:
                pass
            
            # Extract post content
            posts = await self._page.query_selector_all(".post, .postbody, .content")
            
            for post_idx, post in enumerate(posts[:5]):  # First 5 posts
                post_text = await post.inner_text()
                
                # Extract prices from post
                price_data = self._extract_prices(post_text)
                
                for variant_key, price_info in price_data.items():
                    obs = PriceObservation(
                        topic_id=topic_id,
                        post_id=post_idx,
                        variant_key=variant_key,
                        item_name=price_info.get("item_name", variant_key),
                        price_fg=price_info["price"],
                        price_type=price_info["type"],
                        category_id=category_id,
                        author=author.strip(),
                        timestamp=datetime.now(timezone.utc),
                        raw_text=post_text[:500],
                        confidence=price_info.get("confidence", 0.5),
                    )
                    observations.append(obs)
                    
                    # Callback
                    if self.config.on_price_observed:
                        self.config.on_price_observed(obs)
        
        except Exception:
            pass
        
        return observations
    
    def _extract_prices(self, text: str) -> dict[str, dict]:
        """Extract price information from text."""
        
        results = {}
        text_lower = text.lower()
        
        # Find all items mentioned
        items_found = []
        for variant_key, pattern in self._item_patterns.items():
            if pattern.search(text):
                items_found.append(variant_key)
        
        if not items_found:
            return results
        
        # Find prices
        prices_found = []
        for pattern, price_type in self._price_patterns:
            for match in pattern.finditer(text):
                price_val = float(match.group(1))
                if 0.1 <= price_val <= 100000:  # Sanity check
                    prices_found.append({
                        "price": price_val,
                        "type": price_type,
                        "confidence": 0.9 if price_type == "sold" else 0.7 if price_type == "bin" else 0.5,
                    })
        
        # Match items to prices
        if items_found and prices_found:
            # Assume first price applies to first item(s)
            best_price = max(prices_found, key=lambda x: x["confidence"])
            
            for item_key in items_found[:2]:  # Max 2 items per post
                results[item_key] = {
                    **best_price,
                    "item_name": item_key.split(":")[-1].replace("_", " ").title(),
                }
        
        return results
    
    def _is_topic_seen(self, topic_id: int) -> bool:
        """Check if topic was already processed."""
        if not self._db_conn:
            return False
        
        cur = self._db_conn.execute(
            "SELECT 1 FROM seen_topics WHERE topic_id = ?", (topic_id,)
        )
        return cur.fetchone() is not None
    
    def _mark_topic_seen(self, topic_id: int) -> None:
        """Mark topic as processed."""
        if not self._db_conn:
            return
        
        self._db_conn.execute(
            "INSERT OR REPLACE INTO seen_topics (topic_id, last_seen) VALUES (?, ?)",
            (topic_id, datetime.now(timezone.utc).isoformat())
        )
        self._db_conn.commit()
    
    async def _store_scan_result(self, result: ScanResult) -> None:
        """Store scan results in database."""
        
        if not self._db_conn:
            return
        
        # Store observations
        for obs in result.observations:
            try:
                self._db_conn.execute(
                    """INSERT OR IGNORE INTO price_observations 
                    (topic_id, post_id, variant_key, item_name, price_fg, price_type, 
                     category_id, author, observed_at, raw_text, confidence, image_url)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    obs.to_db_tuple()
                )
            except Exception:
                pass
        
        # Store scan history
        self._db_conn.execute(
            """INSERT INTO scan_history 
            (scan_time, pages_scanned, topics_processed, prices_observed, new_prices, errors)
            VALUES (?, ?, ?, ?, ?, ?)""",
            (
                result.scan_time.isoformat(),
                result.pages_scanned,
                result.topics_processed,
                result.prices_observed,
                result.new_prices,
                json.dumps(result.errors),
            )
        )
        
        self._db_conn.commit()
    
    def _save_state(self) -> None:
        """Save collector state to file."""
        state_path = Path(self.config.state_path)
        state_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(state_path, "w") as f:
            json.dump(self.state.to_dict(), f, indent=2)
    
    async def shutdown(self) -> None:
        """Shutdown the collector."""
        
        self._running = False
        self.state.is_running = False
        self._save_state()
        
        if self._browser:
            await self._browser.close()
        
        if self._db_conn:
            self._db_conn.close()
    
    def stop(self) -> None:
        """Signal the collector to stop."""
        self._running = False
    
    def get_recent_observations(self, hours: int = 24, limit: int = 100) -> list[dict]:
        """Get recent price observations."""
        if not self._db_conn:
            return []
        
        cur = self._db_conn.execute(
            """SELECT * FROM price_observations 
            WHERE datetime(observed_at) > datetime('now', ?)
            ORDER BY observed_at DESC LIMIT ?""",
            (f"-{hours} hours", limit)
        )
        
        columns = [desc[0] for desc in cur.description]
        return [dict(zip(columns, row)) for row in cur.fetchall()]


# ---------------------------------------------------------------------------
# Synchronous wrapper
# ---------------------------------------------------------------------------

def run_collector(
    db_path: str = "data/cache/d2lut_live.db",
    headless: bool = False,
    scan_interval: float = 300.0,
    max_pages: int = 50,
    on_price: Optional[Callable] = None,
    on_scan: Optional[Callable] = None,
    on_error: Optional[Callable] = None,
) -> None:
    """Run the live collector (synchronous wrapper).
    
    Args:
        db_path: Path to SQLite database
        headless: Run browser in headless mode (not recommended for Cloudflare)
        scan_interval: Seconds between scans
        max_pages: Maximum pages to scan per category
        on_price: Callback for price observations
        on_scan: Callback for scan completion
        on_error: Callback for errors
    """
    config = CollectorConfig(
        db_path=db_path,
        headless=headless,
        scan_interval_seconds=scan_interval,
        max_pages_per_scan=max_pages,
        on_price_observed=on_price,
        on_scan_complete=on_scan,
        on_error=on_error,
    )
    
    collector = LiveCollector(config)
    asyncio.run(collector.run_daemon())


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="d2jsp Live Collector")
    parser.add_argument("--db", default="data/cache/d2lut_live.db")
    parser.add_argument("--headless", action="store_true")
    parser.add_argument("--interval", type=float, default=300.0)
    parser.add_argument("--max-pages", type=int, default=50)
    parser.add_argument("--once", action="store_true", help="Run single scan and exit")
    
    args = parser.parse_args()
    
    config = CollectorConfig(
        db_path=args.db,
        headless=args.headless,
        scan_interval_seconds=args.interval,
        max_pages_per_scan=args.max_pages,
    )
    
    collector = LiveCollector(config)
    
    if args.once:
        # Single scan - fix AttributeError bug
        init_success = asyncio.run(collector.initialize())
        if not init_success:
            print("Failed to initialize collector")
            result = ScanResult(
                scan_time=datetime.now(timezone.utc),
                pages_scanned=0,
                topics_processed=0,
                prices_observed=0,
                new_prices=0,
                errors=["Failed to initialize collector"],
            )
        else:
            result = asyncio.run(collector.scan_forum())
        print(f"Scan complete: {result.topics_processed} topics, {result.prices_observed} prices")
    else:
        # Daemon mode
        asyncio.run(collector.run_daemon())
