import { NextRequest, NextResponse } from 'next/server';
import { getAllItems, getItemsByCategory, D2Item } from '@/lib/d2r-data';

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

    let items = category ? getItemsByCategory(category) : getAllItems();

    // Apply filters
    if (search) {
      const searchLower = search.toLowerCase();
      items = items.filter(item =>
        item.name.toLowerCase().includes(searchLower) ||
        item.displayName.toLowerCase().includes(searchLower) ||
        item.variantKey.toLowerCase().includes(searchLower)
      );
    }

    if (minPrice > 0 || maxPrice < 999999) {
      items = items.filter(item =>
        (item.priceFg || 0) >= minPrice && (item.priceFg || 0) <= maxPrice
      );
    }

    if (tier) {
      items = items.filter(item => item.tier === tier);
    }

    // Apply sorting
    items.sort((a, b) => {
      let comparison = 0;
      switch (sort) {
        case 'name':
          comparison = a.displayName.localeCompare(b.displayName);
          break;
        case 'category':
          comparison = a.category.localeCompare(b.category);
          break;
        case 'price':
        default:
          comparison = (a.priceFg || 0) - (b.priceFg || 0);
      }
      return order === 'desc' ? -comparison : comparison;
    });

    return NextResponse.json({
      items,
      total: items.length,
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
