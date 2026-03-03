// Tier thresholds: [min, max) — min inclusive, max exclusive
// Matches frontend legend: GG 500+, HIGH 100-499, MID 20-99, LOW 5-19, TRASH <5
export const TIER_THRESHOLDS: Record<string, [number, number]> = {
    GG: [500, Infinity],
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
