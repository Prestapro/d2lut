const { chromium } = require('playwright');

const CRON_SECRET = process.env.CRON_SECRET || 'local-dev-secret';
const API_URL = process.env.API_URL || 'http://localhost:3000/api/cron/refresh-prices';
const PROFILE = process.env.D2JSP_PROFILE || 'data/cache/playwright-d2jsp-profile';

const itemPatterns = [
  ['rune:jah', /\bjah\b/i], ['rune:ber', /\bber\b/i], ['rune:sur', /\bsur\b/i], ['rune:lo', /\blo\b/i], ['rune:ohm', /\bohm\b/i], ['rune:vex', /\bvex\b/i], ['rune:gul', /\bgul\b/i], ['rune:ist', /\bist\b/i], ['rune:mal', /\bmal\b/i], ['rune:um', /\bum\b/i], ['rune:pul', /\bpul\b/i], ['rune:cham', /\bcham\b/i], ['rune:zod', /\bzod\b/i],
  ['runeword:enigma', /\benigma\b/i], ['runeword:infinity', /\binfinity\b/i], ['runeword:cta', /\b(?:cta|call\s*to\s*arms)\b/i], ['runeword:fortitude', /\bfortitude\b/i], ['runeword:grief', /\bgrief\b/i], ['runeword:spirit', /\bspirit\b/i], ['runeword:hoto', /\b(?:hoto|heart\s*of\s*the\s*oak)\b/i], ['runeword:coh', /\b(?:coh|chains\s*of\s*honor)\b/i], ['runeword:phoenix', /\bphoenix\b/i],
  ['unique:torch', /\b(?:torch|hellfire\s*torch)\b/i], ['unique:anni', /\b(?:anni|annihilus)\b/i], ['unique:soj', /\b(?:soj|stone\s*of\s*jordan)\b/i], ['unique:griffon', /\bgriffon/i], ['unique:mara', /\bmara\b/i], ['unique:shako', /\bshako\b|harlequin/i], ['unique:arachnid', /\barachnid\b/i], ['unique:highlord', /\bhighlord/i], ['unique:bk', /\bbul\-?kathos|\bbk\b/i], ['unique:raven', /\braven\s*frost\b/i],
];

const pricePatterns = [
  /\b(?:sold|bin|co|c\/o|ask|offer)\s*[:\-]?\s*(\d{1,6}(?:\.\d+)?)\s*(?:fg|forum\s*gold)?\b/i,
  /\b(\d{1,6}(?:\.\d+)?)\s*fg\b/i,
];

function extractPrice(text) {
  for (const re of pricePatterns) {
    const m = text.match(re);
    if (m) {
      const v = Number(m[1]);
      if (Number.isFinite(v) && v > 0 && v < 200000) return v;
    }
  }
  return null;
}

async function main() {
  const context = await chromium.launchPersistentContext(PROFILE, {
    headless: true,
    viewport: { width: 1366, height: 900 },
  });
  const page = await context.newPage();

  const maxListPages = 35;
  const maxTopics = 200;
  const seen = new Set();
  const topicIds = [];

  for (let p = 0; p < maxListPages; p++) {
    const st = p * 25;
    const url = `https://forums.d2jsp.org/forum.php?f=271&st=${st}`;
    try {
      await page.goto(url, { waitUntil: 'domcontentloaded', timeout: 45000 });
      const html = await page.content();
      const re = /topic\.php\?t=(\d+)/gi;
      let m;
      while ((m = re.exec(html)) !== null) {
        const id = m[1];
        if (!seen.has(id)) {
          seen.add(id);
          topicIds.push(id);
          if (topicIds.length >= maxTopics) break;
        }
      }
      if (topicIds.length >= maxTopics) break;
    } catch (e) {}
  }

  const observations = [];

  for (const tid of topicIds) {
    try {
      await page.goto(`https://forums.d2jsp.org/topic.php?t=${tid}`, { waitUntil: 'domcontentloaded', timeout: 45000 });
      const html = await page.content();
      const text = html
        .replace(/<script[\s\S]*?<\/script>/gi, ' ')
        .replace(/<style[\s\S]*?<\/style>/gi, ' ')
        .replace(/<[^>]+>/g, ' ')
        .replace(/&nbsp;/g, ' ')
        .replace(/&amp;/g, '&')
        .replace(/\s+/g, ' ')
        .trim()
        .slice(0, 12000);

      const price = extractPrice(text);
      if (!price) continue;

      const low = text.toLowerCase();
      for (const [variantKey, re] of itemPatterns) {
        if (re.test(low)) {
          observations.push({
            variantKey,
            priceFg: price,
            signalKind: 'ask',
            confidence: 0.62,
            source: 'd2jsp_topic_scan_live_pw',
            sourceId: tid,
            observedAt: new Date().toISOString(),
          });
        }
      }
    } catch (e) {}
  }

  const payload = {
    source: 'live-playwright',
    forumId: 271,
    postsScanned: topicIds.length,
    observations,
  };

  const res = await fetch(API_URL, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${CRON_SECRET}`,
    },
    body: JSON.stringify(payload),
  });

  const text = await res.text();
  console.log(JSON.stringify({
    ok: res.ok,
    status: res.status,
    scannedTopics: topicIds.length,
    observations: observations.length,
    response: text,
  }));

  await context.close();
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
