import { NextRequest, NextResponse } from 'next/server';
import { db } from '@/lib/db';
import { getTier } from '@/lib/d2r-utils';

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

    // Build where clause
    const where: any = {};
    const andConditions: any[] = [];

    if (category) {
      andConditions.push({ category });
    }

    if (search) {
      andConditions.push({
        OR: [
          { name: { contains: search.toLowerCase() } },
          { displayName: { contains: search } },
          { variantKey: { contains: search.toLowerCase() } },
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
      const price = item.priceEstimate?.priceFg || 0;
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
      const priceA = a.priceEstimate?.priceFg || 0;
      const priceB = b.priceEstimate?.priceFg || 0;

      switch (sort) {
        case 'name':
          comparison = a.displayName.localeCompare(b.displayName);
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
    const result = filteredItems.map(item => ({
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

