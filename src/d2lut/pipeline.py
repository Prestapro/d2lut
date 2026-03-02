from __future__ import annotations

import json
from pathlib import Path

from d2lut.collect.d2jsp import D2JspCollector, D2JspCollectorConfig
from d2lut.exporters.d2r_filter import D2RFilterExporter
from d2lut.normalize.parser import MarketParser
from d2lut.pricing.engine import PricingEngine
from d2lut.models import ObservedPrice


def run_pipeline(data_dir: str = "data", use_live: bool = True) -> None:
    """Pipeline entrypoint.
    
    Args:
        data_dir: Root directory for data storage
        use_live: If True, use LiveCollector (requires Playwright)
                  If False, use static JSON price file if available
    """
    collector = D2JspCollector(D2JspCollectorConfig(
        forum_id=271,
        use_live_collector=use_live,
    ))
    parser = MarketParser()
    pricing = PricingEngine()
    exporter = D2RFilterExporter()

    # Collect posts
    posts = list(collector.fetch_recent())
    
    # If no posts collected and not using live, try loading from cache
    if not posts and not use_live:
        cache_path = Path(data_dir) / "cache" / "price_observations.json"
        if cache_path.exists():
            with open(cache_path, "r") as f:
                cached = json.load(f)
            # Convert cached observations
            observations = [
                ObservedPrice(
                    canonical_item_id=o["canonical_item_id"],
                    variant_key=o["variant_key"],
                    ask_fg=o.get("ask_fg"),
                    bin_fg=o.get("bin_fg"),
                    sold_fg=o.get("sold_fg"),
                    confidence=o.get("confidence", 0.5),
                    source_url=o.get("source_url", ""),
                    thread_category_id=o.get("thread_category_id"),  # Restore from cache
                )
                for o in cached
            ]
        else:
            observations = []
    else:
        # Parse posts into observations
        observations = parser.parse_posts(posts)

    # Build price index
    price_index = pricing.build_index(observations)
    
    # Generate filter output
    filter_text = exporter.export(price_index)

    # Write output
    out = Path(data_dir) / "cache" / "d2lut_filter_preview.txt"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(filter_text, encoding="utf-8")
    
    print(f"Wrote {len(price_index)} price estimates to {out}")


def run_pipeline_from_static(data_dir: str = "data") -> None:
    """Run pipeline using only static price config files (no scraping)."""
    run_pipeline(data_dir, use_live=False)


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="d2lut pipeline")
    parser.add_argument("--data-dir", default="data")
    parser.add_argument("--no-live", action="store_true", help="Don't use live collector")
    
    args = parser.parse_args()
    run_pipeline(args.data_dir, use_live=not args.no_live)
