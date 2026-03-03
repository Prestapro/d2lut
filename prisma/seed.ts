import { PrismaClient } from '@prisma/client';

const prisma = new PrismaClient();

// D2R item data with correct codes
const ITEMS = [
  // Runes (r01-r33)
  { variantKey: 'rune:jah', name: 'jah', displayName: 'Jah Rune', category: 'rune', d2rCode: 'r31' },
  { variantKey: 'rune:ber', name: 'ber', displayName: 'Ber Rune', category: 'rune', d2rCode: 'r30' },
  { variantKey: 'rune:cham', name: 'cham', displayName: 'Cham Rune', category: 'rune', d2rCode: 'r32' },
  { variantKey: 'rune:zod', name: 'zod', displayName: 'Zod Rune', category: 'rune', d2rCode: 'r33' },
  { variantKey: 'rune:sur', name: 'sur', displayName: 'Sur Rune', category: 'rune', d2rCode: 'r29' },
  { variantKey: 'rune:lo', name: 'lo', displayName: 'Lo Rune', category: 'rune', d2rCode: 'r28' },
  { variantKey: 'rune:ohm', name: 'ohm', displayName: 'Ohm Rune', category: 'rune', d2rCode: 'r27' },
  { variantKey: 'rune:vex', name: 'vex', displayName: 'Vex Rune', category: 'rune', d2rCode: 'r26' },
  { variantKey: 'rune:gul', name: 'gul', displayName: 'Gul Rune', category: 'rune', d2rCode: 'r25' },
  { variantKey: 'rune:ist', name: 'ist', displayName: 'Ist Rune', category: 'rune', d2rCode: 'r24' },
  { variantKey: 'rune:mal', name: 'mal', displayName: 'Mal Rune', category: 'rune', d2rCode: 'r23' },
  { variantKey: 'rune:um', name: 'um', displayName: 'Um Rune', category: 'rune', d2rCode: 'r22' },
  { variantKey: 'rune:pul', name: 'pul', displayName: 'Pul Rune', category: 'rune', d2rCode: 'r21' },
  { variantKey: 'rune:lem', name: 'lem', displayName: 'Lem Rune', category: 'rune', d2rCode: 'r20' },
  { variantKey: 'rune:ko', name: 'ko', displayName: 'Ko Rune', category: 'rune', d2rCode: 'r18' },
  { variantKey: 'rune:hel', name: 'hel', displayName: 'Hel Rune', category: 'rune', d2rCode: 'r15' },

  // Uniques - Helms
  { variantKey: 'unique:shako', name: 'shako', displayName: 'Harlequin Crest', category: 'unique', d2rCode: 'uui', subCategory: 'helm' },
  { variantKey: 'unique:griffon', name: 'griffon', displayName: "Griffon's Eye", category: 'unique', d2rCode: 'uap', subCategory: 'helm' },
  { variantKey: 'unique:andariel', name: 'andariel', displayName: "Andariel's Visage", category: 'unique', d2rCode: 'uhm', subCategory: 'helm' },
  { variantKey: 'unique:crownofages', name: 'crownofages', displayName: 'Crown of Ages', category: 'unique', d2rCode: 'ucr', subCategory: 'helm' },
  { variantKey: 'unique:kira', name: 'kira', displayName: "Kira's Guardian", category: 'unique', d2rCode: 'uhl', subCategory: 'helm' },

  // Uniques - Armor
  { variantKey: 'unique:tyraels', name: 'tyraels', displayName: "Tyrael's Might", category: 'unique', d2rCode: 'uar', subCategory: 'armor' },
  { variantKey: 'unique:arkaine', name: 'arkaine', displayName: "Arkaine's Valor", category: 'unique', d2rCode: 'upl', subCategory: 'armor' },
  { variantKey: 'unique:skullder', name: 'skullder', displayName: "Skullder's Ire", category: 'unique', d2rCode: 'ula', subCategory: 'armor' },
  { variantKey: 'unique:skinofvipermagi', name: 'skinofvipermagi', displayName: 'Skin of the Vipermagi', category: 'unique', d2rCode: 'ule', subCategory: 'armor' },
  { variantKey: 'unique:quehagan', name: 'quehagan', displayName: "Que-Hegan's Wisdom", category: 'unique', d2rCode: 'utu', subCategory: 'armor' },

  // Uniques - Belts
  { variantKey: 'unique:arachnid', name: 'arachnid', displayName: 'Arachnid Mesh', category: 'unique', d2rCode: 'umc', subCategory: 'belt' },
  { variantKey: 'unique:verdungo', name: 'verdungo', displayName: "Verdungo's Hearty Cord", category: 'unique', d2rCode: 'umh', subCategory: 'belt' },
  { variantKey: 'unique:tgods', name: 'tgods', displayName: "Thundergod's Vigor", category: 'unique', d2rCode: 'utb', subCategory: 'belt' },

  // Uniques - Boots
  { variantKey: 'unique:wartraveler', name: 'wartraveler', displayName: 'War Traveler', category: 'unique', d2rCode: 'uhb', subCategory: 'boots' },
  { variantKey: 'unique:sandstorm', name: 'sandstorm', displayName: 'Sandstorm Trek', category: 'unique', d2rCode: 'ulb', subCategory: 'boots' },
  { variantKey: 'unique:waterwalk', name: 'waterwalk', displayName: 'Waterwalk', category: 'unique', d2rCode: 'uab', subCategory: 'boots' },
  { variantKey: 'unique:goredriver', name: 'goredriver', displayName: 'Gore Rider', category: 'unique', d2rCode: 'uhg', subCategory: 'boots' },

  // Uniques - Gloves
  { variantKey: 'unique:dracul', name: 'dracul', displayName: "Dracul's Grasp", category: 'unique', d2rCode: 'uvg', subCategory: 'gloves' },
  { variantKey: 'unique:chanceguards', name: 'chanceguards', displayName: 'Chance Guards', category: 'unique', d2rCode: 'xtg', subCategory: 'gloves' },
  { variantKey: 'unique:magefist', name: 'magefist', displayName: 'Magefist', category: 'unique', d2rCode: 'xlg', subCategory: 'gloves' },

  // Uniques - Shields
  { variantKey: 'unique:stormshield', name: 'stormshield', displayName: 'Storm Shield', category: 'unique', d2rCode: 'uit', subCategory: 'shield' },
  { variantKey: 'unique:homunculus', name: 'homunculus', displayName: 'Homunculus', category: 'unique', d2rCode: 'unec', subCategory: 'shield' },
  { variantKey: 'unique:medusa', name: 'medusa', displayName: "Medusa's Gaze", category: 'unique', d2rCode: 'uhd', subCategory: 'shield' },

  // Uniques - Weapons
  { variantKey: 'unique:windforce', name: 'windforce', displayName: 'Windforce', category: 'unique', d2rCode: 'am6', subCategory: 'weapon' },
  { variantKey: 'unique:buriza', name: 'buriza', displayName: 'Buriza-Do Kyanon', category: 'unique', d2rCode: 'xvl', subCategory: 'weapon' },
  { variantKey: 'unique:occulus', name: 'occulus', displayName: 'Occulus', category: 'unique', d2rCode: 'obf', subCategory: 'weapon' },
  { variantKey: 'unique:wizardspike', name: 'wizardspike', displayName: 'Wizardspike', category: 'unique', d2rCode: 'ob2', subCategory: 'weapon' },
  { variantKey: 'unique:leoric', name: 'leoric', displayName: 'Arm of King Leoric', category: 'unique', d2rCode: 'wn5', subCategory: 'weapon' },

  // Uniques - Jewelry
  { variantKey: 'unique:soj', name: 'soj', displayName: 'Stone of Jordan', category: 'unique', d2rCode: 'rin', subCategory: 'ring' },
  { variantKey: 'unique:bk', name: 'bk', displayName: "Bul-Kathos' Wedding Band", category: 'unique', d2rCode: 'rin', subCategory: 'ring' },
  { variantKey: 'unique:raven', name: 'raven', displayName: 'Raven Frost', category: 'unique', d2rCode: 'rin', subCategory: 'ring' },
  { variantKey: 'unique:mara', name: 'mara', displayName: "Mara's Kaleidoscope", category: 'unique', d2rCode: 'amu', subCategory: 'amulet' },
  { variantKey: 'unique:highlord', name: 'highlord', displayName: "Highlord's Wrath", category: 'unique', d2rCode: 'amu', subCategory: 'amulet' },
  { variantKey: 'unique:catseye', name: 'catseye', displayName: "The Cat's Eye", category: 'unique', d2rCode: 'amu', subCategory: 'amulet' },

  // Uniques - Charms
  { variantKey: 'unique:anni', name: 'anni', displayName: 'Annihilus', category: 'unique', d2rCode: 'cm3', subCategory: 'charm' },
  { variantKey: 'unique:torch', name: 'torch', displayName: 'Hellfire Torch', category: 'unique', d2rCode: 'cm2', subCategory: 'charm' },
  { variantKey: 'unique:gheed', name: 'gheed', displayName: "Gheed's Fortune", category: 'unique', d2rCode: 'cm1', subCategory: 'charm' },

  // Runewords - NOTE: No direct D2R codes, filter by base item
  { variantKey: 'runeword:enigma', name: 'enigma', displayName: 'Enigma', category: 'runeword', d2rCode: null, subCategory: 'armor' },
  { variantKey: 'runeword:infinity', name: 'infinity', displayName: 'Infinity', category: 'runeword', d2rCode: null, subCategory: 'weapon' },
  { variantKey: 'runeword:botd', name: 'botd', displayName: 'Breath of the Dying', category: 'runeword', d2rCode: null, subCategory: 'weapon' },
  { variantKey: 'runeword:grief', name: 'grief', displayName: 'Grief', category: 'runeword', d2rCode: null, subCategory: 'weapon' },
  { variantKey: 'runeword:cta', name: 'cta', displayName: 'Call to Arms', category: 'runeword', d2rCode: null, subCategory: 'weapon' },
  { variantKey: 'runeword:fortitude', name: 'fortitude', displayName: 'Fortitude', category: 'runeword', d2rCode: null, subCategory: 'armor' },
  { variantKey: 'runeword:spirit', name: 'spirit', displayName: 'Spirit', category: 'runeword', d2rCode: null, subCategory: 'shield' },
  { variantKey: 'runeword:beast', name: 'beast', displayName: 'Beast', category: 'runeword', d2rCode: null, subCategory: 'weapon' },
  { variantKey: 'runeword:lastwish', name: 'lastwish', displayName: 'Last Wish', category: 'runeword', d2rCode: null, subCategory: 'weapon' },
  { variantKey: 'runeword:faith', name: 'faith', displayName: 'Faith', category: 'runeword', d2rCode: null, subCategory: 'weapon' },
  { variantKey: 'runeword:doom', name: 'doom', displayName: 'Doom', category: 'runeword', d2rCode: null, subCategory: 'weapon' },
  { variantKey: 'runeword:coh', name: 'coh', displayName: 'Chains of Honor', category: 'runeword', d2rCode: null, subCategory: 'armor' },
  { variantKey: 'runeword:exile', name: 'exile', displayName: 'Exile', category: 'runeword', d2rCode: null, subCategory: 'shield' },
  { variantKey: 'runeword:phoenix', name: 'phoenix', displayName: 'Phoenix', category: 'runeword', d2rCode: null, subCategory: 'shield' },
  { variantKey: 'runeword:insight', name: 'insight', displayName: 'Insight', category: 'runeword', d2rCode: null, subCategory: 'weapon' },
  { variantKey: 'runeword:hoto', name: 'hoto', displayName: 'Heart of the Oak', category: 'runeword', d2rCode: null, subCategory: 'weapon' },

  // Set Items
  { variantKey: 'set:talrasha', name: 'talrasha', displayName: "Tal Rasha's Set", category: 'set', d2rCode: 'amu' },
  { variantKey: 'set:arreat', name: 'arreat', displayName: "Arreat's Face", category: 'set', d2rCode: 'ci3' },
  { variantKey: 'set:trang', name: 'trang', displayName: "Trang-Oul's Set", category: 'set', d2rCode: 'uld' },
  { variantKey: 'set:ik', name: 'ik', displayName: "Immortal King's Set", category: 'set', d2rCode: 'uls' },
  { variantKey: 'set:layingofhands', name: 'layingofhands', displayName: 'Laying of Hands', category: 'set', d2rCode: 'xtg' },
  { variantKey: 'set:guillaume', name: 'guillaume', displayName: "Guillaume's Face", category: 'set', d2rCode: 'xhm' },

  // Bases
  { variantKey: 'base:monarch', name: 'monarch', displayName: 'Monarch Shield', category: 'base', d2rCode: 'mon', subCategory: 'shield' },
  { variantKey: 'base:archon', name: 'archon', displayName: 'Archon Plate', category: 'base', d2rCode: 'ar', subCategory: 'armor' },
  { variantKey: 'base:dusk', name: 'dusk', displayName: 'Dusk Shroud', category: 'base', d2rCode: 'ds', subCategory: 'armor' },
  { variantKey: 'base:sacredarmor', name: 'sacredarmor', displayName: 'Sacred Armor', category: 'base', d2rCode: 'sa', subCategory: 'armor' },
  { variantKey: 'base:thresher', name: 'thresher', displayName: 'Thresher', category: 'base', d2rCode: 'th', subCategory: 'weapon' },
  { variantKey: 'base:giantthresher', name: 'giantthresher', displayName: 'Giant Thresher', category: 'base', d2rCode: 'gt', subCategory: 'weapon' },
  { variantKey: 'base:colossusvoulge', name: 'colossusvoulge', displayName: 'Colossus Voulge', category: 'base', d2rCode: 'cv', subCategory: 'weapon' },
  { variantKey: 'base:berserkeraxe', name: 'berserkeraxe', displayName: 'Berserker Axe', category: 'base', d2rCode: 'ba', subCategory: 'weapon' },
  { variantKey: 'base:phaseblade', name: 'phaseblade', displayName: 'Phase Blade', category: 'base', d2rCode: 'pb', subCategory: 'weapon' },

  // Facets
  { variantKey: 'facet:fire', name: 'fire', displayName: 'Fire Facet', category: 'facet', d2rCode: 'jew' },
  { variantKey: 'facet:cold', name: 'cold', displayName: 'Cold Facet', category: 'facet', d2rCode: 'jew' },
  { variantKey: 'facet:light', name: 'light', displayName: 'Lightning Facet', category: 'facet', d2rCode: 'jew' },
  { variantKey: 'facet:poison', name: 'poison', displayName: 'Poison Facet', category: 'facet', d2rCode: 'jew' },

  // Misc
  { variantKey: 'misc:token', name: 'token', displayName: 'Token of Absolution', category: 'misc', d2rCode: 'toa' },
];

// Price data
const PRICES: Record<string, { price: number; confidence: string }> = {
  'rune:jah': { price: 150, confidence: 'high' },
  'rune:ber': { price: 140, confidence: 'high' },
  'rune:cham': { price: 25, confidence: 'medium' },
  'rune:zod': { price: 20, confidence: 'medium' },
  'rune:sur': { price: 35, confidence: 'high' },
  'rune:lo': { price: 30, confidence: 'high' },
  'rune:ohm': { price: 28, confidence: 'high' },
  'rune:vex': { price: 22, confidence: 'medium' },
  'rune:gul': { price: 12, confidence: 'high' },
  'rune:ist': { price: 18, confidence: 'high' },
  'rune:mal': { price: 8, confidence: 'high' },
  'rune:um': { price: 4, confidence: 'high' },
  'rune:pul': { price: 2, confidence: 'high' },
  'rune:lem': { price: 1, confidence: 'medium' },
  'rune:ko': { price: 1, confidence: 'medium' },
  'rune:hel': { price: 0.5, confidence: 'low' },
  'unique:shako': { price: 15, confidence: 'high' },
  'unique:arachnid': { price: 45, confidence: 'high' },
  'unique:tyraels': { price: 200, confidence: 'medium' },
  'unique:torch': { price: 50, confidence: 'high' },
  'unique:anni': { price: 80, confidence: 'high' },
  'unique:mara': { price: 25, confidence: 'high' },
  'unique:griffon': { price: 85, confidence: 'high' },
  'unique:crownofages': { price: 120, confidence: 'medium' },
  'unique:verdungo': { price: 15, confidence: 'high' },
  'unique:tgods': { price: 8, confidence: 'high' },
  'unique:soj': { price: 30, confidence: 'high' },
  'unique:highlord': { price: 18, confidence: 'high' },
  'unique:stormshield': { price: 35, confidence: 'high' },
  'unique:windforce': { price: 180, confidence: 'medium' },
  'runeword:enigma': { price: 160, confidence: 'high' },
  'runeword:infinity': { price: 180, confidence: 'high' },
  'runeword:botd': { price: 85, confidence: 'high' },
  'runeword:grief': { price: 35, confidence: 'high' },
  'runeword:cta': { price: 40, confidence: 'high' },
  'runeword:fortitude': { price: 45, confidence: 'high' },
  'runeword:spirit': { price: 5, confidence: 'high' },
  'runeword:beast': { price: 55, confidence: 'high' },
  'runeword:lastwish': { price: 120, confidence: 'medium' },
  'runeword:faith': { price: 95, confidence: 'high' },
  'runeword:coh': { price: 30, confidence: 'high' },
  'runeword:exile': { price: 75, confidence: 'high' },
  'runeword:phoenix': { price: 65, confidence: 'high' },
  'runeword:insight': { price: 3, confidence: 'high' },
  'runeword:hoto': { price: 15, confidence: 'high' },
  'set:talrasha': { price: 25, confidence: 'high' },
  'set:arreat': { price: 20, confidence: 'high' },
  'set:trang': { price: 15, confidence: 'high' },
  'set:ik': { price: 30, confidence: 'high' },
  'set:layingofhands': { price: 12, confidence: 'high' },
  'base:monarch': { price: 5, confidence: 'high' },
  'base:archon': { price: 8, confidence: 'high' },
  'base:dusk': { price: 6, confidence: 'high' },
  'base:sacredarmor': { price: 15, confidence: 'medium' },
  'base:thresher': { price: 10, confidence: 'high' },
  'base:berserkeraxe': { price: 12, confidence: 'high' },
  'facet:fire': { price: 25, confidence: 'high' },
  'facet:cold': { price: 30, confidence: 'high' },
  'facet:light': { price: 28, confidence: 'high' },
  'facet:poison': { price: 15, confidence: 'high' },
  'misc:token': { price: 5, confidence: 'high' },
};

async function main() {
  console.log('Seeding database...');

  // Clear existing data
  await prisma.filterItem.deleteMany();
  await prisma.filterPreset.deleteMany();
  await prisma.priceObservation.deleteMany();
  await prisma.priceEstimate.deleteMany();
  await prisma.d2Item.deleteMany();

  // Insert items
  console.log(`Inserting ${ITEMS.length} items...`);
  for (const item of ITEMS) {
    await prisma.d2Item.create({ data: item });
  }

  // Insert price estimates
  console.log('Inserting price estimates...');
  const items = await prisma.d2Item.findMany();
  let priceCount = 0;

  for (const item of items) {
    const priceData = PRICES[item.variantKey];
    if (priceData) {
      await prisma.priceEstimate.create({
        data: {
          itemId: item.id,
          priceFg: priceData.price,
          confidence: priceData.confidence,
          nObservations: Math.floor(Math.random() * 100) + 10,
        },
      });
      priceCount++;
    }
  }

  // Create default filter preset
  await prisma.filterPreset.create({
    data: {
      name: 'default',
      description: 'Default filter with all items',
    },
  });

  console.log(`Seeded ${ITEMS.length} items, ${priceCount} prices, 1 preset`);
}

main()
  .catch((e) => {
    console.error(e);
    process.exit(1);
  })
  .finally(async () => {
    await prisma.$disconnect();
  });
