import { NextRequest, NextResponse } from 'next/server';
import { db } from '@/lib/db';
import { getTier, TIER_THRESHOLDS } from '@/lib/d2r-utils';

const VALID_PRESETS = ['default', 'ggplus', 'gg', 'roguecore', 'minimal', 'verbose'];
const VALID_MODES = ['auto', 'python', 'db', 'fallback'] as const;
type BuildMode = typeof VALID_MODES[number];

// ============================================================
// D2R LAYERED FILTER GENERATOR
// Архитектура: 4 слоя правил на каждую базу, в порядке приоритета
// ============================================================

// D2R color codes
const D2R_COLORS = {
  GG: 'ÿc9',  // Purple  — GG tier
  HIGH: 'ÿc7',  // Orange  — HIGH tier
  MID: 'ÿc8',  // Yellow  — MID tier
  LOW: 'ÿc0',  // White   — LOW tier
  TRASH: 'ÿc5',  // Gray    — TRASH tier
  SET: 'ÿc2',  // Green   — set items
  MAGIC: 'ÿc3',  // Blue    — magic items
  RARE: 'ÿc4',  // Gold    — rare items
  CRAFT: 'ÿcf',  // Crafted
  DIM: 'ÿc6',  // Dark    — suppressed/noise
} as const;

// Топ руневорды: name → основы + минимум сокетов + цена
// sockets = минимальное количество сокетов для этого руневорда
const RUNEWORD_BASES: {
  name: string;
  codes: string[];
  sockets: number;
  price: number;
  color?: string;
}[] = [
    // GG tier runewords
    { name: 'Enigma', codes: ['xtp', 'uea', 'utp'], sockets: 3, price: 160 },
    { name: 'Infinity', codes: ['7s8', '7vo', '7pa', '7b8'], sockets: 4, price: 180 },
    { name: 'BotD', codes: ['7wa', '7wh', '7bt', '7fb'], sockets: 6, price: 120 },
    { name: 'Last Wish', codes: ['7wa', '7wh', '7bt', '7fb'], sockets: 6, price: 90 },
    // HIGH tier
    { name: 'Grief', codes: ['7cr', '7ls', '7gy'], sockets: 5, price: 35 },
    { name: 'CTA', codes: ['7cr', '7ls', '7gy'], sockets: 5, price: 40 },
    { name: 'Fortitude', codes: ['xtp', 'uea', 'utp', '7wa'], sockets: 4, price: 50 },
    { name: 'CoH', codes: ['xtp', 'uea', 'utp'], sockets: 4, price: 60 },
    { name: 'Faith', codes: ['am6', '8lx', '8rx'], sockets: 4, price: 45 },
    { name: 'Beast', codes: ['7wa', '7wh'], sockets: 5, price: 30 },
    // MID tier
    { name: 'HotO', codes: ['obf', 'ob7', 'obb'], sockets: 4, price: 35 },
    { name: 'Spirit', codes: ['pa9', '7pa', 'ush', 'xrn'], sockets: 4, price: 5 },
    { name: 'Insight', codes: ['7s8', '7vo', '7pa'], sockets: 4, price: 8 },
    { name: 'Oath', codes: ['7cr', '7ls', '7gy', '7bt'], sockets: 4, price: 5 },
    { name: 'Exile', codes: ['upa', 'upb', 'upc'], sockets: 4, price: 15 },
    { name: 'Phoenix', codes: ['xtp', 'uea', 'utp'], sockets: 4, price: 25 },
    { name: 'Dragon', codes: ['xtp', 'uea', 'utp'], sockets: 3, price: 10 },
  ];

// Для каждой базы строим карту руневордов: code → лучший (дороже) руневорд
function buildRunewordMap(): Map<string, typeof RUNEWORD_BASES[0]> {
  const map = new Map<string, typeof RUNEWORD_BASES[0]>();
  for (const rw of RUNEWORD_BASES) {
    for (const code of rw.codes) {
      const existing = map.get(code);
      // Побеждает более дорогой руневорд
      if (!existing || rw.price > existing.price) {
        map.set(code, rw);
      }
    }
  }
  return map;
}

interface LayeredFilterItem {
  code: string;
  displayName: string;
  price: number | null;
  category: string;
}

function tierColor(price: number | null): string {
  if (price == null) return D2R_COLORS.DIM;
  const tier = getTier(price);
  return D2R_COLORS[tier as keyof typeof D2R_COLORS] ?? D2R_COLORS.DIM;
}

function priceTag(price: number | null): string {
  if (price == null || price <= 0) return '';
  return ` ÿc6[${Math.round(price)} FG]`;
}

// ============================================================
// CORE: генерация слоёв для одного item code
// ============================================================
function generateLayersForCode(
  code: string,
  item: LayeredFilterItem,
  runewordMap: Map<string, typeof RUNEWORD_BASES[0]>,
  threshold: number,
  opts: {
    showUnique: boolean;
    showSet: boolean;
    showRunewordBases: boolean;
    showNormalBases: boolean;
    suppressTrash: boolean;
  }
): string[] {
  const lines: string[] = [];
  const color = tierColor(item.price);
  const tag = priceTag(item.price);
  const isAboveThreshold = (item.price ?? 0) >= threshold;

  // === СЛОЙ 1: Unique items — используем %NAME% токен D2R ===
  if (opts.showUnique) {
    lines.push(`ItemDisplay[${code}&UNIQUE]: ${D2R_COLORS.GG}%NAME%${tag}`);
  }

  // === СЛОЙ 2: Set items ===
  if (opts.showSet) {
    lines.push(`ItemDisplay[${code}&SET]: ${D2R_COLORS.SET}%NAME%${tag}`);
  }

  // === СЛОЙ 3: Runeword base highlighting — по количеству сокетов ===
  if (opts.showRunewordBases) {
    const rw = runewordMap.get(code);
    if (rw && rw.price >= threshold) {
      const rwColor = tierColor(rw.price);
      lines.push(
        `ItemDisplay[${code}>${rw.sockets - 1}]: ${rwColor}${rw.name} BASE ÿc6[${rw.sockets}os]${priceTag(rw.price)}`
      );
    }
  }

  // === СЛОЙ 4: Обычная база ===
  if (opts.showNormalBases && isAboveThreshold) {
    if (opts.suppressTrash && item.price != null && item.price < 5) {
      lines.push(`ItemDisplay[${code}]: `);
    } else {
      lines.push(`ItemDisplay[${code}]: ${color}${item.displayName}${tag}`);
    }
  } else if (opts.showNormalBases && !isAboveThreshold) {
    lines.push(`ItemDisplay[${code}]: `);
  }

  return lines;
}

// ============================================================
// PRESET CONFIGS
// ============================================================
interface PresetConfig {
  showUnique: boolean;
  showSet: boolean;
  showRunewordBases: boolean;
  showNormalBases: boolean;
  suppressTrash: boolean;
  autoThreshold?: (items: LayeredFilterItem[]) => number;
}

const PRESET_CONFIGS: Record<string, PresetConfig> = {
  default: {
    showUnique: true,
    showSet: true,
    showRunewordBases: true,
    showNormalBases: true,
    suppressTrash: false,
  },
  ggplus: {
    showUnique: true,
    showSet: true,
    showRunewordBases: true,
    showNormalBases: true,
    suppressTrash: true,
    autoThreshold: (items) => {
      const prices = items.map(i => i.price ?? 0).filter(p => p > 0).sort((a, b) => b - a);
      return Math.max(100, prices[Math.floor(prices.length * 0.05)] ?? 100);
    },
  },
  gg: {
    showUnique: true,
    showSet: false,
    showRunewordBases: true,
    showNormalBases: false,
    suppressTrash: true,
    autoThreshold: () => 500,
  },
  roguecore: {
    showUnique: true,
    showSet: true,
    showRunewordBases: true,
    showNormalBases: true,
    suppressTrash: true,
  },
  minimal: {
    showUnique: true,
    showSet: false,
    showRunewordBases: false,
    showNormalBases: false,
    suppressTrash: true,
    autoThreshold: () => 100,
  },
  verbose: {
    showUnique: true,
    showSet: true,
    showRunewordBases: true,
    showNormalBases: true,
    suppressTrash: false,
  },
};

// ============================================================
// MAIN GENERATOR
// ============================================================
async function generateLayeredFilter(
  preset: string,
  threshold: number
): Promise<{ content: string, warnings: string[] } | null> {
  const config = PRESET_CONFIGS[preset] ?? PRESET_CONFIGS.default;
  const runewordMap = buildRunewordMap();

  const dbItems = await db.d2Item.findMany({
    where: { d2rCode: { not: null } },
    include: { priceEstimate: true },
  });

  const items: LayeredFilterItem[] = dbItems.map(i => ({
    code: i.d2rCode!,
    displayName: i.displayName || i.name,
    price: i.priceEstimate?.priceFg ?? null,
    category: i.category,
  }));

  if (items.length === 0) return null;

  const effectiveThreshold = config.autoThreshold
    ? config.autoThreshold(items)
    : threshold;

  const byCode = new Map<string, LayeredFilterItem>();
  for (const item of items) {
    const existing = byCode.get(item.code);
    const itemPrice = item.price ?? 0;
    const existingPrice = existing?.price ?? 0;
    if (!existing || itemPrice > existingPrice) {
      byCode.set(item.code, item);
    }
  }

  const header = [
    `# D2R Layered Loot Filter — D2LUT`,
    `# Generated: ${new Date().toISOString()}`,
    `# Preset: ${preset} | Threshold: ${effectiveThreshold} FG`,
    `# Architecture: 4-layer rules (UNIQUE > SET > RUNEWORD_BASE > NORMAL)`,
    `# %NAME% token: D2R resolves unique/set names natively — zero collisions`,
    ``,
    `# ============================================================`,
    `# HOW IT WORKS:`,
    `# Layer 1: [code&UNIQUE]  → %NAME% with tier color (no base collisions!)`,
    `# Layer 2: [code&SET]     → %NAME% with set color`,
    `# Layer 3: [code>N]       → RUNEWORD BASE highlight (N = min sockets)`,
    `# Layer 4: [code]         → normal base display or suppress`,
    `# ============================================================`,
    ``,
  ].join('\n');

  const tierOrder = ['GG', 'HIGH', 'MID', 'LOW', 'TRASH', 'UNKNOWN'];
  const tierGroups = new Map<string, string[]>();
  for (const tier of tierOrder) tierGroups.set(tier, []);

  for (const [code, item] of byCode) {
    const tier = item.price != null ? getTier(item.price) : 'UNKNOWN';
    const layerLines = generateLayersForCode(
      code, item, runewordMap, effectiveThreshold, config
    );
    if (layerLines.length > 0) {
      const group = tierGroups.get(tier) ?? tierGroups.get('UNKNOWN')!;
      group.push(`# --- ${item.displayName} (${item.price ?? '?'} FG) ---`);
      group.push(...layerLines);
      group.push('');
    }
  }

  const sections: string[] = [header];
  for (const tier of tierOrder) {
    const lines = tierGroups.get(tier) ?? [];
    if (lines.length === 0) continue;
    const [low, high] = TIER_THRESHOLDS[tier] ?? [0, 0];
    sections.push(`# ${'='.repeat(60)}`);
    sections.push(`# ${tier} TIER (${low}–${high === Infinity ? '∞' : high} FG) — ${lines.filter(l => l.startsWith('ItemDisplay')).length} rules`);
    sections.push(`# ${'='.repeat(60)}`);
    sections.push('');
    sections.push(...lines);
  }

  return { content: sections.join('\n'), warnings: [] };
}

// Fallback logic, rarely hit unless DB is entirely empty
function buildFilterDirect(preset: string, threshold: number): { content: string; warnings: string[] } {
  // Keeping fallback extremely minimal now since layered is so robust
  const lines = [
    `# D2R Loot Filter - D2LUT FALLBACK`,
    `# Preset: ${preset}`,
    `ItemDisplay[r31]: ÿc9Jah Rune ÿc4[150 FG]`,
    `ItemDisplay[r30]: ÿc9Ber Rune ÿc4[140 FG]`,
    `ItemDisplay[uui&UNIQUE]: ÿc9%NAME% ÿc4[15 FG]`,
    `ItemDisplay[xtp>2]: ÿc9Enigma BASE ÿc6[3os]`,
    `ItemDisplay[uui]: ÿc5Shako`,
  ];
  return { content: lines.join('\n'), warnings: ['database unreachable, using minimal fallback'] };
}

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

function filterResponse(content: string, preset: string) {
  return new NextResponse(content, {
    status: 200,
    headers: {
      'Content-Type': 'text/plain; charset=utf-8',
      'Content-Disposition': `attachment; filename="d2lut_${preset}_${Date.now()}.filter"`,
    },
  });
}

function parseRequestedMode(rawMode: unknown): BuildMode | null {
  const mode = typeof rawMode === 'string' ? rawMode : '';
  if (!mode) return 'auto';
  return (VALID_MODES as readonly string[]).includes(mode) ? (mode as BuildMode) : null;
}

function withBuildHeaders(response: NextResponse, buildResult: { source: string, mode: string, warnings: string[] }): NextResponse {
  response.headers.set('X-D2LUT-Filter-Source', buildResult.source);
  response.headers.set('X-D2LUT-Filter-Mode', buildResult.mode);
  if (buildResult.warnings.length > 0) {
    response.headers.set('X-D2LUT-Filter-Warnings', String(buildResult.warnings.length));
    console.warn('Filter build warnings:', buildResult.warnings);
  }
  return response;
}

export async function POST(request: NextRequest) {
  try {
    const body = await request.json();
    const rawPreset = body.preset ?? 'default';
    const rawThreshold = body.threshold ?? 0;
    const mode = parseRequestedMode(body.mode);
    if (!mode) return NextResponse.json({ error: `Invalid mode` }, { status: 400 });

    const validation = validateInputs(rawPreset, rawThreshold);
    if (typeof validation === 'string') return NextResponse.json({ error: validation }, { status: 400 });
    const { preset, threshold } = validation;

    const dbFilter = await generateLayeredFilter(preset, threshold);
    if (dbFilter) {
      return withBuildHeaders(filterResponse(dbFilter.content, preset), { source: 'db', mode, warnings: dbFilter.warnings });
    }

    const fallback = buildFilterDirect(preset, threshold);
    return withBuildHeaders(filterResponse(fallback.content, preset), { source: 'fallback', mode, warnings: fallback.warnings });
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
    const mode = parseRequestedMode(searchParams.get('mode'));
    if (!mode) return NextResponse.json({ error: `Invalid mode` }, { status: 400 });

    const validation = validateInputs(rawPreset, rawThreshold);
    if (typeof validation === 'string') return NextResponse.json({ error: validation }, { status: 400 });
    const { preset, threshold } = validation;

    const dbFilter = await generateLayeredFilter(preset, threshold);
    if (dbFilter) {
      return withBuildHeaders(filterResponse(dbFilter.content, preset), { source: 'db', mode, warnings: dbFilter.warnings });
    }

    const fallback = buildFilterDirect(preset, threshold);
    return withBuildHeaders(filterResponse(fallback.content, preset), { source: 'fallback', mode, warnings: fallback.warnings });
  } catch (error) {
    console.error('Error building filter:', error);
    return NextResponse.json({ error: 'Failed to build filter' }, { status: 500 });
  }
}
