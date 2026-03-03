import { PrismaClient } from '@prisma/client';
import fs from 'fs';
import path from 'path';

type Row = {
  canonical_item_id?: string;
  display_name?: string;
  category?: string;
  fg_median?: number | null;
  fg_min?: number | null;
  fg_max?: number | null;
  sample_count?: number | null;
  confidence?: string | null;
  source_type?: string | null;
  updated_at?: string | null;
  last_seen?: string | null;
};

function parseDataArray(htmlPath: string): Row[] {
  const html = fs.readFileSync(htmlPath, 'utf8');
  const marker = 'const DATA = ';
  const i = html.indexOf(marker);
  if (i < 0) return [];
  const s = i + marker.length;
  const e = html.indexOf('];', s);
  if (e < 0) return [];
  const text = html.slice(s, e + 1);
  const parsed = JSON.parse(text);
  return Array.isArray(parsed) ? (parsed as Row[]) : [];
}

function labelConfidence(obs: number, incoming?: string | null): 'low' | 'medium' | 'high' {
  const inVal = (incoming || '').toLowerCase();
  if (inVal === 'high' || inVal === 'medium' || inVal === 'low') return inVal;
  if (obs >= 20) return 'high';
  if (obs >= 5) return 'medium';
  return 'low';
}

function nameFromKey(key: string): string {
  const idx = key.indexOf(':');
  return idx >= 0 ? key.slice(idx + 1) : key;
}

async function upsertRows(prisma: PrismaClient, rows: Row[], sourceName: string) {
  let priced = 0;
  let itemsTouched = 0;

  for (const row of rows) {
    const variantKey = (row.canonical_item_id || '').trim();
    if (!variantKey || !variantKey.includes(':')) continue;

    const displayName = (row.display_name || nameFromKey(variantKey)).trim();
    const category = (row.category || variantKey.split(':')[0] || 'misc').trim().toLowerCase();

    const item = await prisma.d2Item.upsert({
      where: { variantKey },
      update: {
        name: nameFromKey(variantKey),
        displayName,
        category,
      },
      create: {
        variantKey,
        name: nameFromKey(variantKey),
        displayName,
        category,
      },
      select: { id: true },
    });
    itemsTouched += 1;

    const price = typeof row.fg_median === 'number' && Number.isFinite(row.fg_median) ? row.fg_median : null;
    if (price == null || price < 5) continue;

    const min = typeof row.fg_min === 'number' ? row.fg_min : price;
    const max = typeof row.fg_max === 'number' ? row.fg_max : price;
    const obs = Math.max(0, Number(row.sample_count || 0));
    const conf = labelConfidence(obs, row.confidence);
    const now = new Date();
    const seen = row.last_seen ? new Date(row.last_seen) : now;

    await prisma.priceEstimate.upsert({
      where: { itemId: item.id },
      update: {
        priceFg: price,
        confidence: conf,
        nObservations: obs,
        minPrice: min,
        maxPrice: max,
        avgPrice: price,
        lastUpdated: now,
      },
      create: {
        itemId: item.id,
        priceFg: price,
        confidence: conf,
        nObservations: obs,
        minPrice: min,
        maxPrice: max,
        avgPrice: price,
        lastUpdated: now,
      },
    });

    await prisma.priceObservation.create({
      data: {
        itemId: item.id,
        priceFg: price,
        confidence: conf === 'high' ? 0.9 : conf === 'medium' ? 0.75 : 0.6,
        signalKind: 'snapshot',
        source: sourceName,
        sourceId: variantKey,
        observedAt: seen,
      },
    });

    priced += 1;
  }

  return { itemsTouched, priced };
}

async function main() {
  const prisma = new PrismaClient();
  const root = process.cwd();
  const files = [
    path.join(root, 'data', 'cache', 'price_table_full.html'),
    path.join(root, 'data', 'cache', 'price_table.html'),
  ];

  let totalRows = 0;
  let totalTouched = 0;
  let totalPriced = 0;

  for (const file of files) {
    if (!fs.existsSync(file)) continue;
    const rows = parseDataArray(file);
    totalRows += rows.length;
    const res = await upsertRows(prisma, rows, path.basename(file));
    totalTouched += res.itemsTouched;
    totalPriced += res.priced;
  }

  const totalItems = await prisma.d2Item.count();
  const priced5 = await prisma.priceEstimate.count({ where: { priceFg: { gte: 5 } } });
  const pricedAny = await prisma.priceEstimate.count({ where: { priceFg: { gt: 0 } } });

  console.log(JSON.stringify({ ok: true, totalRows, totalTouched, totalPriced, totalItems, pricedAny, priced5 }));
  await prisma.$disconnect();
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
