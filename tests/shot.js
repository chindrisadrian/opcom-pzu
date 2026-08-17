const { chromium } = require('playwright');
(async () => {
  const b = await chromium.launch({ executablePath: '/opt/pw-browsers/chromium' });
  const p = await b.newPage({ viewport: { width: 920, height: 900 }, deviceScaleFactor: 2 });
  const errs = [];
  p.on('pageerror', e => errs.push('PAGEERROR ' + e.message));
  p.on('console', m => { if (m.type() === 'error') errs.push('CONSOLE ' + m.text()); });
  await p.goto('file://' + __dirname + '/card_harness.html');
  await p.waitForFunction(() => window.READY === true, { timeout: 5000 });
  await p.waitForTimeout(400);
  // verificari structurale
  const checks = await p.evaluate(() => {
    const c = window.CARDS[0].shadowRoot;
    const bars = c.querySelectorAll('rect.bar').length;
    const colors = new Set([...c.querySelectorAll('rect.bar')].map(r => r.getAttribute('fill')));
    const c2 = window.CARDS[1].shadowRoot;
    return {
      bars48: bars,
      distinctColors: colors.size,
      bars24: c2.querySelectorAll('rect.bar').length,
      legend: c.querySelector('.legend').textContent.trim().replace(/\s+/g,' '),
      head: c.querySelector('.head').textContent.trim().replace(/\s+/g,' '),
      empty: window.CARDS[2].shadowRoot.querySelector('.msg')?.textContent.trim(),
      nowLine: c.querySelectorAll('line').length,
      svgWidth: c.querySelector('svg')?.getAttribute('width'),
      cardRegistered: !!window.customCards.find(x => x.type === 'opcom-pzu-card'),
    };
  });
  console.log(JSON.stringify(checks, null, 2));
  await p.screenshot({ path: 'card_dark.png', fullPage: true });
  await p.click('button'); await p.waitForTimeout(500);
  await p.screenshot({ path: 'card_light.png', fullPage: true });
  console.log(errs.length ? 'ERRORS:\n' + errs.join('\n') : 'fara erori in pagina');
  await b.close();
})();
