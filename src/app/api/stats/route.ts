import { NextResponse } from 'next/server';
import { db } from '@/lib/db';

export const dynamic = 'force-dynamic';

export async function GET() {
  try {
    // Get total items count
    const totalItems = await db.d2Item.count();

    // Get items with prices
    const itemsWithPrices = await db.d2Item.findMany({
      include: { priceEstimate: true },
      where: { priceEstimate: { NOT: null } },
    });

    // Calculate stats
    const prices = itemsWithPrices
      .map(i => i.priceEstimate?.priceFg || 0)
      .filter(p => p > 0);

    const avgPrice = prices.length > 0
      ? prices.reduce((a, b) => a + b, 0) / prices.length
      : 0;

    // Find top item
    const topItem = itemsWithPrices.reduce((max, item) => {
      const price = item.priceEstimate?.priceFg || 0;
      const maxPrice = max?.priceEstimate?.priceFg || 0;
      return price > maxPrice ? item : max;
    }, itemsWithPrices[0] || null);

    // Count by tier
    const tierCounts = { GG: 0, HIGH: 0, MID: 0, LOW: 0, TRASH: 0 };
    for (const item of itemsWithPrices) {
      const price = item.priceEstimate?.priceFg || 0;
      const tier = getTier(price);
      tierCounts[tier as keyof typeof tierCounts]++;
    }

    // Get categories
    const categories = await db.d2Item.groupBy({
      by: ['category'],
      _count: { variantKey: true },
    });

    const categoryNames: Record<string, string> = {
      rune: 'Runes',
      unique: 'Uniques',
      runeword: 'Runewords',
      set: 'Set Items',
      base: 'Bases',
      facet: 'Facets',
      misc: 'Miscellaneous',
      craft: 'Crafted',
    };

    const categoryList = categories.map(c => ({
      id: c.category,
      name: categoryNames[c.category] || c.category,
      count: c._count.variantKey,
      icon: getCategoryIcon(c.category),
    }));

    return NextResponse.json({
      totalItems,
      avgPrice: Math.round(avgPrice * 10) / 10,
      topItem: topItem ? {
        variantKey: topItem.variantKey,
        displayName: topItem.displayName,
        priceFg: topItem.priceEstimate?.priceFg || 0,
        tier: getTier(topItem.priceEstimate?.priceFg || 0),
      } : null,
      ggItems: tierCounts.GG,
      highItems: tierCounts.HIGH,
      tierCounts,
      categories: categoryList,
      lastUpdated: new Date().toISOString(),
    });
  } catch (error) {
    console.error('Error fetching stats:', error);
    return NextResponse.json(
      { error: 'Failed to fetch stats' },
      { status: 500 }
    );
  }
}

import { getTier } from '@/lib/d2r-utils';

function getCategoryIcon(category: string): string {
  const icons: Record<string, string> = {
    rune: '💎',
    unique: '⭐',
    runeword: '🔮',
    set: '📦',
    base: '🛡️',
    facet: '🌈',
    misc: '🎯',
    craft: '🔨',
  };
  return icons[category] || '📋';
}
