// Outils communs : entrée dans la démo, cadres rouges numérotés, capture WebP.
const { chromium } = require("playwright-core");
const sharp = require("sharp");
const SORTIE = "/Users/macbookpro/Suivi-evaluation/SuiviEvaluation3/frontend/public/formation/guide";
const BASE = "http://localhost:5192";
const pause = (ms) => new Promise((r) => setTimeout(r, ms));

async function ouvrir() {
  const nav = await chromium.launch({ channel: "chrome", headless: true });
  const page = await nav.newPage({ viewport: { width: 1280, height: 800 }, deviceScaleFactor: 1.25, locale: "fr-FR" });
  await page.goto(`${BASE}/accueil?demo=1&lang=fr`, { waitUntil: "networkidle" });
  await page.waitForURL((u) => !u.pathname.startsWith("/accueil"), { timeout: 30000 });
  // Bandeau « Mode démonstration » et notifications masqués : ils ne concernent pas la leçon.
  return { nav, page };
}

async function nettoyer(page) {
  await page.evaluate(() => {
    for (const el of document.querySelectorAll(".mantine-Alert-root")) if (el.textContent.includes("Mode démonstration")) el.remove();
    for (const el of document.querySelectorAll(".repere-guide")) el.remove();
  });
}

/** Cadres rouges numérotés autour des éléments [{loc, n}] (un locator Playwright et un numéro). */
async function reperes(page, liste) {
  let premier = true;
  for (const { loc, n } of liste) {
    let boite = null;
    try {
      // Seul le premier repère fait défiler la page : les suivants doivent rester à leur place.
      if (premier) await loc.first().scrollIntoViewIfNeeded({ timeout: 3000 });
      boite = await loc.first().boundingBox({ timeout: 3000 });
    } catch (e) { boite = null; }
    premier = false;
    const vue = page.viewportSize();
    if (!boite || boite.y + boite.height < 0 || boite.y > vue.height) { console.log("   ✗ repère introuvable ou hors écran", n); continue; }
    await page.evaluate(({ b, n }) => {
      const c = document.createElement("div");
      c.className = "repere-guide";
      Object.assign(c.style, { position: "fixed", left: `${b.x - 5}px`, top: `${b.y - 5}px`, width: `${b.width + 10}px`, height: `${b.height + 10}px`,
        border: "3px solid #e03131", borderRadius: "8px", zIndex: 99999, pointerEvents: "none", boxShadow: "0 0 0 3px rgba(224,49,49,.18)" });
      const p = document.createElement("div");
      p.className = "repere-guide";
      p.textContent = n;
      Object.assign(p.style, { position: "fixed", left: `${Math.max(2, b.x - 18)}px`, top: `${Math.max(2, b.y - 18)}px`, width: "26px", height: "26px",
        borderRadius: "50%", background: "#e03131", color: "#fff", font: "700 14px/26px Arial", textAlign: "center", zIndex: 100000, pointerEvents: "none",
        boxShadow: "0 2px 6px rgba(0,0,0,.3)" });
      document.body.append(c, p);
    }, { b: boite, n });
  }
}

async function capture(page, nom, liste = []) {
  await page.mouse.move(640, 799);  // pas d'infobulle due au pointeur
  await pause(500);
  await nettoyer(page);
  await reperes(page, liste);
  await pause(150);
  const png = await page.screenshot();
  await sharp(png).resize(1400).webp({ quality: 78 }).toFile(`${SORTIE}/${nom}.webp`);
  await nettoyer(page);
  console.log("✓", nom);
}

const aller = async (page, chemin) => { await page.goto(BASE + chemin, { waitUntil: "networkidle" }); await pause(1200); await nettoyer(page); };
const bouton = (page, nom) => page.getByRole("button", { name: nom, exact: false });
const onglet = (page, nom) => page.getByRole("tab", { name: nom, exact: false });
const champ = (page, nom) => page.getByLabel(nom, { exact: false });
/** Tout le bloc d'un champ (étiquette, aide et saisie), d'après le texte de son étiquette. */
const zone = (page, etiquette) => page.locator(".mantine-InputWrapper-root, .mantine-Checkbox-root, .mantine-Switch-root, .mantine-Radio-root")
  .filter({ has: page.locator("label", { hasText: etiquette }) }).first();
/** Segment d'un SegmentedControl, d'après son texte. */
const segment = (page, texte) => page.locator(".mantine-SegmentedControl-label", { hasText: texte }).first();

module.exports = { ouvrir, capture, aller, bouton, onglet, champ, zone, segment, pause, nettoyer };
