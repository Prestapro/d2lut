import { NextRequest, NextResponse } from 'next/server';
import { spawn } from 'child_process';
import path from 'path';
import { db } from '@/lib/db';

// Valid forum IDs (whitelist)
const VALID_FORUM_IDS = [271, 272, 273, 274] as const; // D2R Ladder, Non-Ladder, etc.

interface ScrapedObservation {
  variantKey: string;
  priceFg: number;
  confidence: number;
  signalKind: string;
  source: string;
  sourceId: string;
  author: string;
  observedAt: string;
}

// Execute Python bridge safely
function executePythonBridge(action: string, args: Record<string, string | number | boolean>): Promise<{ success: boolean; data?: unknown; error?: string }> {
  return new Promise((resolve) => {
    const bridgePath = path.join(process.cwd(), 'mini-services', 'bridge.py');
    
    const spawnArgs = ['--action', action];
    for (const [key, value] of Object.entries(args)) {
      const argKey = key.replace(/([A-Z])/g, '-$1').toLowerCase();
      if (typeof value === 'boolean') {
        if (value) spawnArgs.push(`--${argKey}`);
      } else {
        spawnArgs.push(`--${argKey}`, String(value));
      }
    }
    
    const proc = spawn('python3', [bridgePath, ...spawnArgs], {
      timeout: 120000, // 2 minutes for scraping
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
          resolve({ success: true, data: result });
        } catch {
          resolve({ success: false, error: 'Failed to parse Python output' });
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

// Sync observations to database
async function syncObservationsToDb(observations: ScrapedObservation[]): Promise<{ synced: number; errors: string[] }> {
  let synced = 0;
  const errors: string[] = [];
  
  for (const obs of observations) {
    try {
      // Find existing item
      let item = await db.d2Item.findFirst({
        where: { variantKey: obs.variantKey },
      });
      
      if (!item) {
        // Create item if it doesn't exist
        const parts = obs.variantKey.split(':');
        const category = parts[0] || 'misc';
        const name = parts[parts.length - 1] || obs.variantKey;
        
        item = await db.d2Item.create({
          data: {
            variantKey: obs.variantKey,
            name: name.toLowerCase(),
            displayName: name.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase()),
            category,
          },
        });
      }
      
      // Check for existing price estimate
      const existingEstimate = await db.priceEstimate.findFirst({
        where: { itemId: item.id },
      });
      
      if (existingEstimate) {
        // Update existing estimate with weighted average
        const newN = existingEstimate.nObservations + 1;
        const newPrice = (existingEstimate.priceFg * existingEstimate.nObservations + obs.priceFg) / newN;
        
        await db.priceEstimate.update({
          where: { id: existingEstimate.id },
          data: {
            priceFg: newPrice,
            nObservations: newN,
            confidence: obs.confidence > 0.8 ? 'high' : obs.confidence > 0.6 ? 'medium' : 'low',
            lastUpdated: new Date(),
          },
        });
      } else {
        // Create new estimate
        await db.priceEstimate.create({
          data: {
            itemId: item.id,
            priceFg: obs.priceFg,
            confidence: obs.confidence > 0.8 ? 'high' : obs.confidence > 0.6 ? 'medium' : 'low',
            nObservations: 1,
          },
        });
      }
      
      // Add observation record
      await db.priceObservation.create({
        data: {
          itemId: item.id,
          priceFg: obs.priceFg,
          confidence: obs.confidence,
          signalKind: obs.signalKind,
          source: obs.source,
          sourceId: obs.sourceId,
          author: obs.author,
          observedAt: new Date(obs.observedAt),
        },
      });
      
      synced++;
    } catch (error) {
      errors.push(`Failed to sync ${obs.variantKey}: ${error}`);
    }
  }
  
  return { synced, errors };
}

export async function POST(request: NextRequest) {
  try {
    const body = await request.json();
    const { forumId = 271, maxItems = 50, syncToDb = true } = body;
    
    // Validate forum ID
    if (!VALID_FORUM_IDS.includes(forumId as typeof VALID_FORUM_IDS[number])) {
      return NextResponse.json(
        { error: 'Invalid forum ID. Must be one of: ' + VALID_FORUM_IDS.join(', ') },
        { status: 400 }
      );
    }
    
    // Validate maxItems
    const safeMaxItems = Math.min(Math.max(1, maxItems), 200);
    
    // Execute Python scraper
    const result = await executePythonBridge('scrape_prices', {
      forumId,
      maxItems: safeMaxItems,
    });
    
    if (!result.success) {
      return NextResponse.json(
        { error: result.error || 'Scraping failed' },
        { status: 500 }
      );
    }
    
    const data = result.data as { observations?: ScrapedObservation[]; total?: number; errors?: string[] };
    const observations = data.observations || [];
    
    // Sync to database if requested
    let syncResult = { synced: 0, errors: [] as string[] };
    if (syncToDb && observations.length > 0) {
      syncResult = await syncObservationsToDb(observations);
    }
    
    return NextResponse.json({
      success: true,
      scraped: observations.length,
      synced: syncResult.synced,
      observations: observations.slice(0, 10), // Return first 10 as preview
      errors: [...(data.errors || []), ...syncResult.errors].slice(0, 5),
      message: `Scraped ${observations.length} price observations, synced ${syncResult.synced} to database`,
    });
    
  } catch (error) {
    console.error('Error scraping prices:', error);
    return NextResponse.json(
      { error: 'Failed to scrape prices' },
      { status: 500 }
    );
  }
}

export async function GET(request: NextRequest) {
  const searchParams = request.nextUrl.searchParams;
  const forumId = parseInt(searchParams.get('forumId') || '271');
  const maxItems = Math.min(50, parseInt(searchParams.get('maxItems') || '20'));
  
  // Validate forum ID
  if (!VALID_FORUM_IDS.includes(forumId as typeof VALID_FORUM_IDS[number])) {
    return NextResponse.json(
      { error: 'Invalid forum ID' },
      { status: 400 }
    );
  }
  
  // Execute Python scraper (no sync for GET)
  const result = await executePythonBridge('scrape_prices', {
    forumId,
    maxItems,
  });
  
  if (!result.success) {
    return NextResponse.json(
      { error: result.error || 'Scraping failed' },
      { status: 500 }
    );
  }
  
  return NextResponse.json(result.data);
}
