import { NextRequest, NextResponse } from 'next/server';
import { spawn } from 'child_process';
import path from 'path';
import { getTier } from '@/lib/d2r-utils';

const VALID_PRESETS = ['default', 'roguecore', 'minimal', 'verbose'];

interface FilterItem {
  name: string;
  codes: string[];  // D2R item codes (base items for runewords)
  price: number;
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

// Filter builder that works without Python (fallback)
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

    // Uniques — unique item codes
    { name: 'Harlequin Crest', codes: ['uui'], price: 15 },
    { name: 'Arachnid Mesh', codes: ['umc'], price: 45 },
    { name: "Tyrael's Might", codes: ['uar'], price: 200 },
    { name: 'Hellfire Torch', codes: ['cm2'], price: 50 },
    { name: 'Annihilus', codes: ['cm3'], price: 80 },
    { name: "Mara's Kaleidoscope", codes: ['amu'], price: 25 },
    { name: "Griffon's Eye", codes: ['uap'], price: 85 },
    { name: 'Crown of Ages', codes: ['ucr'], price: 120 },
    { name: "Verdungo's Hearty Cord", codes: ['umh'], price: 15 },
    { name: "Thundergod's Vigor", codes: ['utb'], price: 8 },
    { name: 'Storm Shield', codes: ['uit'], price: 35 },
    { name: 'Windforce', codes: ['am6'], price: 180 },
    { name: 'Stone of Jordan', codes: ['rin'], price: 30 },
    { name: "Highlord's Wrath", codes: ['amuhl'], price: 18 },

    // Runewords — filter by popular socketable base items
    // Note: runewords sharing bases (e.g. Enigma/Fortitude both use xtp/uea/utp)
    // will generate multiple rules for the same code — this is intentional so
    // all valuable bases are highlighted regardless of intended runeword
    { name: 'Enigma', codes: ['xtp', 'uea', 'utp'], price: 160 },
    { name: 'Infinity', codes: ['7vo', '7s8', '7pa'], price: 180 },
    { name: 'Breath of the Dying', codes: ['7cr', '7gd', '7ws'], price: 85 },
    { name: 'Grief', codes: ['7cr', '7ls'], price: 35 },
    { name: 'Call to Arms', codes: ['7cr', '7gd'], price: 40 },
    { name: 'Fortitude', codes: ['xtp', 'uea', 'utp'], price: 45 },
    { name: 'Spirit', codes: ['xrn', 'pa9', 'ush'], price: 5 },
    { name: 'Beast', codes: ['7bt', '7ba'], price: 55 },
    { name: 'Last Wish', codes: ['7cr', '7ls'], price: 120 },
    { name: 'Faith', codes: ['6cb', '6lw', '8cb'], price: 95 },
    { name: 'Chains of Honor', codes: ['xtp', 'uea', 'utp'], price: 30 },
    { name: 'Heart of the Oak', codes: ['8cs', '8ws'], price: 15 },
  ];

  const colors: Record<string, string> = {
    GG: 'ÿc9', HIGH: 'ÿc7', MID: 'ÿc8', LOW: 'ÿc0', TRASH: 'ÿc5'
  };

  const filtered = items.filter(i => i.price >= threshold);
  const tierList = ['GG', 'HIGH', 'MID', 'LOW', 'TRASH'];

  const lines: string[] = [
    `# D2R Loot Filter - D2LUT`,
    `# Generated: ${new Date().toISOString()}`,
    `# Preset: ${preset}`,
    `# Threshold: ${threshold} FG`,
    `# Items: ${filtered.length}`,
    '',
  ];

  for (const tierName of tierList) {
    const tierItems = filtered.filter(i => getTier(i.price) === tierName);
    if (tierItems.length === 0) continue;

    lines.push(`# === ${tierName} TIER (${tierItems.length} items) ===`);
    lines.push('');

    for (const item of tierItems) {
      const color = colors[tierName];
      // Emit a rule for each base code
      for (const code of item.codes) {
        lines.push(`ItemDisplay[${code}]: ${color}${item.name} ÿc4[${item.price} FG]`);
      }
    }
    lines.push('');
  }

  return lines.join('\n');
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

    // Try Python bridge first
    const bridgePath = path.join(process.cwd(), 'mini-services', 'bridge.py');
    try {
      const stdout = await executePythonBridge(bridgePath, preset, threshold);
      const result = JSON.parse(stdout.trim());
      if (result.success) {
        return new NextResponse(result.content, {
          status: 200,
          headers: {
            'Content-Type': 'text/plain; charset=utf-8',
            'Content-Disposition': `attachment; filename="d2lut_${preset}_${Date.now()}.filter"`,
          },
        });
      }
    } catch {
      console.log('Python bridge not available, using built-in generator');
    }

    // Fallback to direct filter generation
    const filterContent = buildFilterDirect(preset, threshold);
    return new NextResponse(filterContent, {
      status: 200,
      headers: {
        'Content-Type': 'text/plain; charset=utf-8',
        'Content-Disposition': `attachment; filename="d2lut_${preset}_${Date.now()}.filter"`,
      },
    });
  } catch (error) {
    console.error('Error building filter:', error);
    return NextResponse.json({ error: 'Failed to build filter' }, { status: 500 });
  }
}

export async function GET(request: NextRequest) {
  const searchParams = request.nextUrl.searchParams;
  const rawPreset = searchParams.get('preset') || 'default';
  const rawThreshold = searchParams.get('threshold') || '0';

  const validation = validateInputs(rawPreset, rawThreshold);
  if (typeof validation === 'string') {
    return NextResponse.json({ error: validation }, { status: 400 });
  }

  const { preset, threshold } = validation;
  const filterContent = buildFilterDirect(preset, threshold);

  return new NextResponse(filterContent, {
    status: 200,
    headers: {
      'Content-Type': 'text/plain; charset=utf-8',
      'Content-Disposition': `attachment; filename="d2lut_${preset}_${Date.now()}.filter"`,
    },
  });
}

