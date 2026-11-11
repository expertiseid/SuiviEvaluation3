const { chromium } = require('playwright-core');
const DOSSIER = process.argv[2]; const LANGUE = process.argv[3] || 'fr';
(async () => {
  const b = await chromium.launch({ channel: 'chrome' });
  const p = await b.newPage({ viewport: { width: 1600, height: 1000 }, deviceScaleFactor: 2, locale: 'fr-FR' });
  await p.goto('https://demo.204-168-227-18.sslip.io/', { waitUntil: 'networkidle' });
  await p.evaluate((l) => localStorage.setItem('langue', l), LANGUE);
  await p.reload({ waitUntil: 'networkidle' });
  await p.locator('button').filter({ hasText: /démo|demo|Demo|التجريبي|تجرب|Probar|ausprobieren/i }).first().click();
  await p.waitForTimeout(5000);
  const pages = [['tableau-de-bord', '/'], ['projets', '/projets'], ['carte', '/carte'], ['indicateurs', '/indicateurs'], ['suivi', '/suivi'],
    ['beneficiaires', '/beneficiaires'], ['plaintes', '/plaintes/tableau-de-bord'], ['planification', '/planification'], ['strategie', '/strategie'], ['documents', '/documents']];
  for (const [nom, chemin] of pages) {
    await p.goto('https://demo.204-168-227-18.sslip.io' + chemin, { waitUntil: 'networkidle' });
    await p.waitForTimeout(3500);
    // Bandeau « Mode démonstration » et bandeau défilant : retirés de la capture.
    await p.evaluate(() => document.querySelectorAll('.mantine-Alert-root').forEach((a) => { if (a.querySelector('button, a') && /démonstration|demonstration|demostración|Demonstration|عرض|تجريبي/i.test(a.textContent || '')) a.remove(); }));
    await p.screenshot({ path: `${DOSSIER}/${nom}.png` });
    console.log(nom);
  }
  await b.close();
})();
