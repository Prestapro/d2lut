# D2JSP HTML Batch Scraper Instructions

This guide explains how to use the batch scraper to download `forum.php` and `topic.php` pages, using a Tampermonkey userscript + local Python server. By running inside your real browser, this method bypasses various Cloudflare and session login checks.

## Setup

1. **Install Tampermonkey Header:**
   - Add the [Tampermonkey extension](https://www.tampermonkey.net/) to your chrome/firefox browser.
   - Open Tampermonkey -> "Create a new script...".
   - Copy the contents of `scripts/d2jsp_tampermonkey_scraper.user.js` completely and replace the default code.
   - Go to `File` -> `Save`.

2. **Test Server Setup:**
   - Make sure your local repository is set up properly.
   - Run `chmod +x scripts/run_d2jsp_scraper_server.py`.

## Scraping Forums (e.g. D2R Ladder SC)

1. **Generate the target URLs plan:**
   Use the built-in URL generator to create a list of forum URLs you want to scrape.
   ```bash
   python3 scripts/generate_forum_url_plan.py --forum-id 271 --pages 100 > forum_urls.txt
   ```
   *(This will create 100 pages, parsing 25 offsets each time).*

2. **Start the local server & queue:**
   Start the local HTTP Python server and load the newly created `forum_urls.txt`:
   ```bash
   python3 scripts/run_d2jsp_scraper_server.py --url-file forum_urls.txt
   ```
   *The server skips any file that's already completely downloaded in `data/raw/d2jsp/forum_pages`!*

3. **Start scraping:**
   - Go to [d2jsp.org](https://forums.d2jsp.org/). Find the small, black overlay in the top-right corner.
   - Click **▶️ Start Scraper**.
   - The browser will now navigate the list of URLs autonomously, reading and downloading HTML.
   - If Cloudflare challenge hits, wait for it to clear. The scraper will retry or wait naturally.
   
## Processing Results

Once your scraper queue finishes, all HTML pages will cleanly exist inside `data/raw/d2jsp/forum_pages`. To process these pages into your DB project:

```bash
python3 scripts/run_d2jsp_snapshot_pipeline.py --db data/cache/d2lut.db --forum-pages-dir data/raw/d2jsp/forum_pages --topic-pages-dir data/raw/d2jsp/topic_pages --market-key d2r_sc_ladder --max-fg 500 --candidate-limit 500 --candidate-urls-out data/cache/topic_candidates_focus.txt --top-limit 100 --skip-topic-import
```

## Bonus: Scraping Topic Pages

After processing forums, `topic_candidates_focus.txt` gets hydrated with URL paths to specific topics! You can batch run these as well:
```bash
python3 scripts/run_d2jsp_scraper_server.py --url-file data/cache/topic_candidates_focus.txt
```
Click **Start Scraper** in the browser again to gather all Topic details.

## Throttling and Settings
To increase or decrease the delay between navigations (to avoid aggro or speed it up), you can adjust `IDLE_DELAY_MS` in the Tampermonkey script directly, or set the storage variable manually.
