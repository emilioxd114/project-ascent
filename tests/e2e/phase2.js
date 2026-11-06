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
  // a route by hand: Build my own, tap three holds (the laptop knows where they are), take one out again
  const info = await page.evaluate(async () => (await fetch(location.origin + '/api/wall/holds?wall=wall&code=' +
    new URLSearchParams(location.search).get('code'))).json());
  await page.click('#flow-build');
  await page.waitForTimeout(1200);                                    // the view scrolls into place
  const box = await page.$eval('#flow-view', c => { const r = c.getBoundingClientRect();
    return { x: r.x, y: r.y, w: r.width, h: r.height, cw: c.width, ch: c.height }; });
  const tapHold = async h => {
    await page.mouse.click(box.x + h.px[0] * box.w / box.cw, box.y + h.px[1] * box.h / box.ch);
    await page.waitForTimeout(700);
  };
  const picks = [info.holds[0], info.holds[12], info.holds[25]];
  for (const h of picks) await tapHold(h);
  const built = await page.textContent('#flow-route-msg');
  console.log('built route:', built);
  await tapHold(picks[1]);                                            // a tap on a ring takes the hold out
  const edited = await page.textContent('#flow-route-msg');
  console.log('edited route:', edited);
  await page.click('#flow-skills button[data-skill="easy"]');     // pick another skill first ...
  await page.click('#flow-make');
  await page.waitForFunction(() => /, easy\./.test(document.getElementById('flow-route-msg').textContent), null, { timeout: 30000 });
  console.log('easy route:', await page.textContent('#flow-route-msg'));
  await page.click('#flow-skills button[data-skill="reach"]');    // ... then reach: remakes the route
  await page.waitForTimeout(1500);
  console.log('reach route:', await page.textContent('#flow-route-msg'));
  await page.screenshot({ path: shot });
  await page.click('#flow-keep');
  await page.waitForSelector('#flow-s-climb:not(.hidden)', { timeout: 15000 });
  console.log('climb step:', await page.textContent('#flow-climb-title'), '-', await page.textContent('#flow-climb-text'));
  await page.$eval('#flow-touch', s => { s.value = 'sticker'; });   // the footage shows a sticker, not a hand (the select sits in a closed Options fold)
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
  // Fix the holds: the saved wall comes back on the screen, Looks good saves it as version 2
  await page.click('#flow-climb-back');
  await page.waitForSelector('#flow-s-route:not(.hidden)', { timeout: 15000 });
  await page.click('#flow-fix');
  await page.waitForFunction(() => !document.getElementById('flow-holds-ok').disabled, null, { timeout: 30000 });
  const fixing = await page.textContent('#flow-holds-msg');
  console.log('fix step:', fixing);
  await page.click('#flow-holds-ok');
  await page.waitForSelector('#flow-s-route:not(.hidden)', { timeout: 60000 });
  const fixed = await page.textContent('#flow-route-msg');
  console.log('fixed:', fixed);
  console.log('errors:', errors.length ? errors.join('\n') : 'none');
  await browser.close();
  const n = +nHolds;
  const good = events.filter(e => e === 'good').length;
  if (!/3 holds, grade ~\S+ \(estimated\), built by hand/.test(built) || !/^2 holds/.test(edited) ||
      !/as saved, 26 holds/.test(fixing) || !/version 2, 26 holds/.test(fixed)) process.exit(1);
  if (!top || events[events.length - 1] !== 'top' || good !== n - 1 || errors.length) process.exit(1);
})().catch(e => { console.error(e); process.exit(1); });
