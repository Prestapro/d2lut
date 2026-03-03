import { PrismaClient } from '@prisma/client';
import fs from 'fs';
import path from 'path';

type SnapshotRow = {
  canonical_item_id?: string;
  name?: string;
  display_name?: string;
  category?: string;
  sell_fg?: number | null;
  estimate_fg?: number | null;
  obs_count?: number | null;
  last_seen?: string | null;
  source_type?: string | null;
};

function extractDataArray(html: string): SnapshotRow[] {
  const marker = 'const DATA = ';
  const idx = html.indexOf(marker);
  if (idx < 0) throw new Error('DATA marker not found');
  const start = idx + marker.length;
  const end = html.indexOf('];', start);
  if (end < 0) throw new Error('DATA closing bracket not found');
  const jsonText = html.slice(start, end + 1);
  const parsed = JSON.parse(jsonText);
  if (!Array.isArray(parsed)) throw new Error('DATA is not array');
  return parsed as SnapshotRow[];
}

function confidenceLabel(count: number): 'low' | 'medium' | 'high' {
  if (count >= 20) return 'high';
  if (count >= 5) return 'medium';
  return 'low';
}

function toNameFromKey(key: string): string {
  const i = key.indexOf(':');
  return i >= 0 ? key.slice(i + 1) : key;
}

async function main() {
  const prisma = new PrismaClient();
  const htmlPath = path.join(process.cwd(), 'data', 'cache', 'all_items_market_table.html');
  const html = fs.readFileSync(htmlPath, 'utf8');
  const rows = extractDataArray(html);

  let upsertedItems = 0;
  let pricedRows = 0;

  for (const row of rows) {
    const variantKey = (row.canonical_item_id || '').trim();
    if (!variantKey || !variantKey.includes(':')) continue;

    const displayName = (row.name || row.display_name || toNameFromKey(variantKey)).trim();
    const category = (row.category || variantKey.split(':')[0] || 'misc').trim().toLowerCase();
    const item = await prisma.d2Item.upsert({
      where: { variantKey },
      update: {
        name: toNameFromKey(variantKey),
        displayName,
        category,
      },
      create: {
        variantKey,
        name: toNameFromKey(variantKey),
        displayName,
        category,
      },
      select: { id: true },
    });
    upsertedItems += 1;

    const sell = typeof row.sell_fg === 'number' ? row.sell_fg : null;
    const est = typeof row.estimate_fg === 'number' ? row.estimate_fg : null;
    const price = sell != null && sell > 0 ? sell : (est != null && est > 0 ? est : null);
    if (price == null) continue;

    const obs = Math.max(0, Number(row.obs_count || 0));
    const now = new Date();
    const seen = row.last_seen ? new Date(row.last_seen) : now;

    await prisma.priceEstimate.upsert({
      where: { itemId: item.id },
      update: {
        priceFg: price,
        confidence: confidenceLabel(obs),
        nObservations: obs,
        minPrice: price,
        maxPrice: price,
        avgPrice: price,
        lastUpdated: now,
      },
      create: {
        itemId: item.id,
        priceFg: price,
        confidence: confidenceLabel(obs),
        nObservations: obs,
        minPrice: price,
        maxPrice: price,
        avgPrice: price,
        lastUpdated: now,
      },
    });

    // Keep one lightweight observation for provenance
    await prisma.priceObservation.create({
      data: {
        itemId: item.id,
        priceFg: price,
        confidence: Math.min(1, Math.max(0.3, obs >= 20 ? 0.9 : obs >= 5 ? 0.75 : 0.6)),
        signalKind: 'snapshot',
        source: row.source_type || 'all_items_market_table',
        sourceId: variantKey,
        observedAt: seen,
      },
    });

    pricedRows += 1;
  }

  const totalItems = await prisma.d2Item.count();
  const priced5 = await prisma.priceEstimate.count({ where: { priceFg: { gte: 5 } } });
  const pricedAny = await prisma.priceEstimate.count({ where: { priceFg: { gt: 0 } } });

  console.log(JSON.stringify({ ok: true, snapshotRows: rows.length, upsertedItems, pricedRows, totalItems, pricedAny, priced5 }));
  await prisma.$disconnect();
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});
