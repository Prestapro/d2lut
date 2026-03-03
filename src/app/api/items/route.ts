import { NextRequest, NextResponse } from 'next/server';
import { db } from '@/lib/db';
import { Prisma } from '@prisma/client';

// Tier thresholds - inclusive on both ends
const TIER_THRESHOLDS: Record<string, [number, number]> = {
  GG: [500, Infinity],     // 500+
  HIGH: [100, 499.99],     // 100-499.99
  MID: [20, 99.99],        // 20-99.99
  LOW: [5, 19.99],         // 5-19.99
  TRASH: [0, 4.99],        // 0-4.99
};

function getTier(price: number): string {
  // Handle edge cases
  if (price < 0) return 'TRASH';
  if (price >= 500) return 'GG';
  if (price >= 100) return 'HIGH';
  if (price >= 20) return 'MID';
  if (price >= 5) return 'LOW';
  return 'TRASH';
}

// Get tier boundaries for price filtering
function getTierPriceRange(tier: string): { min: number; max: number } | null {
  const range = TIER_THRESHOLDS[tier];
  if (!range) return null;
  return { min: range[0], max: range[1] === Infinity ? 999999 : range[1] };
}

export async function GET(request: NextRequest) {
  try {
    const searchParams = request.nextUrl.searchParams;
    const category = searchParams.get('category');
    const search = searchParams.get('search');
    const sort = searchParams.get('sort') || 'price';
    const order = searchParams.get('order') || 'desc';
    const minPrice = parseFloat(searchParams.get('minPrice') || '0');
    const maxPrice = parseFloat(searchParams.get('maxPrice') || '999999');
    const tier = searchParams.get('tier');

    // Build where clause with proper AND/OR logic
    const whereConditions: Prisma.D2ItemWhereInput[] = [];
    
    // Category filter (if specified)
    if (category) {
      whereConditions.push({ category });
    }
    
    // Search filter - applies to name fields (if specified)
    if (search) {
      whereConditions.push({
        OR: [
          { name: { contains: search.toLowerCase() } },
          { displayName: { contains: search } },
          { variantKey: { contains: search.toLowerCase() } },
        ],
      });
    }
    
    // Price filtering at database level
    const priceConditions: Prisma.D2ItemWhereInput[] = [];
    
    // Apply min/max price filter
    if (minPrice > 0 || maxPrice < 999999) {
      priceConditions.push({
        priceEstimate: {
          priceFg: {
            gte: minPrice,
            lte: maxPrice,
          },
        },
      });
    }
    
    // Apply tier filter if specified
    if (tier) {
      const tierRange = getTierPriceRange(tier);
      if (tierRange) {
        priceConditions.push({
          priceEstimate: {
            priceFg: {
              gte: tierRange.min,
              lte: tierRange.max,
            },
          },
        });
      }
    }
    
    // Combine all conditions with AND
    // Result: category AND (name search) AND (price conditions)
    const allConditions = [...whereConditions, ...priceConditions];
    
    const where: Prisma.D2ItemWhereInput = allConditions.length > 0 
      ? { AND: allConditions }
      : {};

    // Determine sort order
    let orderBy: Prisma.D2ItemOrderByWithRelationInput = {};
    
    switch (sort) {
      case 'name':
        orderBy = { displayName: order === 'desc' ? 'desc' : 'asc' };
        break;
      case 'category':
        orderBy = { category: order === 'desc' ? 'desc' : 'asc' };
        break;
      case 'price':
      default:
        // For price sorting, we need to sort by the related priceEstimate
        orderBy = {
          priceEstimate: {
            priceFg: order === 'desc' ? 'desc' : 'asc',
          },
        };
    }

    // Fetch items with prices - all filtering done at DB level
    const items = await db.d2Item.findMany({
      where,
      include: {
        priceEstimate: true,
      },
      orderBy,
    });

    // Transform for response (no additional filtering needed)
    const result = items.map(item => ({
      variantKey: item.variantKey,
      name: item.name,
      displayName: item.displayName,
      category: item.category,
      d2rCode: item.d2rCode,
      subCategory: item.subCategory,
      priceFg: item.priceEstimate?.priceFg || null,
      tier: getTier(item.priceEstimate?.priceFg || 0),
      confidence: item.priceEstimate?.confidence || null,
      nObservations: item.priceEstimate?.nObservations || 0,
    }));

    return NextResponse.json({
      items: result,
      total: result.length,
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
