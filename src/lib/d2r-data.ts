/**
 * D2R Static Data
 * 
 * Item codes and display names for filter generation.
 * For tier logic, colors, and D2Item type, see d2r-utils.ts (single source of truth).
 */

// Re-export from d2r-utils for backward compatibility
export type { D2Item } from './d2r-utils';
export { TIER_COLORS, TIER_LABELS, TIER_THRESHOLDS, getTier } from './d2r-utils';

// D2R item codes for filter generation
export const D2R_CODES: Record<string, string | null> = {
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

  // Uniques
  'unique:shako': 'uui', 'unique:griffon': 'uap', 'unique:andariel': 'uhm',
  'unique:crownofages': 'ucr', 'unique:kira': 'uhl', 'unique:tyraels': 'uar',
  'unique:arachnid': 'umc', 'unique:verdungo': 'umh', 'unique:tgods': 'utb',
  'unique:wartraveler': 'uhb', 'unique:sandstorm': 'ulb', 'unique:goredriver': 'uhg',
  'unique:dracul': 'uvg', 'unique:stormshield': 'uit', 'unique:homunculus': 'unec',
  'unique:windforce': 'am6', 'unique:occulus': 'obf', 'unique:wizardspike': 'ob2',
  // Ambiguous generic base codes (ring/amulet) intentionally nulled to avoid
  // false-positive collisions in generated filters.
  'unique:soj': null, 'unique:bk': null, 'unique:raven': null,
  'unique:mara': null, 'unique:highlord': null, 'unique:catseye': null,
  'unique:anni': 'cm3', 'unique:torch': 'cm2', 'unique:gheed': 'cm1',
};

// Item display name mappings
export const DISPLAY_NAMES: Record<string, string> = {
  'rune:jah': 'Jah Rune', 'rune:ber': 'Ber Rune', 'rune:cham': 'Cham Rune',
  'rune:zod': 'Zod Rune', 'rune:sur': 'Sur Rune', 'rune:lo': 'Lo Rune',
  'rune:ohm': 'Ohm Rune', 'rune:vex': 'Vex Rune', 'rune:gul': 'Gul Rune',
  'rune:ist': 'Ist Rune', 'rune:mal': 'Mal Rune', 'rune:um': 'Um Rune',
  'unique:shako': 'Harlequin Crest', 'unique:griffon': "Griffon's Eye",
  'unique:andariel': "Andariel's Visage", 'unique:crownofages': 'Crown of Ages',
  'unique:tyraels': "Tyrael's Might", 'unique:arachnid': 'Arachnid Mesh',
  'unique:verdungo': "Verdungo's Hearty Cord", 'unique:tgods': "Thundergod's Vigor",
  'unique:wartraveler': 'War Traveler', 'unique:sandstorm': 'Sandstorm Trek',
  'unique:goredriver': 'Gore Rider', 'unique:dracul': "Dracul's Grasp",
  'unique:stormshield': 'Storm Shield', 'unique:homunculus': 'Homunculus',
  'unique:windforce': 'Windforce', 'unique:occulus': 'Occulus',
  'unique:wizardspike': 'Wizardspike', 'unique:soj': 'Stone of Jordan',
  'unique:bk': "Bul-Kathos' Wedding Band", 'unique:raven': 'Raven Frost',
  'unique:mara': "Mara's Kaleidoscope", 'unique:highlord': "Highlord's Wrath",
  'unique:catseye': "Cat's Eye", 'unique:anni': 'Annihilus',
  'unique:torch': 'Hellfire Torch', 'unique:gheed': "Gheed's Fortune",
  'runeword:enigma': 'Enigma', 'runeword:infinity': 'Infinity',
  'runeword:botd': 'Breath of the Dying', 'runeword:grief': 'Grief',
  'runeword:cta': 'Call to Arms', 'runeword:fortitude': 'Fortitude',
  'runeword:spirit': 'Spirit', 'runeword:beast': 'Beast',
  'runeword:lastwish': 'Last Wish', 'runeword:faith': 'Faith',
  'runeword:coh': 'Chains of Honor', 'runeword:hoto': 'Heart of the Oak',
};
