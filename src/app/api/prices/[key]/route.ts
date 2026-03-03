import { NextRequest, NextResponse } from 'next/server';
import { getPriceHistory } from '@/lib/d2r-data';

export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ key: string }> }
) {
  try {
    const { key } = await params;
    const variantKey = decodeURIComponent(key);
    const history = getPriceHistory(variantKey);

    if (!history) {
      return NextResponse.json(
        { error: 'Item not found' },
        { status: 404 }
      );
    }

    return NextResponse.json(history);
  } catch (error) {
    console.error('Error fetching price history:', error);
    return NextResponse.json(
      { error: 'Failed to fetch price history' },
      { status: 500 }
    );
  }
}
