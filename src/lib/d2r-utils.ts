// === Single Source of Truth for Tier Logic ===

// D2Item type — used across UI and API
export interface D2Item {
    variantKey: string;
    name: string;
    displayName: string;
    category: string;
    d2rCode: string | null;
    subCategory?: string;
    priceFg?: number;
    tier?: string;
    confidence?: string | null;
    nObservations?: number;
    priceChange?: number;
}

// Tier thresholds: [min, max) — min inclusive, max exclusive
export const TIER_THRESHOLDS: Record<string, [number, number]> = {
    GG: [500, Infinity],
    HIGH: [100, 500],
    MID: [20, 100],
    LOW: [5, 20],
    TRASH: [0, 5],
};

// Tier colors for UI
export const TIER_COLORS: Record<string, string> = {
    GG: '#c082dc',      // Purple
    HIGH: '#ff8000',    // Orange
    MID: '#ffff00',     // Yellow
    LOW: '#ffffff',     // White
    TRASH: '#808080',   // Gray
};

// Tier labels for UI legend — derived from thresholds
export const TIER_LABELS: Record<string, string> = {
    GG: '500+ FG',
    HIGH: '100-499 FG',
    MID: '20-99 FG',
    LOW: '5-19 FG',
    TRASH: '<5 FG',
};

export function getTier(price: number): string {
    for (const [tier, [low, high]] of Object.entries(TIER_THRESHOLDS)) {
        if (price >= low && price < high) {
            return tier;
        }
    }
    return 'TRASH';
}
