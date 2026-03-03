import { NextRequest, NextResponse } from 'next/server';

// Common D2 slang aliases mapping
const SLANG_ALIASES: Record<string, string> = {
  // Runes
  'jah': 'rune:jah',
  'ber': 'rune:ber',
  'zod': 'rune:zod',
  'cham': 'rune:cham',
  'sur': 'rune:sur',
  'lo': 'rune:lo',
  'ohm': 'rune:ohm',
  'vex': 'rune:vex',
  'gul': 'rune:gul',
  'ist': 'rune:ist',
  'mal': 'rune:mal',
  'um': 'rune:um',
  'pul': 'rune:pul',
  'lem': 'rune:lem',
  'ko': 'rune:ko',
  'hel': 'rune:hel',
  
  // Uniques - Common Names
  'shako': 'unique:shako',
  'harlequin': 'unique:shako',
  'harlequin crest': 'unique:shako',
  'griffon': 'unique:griffon',
  'griffons': 'unique:griffon',
  'griffons eye': 'unique:griffon',
  'andy': 'unique:andariel',
  'andys': 'unique:andariel',
  'coa': 'unique:crownofages',
  'crown of ages': 'unique:crownofages',
  'kira': 'unique:kira',
  'kiras': 'unique:kira',
  
  // Uniques - Armor
  'tyrael': 'unique:tyraels',
  'tyraels': 'unique:tyraels',
  'tyraels might': 'unique:tyraels',
  'vipermagi': 'unique:skinofvipermagi',
  'viper': 'unique:skinofvipermagi',
  'skin of the viper': 'unique:skinofvipermagi',
  'skullder': 'unique:skullder',
  'skullders': 'unique:skullder',
  
  // Uniques - Belts
  'arach': 'unique:arachnid',
  'arachnid': 'unique:arachnid',
  'spider belt': 'unique:arachnid',
  'dungo': 'unique:verdungo',
  'verdungo': 'unique:verdungo',
  'tgod': 'unique:tgods',
  'tgods': 'unique:tgods',
  'thundergod': 'unique:tgods',
  'thundergods': 'unique:tgods',
  
  // Uniques - Boots
  'wartraveler': 'unique:wartraveler',
  'war trav': 'unique:wartraveler',
  'wt': 'unique:wartraveler',
  'wartrav': 'unique:wartraveler',
  'sandstorm': 'unique:sandstorm',
  'sst': 'unique:sandstorm',
  'trek': 'unique:sandstorm',
  'gore': 'unique:goredriver',
  'goredriver': 'unique:goredriver',
  'gore rider': 'unique:goredriver',
  'waterwalk': 'unique:waterwalk',
  
  // Uniques - Gloves
  'drac': 'unique:dracul',
  'dracs': 'unique:dracul',
  'dracul': 'unique:dracul',
  'draculs': 'unique:dracul',
  'chance': 'unique:chanceguards',
  'chancy': 'unique:chanceguards',
  'chance guards': 'unique:chanceguards',
  'magefist': 'unique:magefist',
  'mage': 'unique:magefist',
  'steelrend': 'unique:steelrend',
  'lavagout': 'unique:lavagout',
  'lava gout': 'unique:lavagout',
  
  // Uniques - Shields
  'stormshield': 'unique:stormshield',
  'ss': 'unique:stormshield',
  'storm': 'unique:stormshield',
  'homu': 'unique:homunculus',
  'homunculus': 'unique:homunculus',
  'medusa': 'unique:medusa',
  'medusas': 'unique:medusa',
  'tiamat': 'unique:tiamat',
  'tiamats': 'unique:tiamat',
  
  // Uniques - Weapons
  'wf': 'unique:windforce',
  'windforce': 'unique:windforce',
  'buriza': 'unique:buriza',
  'occy': 'unique:occulus',
  'occulus': 'unique:occulus',
  'wizzy': 'unique:wizardspike',
  'wiz': 'unique:wizardspike',
  'wizardspike': 'unique:wizardspike',
  'leoric': 'unique:leoric',
  'aokl': 'unique:leoric',
  'arm of king leoric': 'unique:leoric',
  'death fathom': 'unique:death',
  'fathom': 'unique:death',
  'eschuta': 'unique:eschuta',
  'eschutas': 'unique:eschuta',
  
  // Uniques - Jewelry
  'soj': 'unique:soj',
  'stone of jordan': 'unique:soj',
  'bk': 'unique:bk',
  'bul kathos': 'unique:bk',
  'bul kathoss': 'unique:bk',
  'raven': 'unique:raven',
  'ravenfrost': 'unique:raven',
  'dwarf': 'unique:dwarf',
  'dwarf star': 'unique:dwarf',
  'mara': 'unique:mara',
  'maras': 'unique:mara',
  'maras kaleidoscope': 'unique:mara',
  'highlord': 'unique:highlord',
  'highlords': 'unique:highlord',
  'hlw': 'unique:highlord',
  'catseye': 'unique:catseye',
  'cats eye': 'unique:catseye',
  'atma': 'unique:atma',
  'atmas': 'unique:atma',
  
  // Uniques - Charms
  'anni': 'unique:anni',
  'annihilus': 'unique:anni',
  'torch': 'unique:torch',
  'hellfire': 'unique:torch',
  'hellfire torch': 'unique:torch',
  'gheed': 'unique:gheed',
  'gheeds': 'unique:gheed',
  
  // Runewords
  'eni': 'runeword:enigma',
  'enigma': 'runeword:enigma',
  'enig': 'runeword:enigma',
  'infy': 'runeword:infinity',
  'infinity': 'runeword:infinity',
  'botd': 'runeword:botd',
  'breath of the dying': 'runeword:botd',
  'grief': 'runeword:grief',
  'beast': 'runeword:beast',
  'lw': 'runeword:lastwish',
  'last wish': 'runeword:lastwish',
  'lastwish': 'runeword:lastwish',
  'cta': 'runeword:cta',
  'call to arms': 'runeword:cta',
  'hoto': 'runeword:hoto',
  'heart of the oak': 'runeword:hoto',
  'forti': 'runeword:fortitude',
  'fortitude': 'runeword:fortitude',
  'spirit': 'runeword:spirit',
  'coh': 'runeword:coh',
  'chains of honor': 'runeword:coh',
  'insight': 'runeword:insight',
  'exile': 'runeword:exile',
  'phoenix': 'runeword:phoenix',
  'faith': 'runeword:faith',
  'doom': 'runeword:doom',
  'edeath': 'runeword:edeath',
  'eth death': 'runeword:edeath',
  
  // Set Items
  'tal': 'set:talrasha',
  'tals': 'set:talrasha',
  'tal rasha': 'set:talrasha',
  'talrasha': 'set:talrasha',
  'ik': 'set:ik',
  'immortal king': 'set:ik',
  'arreat': 'set:arreat',
  'arreats': 'set:arreat',
  'arreats face': 'set:arreat',
  'trang': 'set:trang',
  'trang oul': 'set:trang',
  'trang ouls': 'set:trang',
  'loh': 'set:layingofhands',
  'laying of hands': 'set:layingofhands',
  'guillaume': 'set:guillaume',
  'guillaumes': 'set:guillaume',
  'guillaumes face': 'set:guillaume',
  
  // Bases
  'monarch': 'base:monarch',
  'mon': 'base:monarch',
  'archon': 'base:archon',
  'ap': 'base:archon',
  'archon plate': 'base:archon',
  'dusk': 'base:dusk',
  'ds': 'base:dusk',
  'dusk shroud': 'base:dusk',
  'thresh': 'base:thresher',
  'thresher': 'base:thresher',
  'gt': 'base:giantthresher',
  'giant thresher': 'base:giantthresher',
  'cv': 'base:colossusvoulge',
  'colossus voulge': 'base:colossusvoulge',
  'ba': 'base:berserkeraxe',
  'berserker axe': 'base:berserkeraxe',
  'pb': 'base:phaseblade',
  'phase blade': 'base:phaseblade',
  'sa': 'base:sacredarmor',
  'sacred armor': 'base:sacredarmor',
  
  // Facets
  'fire facet': 'facet:fire',
  'cold facet': 'facet:cold',
  'light facet': 'facet:light',
  'lightning facet': 'facet:light',
  'poison facet': 'facet:poison',
  'rainbow': 'facet:fire',
  
  // Misc
  'token': 'misc:token',
  'retoken': 'misc:token',
  'token of absolution': 'misc:token',
  
  // Crafts
  'blood ring': 'craft:bloodring',
  'blood rings': 'craft:bloodring',
  'blood gloves': 'craft:bloodgloves',
  'caster amulet': 'craft:casteramulet',
  '2/20 ammy': 'craft:casteramulet',
  '2/20 amulet': 'craft:casteramulet',
  'kb gloves': 'craft:hitgloves',
  
  // Charms
  'sc': 'magic:smallcharm',
  'small charm': 'magic:smallcharm',
  'gc': 'magic:grandcharm',
  'grand charm': 'magic:grandcharm',
  'pcomb': 'magic:grandcharm',
  'skiller': 'magic:grandcharm',
};

// Get all aliases
export async function GET(request: NextRequest) {
  const searchParams = request.nextUrl.searchParams;
  const term = searchParams.get('term');
  
  if (term) {
    // Resolve specific term
    const normalized = term.toLowerCase().trim();
    const variantKey = SLANG_ALIASES[normalized];
    
    if (variantKey) {
      return NextResponse.json({
        term,
        variantKey,
        success: true,
      });
    }
    
    // Find partial matches
    const suggestions = Object.entries(SLANG_ALIASES)
      .filter(([alias]) => alias.includes(normalized) || normalized.includes(alias))
      .slice(0, 10)
      .map(([alias, key]) => ({ alias, variantKey: key }));
    
    if (suggestions.length > 0) {
      return NextResponse.json({
        term,
        suggestions,
        success: false,
        message: 'Exact match not found, showing suggestions',
      });
    }
    
    return NextResponse.json({
      term,
      error: 'No matching alias found',
      success: false,
    });
  }
  
  // Return all aliases
  return NextResponse.json({
    aliases: SLANG_ALIASES,
    total: Object.keys(SLANG_ALIASES).length,
  });
}

// Batch resolve multiple terms
export async function POST(request: NextRequest) {
  try {
    const body = await request.json();
    const { terms } = body;
    
    if (!Array.isArray(terms)) {
      return NextResponse.json(
        { error: 'terms must be an array of strings' },
        { status: 400 }
      );
    }
    
    const results = terms.map((term: string) => {
      const normalized = term.toLowerCase().trim();
      const variantKey = SLANG_ALIASES[normalized];
      return {
        term,
        variantKey: variantKey || null,
        found: !!variantKey,
      };
    });
    
    return NextResponse.json({
      results,
      found: results.filter(r => r.found).length,
      total: results.length,
    });
    
  } catch (error) {
    return NextResponse.json(
      { error: 'Invalid request body' },
      { status: 400 }
    );
  }
}
