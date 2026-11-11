/* Affiches d'une langue : node rendre_affiches.js <langue> <dossier de sortie> [type] */
const { chromium } = require("playwright-core");
const fs = require("fs");

const [langue, sortie, seul] = process.argv.slice(2);
const ICI = __dirname;
const textes = JSON.parse(fs.readFileSync(`${ICI}/textes.json`, "utf8"));
const TYPES = ["lancement", "fonctionnalites", "tableau", "plaintes", "carte", "offres", "qr"];
const A4 = ["lancement", "fonctionnalites", "offres", "qr"];
const TAILLES = { publication: [1080, 1350, 1], story: [1080, 1920, 1], a4: [1240, 1754, 2] };
const NUMEROS = { lancement: "01", fonctionnalites: "02", tableau: "03", plaintes: "04", carte: "05", offres: "06", qr: "07" };

(async () => {
  const navigateur = await chromium.launch({ channel: "chrome", args: ["--allow-file-access-from-files"] });
  fs.mkdirSync(sortie, { recursive: true });
  for (const type of seul ? [seul] : TYPES) {
    for (const [format, [w, h, echelle]] of Object.entries(TAILLES)) {
      if (format === "a4" && !A4.includes(type)) continue;
      const page = await navigateur.newPage({ viewport: { width: w, height: h }, deviceScaleFactor: echelle });
      await page.addInitScript((d) => { window.DONNEES = d; }, { t: textes[langue], langue });
      page.on("pageerror", (e) => console.error("Erreur page :", e.message));
      await page.goto(`file://${ICI}/studio/affiches.html?type=${type}&format=${format}`);
      await page.waitForFunction(() => window.pret);
      await page.evaluate(() => window.pret);
      const nom = `${NUMEROS[type]}-${type}-${format === "a4" ? "a4-impression" : format}-${langue}.png`;
      await page.screenshot({ path: `${sortie}/${nom}` });
      await page.close();
    }
  }
  await navigateur.close();
  console.log(langue, "affiches faites");
})();
