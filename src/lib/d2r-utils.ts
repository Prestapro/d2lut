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
    priceLastUpdated?: string | null;
    tier?: string;
    confidence?: string | null;
    nObservations?: number;
    priceChange?: number;
    topicUrls?: string[];
    topicSearchUrl?: string;
}

// Tier definitions in explicit descending order (highest first)
// Using ordered array to guarantee iteration order across all JS engines
const TIER_LIST: [string, number, number][] = [
    ['GG', 500, Infinity],
    ['HIGH', 100, 500],
    ['MID', 20, 100],
    ['LOW', 5, 20],
    ['TRASH', 0, 5],
];

// Record form for backward compatibility (lookup by tier name)
export const TIER_THRESHOLDS: Record<string, [number, number]> = Object.fromEntries(
    TIER_LIST.map(([name, low, high]) => [name, [low, high] as [number, number]])
);

// Tier colors for UI
export const TIER_COLORS: Record<string, string> = {
    GG: '#c082dc',      // Purple
    HIGH: '#ff8000',    // Orange
    MID: '#ffff00',     // Yellow
    LOW: '#ffffff',     // White
    TRASH: '#808080',   // Gray
};

// Tier color codes for D2R item labels
export const TIER_D2R_COLOR_CODES: Record<string, string> = {
    GG: 'ÿc9',
    HIGH: 'ÿc7',
    MID: 'ÿc8',
    LOW: 'ÿc0',
    TRASH: 'ÿc5',
};

// Tier labels for UI legend
export const TIER_LABELS: Record<string, string> = {
    GG: '500+ FG',
    HIGH: '100-499 FG',
    MID: '20-99 FG',
    LOW: '5-19 FG',
    TRASH: '<5 FG',
};

export function getTier(price: number): string {
    for (const [name, low, high] of TIER_LIST) {
        if (price >= low && price < high) {
            return name;
        }
    }
    return 'TRASH';
}
