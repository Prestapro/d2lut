import { NextRequest, NextResponse } from 'next/server';
import { spawn } from 'child_process';
import path from 'path';

const VALID_PRESETS = ['default', 'roguecore', 'minimal', 'verbose'];

interface FilterItem {
  name: string;
  codes: string[];  // D2R item codes (base items for runewords)
  price: number;
  tier: string;
}

// Validate and sanitize inputs
function validateInputs(preset: string, threshold: unknown): { preset: string; threshold: number } | string {
  if (!/^[a-zA-Z0-9_-]+$/.test(preset)) {
    return 'Invalid preset name. Only alphanumeric characters, dashes, and underscores are allowed.';
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
    { name: 'Jah Rune', codes: ['r31'], price: 150, tier: 'GG' },
    { name: 'Ber Rune', codes: ['r30'], price: 140, tier: 'GG' },
    { name: 'Cham Rune', codes: ['r32'], price: 25, tier: 'MID' },
    { name: 'Sur Rune', codes: ['r29'], price: 35, tier: 'MID' },
    { name: 'Lo Rune', codes: ['r28'], price: 30, tier: 'MID' },
    { name: 'Ohm Rune', codes: ['r27'], price: 28, tier: 'MID' },
    { name: 'Vex Rune', codes: ['r26'], price: 22, tier: 'MID' },
    { name: 'Gul Rune', codes: ['r25'], price: 12, tier: 'LOW' },
    { name: 'Ist Rune', codes: ['r24'], price: 18, tier: 'MID' },
    { name: 'Mal Rune', codes: ['r23'], price: 8, tier: 'LOW' },
    { name: 'Um Rune', codes: ['r22'], price: 4, tier: 'TRASH' },

    // Uniques — unique item codes
    { name: 'Harlequin Crest', codes: ['uui'], price: 15, tier: 'MID' },
    { name: 'Arachnid Mesh', codes: ['umc'], price: 45, tier: 'MID' },
    { name: "Tyrael's Might", codes: ['uar'], price: 200, tier: 'GG' },
    { name: 'Hellfire Torch', codes: ['cm2'], price: 50, tier: 'HIGH' },
    { name: 'Annihilus', codes: ['cm3'], price: 80, tier: 'HIGH' },
    { name: "Mara's Kaleidoscope", codes: ['amu'], price: 25, tier: 'MID' },
    { name: "Griffon's Eye", codes: ['uap'], price: 85, tier: 'HIGH' },
    { name: 'Crown of Ages', codes: ['ucr'], price: 120, tier: 'HIGH' },
    { name: "Verdungo's Hearty Cord", codes: ['umh'], price: 15, tier: 'MID' },
    { name: "Thundergod's Vigor", codes: ['utb'], price: 8, tier: 'LOW' },
    { name: 'Storm Shield', codes: ['uit'], price: 35, tier: 'MID' },
    { name: 'Windforce', codes: ['am6'], price: 180, tier: 'GG' },
    { name: 'Stone of Jordan', codes: ['rin'], price: 30, tier: 'MID' },
    { name: "Highlord's Wrath", codes: ['amuhl'], price: 18, tier: 'MID' },

    // Runewords — filter by popular base items (socketable)
    { name: 'Enigma', codes: ['xtp', 'uea', 'utp'], price: 160, tier: 'GG' },
    { name: 'Infinity', codes: ['7vo', '7s8', '7pa'], price: 180, tier: 'GG' },
    { name: 'Breath of the Dying', codes: ['7cr', '7gd', '7ws'], price: 85, tier: 'HIGH' },
    { name: 'Grief', codes: ['7cr', '7ls'], price: 35, tier: 'MID' },
    { name: 'Call to Arms', codes: ['7cr', '7gd'], price: 40, tier: 'MID' },
    { name: 'Fortitude', codes: ['xtp', 'uea', 'utp'], price: 45, tier: 'MID' },
    { name: 'Spirit', codes: ['xrn', 'pa9', 'ush'], price: 5, tier: 'LOW' },
    { name: 'Beast', codes: ['7bt', '7ba'], price: 55, tier: 'HIGH' },
    { name: 'Last Wish', codes: ['7cr', '7ls'], price: 120, tier: 'HIGH' },
    { name: 'Faith', codes: ['6cb', '6lw', '8cb'], price: 95, tier: 'HIGH' },
    { name: 'Chains of Honor', codes: ['xtp', 'uea', 'utp'], price: 30, tier: 'MID' },
    { name: 'Heart of the Oak', codes: ['8cs', '8ws'], price: 15, tier: 'MID' },
  ];

  const colors: Record<string, string> = {
    GG: 'ÿc9', HIGH: 'ÿc7', MID: 'ÿc8', LOW: 'ÿc0', TRASH: 'ÿc5'
  };

  const filtered = items.filter(i => i.price >= threshold);
  const tiers = ['GG', 'HIGH', 'MID', 'LOW', 'TRASH'];

  const lines: string[] = [
    `# D2R Loot Filter - D2LUT`,
    `# Generated: ${new Date().toISOString()}`,
    `# Preset: ${preset}`,
    `# Threshold: ${threshold} FG`,
    `# Items: ${filtered.length}`,
    '',
  ];

  for (const tier of tiers) {
    const tierItems = filtered.filter(i => i.tier === tier);
    if (tierItems.length === 0) continue;

    lines.push(`# === ${tier} TIER (${tierItems.length} items) ===`);
    lines.push('');

    for (const item of tierItems) {
      const color = colors[tier];
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

