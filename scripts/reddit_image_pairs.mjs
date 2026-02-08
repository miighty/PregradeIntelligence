import { chromium } from 'playwright';

const SEARCH_URL = 'https://www.reddit.com/search/?q=pokemon%20card%20front%20back%20grade%20help&sort=new';

function uniq(arr) {
  return Array.from(new Set(arr));
}

const browser = await chromium.launch({ headless: true });
const page = await browser.newPage({
  userAgent:
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36'
});

async function safeGoto(url) {
  await page.goto(url, { waitUntil: 'domcontentloaded', timeout: 30000 });
  await page.waitForTimeout(1200);
}

await safeGoto(SEARCH_URL);

// Grab candidate post links
const postLinks = uniq(
  await page
    .locator('a[data-testid="post-title"]')
    .evaluateAll((as) => as.map((a) => a.href).filter(Boolean))
    .catch(() => [])
);

const candidates = postLinks
  .filter((u) => u.includes('/comments/'))
  .slice(0, 20);

const pairs = [];

for (const url of candidates) {
  const p = await browser.newPage({ userAgent: await page.evaluate(() => navigator.userAgent) });
  try {
    await p.goto(url, { waitUntil: 'domcontentloaded', timeout: 30000 });
    await p.waitForTimeout(1500);

    // Try to collect i.redd.it images
    const imgs = uniq(
      await p
        .locator('img')
        .evaluateAll((imgs) =>
          imgs
            .map((i) => i.getAttribute('src') || '')
            .filter((src) => src.includes('i.redd.it/') && !src.includes('emoji'))
        )
        .catch(() => [])
    );

    // Also check for gallery links (sometimes in <a href="https://preview.redd.it/...">)
    const preview = uniq(
      await p
        .locator('a')
        .evaluateAll((as) =>
          as
            .map((a) => a.getAttribute('href') || '')
            .filter((href) => href.includes('i.redd.it/') || href.includes('preview.redd.it/'))
        )
        .catch(() => [])
    );

    const all = uniq([...imgs, ...preview]).filter(Boolean);

    // We want at least 2 distinct images for front/back.
    if (all.length >= 2) {
      pairs.push({ post: url, front: all[0], back: all[1], all: all.slice(0, 6) });
    }

    if (pairs.length >= 5) break;
  } catch {
    // ignore
  } finally {
    await p.close();
  }
}

await browser.close();

console.log(JSON.stringify({ search: SEARCH_URL, found: pairs.length, pairs }, null, 2));
