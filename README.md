# D2LUT - D2R Loot Filter Generator

A web application for generating Diablo 2 Resurrected loot filters with Forum Gold (FG) price data from d2jsp marketplace.

## Features

- **Price Dashboard**: Browse 100+ D2R items with current FG prices
- **Tier-based Colors**: GG (purple), HIGH (orange), MID (yellow), LOW (white), TRASH (gray)
- **Filter Builder**: Generate `.filter` files with customizable presets
- **Price History**: View historical price trends for each item
- **Category Filtering**: Runes, Uniques, Runewords, Sets, Bases, Facets

## Tech Stack

- **Frontend**: Next.js 14, React 18, TypeScript 5, Tailwind CSS
- **UI Components**: shadcn/ui with Radix UI primitives
- **Database**: Prisma ORM with SQLite
- **Backend**: Python CLI tool for price collection

## Project Structure

```
├── src/                    # Next.js web application
│   ├── app/               # App Router pages and API routes
│   ├── components/        # React components (ItemTable, FilterBuilder, etc.)
│   └── lib/               # D2R data and utilities
├── d2lut/                  # Python package (CLI tool)
│   ├── src/d2lut/         # Core library (patterns, parser, collector)
│   ├── scripts/           # Filter builder CLI
│   ├── config/            # Presets and item configurations
│   └── data/              # Item codes and templates
└── prisma/                # Database schema
```

## Quick Start

### Web Application

```bash
# Install dependencies
bun install

# Setup database
cp .env.example .env
bun run db:push

# Start development server
bun run dev
```

Open http://localhost:3000 to see the dashboard.

### Python CLI Tool

```bash
cd d2lut

# Install package
pip install -e ".[dev,scraper]"

# Build filter
python scripts/build_d2r_filter.py --preset roguecore --output dist/filter.filter
```

## API Endpoints

| Endpoint | Description |
|----------|-------------|
| `GET /api/items` | List items with filtering and sorting |
| `GET /api/prices/[key]` | Price history for an item |
| `POST /api/filter/build` | Generate and download filter file |
| `GET /api/stats` | Dashboard statistics |

## Price Tiers

| Tier | FG Range | Color |
|------|----------|-------|
| GG | 500+ | Purple |
| HIGH | 100-500 | Orange |
| MID | 20-100 | Yellow |
| LOW | 5-20 | White |
| TRASH | <5 | Gray |

## Data Sources

- **d2jsp.org**: Forum gold prices from marketplace posts
- **item_codes.json**: D2R filter code mappings
- **SAMPLE_PRICES**: Mock data for demonstration

## Development

```bash
# Run linting
bun run lint

# Database operations
bun run db:push      # Push schema to database
bun run db:generate  # Generate Prisma client
bun run db:migrate   # Create migration
```

## Related

- [d2jsp.org](https://d2jsp.org) - Forum gold marketplace
- [D2R Loot Filter Guide](https://github.com/D2R-Modding/D2RModding.Scripts)

## License

MIT License - See [LICENSE](LICENSE) for details.

---

Built for the Diablo 2 Resurrected community.
