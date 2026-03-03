/**
 * D2R Data Loader
 * 
 * Loads D2R item data from the Python package's JSON files.
 * Provides sample price data for demonstration.
 */

import fs from 'fs';
import path from 'path';

// Types
export interface D2Item {
  variantKey: string;
  name: string;
  displayName: string;
  category: string;
  d2rCode: string | null;
  subCategory?: string;
  priceFg?: number;
  tier?: string;
  confidence?: string;
  nObservations?: number;
  priceChange?: number;
}

export interface CategoryInfo {
  id: string;
  name: string;
  count: number;
  icon: string;
}

// Tier colors for UI
export const TIER_COLORS: Record<string, string> = {
  GG: '#c082dc',      // Purple - 500+ FG
  HIGH: '#ff8000',    // Orange - 100-500 FG
  MID: '#ffff00',     // Yellow - 20-100 FG
  LOW: '#ffffff',     // White - 5-20 FG
  TRASH: '#808080',   // Gray - <5 FG
};

// Tier thresholds (FG)
export const TIER_THRESHOLDS: Record<string, [number, number]> = {
  GG: [500, Infinity],
  HIGH: [100, 500],
  MID: [20, 100],
  LOW: [5, 20],
  TRASH: [0, 5],
};

/**
 * Determine tier from price
 */
export function getTier(price: number): string {
  for (const [tier, [low, high]] of Object.entries(TIER_THRESHOLDS)) {
    if (price >= low && price < high) {
      return tier;
    }
  }
  return 'TRASH';
}

/**
 * Sample price data for demonstration
 * In production, this would come from the database
 */
const SAMPLE_PRICES: Record<string, { price: number; confidence: string; obs: number }> = {
  // High Runes
  'rune:jah': { price: 150, confidence: 'high', obs: 245 },
  'rune:ber': { price: 140, confidence: 'high', obs: 312 },
  'rune:cham': { price: 25, confidence: 'medium', obs: 89 },
  'rune:zod': { price: 20, confidence: 'medium', obs: 67 },
  'rune:sur': { price: 35, confidence: 'high', obs: 156 },
  'rune:lo': { price: 30, confidence: 'high', obs: 178 },
  'rune:ohm': { price: 28, confidence: 'high', obs: 145 },
  'rune:vex': { price: 22, confidence: 'medium', obs: 98 },
  'rune:gul': { price: 12, confidence: 'high', obs: 234 },
  'rune:ist': { price: 18, confidence: 'high', obs: 267 },
  'rune:mal': { price: 8, confidence: 'high', obs: 345 },
  'rune:um': { price: 4, confidence: 'high', obs: 456 },
  'rune:ko': { price: 1, confidence: 'medium', obs: 123 },
  'rune:lem': { price: 1, confidence: 'medium', obs: 134 },
  'rune:pul': { price: 2, confidence: 'high', obs: 234 },
  'rune:hel': { price: 0.5, confidence: 'low', obs: 56 },

  // Uniques - High Value
  'unique:shako': { price: 15, confidence: 'high', obs: 567 },
  'unique:arachnid': { price: 45, confidence: 'high', obs: 234 },
  'unique:tyraels': { price: 200, confidence: 'medium', obs: 45 },
  'unique:torch': { price: 50, confidence: 'high', obs: 678 },
  'unique:anni': { price: 80, confidence: 'high', obs: 456 },
  'unique:mara': { price: 25, confidence: 'high', obs: 345 },
  'unique:griffon': { price: 85, confidence: 'high', obs: 123 },
  'unique:crownofages': { price: 120, confidence: 'medium', obs: 67 },
  'unique:andariel': { price: 12, confidence: 'high', obs: 234 },
  'unique:verdungo': { price: 15, confidence: 'high', obs: 345 },
  'unique:tgods': { price: 8, confidence: 'high', obs: 234 },
  'unique:soj': { price: 30, confidence: 'high', obs: 567 },
  'unique:highlord': { price: 18, confidence: 'high', obs: 345 },
  'unique:catseye': { price: 12, confidence: 'high', obs: 234 },
  'unique:bk': { price: 25, confidence: 'high', obs: 189 },
  'unique:raven': { price: 8, confidence: 'high', obs: 456 },
  'unique:dracul': { price: 20, confidence: 'high', obs: 234 },
  'unique:wartraveler': { price: 15, confidence: 'high', obs: 345 },
  'unique:sandstorm': { price: 12, confidence: 'high', obs: 289 },
  'unique:goredriver': { price: 10, confidence: 'high', obs: 234 },
  'unique:stormshield': { price: 35, confidence: 'high', obs: 123 },
  'unique:homunculus': { price: 15, confidence: 'high', obs: 167 },
  'unique:occulus': { price: 8, confidence: 'high', obs: 234 },
  'unique:wizardspike': { price: 5, confidence: 'high', obs: 345 },
  'unique:windforce': { price: 180, confidence: 'medium', obs: 56 },
  'unique:deathcleaver': { price: 95, confidence: 'medium', obs: 34 },
  'unique:azurewrath': { price: 45, confidence: 'medium', obs: 67 },
  'unique:grandfather': { price: 25, confidence: 'medium', obs: 89 },
  'unique:leoric': { price: 12, confidence: 'high', obs: 234 },

  // Runewords
  'runeword:enigma': { price: 160, confidence: 'high', obs: 345 },
  'runeword:infinity': { price: 180, confidence: 'high', obs: 234 },
  'runeword:botd': { price: 85, confidence: 'high', obs: 156 },
  'runeword:grief': { price: 35, confidence: 'high', obs: 456 },
  'runeword:cta': { price: 40, confidence: 'high', obs: 567 },
  'runeword:fortitude': { price: 45, confidence: 'high', obs: 345 },
  'runeword:spirit': { price: 5, confidence: 'high', obs: 789 },
  'runeword:beast': { price: 55, confidence: 'high', obs: 234 },
  'runeword:lastwish': { price: 120, confidence: 'medium', obs: 67 },
  'runeword:faith': { price: 95, confidence: 'high', obs: 123 },
  'runeword:doom': { price: 35, confidence: 'medium', obs: 89 },
  'runeword:coh': { price: 30, confidence: 'high', obs: 345 },
  'runeword:exile': { price: 75, confidence: 'high', obs: 123 },
  'runeword:phoenix': { price: 65, confidence: 'high', obs: 156 },
  'runeword:insight': { price: 3, confidence: 'high', obs: 567 },
  'runeword:hoto': { price: 15, confidence: 'high', obs: 234 },
  'runeword:oath': { price: 12, confidence: 'high', obs: 167 },
  'runeword:destruction': { price: 45, confidence: 'medium', obs: 45 },
  'runeword:ebotd': { price: 120, confidence: 'high', obs: 89 },
  'runeword:edeath': { price: 45, confidence: 'medium', obs: 56 },

  // Set Items
  'set:talrasha': { price: 25, confidence: 'high', obs: 234 },
  'set:arreat': { price: 20, confidence: 'high', obs: 189 },
  'set:trang': { price: 15, confidence: 'high', obs: 145 },
  'set:ik': { price: 30, confidence: 'high', obs: 167 },
  'set:layingofhands': { price: 12, confidence: 'high', obs: 234 },
  'set:guillaume': { price: 8, confidence: 'high', obs: 178 },

  // Bases
  'base:monarch': { price: 5, confidence: 'high', obs: 567 },
  'base:archon': { price: 8, confidence: 'high', obs: 234 },
  'base:dusk': { price: 6, confidence: 'high', obs: 189 },
  'base:sacredarmor': { price: 15, confidence: 'medium', obs: 67 },
  'base:thresher': { price: 10, confidence: 'high', obs: 156 },
  'base:giantthresher': { price: 12, confidence: 'high', obs: 123 },
  'base:colossusvoulge': { price: 8, confidence: 'high', obs: 145 },
  'base:berserkeraxe': { price: 12, confidence: 'high', obs: 234 },
  'base:phaseblade': { price: 5, confidence: 'high', obs: 345 },

  // Facets
  'facet:fire': { price: 25, confidence: 'high', obs: 189 },
  'facet:cold': { price: 30, confidence: 'high', obs: 156 },
  'facet:light': { price: 28, confidence: 'high', obs: 167 },
  'facet:poison': { price: 15, confidence: 'high', obs: 123 },

  // Misc
  'misc:token': { price: 5, confidence: 'high', obs: 678 },
  'unique:gheed': { price: 8, confidence: 'high', obs: 234 },
};

// D2R item codes for filter generation
const D2R_CODES: Record<string, string> = {
  // Runes (r01-r33)
  'rune:el': 'r01', 'rune:eld': 'r02', 'rune:tir': 'r03', 'rune:nef': 'r04',
  'rune:eth': 'r05', 'rune:ith': 'r06', 'rune:tal': 'r07', 'rune:ral': 'r08',
  'rune:ort': 'r09', 'rune:thul': 'r10', 'rune:amn': 'r11', 'rune:sol': 'r12',
  'rune:shael': 'r13', 'rune:dol': 'r14', 'rune:hel': 'r15', 'rune:io': 'r16',
  'rune:lum': 'r17', 'rune:ko': 'r18', 'rune:fal': 'r19', 'rune:lem': 'r20',
  'rune:pul': 'r21', 'rune:um': 'r22', 'rune:mal': 'r23', 'rune:ist': 'r24',
  'rune:gul': 'r25', 'rune:vex': 'r26', 'rune:ohm': 'r27', 'rune:lo': 'r28',
  'rune:sur': 'r29', 'rune:ber': 'r30', 'rune:jah': 'r31', 'rune:cham': 'r32',
  'rune:zod': 'r33',

  // Uniques - using correct D2R item codes
  // Helms
  'unique:shako': 'uui',       // Harlequin Crest (Unique Helm)
  'unique:griffon': 'uap',     // Griffon's Eye (Unique Diadem)
  'unique:andariel': 'uhm',    // Andariel's Visage (Unique Demonhead)
  'unique:crownofages': 'ucr', // Crown of Ages (Unique Corona)
  'unique:kira': 'uhl',        // Kira's Guardian (Unique Tiara)
  
  // Armor
  'unique:tyraels': 'uar',     // Tyrael's Might (Unique Sacred Armor)
  'unique:arkaine': 'upl',     // Arkaine's Valor (Unique Balrog Skin)
  'unique:skullder': 'ula',    // Skullder's Ire (Unique Hydra Edge)
  'unique:skinofvipermagi': 'ule', // Skin of the Vipermagi (Unique Serpentskin)
  'unique:quehagan': 'utu',    // Que-Hegan's Wisdom (Unique Dusk Shroud)
  
  // Belts
  'unique:arachnid': 'umc',    // Arachnid Mesh (Unique Spiderweb Sash)
  'unique:verdungo': 'umh',    // Verdungo's Hearty Cord (Unique Mithril Coil)
  'unique:tgods': 'utb',       // Thundergod's Vigor (Unique War Belt)
  
  // Boots
  'unique:wartraveler': 'uhb', // War Traveler (Unique Battle Boots)
  'unique:sandstorm': 'ulb',   // Sandstorm Trek (Unique Scarabshell)
  'unique:waterwalk': 'uab',   // Waterwalk (Unique Sharkskin)
  'unique:goredriver': 'uhg',  // Gore Rider (Unique War Boots)
  
  // Gloves - all use appropriate glove base codes
  'unique:dracul': 'ulg',      // Dracul's Grasp (Unique Vampirebone)
  'unique:souldrain': 'uhg',   // Soul Drain (Unique Heavy Bracers)
  'unique:chanceguards': 'ulg', // Chance Guards (Unique Chain Gloves)
  'unique:magefist': 'ulg',    // Magefist (Unique Light Gauntlets)
  
  // Shields
  'unique:stormshield': 'uit', // Storm Shield (Unique Monarch)
  'unique:homunculus': 'unec', // Homunculus (Unique Hierophant Trophy)
  'unique:medusa': 'uhd',      // Medusa's Gaze (Unique Aegis)
  'unique:tiamat': 'uas',      // Tiamat's Rebuke (Unique Dragon Scale)
  'unique:moser': 'upk',       // Moser's Blessed Circle (Unique Round Shield)
  
  // Weapons - Bows
  'unique:windforce': 'am6',   // Windforce (Unique Hydra Bow) - corrected from 'ama'
  'unique:eaglehorn': 'ab8',   // Eaglehorn (Unique Crusader Bow)
  'unique:buriza': 'xvl',      // Buriza-Do Kyanon (Unique Ballista) - corrected from 'ama'
  
  // Weapons - Orbs/Staves
  'unique:occulus': 'obf',     // Occulus (Unique Swirling Crystal)
  'unique:wizardspike': 'ob2', // Wizardspike (Unique Bone Knife)
  'unique:eschuta': 'ob5',     // Eschuta's Temper (Unique Eldritch Orb)
  'unique:death': 'uac',       // Death's Fathom (Unique Dimensional Shard)
  'unique:leoric': 'wn5',      // Arm of King Leoric (Unique Tomb Wand) - corrected
  
  // Jewelry
  'unique:soj': 'rin',         // Stone of Jordan (Unique Ring)
  'unique:bk': 'rin',          // Bul-Kathos' Wedding Band (Unique Ring)
  'unique:raven': 'rin',       // Raven Frost (Unique Ring)
  'unique:mara': 'amu',        // Mara's Kaleidoscope (Unique Amulet)
  'unique:highlord': 'amu',    // Highlord's Wrath (Unique Amulet)
  'unique:catseye': 'amu',     // The Cat's Eye (Unique Amulet)
  'unique:atma': 'amu',        // Atma's Scarab (Unique Amulet)
  
  // Charms
  'unique:anni': 'cm3',        // Annihilus (Unique Small Charm)
  'unique:torch': 'cm2',       // Hellfire Torch (Unique Large Charm)
  'unique:gheed': 'cm1',       // Gheed's Fortune (Unique Grand Charm)

  // Runewords - NOTE: D2R loot filters cannot filter runewords directly
  // These codes are for display only - actual filtering uses base item codes
  // Users should filter by the base item (e.g., 'Monarch' for Spirit shield)
  'runeword:enigma': null,    // No direct code - filter by base armor
  'runeword:infinity': null,  // No direct code - filter by base polearm
  'runeword:botd': null,      // No direct code - filter by base weapon
  'runeword:grief': null,     // No direct code - filter by base sword/axe
  'runeword:cta': null,       // No direct code - filter by base weapon
  'runeword:fortitude': null, // No direct code - filter by base armor
  'runeword:spirit': null,    // No direct code - filter by monarch/sword
  'runeword:beast': null,     // No direct code
  'runeword:lastwish': null,  // No direct code
  'runeword:faith': null,     // No direct code
  'runeword:doom': null,      // No direct code
  'runeword:coh': null,       // No direct code
  'runeword:exile': null,     // No direct code
  'runeword:phoenix': null,   // No direct code
  'runeword:insight': null,   // No direct code
  'runeword:hoto': null,      // No direct code
  'runeword:oath': null,      // No direct code

  // Set Items - use set item codes (prefixed with set code)
  // These are simplified - actual set items have specific codes
  'set:talrasha': 'set',      // Tal Rasha's Adjudication (set amulet)
  'set:arreat': 'set',        // Arreat's Face (set helm)
  'set:trang': 'set',         // Trang-Oul's items
  'set:ik': 'set',            // Immortal King's items

  // Bases
  'base:monarch': 'mon', 'base:archon': 'ar', 'base:dusk': 'ds',
  'base:sacredarmor': 'sa', 'base:thresher': 'th', 'base:giantthresher': 'gt',
  'base:colossusvoulge': 'cv', 'base:berserkeraxe': 'ba', 'base:phaseblade': 'pb',
};

// Item name mappings
const DISPLAY_NAMES: Record<string, string> = {
  // Runes
  'rune:jah': 'Jah Rune', 'rune:ber': 'Ber Rune', 'rune:cham': 'Cham Rune',
  'rune:zod': 'Zod Rune', 'rune:sur': 'Sur Rune', 'rune:lo': 'Lo Rune',
  'rune:ohm': 'Ohm Rune', 'rune:vex': 'Vex Rune', 'rune:gul': 'Gul Rune',
  'rune:ist': 'Ist Rune', 'rune:mal': 'Mal Rune', 'rune:um': 'Um Rune',
  'rune:ko': 'Ko Rune', 'rune:lem': 'Lem Rune', 'rune:pul': 'Pul Rune',
  'rune:hel': 'Hel Rune',

  // Uniques
  'unique:shako': 'Harlequin Crest', 'unique:griffon': "Griffon's Eye",
  'unique:andariel': "Andariel's Visage", 'unique:crownofages': 'Crown of Ages',
  'unique:kira': "Kira's Guardian", 'unique:tyraels': "Tyrael's Might",
  'unique:arkaine': "Arkaine's Valor", 'unique:skullder': "Skullder's Ire",
  'unique:skinofvipermagi': 'Skin of the Vipermagi', 'unique:quehagan': "Que-Hegan's Wisdom",
  'unique:arachnid': 'Arachnid Mesh', 'unique:verdungo': "Verdungo's Hearty Cord",
  'unique:tgods': "Thundergod's Vigor", 'unique:wartraveler': 'War Traveler',
  'unique:sandstorm': 'Sandstorm Trek', 'unique:waterwalk': 'Waterwalk',
  'unique:goredriver': 'Gore Rider', 'unique:dracul': "Dracul's Grasp",
  'unique:souldrain': 'Soul Drain', 'unique:chanceguards': 'Chance Guards',
  'unique:magefist': 'Magefist', 'unique:stormshield': 'Storm Shield',
  'unique:homunculus': 'Homunculus', 'unique:medusa': "Medusa's Gaze",
  'unique:tiamat': "Tiamat's Rebuke", 'unique:moser': "Moser's Blessed Circle",
  'unique:windforce': 'Windforce', 'unique:eaglehorn': 'Eaglehorn',
  'unique:buriza': 'Buriza-Do Kyanon', 'unique:occulus': 'Occulus',
  'unique:wizardspike': 'Wizardspike', 'unique:eschuta': "Eschuta's Temper",
  'unique:death': "Death's Fathom", 'unique:leoric': 'Arm of King Leoric',
  'unique:soj': 'Stone of Jordan', 'unique:bk': "Bul-Kathos' Wedding Band",
  'unique:raven': 'Raven Frost', 'unique:mara': "Mara's Kaleidoscope",
  'unique:highlord': "Highlord's Wrath", 'unique:catseye': "Cat's Eye",
  'unique:atma': "Atma's Scarab", 'unique:anni': 'Annihilus',
  'unique:torch': 'Hellfire Torch', 'unique:gheed': "Gheed's Fortune",

  // Runewords
  'runeword:enigma': 'Enigma', 'runeword:infinity': 'Infinity',
  'runeword:botd': 'Breath of the Dying', 'runeword:grief': 'Grief',
  'runeword:cta': 'Call to Arms', 'runeword:fortitude': 'Fortitude',
  'runeword:spirit': 'Spirit', 'runeword:beast': 'Beast',
  'runeword:lastwish': 'Last Wish', 'runeword:faith': 'Faith',
  'runeword:doom': 'Doom', 'runeword:coh': 'Chains of Honor',
  'runeword:exile': 'Exile', 'runeword:phoenix': 'Phoenix',
  'runeword:insight': 'Insight', 'runeword:hoto': 'Heart of the Oak',
  'runeword:oath': 'Oath',

  // Sets
  'set:talrasha': "Tal Rasha's Set", 'set:arreat': "Arreat's Face",
  'set:trang': "Trang-Oul's Set", 'set:ik': "Immortal King's Set",

  // Bases
  'base:monarch': 'Monarch Shield', 'base:archon': 'Archon Plate',
  'base:dusk': 'Dusk Shroud', 'base:sacredarmor': 'Sacred Armor',
  'base:thresher': 'Thresher', 'base:giantthresher': 'Giant Thresher',
  'base:colossusvoulge': 'Colossus Voulge', 'base:berserkeraxe': 'Berserker Axe',
  'base:phaseblade': 'Phase Blade',

  // Facets
  'facet:fire': 'Fire Facet', 'facet:cold': 'Cold Facet',
  'facet:light': 'Lightning Facet', 'facet:poison': 'Poison Facet',

  // Misc
  'misc:token': 'Token of Absolution',
};

/**
 * Get all items with their prices
 */
export function getAllItems(): D2Item[] {
  const items: D2Item[] = [];

  for (const [variantKey, priceData] of Object.entries(SAMPLE_PRICES)) {
    const [category, name] = variantKey.split(':');
    const price = priceData.price;

    items.push({
      variantKey,
      name,
      displayName: DISPLAY_NAMES[variantKey] || name.charAt(0).toUpperCase() + name.slice(1),
      category,
      d2rCode: D2R_CODES[variantKey] || null,
      priceFg: price,
      tier: getTier(price),
      confidence: priceData.confidence,
      nObservations: priceData.obs,
      // Deterministic price change based on variantKey (avoids hydration mismatch)
      priceChange: ((variantKey.split('').reduce((a, b) => a + b.charCodeAt(0), 0) % 20) - 10),
    });
  }

  return items.sort((a, b) => (b.priceFg || 0) - (a.priceFg || 0));
}

/**
 * Get items by category
 */
export function getItemsByCategory(category: string): D2Item[] {
  return getAllItems().filter(item => item.category === category);
}

/**
 * Get category statistics
 */
export function getCategories(): CategoryInfo[] {
  const items = getAllItems();
  const categoryMap = new Map<string, number>();

  for (const item of items) {
    const count = categoryMap.get(item.category) || 0;
    categoryMap.set(item.category, count + 1);
  }

  const categoryNames: Record<string, string> = {
    rune: 'Runes',
    unique: 'Uniques',
    runeword: 'Runewords',
    set: 'Set Items',
    base: 'Bases',
    facet: 'Facets',
    misc: 'Miscellaneous',
    craft: 'Crafted',
  };

  const categoryIcons: Record<string, string> = {
    rune: '💎',
    unique: '⭐',
    runeword: '🔮',
    set: '📦',
    base: '🛡️',
    facet: '🌈',
    misc: '🎯',
    craft: '🔨',
  };

  return Array.from(categoryMap.entries())
    .map(([id, count]) => ({
      id,
      name: categoryNames[id] || id,
      count,
      icon: categoryIcons[id] || '📋',
    }))
    .sort((a, b) => b.count - a.count);
}

/**
 * Get dashboard statistics
 */
export function getStats() {
  const items = getAllItems();

  const totalItems = items.length;
  const avgPrice = items.reduce((sum, item) => sum + (item.priceFg || 0), 0) / totalItems;
  const topItem = items[0];
  const ggItems = items.filter(i => i.tier === 'GG').length;
  const highItems = items.filter(i => i.tier === 'HIGH').length;

  return {
    totalItems,
    avgPrice: Math.round(avgPrice * 10) / 10,
    topItem,
    ggItems,
    highItems,
    lastUpdated: new Date().toISOString(),
  };
}

/**
 * Get price history for an item (mock data)
 */
export function getPriceHistory(variantKey: string) {
  const item = getAllItems().find(i => i.variantKey === variantKey);
  if (!item) return null;

  const basePrice = item.priceFg || 50;
  const history = [];
  const now = Date.now();

  // Generate 30 days of mock price history
  for (let i = 30; i >= 0; i--) {
    const variance = (Math.random() - 0.5) * basePrice * 0.2;
    const price = Math.max(1, basePrice + variance);
    history.push({
      date: new Date(now - i * 24 * 60 * 60 * 1000).toISOString().split('T')[0],
      price: Math.round(price * 10) / 10,
    });
  }

  return {
    item,
    history,
    minPrice: Math.min(...history.map(h => h.price)),
    maxPrice: Math.max(...history.map(h => h.price)),
    avgPrice: history.reduce((sum, h) => sum + h.price, 0) / history.length,
  };
}

/**
 * Build filter file content
 */
export function buildFilter(preset: string, threshold: number = 0): string {
  const items = getAllItems();
  const filteredItems = items.filter(i => (i.priceFg || 0) >= threshold);

  const lines: string[] = [
    `# D2R Loot Filter - D2LUT`,
    `# Generated: ${new Date().toISOString()}`,
    `# Preset: ${preset}`,
    `# Threshold: ${threshold} FG`,
    `# Items: ${filteredItems.length}`,
    '',
  ];

  // Group by tier
  const tiers = ['GG', 'HIGH', 'MID', 'LOW', 'TRASH'];

  for (const tier of tiers) {
    const tierItems = filteredItems.filter(i => i.tier === tier);
    if (tierItems.length === 0) continue;

    lines.push(`# === ${tier} TIER (${tierItems.length} items) ===`);
    lines.push('');

    for (const item of tierItems) {
      const color = TIER_COLORS[tier];
      const code = item.d2rCode || item.name;
      const price = item.priceFg || 0;
      lines.push(`ItemDisplay[${code}]: ${item.displayName} [${price} FG]`);
    }
    lines.push('');
  }

  return lines.join('\n');
}
