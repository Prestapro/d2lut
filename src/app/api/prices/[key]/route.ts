import { NextRequest, NextResponse } from 'next/server';
import { db } from '@/lib/db';
import { getTier } from '@/lib/d2r-utils';

export const dynamic = 'force-dynamic';

// Deterministic pseudo-random number generator (mulberry32)
// Same seed always produces same sequence — no hydration mismatch
function seededRandom(seed: number): () => number {
  return () => {
    seed |= 0;
    seed = (seed + 0x6d2b79f5) | 0;
    let t = Math.imul(seed ^ (seed >>> 15), 1 | seed);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

// Hash string to number for deterministic seeding
function hashString(str: string): number {
  let hash = 0;
  for (let i = 0; i < str.length; i++) {
    const char = str.charCodeAt(i);
    hash = ((hash << 5) - hash) + char;
    hash |= 0;
  }
  return hash;
}

export async function GET(
  request: NextRequest,
  { params }: { params: { key: string } }
) {
  try {
    const variantKey = decodeURIComponent(params.key);

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

    // Use real observations if available, otherwise generate deterministic estimates
    const hasRealData = observations.length > 0;
    const history = hasRealData
      ? observations.map(o => ({
        date: o.observedAt.toISOString().split('T')[0],
        price: o.priceFg,
      }))
      : generateEstimatedHistory(variantKey, item.priceEstimate?.priceFg || 50);

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
        priceFg: item.priceEstimate?.priceFg ?? null,
        tier: getTier(item.priceEstimate?.priceFg ?? 0),
        confidence: item.priceEstimate?.confidence ?? null,
        nObservations: item.priceEstimate?.nObservations ?? 0,
      },
      history,
      estimated: !hasRealData,
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

// Generate deterministic estimated price history when no observations exist
// Uses seeded PRNG so same variantKey always produces same history
function generateEstimatedHistory(variantKey: string, currentPrice: number) {
  const history: { date: string; price: number }[] = [];
  const now = Date.now();
  const rand = seededRandom(hashString(variantKey));

  for (let i = 30; i >= 0; i--) {
    const variance = (Math.sin(i * 0.5) * currentPrice * 0.15) + (rand() - 0.5) * currentPrice * 0.1;
    const price = Math.max(1, currentPrice + variance);
    history.push({
      date: new Date(now - i * 24 * 60 * 60 * 1000).toISOString().split('T')[0],
      price: Math.round(price * 10) / 10,
    });
  }

  return history;
}

