# D2R Loot Filter Builder (d2lut)

D2R Loot Value Pipeline - Parse d2jsp forum prices and generate loot filters with FG (Forum Gold) values for Diablo 2 Resurrected.

## Features

- **Price Collection**: Scrape live prices from d2jsp trading forums
- **Price Parsing**: Extract FG prices from forum posts with confidence scoring
- **Filter Generation**: Build customized item filters for D2R
- **Multi-platform**: Works on Windows, Linux, and macOS

## Installation

### From PyPI (recommended)
```bash
pip install d2lut
```

### From Source
```bash
git clone https://github.com/Prestapro/d2lut.git
cd d2lut
pip install -e ".[dev,overlay,scraper]"
```

### Optional Dependencies

- `[overlay]` - OCR and overlay features (opencv, pillow, easyocr)
- `[scraper]` - Live price scraping (playwright, websockets)
- `[dev]` - Development tools (pytest, ruff, pyinstaller)

## Usage

### Command Line

```bash
# Build filter with default settings
D2R_Filter_Builder --preset default --db d2lut.db

# Use roguecore preset (minimal, efficient)
D2R_Filter_Builder --preset roguecore --output dist/my_filter.filter

# List price tiers
D2R_Filter_Builder --list-tiers

# Verbose output
D2R_Filter_Builder -v --preset verbose --db d2lut.db
```

### As a Library

```python
from d2lut.collect import D2JspCollector
from d2lut.normalize import MarketParser
from d2lut.models import MarketPost

# Collect posts from d2jsp
collector = D2JspCollector(forum_id=271, use_live_collector=True)
posts = list(collector.fetch_recent())

# Parse prices from posts
parser = MarketParser()
observations = parser.parse_posts(posts)

# Print extracted prices
for obs in observations:
    print(f"{obs.variant_key}: {obs.price_fg} FG (confidence: {obs.confidence})")
```

## Price Tiers

| Tier | FG Range | Color | Description |
|------|----------|-------|-------------|
| GG | 500+ | Purple | God-tier items |
| HIGH | 100-500 | Orange | High-value items |
| MID | 20-100 | Yellow | Mid-value items |
| LOW | 5-20 | White | Low-value items |
| TRASH | <5 | Gray | Low priority |

## Filter Presets

- **default**: Balanced filter with all value tiers
- **roguecore**: Minimalist filter for efficient farming
- **minimal**: Show only high-value items (20+ FG)
- **verbose**: Show all items with detailed info

## Project Structure

```
d2lut/
├── config/
│   ├── base_potential.yml    # Crafting/runeword base definitions
│   ├── perfect_rolls.yml     # Perfect stat definitions
│   └── presets.yml           # Filter preset configurations
├── data/templates/
│   └── item-names-full.json  # Item name mappings
├── src/d2lut/
│   ├── collect/
│   │   ├── __init__.py
│   │   ├── d2jsp.py          # Forum collector
│   │   └── live_collector.py # Playwright-based scraper
│   ├── normalize/
│   │   ├── __init__.py
│   │   └── parser.py         # Price parser
│   ├── models.py             # Data models
│   └── __init__.py
├── scripts/
│   └── build_d2r_filter.py   # CLI entry point
├── tests/
├── pyproject.toml
└── CHANGELOG.md
```

## Configuration

### Base Potential (`config/base_potential.yml`)

Defines which base items have crafting or runeword value:

- Elite armor bases (Archon Plate, Dusk Shroud, etc.)
- Spirit shield bases (Monarch, Sacred Rondache, etc.)
- Infinity polearm bases (Thresher, Giant Thresher, etc.)

### Perfect Rolls (`config/perfect_rolls.yml`)

Perfect stat definitions for valuable items:

- Uniques (Shako, Arachnid, Mara's, Tyrael's)
- Torches and Annis
- Runewords (Enigma, Infinity, CTA, Grief)
- Facets (Fire, Cold, Lightning, Poison)

## Development

### Run Tests
```bash
PYTHONPATH=src pytest tests/ -v
```

### Lint
```bash
ruff check src/ tests/
```

### Build Executable
```bash
pyinstaller scripts/build_d2r_filter.py --onefile
```

## License

MIT License - see [LICENSE](LICENSE) for details.

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## Acknowledgments

- d2jsp.org for providing the trading forum data
- Blizzard Entertainment for Diablo 2 Resurrected
- The D2R modding community
