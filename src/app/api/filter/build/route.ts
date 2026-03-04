import { NextRequest, NextResponse } from 'next/server';
import { spawn } from 'child_process';
import { existsSync } from 'fs';
import path from 'path';
import { getTier, TIER_D2R_COLOR_CODES } from '@/lib/d2r-utils';
import { db } from '@/lib/db';

const VALID_PRESETS = ['default', 'ggplus', 'gg', 'roguecore', 'minimal', 'verbose'];

interface FilterItem {
  name: string;
  codes: string[];  // D2R item codes (base items for runewords)
  price: number;
}

interface BridgeResult {
  success: boolean;
  content?: string;
  error?: string;
}

const TIER_LIST = ['GG', 'HIGH', 'MID', 'LOW', 'TRASH'] as const;

function generateFilterContent(
  preset: string,
  threshold: number,
  sourceLabel: string,
  items: FilterItem[]
): string {
  const filtered = items.filter((item) => item.price >= threshold);

  const lines: string[] = [
    `# D2R Loot Filter - D2LUT`,
    `# Generated: ${new Date().toISOString()}`,
    `# Preset: ${preset}`,
    `# Threshold: ${threshold} FG`,
    `# Source: ${sourceLabel} (${filtered.length} items)`,
    '',
  ];

  for (const tierName of TIER_LIST) {
    const tierItems = filtered.filter((item) => getTier(item.price) === tierName);
    if (tierItems.length === 0) continue;

    lines.push(`# === ${tierName} TIER (${tierItems.length} items) ===`);
    lines.push('');

    for (const item of tierItems) {
      const color = TIER_D2R_COLOR_CODES[tierName];
      for (const code of item.codes) {
        lines.push(`ItemDisplay[${code}]: ${color}${item.name} ÿc4[${item.price} FG]`);
      }
    }
    lines.push('');
  }

  return lines.join('\n');
}

function getAutoTopThreshold(items: FilterItem[], preset: string): number | null {
  if (preset !== 'gg' && preset !== 'ggplus') return null;

  const priced = items
    .filter((item) => Number.isFinite(item.price) && item.price > 0)
    .sort((a, b) => b.price - a.price);

  if (priced.length === 0) return null;

  const percentile = preset === 'gg' ? 0.99 : 0.95;
  const floor = preset === 'gg' ? 500 : 100;
  const idx = Math.min(priced.length - 1, Math.max(0, Math.floor(priced.length * (1 - percentile))));
  const dynamic = priced[idx]?.price ?? floor;

  return Math.max(floor, dynamic);
}

// Validate and sanitize inputs
function validateInputs(preset: string, threshold: unknown): { preset: string; threshold: number } | string {
  if (!/^[a-zA-Z0-9_-]+$/.test(preset)) {
    return 'Invalid preset name. Only alphanumeric characters, dashes, and underscores are allowed.';
  }
  if (!VALID_PRESETS.includes(preset)) {
    return `Invalid preset. Must be one of: ${VALID_PRESETS.join(', ')}`;
  }
  const th = typeof threshold === 'number' ? threshold : parseFloat(String(threshold));
  if (isNaN(th) || th < 0 || th > 100000) {
    return 'Invalid threshold. Must be a number between 0 and 100000.';
  }
  return { preset, threshold: th };
}

// Build filter from Prisma DB — uses real prices from database
async function buildFilterFromDB(preset: string, threshold: number): Promise<string | null> {
  try {
    const items = await db.d2Item.findMany({
      where: {
        d2rCode: { not: null },
      },
      include: {
        priceEstimate: true,
      },
    });

    // Only items with prices and valid d2r codes
    const priced: FilterItem[] = items
      .filter(i => i.priceEstimate && i.d2rCode)
      .map(i => ({
        name: i.displayName,
        codes: [i.d2rCode!],
        price: i.priceEstimate!.priceFg,
      }));

    const autoThreshold = getAutoTopThreshold(priced, preset);
    const effectiveThreshold = autoThreshold ?? threshold;

    const hasAnyMatch = priced.some((item) => item.price >= effectiveThreshold);
    if (!hasAnyMatch) return null; // No matching items — fall through to hardcoded

    const sourceLabel = autoThreshold != null
      ? `database + auto-top threshold (${effectiveThreshold} FG)`
      : 'database';

    return generateFilterContent(preset, effectiveThreshold, sourceLabel, priced);
  } catch (error) {
    console.error('DB filter build failed:', error);
    return null;
  }
}

// Hardcoded fallback filter builder (works without DB)
function buildFilterDirect(preset: string, threshold: number): string {
  const items: FilterItem[] = [
    // Runes — direct item codes
    { name: 'Jah Rune', codes: ['r31'], price: 150 },
    { name: 'Ber Rune', codes: ['r30'], price: 140 },
    { name: 'Cham Rune', codes: ['r32'], price: 25 },
    { name: 'Sur Rune', codes: ['r29'], price: 35 },
    { name: 'Lo Rune', codes: ['r28'], price: 30 },
    { name: 'Ohm Rune', codes: ['r27'], price: 28 },
    { name: 'Vex Rune', codes: ['r26'], price: 22 },
    { name: 'Gul Rune', codes: ['r25'], price: 12 },
    { name: 'Ist Rune', codes: ['r24'], price: 18 },
    { name: 'Mal Rune', codes: ['r23'], price: 8 },
    { name: 'Um Rune', codes: ['r22'], price: 4 },

    // Uniques
    { name: 'Harlequin Crest', codes: ['uui'], price: 15 },
    { name: 'Arachnid Mesh', codes: ['umc'], price: 45 },
    { name: "Tyrael's Might", codes: ['uar'], price: 200 },
    { name: 'Hellfire Torch', codes: ['cm2'], price: 50 },
    { name: 'Annihilus', codes: ['cm3'], price: 80 },
    { name: "Mara's Kaleidoscope", codes: ['amu'], price: 25 },
    { name: "Griffon's Eye", codes: ['uap'], price: 85 },
    { name: 'Crown of Ages', codes: ['ucr'], price: 120 },

    // Runewords — filter by popular socketable base items
    { name: 'Enigma', codes: ['xtp', 'uea', 'utp'], price: 160 },
    { name: 'Infinity', codes: ['7vo', '7s8', '7pa'], price: 180 },
    { name: 'Grief', codes: ['7ls'], price: 35 },
    { name: 'Call to Arms', codes: ['7cr', '7gd'], price: 40 },
    { name: 'Spirit', codes: ['xrn', 'pa9', 'ush'], price: 5 },
  ];

  const autoThreshold = getAutoTopThreshold(items, preset);
  const effectiveThreshold = autoThreshold ?? threshold;
  const sourceLabel = autoThreshold != null
    ? `hardcoded fallback + auto-top threshold (${effectiveThreshold} FG)`
    : 'hardcoded fallback';

  return generateFilterContent(preset, effectiveThreshold, sourceLabel, items);
}

// Execute Python bridge with spawn (no shell)
function executePythonBridge(bridgePath: string, preset: string, threshold: number): Promise<string> {
  return new Promise<string>((resolve, reject) => {
    const args = [bridgePath, '--action', 'build_filter', '--preset', preset, '--threshold', String(threshold)];
    const proc = spawn('python3', args, { timeout: 30000 });
    let out = '';
    let err = '';
    proc.stdout.on('data', (d) => { out += d; });
    proc.stderr.on('data', (d) => { err += d; });
    proc.on('close', (code) => code === 0 ? resolve(out) : reject(new Error(err || `exit ${code}`)));
    proc.on('error', reject);
  });
}

// Helper to return filter as downloadable file
function filterResponse(content: string, preset: string) {
  return new NextResponse(content, {
    status: 200,
    headers: {
      'Content-Type': 'text/plain; charset=utf-8',
      'Content-Disposition': `attachment; filename="d2lut_${preset}_${Date.now()}.filter"`,
    },
  });
}

function isBridgeResult(value: unknown): value is BridgeResult {
  if (!value || typeof value !== 'object') return false;
  const candidate = value as Partial<BridgeResult>;
  return typeof candidate.success === 'boolean';
}

async function getFilterWithFallback(preset: string, threshold: number): Promise<string> {
  // Try Python bridge first for legacy presets.
  // GG/GG+ need local auto-top threshold logic, so they intentionally bypass bridge.
  const shouldUsePythonBridge = preset !== 'gg' && preset !== 'ggplus';
  if (shouldUsePythonBridge) {
    const bridgePath = path.join(process.cwd(), 'mini-services', 'bridge.py');
    if (!existsSync(bridgePath)) {
      console.warn(`Python bridge not found at ${bridgePath}; using built-in generator`);
    } else {
      try {
        const stdout = await executePythonBridge(bridgePath, preset, threshold);
        const parsed: unknown = JSON.parse(stdout.trim());
        if (!isBridgeResult(parsed)) {
          console.error('Python bridge returned invalid payload shape');
        } else if (parsed.success && typeof parsed.content === 'string') {
          return parsed.content;
        } else if (parsed.error) {
          console.error('Python bridge returned unsuccessful result:', parsed.error);
        } else {
          console.error('Python bridge returned unsuccessful result without error message');
        }
      } catch (error) {
        console.error('Python bridge failed, using built-in generator:', error);
      }
    }
  }

  const dbFilter = await buildFilterFromDB(preset, threshold);
  if (dbFilter) {
    return dbFilter;
  }

  return buildFilterDirect(preset, threshold);
}

export async function POST(request: NextRequest) {
  try {
    const body = await request.json();
    const rawPreset = body.preset ?? 'default';
    const rawThreshold = body.threshold ?? 0;

    const validation = validateInputs(rawPreset, rawThreshold);
    if (typeof validation === 'string') {
      return NextResponse.json({ error: validation }, { status: 400 });
    }

    const { preset, threshold } = validation;
    const filterContent = await getFilterWithFallback(preset, threshold);

    return filterResponse(filterContent, preset);
  } catch (error) {
    console.error('Error building filter:', error);
    return NextResponse.json({ error: 'Failed to build filter' }, { status: 500 });
  }
}

export async function GET(request: NextRequest) {
  try {
    const searchParams = request.nextUrl.searchParams;
    const rawPreset = searchParams.get('preset') || 'default';
    const rawThreshold = searchParams.get('threshold') || '0';

    const validation = validateInputs(rawPreset, rawThreshold);
    if (typeof validation === 'string') {
      return NextResponse.json({ error: validation }, { status: 400 });
    }

    const { preset, threshold } = validation;

    const filterContent = await getFilterWithFallback(preset, threshold);

    return filterResponse(filterContent, preset);
  } catch (error) {
    console.error('Error building filter:', error);
    return NextResponse.json({ error: 'Failed to build filter' }, { status: 500 });
  }
}
