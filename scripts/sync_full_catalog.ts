import { PrismaClient } from '@prisma/client';
import fs from 'fs';
import path from 'path';

type CatalogRow = {
  id?: number;
  Key: string;
  enUS?: string;
  category?: string;
  quality?: string;
};

type ItemCodes = Record<string, Record<string, string>>;

function toCategory(variantKey: string, fallback?: string): string {
  if (fallback && fallback.trim()) return fallback.trim().toLowerCase();
  const idx = variantKey.indexOf(':');
  if (idx > 0) return variantKey.slice(0, idx).toLowerCase();
  return 'misc';
}

function toName(variantKey: string): string {
  const idx = variantKey.indexOf(':');
  if (idx > 0 && idx + 1 < variantKey.length) return variantKey.slice(idx + 1);
  return variantKey;
}

function flattenItemCodes(itemCodes: ItemCodes): Map<string, string> {
  const out = new Map<string, string>();
  for (const group of Object.values(itemCodes)) {
    if (!group || typeof group !== 'object') continue;
    for (const [k, code] of Object.entries(group)) {
      if (typeof code === 'string' && code.trim()) out.set(k, code.trim());
    }
  }
  return out;
}

async function main() {
  const prisma = new PrismaClient();
  const root = process.cwd();
  const catalogPath = path.join(root, 'output', 'item-names.json');
  const codesPath = path.join(root, 'd2lut', 'data', 'item_codes.json');

  const rawCatalog = fs.readFileSync(catalogPath, 'utf8');
  const parsedCatalog = JSON.parse(rawCatalog) as CatalogRow[];
  if (!Array.isArray(parsedCatalog)) {
    throw new Error('output/item-names.json must be an array');
  }

  const rawCodes = fs.readFileSync(codesPath, 'utf8');
  const parsedCodes = JSON.parse(rawCodes) as ItemCodes;
  const d2rCodes = flattenItemCodes(parsedCodes);

  let upserts = 0;
  for (const row of parsedCatalog) {
    const variantKey = (row.Key || '').trim();
    if (!variantKey || !variantKey.includes(':')) continue;

    const displayName = (row.enUS || toName(variantKey)).trim();
    const category = toCategory(variantKey, row.category);
    const name = toName(variantKey);
    const d2rCode = d2rCodes.get(variantKey) ?? null;

    await prisma.d2Item.upsert({
      where: { variantKey },
      update: {
        name,
        displayName,
        category,
        d2rCode,
      },
      create: {
        variantKey,
        name,
        displayName,
        category,
        d2rCode,
      },
    });
    upserts += 1;
  }

  const total = await prisma.d2Item.count();
  const priced = await prisma.priceEstimate.count({
    where: { priceFg: { gt: 0 } },
  });

  console.log(JSON.stringify({ ok: true, catalogRows: parsedCatalog.length, upserts, totalItems: total, pricedItems: priced }));
  await prisma.$disconnect();
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
