import { NextRequest, NextResponse } from 'next/server';
import { spawn } from 'child_process';
import path from 'path';

// Filter builder that works without Python (fallback)
function buildFilterDirect(preset: string, threshold: number): string {
  const items = [
    // Runes
    { name: 'Jah Rune', code: 'r31', price: 150, tier: 'GG' },
    { name: 'Ber Rune', code: 'r30', price: 140, tier: 'GG' },
    { name: 'Cham Rune', code: 'r32', price: 25, tier: 'MID' },
    { name: 'Sur Rune', code: 'r29', price: 35, tier: 'MID' },
    { name: 'Lo Rune', code: 'r28', price: 30, tier: 'MID' },
    { name: 'Ohm Rune', code: 'r27', price: 28, tier: 'MID' },
    { name: 'Vex Rune', code: 'r26', price: 22, tier: 'MID' },
    { name: 'Gul Rune', code: 'r25', price: 12, tier: 'LOW' },
    { name: 'Ist Rune', code: 'r24', price: 18, tier: 'MID' },
    { name: 'Mal Rune', code: 'r23', price: 8, tier: 'LOW' },
    { name: 'Um Rune', code: 'r22', price: 4, tier: 'TRASH' },
    
    // Uniques
    { name: 'Harlequin Crest', code: 'uui', price: 15, tier: 'MID' },
    { name: 'Arachnid Mesh', code: 'umc', price: 45, tier: 'MID' },
    { name: "Tyrael's Might", code: 'uar', price: 200, tier: 'GG' },
    { name: 'Hellfire Torch', code: 'cm2', price: 50, tier: 'HIGH' },
    { name: 'Annihilus', code: 'cm3', price: 80, tier: 'HIGH' },
    { name: "Mara's Kaleidoscope", code: 'amu', price: 25, tier: 'MID' },
    { name: "Griffon's Eye", code: 'uap', price: 85, tier: 'HIGH' },
    { name: 'Crown of Ages', code: 'ucr', price: 120, tier: 'HIGH' },
    { name: "Verdungo's Hearty Cord", code: 'umh', price: 15, tier: 'MID' },
    { name: "Thundergod's Vigor", code: 'utb', price: 8, tier: 'LOW' },
    { name: 'Storm Shield', code: 'uit', price: 35, tier: 'MID' },
    { name: 'Windforce', code: 'am6', price: 180, tier: 'GG' },
    { name: 'Stone of Jordan', code: 'rin', price: 30, tier: 'MID' },
    { name: "Highlord's Wrath", code: 'amu', price: 18, tier: 'MID' },
    
    // Runewords
    { name: 'Enigma', code: null, price: 160, tier: 'GG' },
    { name: 'Infinity', code: null, price: 180, tier: 'GG' },
    { name: 'Breath of the Dying', code: null, price: 85, tier: 'HIGH' },
    { name: 'Grief', code: null, price: 35, tier: 'MID' },
    { name: 'Call to Arms', code: null, price: 40, tier: 'MID' },
    { name: 'Fortitude', code: null, price: 45, tier: 'MID' },
    { name: 'Spirit', code: null, price: 5, tier: 'LOW' },
    { name: 'Beast', code: null, price: 55, tier: 'HIGH' },
    { name: 'Last Wish', code: null, price: 120, tier: 'HIGH' },
    { name: 'Faith', code: null, price: 95, tier: 'HIGH' },
    { name: 'Chains of Honor', code: null, price: 30, tier: 'MID' },
    { name: 'Heart of the Oak', code: null, price: 15, tier: 'MID' },
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
      if (item.code) {
        lines.push(`ItemDisplay[${item.code}]: ${color}${item.name} ÿc4[${item.price} FG]`);
      } else {
        // Runewords don't have direct codes - add comment
        lines.push(`# ${item.name} (${item.price} FG) - filter by base item`);
      }
    }
    lines.push('');
  }

  return lines.join('\n');
}

// Valid preset names (whitelist for security)
const VALID_PRESETS = ['default', 'roguecore', 'minimal', 'verbose'] as const;
type ValidPreset = typeof VALID_PRESETS[number];

// Validate and sanitize inputs
function validateInputs(preset: string, threshold: number): { valid: boolean; preset: ValidPreset; error?: string } {
  // Validate preset against whitelist
  if (!VALID_PRESETS.includes(preset as ValidPreset)) {
    return { valid: false, preset: 'default', error: `Invalid preset. Must be one of: ${VALID_PRESETS.join(', ')}` };
  }
  
  // Validate threshold is a reasonable number
  if (!Number.isFinite(threshold) || threshold < 0 || threshold > 1000000) {
    return { valid: false, preset: 'default', error: 'Invalid threshold. Must be between 0 and 1,000,000' };
  }
  
  return { valid: true, preset: preset as ValidPreset };
}

// Execute Python bridge safely using spawn with array arguments
function executePythonBridge(bridgePath: string, preset: ValidPreset, threshold: number): Promise<{ success: boolean; content?: string; error?: string }> {
  return new Promise((resolve) => {
    // Use spawn with array arguments to prevent command injection
    const args = [
      bridgePath,
      '--action', 'build_filter',
      '--preset', preset,  // Safe: validated against whitelist
      '--threshold', String(threshold),  // Safe: validated as number
    ];
    
    const proc = spawn('python3', args, {
      timeout: 30000,
      stdio: ['ignore', 'pipe', 'pipe'],
    });
    
    let stdout = '';
    let stderr = '';
    
    proc.stdout.on('data', (data) => {
      stdout += data.toString();
    });
    
    proc.stderr.on('data', (data) => {
      stderr += data.toString();
    });
    
    proc.on('close', (code) => {
      if (code === 0) {
        try {
          const result = JSON.parse(stdout);
          if (result.success) {
            resolve({ success: true, content: result.content });
          } else {
            resolve({ success: false, error: result.error || 'Python bridge returned failure' });
          }
        } catch {
          resolve({ success: false, error: 'Failed to parse Python bridge output' });
        }
      } else {
        resolve({ success: false, error: stderr || `Python exited with code ${code}` });
      }
    });
    
    proc.on('error', (err) => {
      resolve({ success: false, error: err.message });
    });
  });
}

export async function POST(request: NextRequest) {
  try {
    const body = await request.json();
    const rawPreset = String(body.preset || 'default');
    const rawThreshold = Number(body.threshold) || 0;
    
    // Validate inputs
    const validation = validateInputs(rawPreset, rawThreshold);
    if (!validation.valid) {
      return NextResponse.json(
        { error: validation.error },
        { status: 400 }
      );
    }
    
    const { preset, /* threshold is already validated as number */ } = validation;
    const threshold = rawThreshold;

    // Try Python bridge first
    const bridgePath = path.join(process.cwd(), 'mini-services', 'bridge.py');
    
    const pythonResult = await executePythonBridge(bridgePath, preset, threshold);
    
    if (pythonResult.success && pythonResult.content) {
      return new NextResponse(pythonResult.content, {
        status: 200,
        headers: {
          'Content-Type': 'text/plain; charset=utf-8',
          'Content-Disposition': `attachment; filename="d2lut_${preset}_${Date.now()}.filter"`,
        },
      });
    }
    
    // Log why Python bridge failed (for debugging)
    if (pythonResult.error) {
      console.log('Python bridge not available:', pythonResult.error);
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
    return NextResponse.json(
      { error: 'Failed to build filter' },
      { status: 500 }
    );
  }
}

export async function GET(request: NextRequest) {
  const searchParams = request.nextUrl.searchParams;
  const rawPreset = searchParams.get('preset') || 'default';
  const rawThreshold = parseFloat(searchParams.get('threshold') || '0');
  
  // Validate inputs
  const validation = validateInputs(rawPreset, rawThreshold);
  if (!validation.valid) {
    return NextResponse.json(
      { error: validation.error },
      { status: 400 }
    );
  }
  
  const { preset } = validation;
  const threshold = rawThreshold;

  // Use direct generation for GET requests
  const filterContent = buildFilterDirect(preset, threshold);

  return new NextResponse(filterContent, {
    status: 200,
    headers: {
      'Content-Type': 'text/plain; charset=utf-8',
      'Content-Disposition': `attachment; filename="d2lut_${preset}_${Date.now()}.filter"`,
    },
  });
}
