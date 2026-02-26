from __future__ import annotations

from pathlib import Path

from d2lut.collect.d2jsp import D2JspCollector, D2JspCollectorConfig
from d2lut.exporters.d2r_filter import D2RFilterExporter
from d2lut.normalize.parser import MarketParser
from d2lut.pricing.engine import PricingEngine


def run_pipeline(data_dir: str = "data") -> None:
    """Skeleton pipeline entrypoint."""
    collector = D2JspCollector(D2JspCollectorConfig(forum_id=271))
    parser = MarketParser()
    pricing = PricingEngine()
    exporter = D2RFilterExporter()

    posts = list(collector.fetch_recent())
    observations = parser.parse_posts(posts)
    price_index = pricing.build_index(observations)
    filter_text = exporter.export(price_index)

    out = Path(data_dir) / "cache" / "d2lut_filter_preview.txt"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(filter_text, encoding="utf-8")


if __name__ == "__main__":
    run_pipeline()

