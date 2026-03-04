import { NextRequest, NextResponse } from 'next/server';
import { spawn } from 'child_process';
import path from 'path';
import { db } from '@/lib/db';

export const dynamic = 'force-dynamic';
export const runtime = 'nodejs';

interface CollectorObservation {
  variantKey: string;
  priceFg: number;
  signalKind: string;
  confidence: number;
  source?: string | null;
  sourceId?: string | null;
  author?: string | null;
  observedAt?: string | null;
}

interface CollectorResponse {
  ok: boolean;
  error?: string;
  mode?: 'static' | 'live';
  forumId?: number;
  postsScanned?: number;
  observations?: CollectorObservation[];
}

interface PersistResult {
  observationsStored: number;
  estimatesUpdated: number;
  unmatchedItems: number;
  truncatedObservations: number;
}

const MAX_DIRECT_OBSERVATIONS = 2000;
const MAX_TOTAL_OBSERVATIONS = 2000;
const CREATE_MANY_BATCH_SIZE = 500;
const PRICE_WINDOW_DAYS = 30;

function unauthorized() {
  return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
}

function confidenceLabel(count: number): 'low' | 'medium' | 'high' {
  if (count >= 20) return 'high';
  if (count >= 5) return 'medium';
  return 'low';
}

function runPythonCommand(pythonCmd: string, args: string[]): Promise<string> {
  return new Promise((resolve, reject) => {
    const proc = spawn(pythonCmd, args, { timeout: 180000 });
    let out = '';
    let err = '';

    proc.stdout.on('data', (d) => { out += d.toString(); });
    proc.stderr.on('data', (d) => { err += d.toString(); });
    proc.on('error', reject);
    proc.on('close', (code) => {
      if (code !== 0) {
        reject(new Error(err || `collector exited with code ${code}`));
        return;
      }
      resolve(out);
    });
  });
}

function runCollector(mode: 'static' | 'live', forumId: number, maxPosts: number): Promise<CollectorResponse> {
  return new Promise((resolve, reject) => {
    const scriptPath = path.join(process.cwd(), 'mini-services', 'collect_observations.py');
    const args = [
      scriptPath,
      '--mode',
      mode,
      '--forum-id',
      String(forumId),
      '--max-posts',
      String(maxPosts),
    ];

    const pythonCandidates = process.platform === 'win32'
      ? ['python', 'python3']
      : ['python3', 'python'];

    (async () => {
      let lastError: unknown;
      for (const pythonCmd of pythonCandidates) {
        try {
          const out = await runPythonCommand(pythonCmd, args);
          resolve(JSON.parse(out.trim()) as CollectorResponse);
          return;
        } catch (error) {
          lastError = error;
        }
      }

      reject(lastError instanceof Error ? lastError : new Error('failed to run python collector'));
    })().catch(reject);
  });
}

async function persistObservations(observations: CollectorObservation[]): Promise<PersistResult> {
  const items = await db.d2Item.findMany({
    select: { id: true, variantKey: true },
  });
  const itemByVariant = new Map(items.map((item) => [item.variantKey, item.id]));

  const now = new Date();
  const priceWindowStart = new Date(now.getTime() - PRICE_WINDOW_DAYS * 24 * 60 * 60 * 1000);
  const creates = observations
    .map((o) => {
      const itemId = itemByVariant.get(o.variantKey);
      if (!itemId || !Number.isFinite(o.priceFg) || o.priceFg <= 0) return null;
      const observedAt = o.observedAt ? new Date(o.observedAt) : now;
      if (Number.isNaN(observedAt.getTime())) return null;

      return {
        itemId,
        priceFg: o.priceFg,
        confidence: Number.isFinite(o.confidence) ? Math.max(0, Math.min(1, o.confidence)) : 0.5,
        signalKind: o.signalKind || 'bin',
        source: o.source || 'd2jsp_live_chrome',
        sourceId: o.sourceId || null,
        author: o.author || null,
        observedAt,
      };
    })
    .filter((o): o is NonNullable<typeof o> => o !== null);

  if (creates.length === 0) {
    return {
      observationsStored: 0,
      estimatesUpdated: 0,
      unmatchedItems: observations.length,
      truncatedObservations: 0,
    };
  }

  const truncatedObservations = Math.max(0, creates.length - MAX_TOTAL_OBSERVATIONS);
  const acceptedCreates = creates.slice(0, MAX_TOTAL_OBSERVATIONS);

  await db.$transaction(async (tx) => {
    for (let offset = 0; offset < acceptedCreates.length; offset += CREATE_MANY_BATCH_SIZE) {
      const batch = acceptedCreates.slice(offset, offset + CREATE_MANY_BATCH_SIZE);
      await tx.priceObservation.createMany({ data: batch });
    }
  });
  const touchedItemIds = [...new Set(acceptedCreates.map((o) => o.itemId))];

  let estimatesUpdated = 0;
  for (const itemId of touchedItemIds) {
    const [aggregate, previous] = await Promise.all([
      db.priceObservation.aggregate({
        where: {
          itemId,
          observedAt: { gte: priceWindowStart },
        },
        _count: { _all: true },
        _avg: { priceFg: true },
        _min: { priceFg: true },
        _max: { priceFg: true },
      }),
      db.priceEstimate.findUnique({
        where: { itemId },
        select: { priceFg: true },
      }),
    ]);

    const count = aggregate._count._all;
    const avg = aggregate._avg.priceFg;
    if (!count || avg == null) continue;

    const priceChange = previous?.priceFg
      ? ((avg - previous.priceFg) / previous.priceFg) * 100
      : null;

    await db.priceEstimate.upsert({
      where: { itemId },
      update: {
        priceFg: avg,
        confidence: confidenceLabel(count),
        nObservations: count,
        minPrice: aggregate._min.priceFg ?? avg,
        maxPrice: aggregate._max.priceFg ?? avg,
        avgPrice: avg,
        priceChange,
        lastUpdated: now,
      },
      create: {
        itemId,
        priceFg: avg,
        confidence: confidenceLabel(count),
        nObservations: count,
        minPrice: aggregate._min.priceFg ?? avg,
        maxPrice: aggregate._max.priceFg ?? avg,
        avgPrice: avg,
        priceChange: null,
        lastUpdated: now,
      },
    });
    estimatesUpdated += 1;
  }

  return {
    observationsStored: acceptedCreates.length,
    estimatesUpdated,
    unmatchedItems: observations.length - acceptedCreates.length,
    truncatedObservations,
  };
}

export async function POST(request: NextRequest) {
  try {
    const secret = process.env.CRON_SECRET;
    if (!secret) {
      return NextResponse.json(
        { error: 'CRON_SECRET is not configured' },
        { status: 500 }
      );
    }

    const body = await request.json().catch(() => ({}));
    const auth = request.headers.get('authorization');
    const bodySecret = typeof body.secret === 'string' ? body.secret : '';
    const allowBodySecret =
      process.env.NODE_ENV !== 'production' &&
      bodySecret.length > 0 &&
      bodySecret === secret;

    if (auth !== `Bearer ${secret}` && !allowBodySecret) return unauthorized();

    const mode: 'static' | 'live' = body.mode === 'live' ? 'live' : 'static';
    const forumIdRaw = Number(body.forumId);
    const maxPostsRaw = Number(body.maxPosts);
    const forumId = Number.isFinite(forumIdRaw) && forumIdRaw > 0 ? forumIdRaw : 271;
    const maxPosts = Number.isFinite(maxPostsRaw) && maxPostsRaw > 0 ? Math.min(maxPostsRaw, 100) : 20;

    let observations: CollectorObservation[] = [];
    let postsScanned = 0;
    let usedMode: 'static' | 'live' | 'direct' = mode;

    if (Array.isArray(body.observations)) {
      if (body.observations.length > MAX_DIRECT_OBSERVATIONS) {
        return NextResponse.json(
          {
            error: `Too many observations in request body. Maximum allowed: ${MAX_DIRECT_OBSERVATIONS}`,
          },
          { status: 413 }
        );
      }
      observations = body.observations as CollectorObservation[];
      postsScanned = Number.isFinite(Number(body.postsScanned)) ? Number(body.postsScanned) : observations.length;
      usedMode = 'direct';
    } else {
      const collector = await runCollector(mode, forumId, maxPosts);
      if (!collector.ok || !collector.observations) {
        return NextResponse.json(
          { error: collector.error || 'collector failed' },
          { status: 500 }
        );
      }

      if ((collector.postsScanned || 0) <= 0) {
        return NextResponse.json(
          {
            error: 'collector scanned 0 posts (source unavailable or blocked by anti-bot)',
            mode,
            forumId,
          },
          { status: 502 }
        );
      }

      observations = collector.observations;
      postsScanned = collector.postsScanned || 0;
      usedMode = collector.mode || mode;
    }

    const persisted = await persistObservations(observations);

    return NextResponse.json({
      ok: true,
      mode: usedMode,
      forumId,
      postsScanned,
      observationsReceived: observations.length,
      observationsStored: persisted.observationsStored,
      estimatesUpdated: persisted.estimatesUpdated,
      unmatchedItems: persisted.unmatchedItems,
      truncatedObservations: persisted.truncatedObservations,
    });
  } catch (error) {
    console.error('Failed to refresh prices:', error);
    return NextResponse.json(
      { error: 'Failed to refresh prices' },
      { status: 500 }
    );
  }
}
