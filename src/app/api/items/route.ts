import { NextRequest, NextResponse } from 'next/server';
import { db } from '@/lib/db';
import { getTier, TIER_PRICE_RANGES, TIER_NAMES, type TierName } from '@/lib/d2r-utils';
import { Prisma } from '@prisma/client';

export const dynamic = 'force-dynamic';

const VALID_SORT = ['price', 'name', 'category'] as const;
const VALID_ORDER = ['asc', 'desc'] as const;
const VALID_TIERS = TIER_NAMES;
const MAX_PRICE_DEFAULT = 999999;

function toTopicId(sourceId: string | null | undefined): string | null {
  if (!sourceId) return null;
  const trimmed = sourceId.trim();
  if (!trimmed) return null;

  if (/^\d+$/.test(trimmed)) return trimmed;

  const urlMatch = trimmed.match(/[?&]t=(\d+)/i);
  if (urlMatch?.[1]) return urlMatch[1];

  return null;
}

function cleanSearchText(raw: string): string {
  return raw
    .replace(/ÿc[0-9a-z;]*/gi, ' ')
    .replace(/\[[^\]]*fg[^\]]*\]/gi, ' ')
    .replace(/[\u2018\u2019`]/g, "'")
    .normalize('NFKD')
    .replace(/[\u0300-\u036f]/g, '')
    .replace(/[^a-zA-Z0-9' ]+/g, ' ')
    .replace(/\s+/g, ' ')
    .trim();
}

function buildTopicSearchUrl(rawQuery: string): string {
  const normalized = cleanSearchText(rawQuery);

  const params = new URLSearchParams({
    c: '7',
    f: '271',
    t: '0',
    stext: normalized,
    s: 'Search',
  });

  return `https://forums.d2jsp.org/search.php?${params.toString()}`;
}

function cleanDisplayName(raw: string): string {
  const cleaned = raw
    .replace(/ÿc[0-9a-z;]*/gi, ' ')
    .replace(/\[[^\]]*fg[^\]]*\]/gi, ' ')
    .replace(/\s+/g, ' ')
    .trim();

  return cleaned;
}

function extractInlineFg(raw: string): number | null {
  const match = raw.match(/\[(\d+(?:\.\d+)?)\s*fg\]/i);
  if (!match?.[1]) return null;

  const parsed = Number.parseFloat(match[1]);
  if (!Number.isFinite(parsed) || parsed <= 0) return null;

  return parsed;
}

function buildTopicSearchQuery(item: {
  variantKey: string;
  displayName: string;
  name: string;
  category: string;
  hasPriceEstimate: boolean;
}): string {
  const category = item.variantKey.split(':')[0] || '';
  const variantQuery = item.variantKey
    .replace(/^[^:]+:/, '')
    .replace(/[:_+\-]+/g, ' ')
    .replace(/\s+/g, ' ')
    .trim();

  const displayRaw = (item.displayName || '').replace(/^[a-z]+:/i, '');
  const displayQuery = cleanSearchText(displayRaw);
  const variantClean = cleanSearchText(variantQuery);
  const nameQuery = cleanSearchText(item.name || '');

  const candidates = [displayQuery, variantClean, nameQuery].filter((value) => value.length > 0);
  const best = candidates.sort((a, b) => b.length - a.length)[0] || item.variantKey;

  if (!item.hasPriceEstimate) {
    const categoryPrefix = cleanSearchText(item.category || category);
    if (categoryPrefix) return `${categoryPrefix} ${best}`.trim();
  }

  if (best.split(/\s+/).length >= 2) return best;
  if (!category) return best;

  return `${category} ${best}`;
}

export async function GET(request: NextRequest) {
  try {
    const url = new URL(request.url);
    const searchParams = url.searchParams;
    const category = searchParams.get('category');
    const search = searchParams.get('search');

    // Validate sort/order
    const sortRaw = searchParams.get('sort') || 'price';
    const orderRaw = searchParams.get('order') || 'desc';
    const sort = ((VALID_SORT as readonly string[]).includes(sortRaw) ? sortRaw : 'price') as typeof VALID_SORT[number];
    const order = ((VALID_ORDER as readonly string[]).includes(orderRaw) ? orderRaw : 'desc') as Prisma.SortOrder;

    // Validate price range
    const minPriceRaw = parseFloat(searchParams.get('minPrice') || '0');
    const maxPriceRaw = parseFloat(searchParams.get('maxPrice') || String(MAX_PRICE_DEFAULT));
    const minPrice = isNaN(minPriceRaw) || minPriceRaw < 0 ? 0 : minPriceRaw;
    const maxPrice = isNaN(maxPriceRaw) || maxPriceRaw < 0 ? MAX_PRICE_DEFAULT : maxPriceRaw;

    // Validate tier
    const tierRaw = searchParams.get('tier');
    const tier = tierRaw && (VALID_TIERS as readonly string[]).includes(tierRaw) ? tierRaw : null;

    // Validate pagination
    const limitRaw = parseInt(searchParams.get('limit') || '100', 10);
    const offsetRaw = parseInt(searchParams.get('offset') || '0', 10);
    const limit = isNaN(limitRaw) || limitRaw < 1 ? 100 : Math.min(limitRaw, 500);
    const offset = isNaN(offsetRaw) || offsetRaw < 0 ? 0 : offsetRaw;

    // Build where clause
    const andConditions: Prisma.D2ItemWhereInput[] = [];

    if (category) {
      andConditions.push({ category });
    }

    if (search) {
      andConditions.push({
        OR: [
          { name: { contains: search } },
          { displayName: { contains: search } },
          { variantKey: { contains: search } },
        ],
      });
    }

    const includeNullPrices = minPrice <= 0 && !tier;

    if (tier) {
      const tierRange = TIER_PRICE_RANGES[tier as TierName];
      const boundedMin = Math.max(minPrice, tierRange.min);
      const boundedMaxExclusive = tierRange.maxExclusive == null
        ? null
        : Math.min(maxPrice, tierRange.maxExclusive);
      andConditions.push({
        priceEstimate: {
          is: {
            priceFg: {
              gte: boundedMin,
              lt: boundedMaxExclusive ?? undefined,
            },
          },
        },
      });
    } else {
      const pricedInRange: Prisma.D2ItemWhereInput = {
        priceEstimate: {
          is: {
            priceFg: {
              gte: minPrice,
              lt: maxPrice,
            },
          },
        },
      };

      if (includeNullPrices) {
        andConditions.push({
          OR: [
            { priceEstimate: { is: null } },
            pricedInRange,
          ],
        });
      } else {
        andConditions.push(pricedInRange);
      }
    }

    const where: Prisma.D2ItemWhereInput = andConditions.length > 0 ? { AND: andConditions } : {};

    let orderBy: Prisma.D2ItemOrderByWithRelationInput;
    switch (sort) {
      case 'name':
        orderBy = { displayName: order };
        break;
      case 'category':
        orderBy = { category: order };
        break;
      case 'price':
      default:
        // Relation-field ordering for one-to-one price estimate.
        orderBy = { priceEstimate: { priceFg: order } } as Prisma.D2ItemOrderByWithRelationInput;
        break;
    }

    const [items, total] = await Promise.all([
      db.d2Item.findMany({
        where,
        include: {
          priceEstimate: true,
          observations: {
            select: { sourceId: true, observedAt: true },
            orderBy: { observedAt: 'desc' },
            take: 20,
          },
        },
        orderBy,
        skip: offset,
        take: limit,
      }),
      db.d2Item.count({ where }),
    ]);

    // Transform for response
    const result = items.map(item => {
      const estimatePrice = item.priceEstimate?.priceFg;
      const inlinePrice = extractInlineFg(item.displayName || '');
      const price = estimatePrice ?? inlinePrice;
      const topicIds = Array.from(
        new Set(
          item.observations
            .map((obs) => toTopicId(obs.sourceId))
            .filter((id): id is string => Boolean(id))
        )
      ).slice(0, 3);

      const query = buildTopicSearchQuery({
        variantKey: item.variantKey,
        displayName: item.displayName,
        name: item.name,
        category: item.category,
        hasPriceEstimate: Boolean(item.priceEstimate),
      });

      return {
        variantKey: item.variantKey,
        name: item.name,
        displayName: cleanDisplayName(item.displayName || item.name || item.variantKey),
        category: item.category,
        d2rCode: item.d2rCode,
        subCategory: item.subCategory,
        priceFg: price ?? null,
        priceLastUpdated: item.priceEstimate?.lastUpdated?.toISOString() ?? null,
        tier: price != null ? getTier(price) : 'UNKNOWN',
        confidence: item.priceEstimate?.confidence ?? (inlinePrice != null ? 'low' : null),
        nObservations: item.priceEstimate?.nObservations ?? (inlinePrice != null ? 1 : 0),
        topicUrls: topicIds.map((id) => `https://forums.d2jsp.org/topic.php?t=${id}`),
        topicSearchUrl: buildTopicSearchUrl(query),
      };
    });

    return NextResponse.json({
      items: result,
      total,
      limit,
      offset,
      hasMore: offset + result.length < total,
      filters: { category, search, sort, order, minPrice, maxPrice, tier },
    });
  } catch (error) {
    console.error('Error fetching items:', error);
    return NextResponse.json(
      { error: 'Failed to fetch items' },
      { status: 500 }
    );
  }
}
