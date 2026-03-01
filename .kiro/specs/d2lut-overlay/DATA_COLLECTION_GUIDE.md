# Data Collection Guide for Task 0.10

**Date**: February 27, 2026  
**Task**: 0.10 One-shot data refresh before uncapped reparse  
**Purpose**: Collect category-specific forum snapshots and additional topic pages for comprehensive market data

## Overview

This guide provides step-by-step instructions for collecting additional d2jsp forum snapshots with category filters. The data collection uses Playwright to navigate d2jsp forums and save HTML snapshots for offline parsing.

## Prerequisites

- Python 3.10+ with Playwright installed
- Chrome browser
- d2jsp account (for accessing full forum content)
- Stable internet connection

## Category Reference

d2jsp forum categories for forum ID 271 (D2R SC Ladder):

- **c=2**: Weapons, armor, and bases
- **c=3**: Charms and jewels
- **c=4**: Runes, keys, tokens, and essences
- **c=5**: Low Level Dueling (LLD) items

## Step 1: Collect Category-Specific Forum Pages

### Command Template

```bash
python scripts/fetch_d2jsp_forum_pages.py \
  --forum-id 271 \
  --pages 1000 \
  --categories "2,3,4,5" \
  --no-include-main \
  --out-dir data/raw/d2jsp/forum_pages \
  --profile-dir data/cache/playwright-d2jsp-profile \
  --manual-start \
  --delay-ms 1200 \
  --skip-existing
```

### What This Does

- Collects 1000 pages (25 topics each) for each category (c=2, c=3, c=4, c=5)
- Total: 4000 pages × 25 topics = 100,000 thread listings
- Preserves category in filename: `forum_f271_c2_o0.html`, `forum_f271_c3_o25.html`, etc.
- Skips existing files to allow resuming
- Uses persistent browser profile to maintain login session

### Execution Steps

1. **Start the collection**:
   ```bash
   python scripts/fetch_d2jsp_forum_pages.py \
     --forum-id 271 \
     --pages 1000 \
     --categories "2,3,4,5" \
     --no-include-main \
     --out-dir data/raw/d2jsp/forum_pages \
     --manual-start
   ```

2. **Browser will open** - You'll see: "Browser opened. Log in / pass Cloudflare in this browser window, open the target forum, then press Enter here."

3. **Complete manual steps**:
   - Log in to d2jsp if prompted
   - Pass Cloudflare challenge if present
   - Navigate to the D2R SC Ladder forum (forum ID 271)
   - Press Enter in the terminal

4. **Monitor progress**:
   - Script will save files like: `forum_f271_c2_o0.html`, `forum_f271_c3_o25.html`, etc.
   - Progress printed: `[1] saved forum_f271_c2_o0.html (45231 bytes)`
   - Failures logged to: `data/raw/d2jsp/forum_pages/_fetch_failures.txt`

5. **Expected duration**: ~2-3 hours for 4000 pages (with 1.2s delay between requests)

### Resuming After Interruption

If the script is interrupted, simply re-run the same command. The `--skip-existing` flag will skip already-downloaded files.

## Step 2: Identify High-Value Topic Candidates

After collecting forum pages, identify high-value topics to collect:

```bash
python scripts/build_market_db.py \
  --db data/cache/d2lut.db \
  dump-topic-candidates \
  --market-key d2r_sc_ladder \
  --forum-id 271 \
  --limit 1000 \
  --include-terms "charm,skiller,lld,torch,anni,facet,jewel,circlet,ring,amulet" \
  --exclude-terms "rush,service,grush" \
  --export-urls data/cache/topic_candidates_charms_lld.txt
```

This generates a list of topic URLs focusing on:
- Charms (c=3): skillers, grand charms, small charms
- LLD (c=5): low-level dueling items
- High-value items: torches, annis, facets, jewels, circlets

## Step 3: Collect Topic Pages

### Option A: Using Tampermonkey Scraper (Recommended)

The Tampermonkey scraper is more reliable for topic pages:

1. **Install the userscript**:
   - Open `scripts/d2jsp_tampermonkey_scraper.user.js` in a text editor
   - Copy the entire script
   - Install Tampermonkey extension in Chrome
   - Create new script and paste the code

2. **Load topic URLs**:
   - Open the scraper server: `python scripts/run_d2jsp_scraper_server.py`
   - Navigate to `http://localhost:8765` in Chrome
   - Load `data/cache/topic_candidates_charms_lld.txt`

3. **Start scraping**:
   - Click "Start" in the scraper UI
   - Topics will be saved to `data/raw/d2jsp/topic_pages/`
   - Monitor progress in the UI

### Option B: Using Playwright (Alternative)

If you prefer Playwright, you can manually navigate and save topic pages:

```bash
# This requires a custom script - not yet implemented
# For now, use the Tampermonkey approach
```

## Step 4: Verify Collection

Check collected files:

```bash
# Count category-specific forum pages
ls data/raw/d2jsp/forum_pages/forum_f271_c*.html | wc -l

# Expected: ~4000 files (1000 pages × 4 categories)

# Count topic pages
ls data/raw/d2jsp/topic_pages/*.html | wc -l

# Expected: 500-1000+ files
```

## Step 5: Run Uncapped Reparse

After collecting data, run the full pipeline without price cap:

```bash
python scripts/run_d2jsp_snapshot_pipeline.py \
  --db data/cache/d2lut.db \
  --forum-id 271 \
  --market-key d2r_sc_ladder \
  --clear-market \
  --recursive \
  --candidate-limit 1000 \
  --top-limit 200
```

**Note**: No `--max-fg` parameter = uncapped pricing

## Step 6: Verify Results

Check that high-value items are captured:

```bash
sqlite3 data/cache/d2lut.db "SELECT MAX(price_fg) FROM observed_prices;"
# Expected: > 500 (should see items like Ber, Jah, high-roll torches, etc.)

sqlite3 data/cache/d2lut.db "SELECT variant_key, price_fg FROM observed_prices WHERE price_fg > 500 ORDER BY price_fg DESC LIMIT 10;"
# Should show high-value items
```

## Step 7: Re-export HTML Tables

```bash
# Export price table
python scripts/export_price_table_html.py \
  --db data/cache/d2lut.db \
  --market-key d2r_sc_ladder \
  --out data/exports/price_table.html

# Export property price table
python scripts/export_property_price_table_html.py \
  --db data/cache/d2lut.db \
  --market-key d2r_sc_ladder \
  --out data/exports/property_price_table.html
```

## Troubleshooting

### Cloudflare Blocks

If Cloudflare blocks the scraper:
- Use `--manual-start` to pass challenge manually
- Increase `--delay-ms` to 2000-3000
- Use persistent profile: `--profile-dir data/cache/playwright-d2jsp-profile`

### Login Required

If login is required:
- Use `--manual-start` and log in manually
- Browser profile will persist login for future runs

### Rate Limiting

If you hit rate limits:
- Increase `--delay-ms` to 2000-3000
- Reduce `--pages` and run multiple smaller batches
- Use `--skip-existing` to resume

### Incomplete Data

If some pages fail:
- Check `data/raw/d2jsp/forum_pages/_fetch_failures.txt`
- Re-run with `--skip-existing` to retry failures
- Manually download problematic pages if needed

## Expected Outcomes

After completing this guide:

1. **Forum pages**: 4000+ category-specific pages (c=2, c=3, c=4, c=5)
2. **Topic pages**: 500-1000+ high-value topic pages
3. **Database**: Uncapped price observations with max(price_fg) > 500
4. **HTML exports**: Updated price_table.html and property_price_table.html

## Time Estimates

- **Forum page collection**: 2-3 hours (4000 pages @ 1.2s delay)
- **Topic candidate identification**: 5 minutes
- **Topic page collection**: 1-2 hours (1000 topics)
- **Reparse pipeline**: 10-20 minutes
- **HTML export**: 2-5 minutes

**Total**: 4-6 hours for complete data refresh

## Notes

- The `--skip-existing` flag allows resuming interrupted collections
- Category-specific pages improve pricing accuracy for category-specific items
- Uncapped reparse captures high-value items (Ber, Jah, perfect torches, etc.)
- HTML tables provide browser-based diagnostics for market data quality
