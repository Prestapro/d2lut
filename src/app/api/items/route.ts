import { NextRequest, NextResponse } from 'next/server';
import { db } from '@/lib/db';
import { getTier } from '@/lib/d2r-utils';

export const dynamic = 'force-dynamic';

const VALID_SORT = ['price', 'name', 'category'] as const;
const VALID_ORDER = ['asc', 'desc'] as const;
const VALID_TIERS = ['GG', 'HIGH', 'MID', 'LOW', 'TRASH'] as const;

export async function GET(request: NextRequest) {
  try {
    const url = new URL(request.url);
    const searchParams = url.searchParams;
    const category = searchParams.get('category');
    const search = searchParams.get('search');

    // Validate sort/order
    const sortRaw = searchParams.get('sort') || 'price';
    const orderRaw = searchParams.get('order') || 'desc';
    const sort = (VALID_SORT as readonly string[]).includes(sortRaw) ? sortRaw : 'price';
    const order = (VALID_ORDER as readonly string[]).includes(orderRaw) ? orderRaw : 'desc';

    // Validate price range
    const minPriceRaw = parseFloat(searchParams.get('minPrice') || '0');
    const maxPriceRaw = parseFloat(searchParams.get('maxPrice') || '999999');
    const minPrice = isNaN(minPriceRaw) || minPriceRaw < 0 ? 0 : minPriceRaw;
    const maxPrice = isNaN(maxPriceRaw) || maxPriceRaw < 0 ? 999999 : maxPriceRaw;

    // Validate tier
    const tierRaw = searchParams.get('tier');
    const tier = tierRaw && (VALID_TIERS as readonly string[]).includes(tierRaw) ? tierRaw : null;

    // Validate pagination
    const limitRaw = parseInt(searchParams.get('limit') || '100', 10);
    const offsetRaw = parseInt(searchParams.get('offset') || '0', 10);
    const limit = isNaN(limitRaw) || limitRaw < 1 ? 100 : Math.min(limitRaw, 500);
    const offset = isNaN(offsetRaw) || offsetRaw < 0 ? 0 : offsetRaw;

    // Build where clause
    const where: Record<string, unknown> = {};
    const andConditions: Record<string, unknown>[] = [];

    if (category) {
      andConditions.push({ category });
    }

    if (search) {
      andConditions.push({
        OR: [
          { name: { contains: search, mode: 'insensitive' } },
          { displayName: { contains: search, mode: 'insensitive' } },
          { variantKey: { contains: search, mode: 'insensitive' } },
        ]
      });
    }

    if (andConditions.length > 0) {
      where.AND = andConditions;
    }

    // Fetch items with prices
    const items = await db.d2Item.findMany({
      where,
      include: {
        priceEstimate: true,
      },
    });

    // Filter by price and tier
    let filteredItems = items.filter(item => {
      const price = item.priceEstimate?.priceFg;

      // Items without prices: include only if no price/tier filter is active
      if (price == null) {
        return minPrice <= 0 && !tier;
      }

      if (price < minPrice || price > maxPrice) return false;

      if (tier) {
        const itemTier = getTier(price);
        if (itemTier !== tier) return false;
      }

      return true;
    });

    // Sort
    filteredItems.sort((a, b) => {
      let comparison = 0;
      const priceA = a.priceEstimate?.priceFg ?? 0;
      const priceB = b.priceEstimate?.priceFg ?? 0;

      switch (sort) {
        case 'name':
          comparison = (a.displayName ?? a.name).localeCompare(b.displayName ?? b.name);
          break;
        case 'category':
          comparison = a.category.localeCompare(b.category);
          break;
        case 'price':
        default:
          comparison = priceA - priceB;
      }
      return order === 'desc' ? -comparison : comparison;
    });

    // Transform for response
    const result = filteredItems.map(item => {
      const price = item.priceEstimate?.priceFg;
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
      };
    });

    // Apply pagination
    const total = result.length;
    const paged = result.slice(offset, offset + limit);

    return NextResponse.json({
      items: paged,
      total,
      limit,
      offset,
      hasMore: offset + limit < total,
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

