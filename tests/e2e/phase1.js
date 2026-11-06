// Phase 1: open the link, New wall, Capture, holds found, Looks good -> wall saved, route step shown.
const { chromium } = require('playwright');
const [url, video, shot] = process.argv.slice(2);
(async () => {
  const browser = await chromium.launch({ args: [
    '--use-fake-ui-for-media-stream', '--use-fake-device-for-media-stream',
    `--use-file-for-fake-video-capture=${video}`, '--autoplay-policy=no-user-gesture-required'] });
  const page = await browser.newPage({ viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true });
  const errors = [];
  page.on('pageerror', e => errors.push('pageerror: ' + e.message));
  page.on('console', m => { if (m.type() === 'error') errors.push(m.text()); });
  await page.goto(url);
  await page.waitForSelector('#view-climb:not(.hidden)');
  const tabs = await page.$$eval('#tabs a', a => a.map(x => x.textContent));
  console.log('tabs:', tabs.join(' | '));
  await page.click('#flow-new');
  await page.waitForFunction(() => document.getElementById('flow-video').videoWidth > 0, null, { timeout: 15000 });
  await page.waitForTimeout(800);
  await page.click('#flow-shutter');
  await page.waitForFunction(() => !document.getElementById('flow-holds-ok').disabled, null, { timeout: 60000 });
  const msg = await page.textContent('#flow-holds-msg');
  console.log('holds step:', msg);
  // fix one hold: tap a ring to remove it, then tap it again to add it back
  const n0 = (msg.match(/(\d+) holds/) || [])[1];
  await page.screenshot({ path: shot });
  await page.click('#flow-holds-ok');
  await page.waitForSelector('#flow-s-route:not(.hidden)', { timeout: 60000 });
  console.log('route step:', await page.textContent('#flow-route-msg'));
  console.log('errors:', errors.length ? errors.join('\n') : 'none');
  await browser.close();
  if (!/Wall found from the board's outline, \d+ holds/.test(msg) || errors.length || !(+n0 >= 24)) process.exit(1);
})().catch(e => { console.error(e); process.exit(1); });
