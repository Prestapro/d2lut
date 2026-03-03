import { NextRequest, NextResponse } from 'next/server';
import { buildFilter } from '@/lib/d2r-data';

export async function POST(request: NextRequest) {
  try {
    const body = await request.json();
    const { preset = 'default', threshold = 0 } = body;

    const filterContent = buildFilter(preset, threshold);

    return new NextResponse(filterContent, {
      status: 200,
      headers: {
        'Content-Type': 'text/plain; charset=utf-8',
        'Content-Disposition': `attachment; filename="d2lut_${preset}_${Date.now()}.filter"`,
      },
    });
  } catch (error) {
    console.error('Error building filter:', error);
    return NextResponse.json(
      { error: 'Failed to build filter' },
      { status: 500 }
    );
  }
}

export async function GET(request: NextRequest) {
  const searchParams = request.nextUrl.searchParams;
  const preset = searchParams.get('preset') || 'default';
  const threshold = parseFloat(searchParams.get('threshold') || '0');

  try {
    const filterContent = buildFilter(preset, threshold);

    return new NextResponse(filterContent, {
      status: 200,
      headers: {
        'Content-Type': 'text/plain; charset=utf-8',
        'Content-Disposition': `attachment; filename="d2lut_${preset}_${Date.now()}.filter"`,
      },
    });
  } catch (error) {
    console.error('Error building filter:', error);
    return NextResponse.json(
      { error: 'Failed to build filter' },
      { status: 500 }
    );
  }
}
