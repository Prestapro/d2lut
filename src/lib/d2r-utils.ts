// Tier thresholds
export const TIER_THRESHOLDS: Record<string, [number, number]> = {
    GG: [500, 999999],
    HIGH: [100, 500],
    MID: [20, 100],
    LOW: [5, 20],
    TRASH: [0, 5],
};

export function getTier(price: number): string {
    for (const [tier, [low, high]] of Object.entries(TIER_THRESHOLDS)) {
        if (price >= low && price < high) {
            return tier;
        }
    }
    return 'TRASH';
}
