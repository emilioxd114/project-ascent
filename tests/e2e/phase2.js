// Phase 2: existing wall -> Make route (seeded by the test) -> Another one -> Use this route -> Start ->
// the fake camera shows a sticker climbing the route -> sounds (events) until "Top reached" -> Done.
const { chromium } = require('playwright');
const [url, video, shot, nHolds] = process.argv.slice(2);
(async () => {
  const browser = await chromium.launch({ args: [
    '--use-fake-ui-for-media-stream', '--use-fake-device-for-media-stream',
    `--use-file-for-fake-video-capture=${video}`, '--autoplay-policy=no-user-gesture-required'] });
  const page = await browser.newPage({ viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true });
  const errors = [], states = [];
  page.on('pageerror', e => errors.push('pageerror: ' + e.message));
  page.on('console', m => { if (m.type() === 'error') errors.push(m.text()); });
  // the test fixes the generator's seed so the footage matches the route
  await page.route('**/api/route/make*', route => {
    const body = JSON.parse(route.request().postData() || '{}');
    route.continue({ postData: JSON.stringify({ ...body, seed: body.skill === 'reach' ? 3 : 9 }) });
  });
  const seen = [];
  page.on('response', async r => {
    if (r.url().includes('/api/frame')) { try { const a = await r.json(); seen.push(a); } catch (e) {} }
  });
  await page.goto(url);
  await page.waitForSelector('#flow-have:not(.hidden)', { timeout: 15000 });
  await page.click('#flow-use-wall');
  await page.waitForSelector('#flow-s-route:not(.hidden)', { timeout: 15000 });
  await page.click('#flow-skills button[data-skill="easy"]');     // pick another skill first ...
  await page.click('#flow-make');
  await page.waitForSelector('#flow-keep:not(.hidden)', { timeout: 30000 });
  console.log('easy route:', await page.textContent('#flow-route-msg'));
  await page.click('#flow-skills button[data-skill="reach"]');    // ... then reach: remakes the route
  await page.waitForTimeout(1500);
  console.log('reach route:', await page.textContent('#flow-route-msg'));
  await page.screenshot({ path: shot });
  await page.click('#flow-keep');
  await page.waitForSelector('#flow-s-climb:not(.hidden)', { timeout: 15000 });
  console.log('climb step:', await page.textContent('#flow-climb-title'), '-', await page.textContent('#flow-climb-text'));
  await page.click('#flow-start');
  await page.waitForFunction(() => document.getElementById('flow-video').videoWidth > 0, null, { timeout: 15000 });
  const t0 = Date.now();
  let top = false;
  while (Date.now() - t0 < 60000) {
    const st = await page.textContent('#flow-state');
    states.push(st);
    if (/Top reached/.test(st)) { top = true; break; }
    await page.waitForTimeout(500);
  }
  const events = seen.flatMap(a => (a.events || []).map(e => e.sound));
  const locked = seen.filter(a => a.state === 'locked').length;
  console.log(`frames answered: ${seen.length}, locked: ${locked}, events: ${events.join(',')}`);
  console.log('states seen:', [...new Set(states)].join(' / '));
  await page.click('#flow-done');
  await page.waitForSelector('#flow-summary:not(.hidden)', { timeout: 10000 });
  console.log('summary:', (await page.textContent('#flow-summary')).replace(/\n/g, ' '));
  await page.click('#flow-stop');
  console.log('errors:', errors.length ? errors.join('\n') : 'none');
  await browser.close();
  const n = +nHolds;
  const good = events.filter(e => e === 'good').length;
  if (!top || events[events.length - 1] !== 'top' || good !== n - 1 || errors.length) process.exit(1);
})().catch(e => { console.error(e); process.exit(1); });
