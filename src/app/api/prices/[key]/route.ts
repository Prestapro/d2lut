import { NextRequest, NextResponse } from 'next/server';
import { db } from '@/lib/db';

export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ key: string }> }
) {
  try {
    const { key } = await params;
    const variantKey = decodeURIComponent(key);
    
    // Find item
    const item = await db.d2Item.findUnique({
      where: { variantKey },
      include: { priceEstimate: true },
    });
    
    if (!item) {
      return NextResponse.json(
        { error: 'Item not found' },
        { status: 404 }
      );
    }
    
    // Get price observations (last 30 days)
    const thirtyDaysAgo = new Date();
    thirtyDaysAgo.setDate(thirtyDaysAgo.getDate() - 30);
    
    const observations = await db.priceObservation.findMany({
      where: {
        itemId: item.id,
        observedAt: { gte: thirtyDaysAgo },
      },
      orderBy: { observedAt: 'asc' },
    });
    
    // Generate history from observations or estimate
    const history = observations.length > 0
      ? observations.map(o => ({
          date: o.observedAt.toISOString().split('T')[0],
          price: o.priceFg,
        }))
      : generateEstimatedHistory(item.priceEstimate?.priceFg || 50);
    
    const prices = history.map(h => h.price);
    const minPrice = Math.min(...prices);
    const maxPrice = Math.max(...prices);
    const avgPrice = prices.reduce((a, b) => a + b, 0) / prices.length;

    return NextResponse.json({
      item: {
        variantKey: item.variantKey,
        name: item.name,
        displayName: item.displayName,
        category: item.category,
        d2rCode: item.d2rCode,
        priceFg: item.priceEstimate?.priceFg || null,
        tier: getTier(item.priceEstimate?.priceFg || 0),
        confidence: item.priceEstimate?.confidence || null,
        nObservations: item.priceEstimate?.nObservations || 0,
      },
      history,
      minPrice,
      maxPrice,
      avgPrice: Math.round(avgPrice * 10) / 10,
      nObservations: observations.length,
    });
  } catch (error) {
    console.error('Error fetching price history:', error);
    return NextResponse.json(
      { error: 'Failed to fetch price history' },
      { status: 500 }
    );
  }
}

const TIER_THRESHOLDS: Record<string, [number, number]> = {
  GG: [500, 999999],
  HIGH: [100, 500],
  MID: [20, 100],
  LOW: [5, 20],
  TRASH: [0, 5],
};

function getTier(price: number): string {
  for (const [tier, [low, high]] of Object.entries(TIER_THRESHOLDS)) {
    if (price >= low && price < high) return tier;
  }
  return 'TRASH';
}

// Generate estimated price history when no observations exist
function generateEstimatedHistory(currentPrice: number) {
  const history = [];
  const now = Date.now();
  
  for (let i = 30; i >= 0; i--) {
    const variance = (Math.sin(i * 0.5) * currentPrice * 0.15) + (Math.random() - 0.5) * currentPrice * 0.1;
    const price = Math.max(1, currentPrice + variance);
    history.push({
      date: new Date(now - i * 24 * 60 * 60 * 1000).toISOString().split('T')[0],
      price: Math.round(price * 10) / 10,
    });
  }
  
  return history;
}
