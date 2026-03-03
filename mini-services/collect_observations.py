#!/usr/bin/env python3
"""Collect and normalize price observations from d2jsp as JSON."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Add local package source for monorepo usage without install.
sys.path.insert(0, str(Path(__file__).parent.parent / "d2lut" / "src"))

try:
    from d2lut.collect.d2jsp import D2JspCollector
    from d2lut.normalize.parser import MarketParser
except ImportError as exc:
    print(json.dumps({"ok": False, "error": f"Import failed: {exc}"}))
    sys.exit(1)


def main() -> int:
    parser = argparse.ArgumentParser(description="Collect d2jsp observations")
    parser.add_argument("--forum-id", type=int, default=271)
    parser.add_argument("--mode", choices=["static", "live"], default="static")
    parser.add_argument("--max-posts", type=int, default=10)
    parser.add_argument("--max-items-per-post", type=int, default=5)
    args = parser.parse_args()

    collector = D2JspCollector(
        forum_id=args.forum_id,
        use_live_collector=args.mode == "live",
    )
    posts = list(collector.fetch_recent())
    if args.max_posts > 0:
        posts = posts[: args.max_posts]

    parser_obj = MarketParser(max_items_per_post=args.max_items_per_post)
    observations = parser_obj.parse_posts(posts)

    payload = {
        "ok": True,
        "forumId": args.forum_id,
        "mode": args.mode,
        "postsScanned": len(posts),
        "observations": [
            {
                "variantKey": obs.variant_key,
                "priceFg": float(obs.price_fg),
                "signalKind": obs.signal_kind,
                "confidence": float(obs.confidence),
                "source": obs.source,
                "sourceId": str(obs.thread_id) if obs.thread_id else None,
                "author": None,
                "observedAt": (
                    obs.observed_at.isoformat() if obs.observed_at else None
                ),
            }
            for obs in observations
        ],
    }

    print(json.dumps(payload))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
