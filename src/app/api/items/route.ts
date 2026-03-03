import { NextRequest, NextResponse } from 'next/server';
import { db } from '@/lib/db';
import { getTier } from '@/lib/d2r-utils';
import { Prisma } from '@prisma/client';

export const dynamic = 'force-dynamic';

const VALID_SORT = ['price', 'name', 'category'] as const;
const VALID_ORDER = ['asc', 'desc'] as const;
const VALID_TIERS = ['GG', 'HIGH', 'MID', 'LOW', 'TRASH'] as const;
const MAX_PRICE_DEFAULT = 999999;

const TIER_RANGES: Record<string, { min: number; max: number }> = {
  GG: { min: 500, max: Number.POSITIVE_INFINITY },
  HIGH: { min: 100, max: 500 },
  MID: { min: 20, max: 100 },
  LOW: { min: 5, max: 20 },
  TRASH: { min: 0, max: 5 },
};

function toTopicId(sourceId: string | null | undefined): string | null {
  if (!sourceId) return null;
  const trimmed = sourceId.trim();
  if (!trimmed) return null;

  if (/^\d+$/.test(trimmed)) return trimmed;

  const urlMatch = trimmed.match(/[?&]t=(\d+)/i);
  if (urlMatch?.[1]) return urlMatch[1];

  return null;
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
      const tierRange = TIER_RANGES[tier];
      const boundedMin = Math.max(minPrice, tierRange.min);
      const boundedMax = Math.min(maxPrice, tierRange.max);
      andConditions.push({
        priceEstimate: {
          is: {
            priceFg: {
              gte: boundedMin,
              lte: Number.isFinite(boundedMax) ? boundedMax : undefined,
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
              lte: maxPrice,
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
      const price = item.priceEstimate?.priceFg;
      const topicIds = Array.from(
        new Set(
          item.observations
            .map((obs) => toTopicId(obs.sourceId))
            .filter((id): id is string => Boolean(id))
        )
      ).slice(0, 3);

      const query = encodeURIComponent(item.displayName || item.name || item.variantKey);

      return {
        variantKey: item.variantKey,
        name: item.name,
        displayName: item.displayName,
        category: item.category,
        d2rCode: item.d2rCode,
        subCategory: item.subCategory,
        priceFg: price ?? null,
        tier: price != null ? getTier(price) : 'UNKNOWN',
        confidence: item.priceEstimate?.confidence ?? null,
        nObservations: item.priceEstimate?.nObservations ?? 0,
        topicUrls: topicIds.map((id) => `https://forums.d2jsp.org/topic.php?t=${id}`),
        topicSearchUrl: `https://forums.d2jsp.org/search.php?c=1&f=271&q=${query}`,
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
