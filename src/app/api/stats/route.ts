import { NextResponse } from 'next/server';
import { getStats, getCategories } from '@/lib/d2r-data';

export async function GET() {
  try {
    const stats = getStats();
    const categories = getCategories();

    return NextResponse.json({
      ...stats,
      categories,
    });
  } catch (error) {
    console.error('Error fetching stats:', error);
    return NextResponse.json(
      { error: 'Failed to fetch stats' },
      { status: 500 }
    );
  }
}
