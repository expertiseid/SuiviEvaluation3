// Vidéo de présentation (≈ 1 min) : visite guidée de l'espace de démonstration, avec légendes.
const { chromium } = require("playwright-core");
const fs = require("fs");
const BASE = "http://localhost:5192";
// Langue de la vidéo : node video.js en  (fr par défaut). Interface de la démo et légendes dans cette langue.
const LANGUE = process.argv[2] || "fr";
const T = require("./video_textes.json")[LANGUE];
const I18N = LANGUE === "fr" ? {} : require(`/Users/macbookpro/Suivi-evaluation/SuiviEvaluation3/frontend/src/i18n/${LANGUE}.json`);
const tr = (fr) => I18N[fr] || fr;
const pause = (ms) => new Promise((r) => setTimeout(r, ms));
(async () => {
  const nav = await chromium.launch({ channel: "chrome", headless: true });
  // 1. Connexion à la démo hors enregistrement.
  const ctx0 = await nav.newContext({ viewport: { width: 1280, height: 720 } });
  const p0 = await ctx0.newPage();
  await p0.goto(`${BASE}/accueil?demo=1&lang=${LANGUE}`, { waitUntil: "networkidle" });
  await p0.waitForURL((u) => !u.pathname.startsWith("/accueil"), { timeout: 30000 });
  const etat = await ctx0.storageState(); await ctx0.close();
  // 2. Enregistrement.
  const ctx = await nav.newContext({ viewport: { width: 1280, height: 720 }, storageState: etat, recordVideo: { dir: "video_tmp", size: { width: 1280, height: 720 } }, locale: "fr-FR" });
  // Préchauffage (onglet non retenu) : les tuiles de la carte, aux mêmes zooms, entrent dans le cache.
  const chauffe = await ctx.newPage();
  await chauffe.goto(`${BASE}/carte`, { waitUntil: "networkidle" }); await pause(4000);
  await chauffe.evaluate(() => document.querySelector(".leaflet-container")?.scrollIntoView({ block: "center" })); await pause(4000);
  for (let i = 0; i < 2; i++) { await chauffe.evaluate(() => document.querySelector(".leaflet-control-zoom-in")?.click()); await pause(7000); }
  await chauffe.close();
  const page = await ctx.newPage();
  const debut = Date.now(); const chapitres = [];
  await page.addInitScript(() => {
    const css = `
      #legende{position:fixed;inset-inline-start:32px;bottom:32px;z-index:99999;max-width:760px;padding:18px 24px;border-radius:16px;
        background:rgba(12,22,34,.88);color:#fff;font:600 26px/1.25 system-ui,-apple-system,Segoe UI,sans-serif;
        box-shadow:0 20px 50px rgba(0,0,0,.35);opacity:0;transform:translateY(12px);transition:all .5s ease}
      #legende.vue{opacity:1;transform:none}
      #legende small{display:block;font:500 15px/1.4 system-ui,sans-serif;color:#F4B740;margin-bottom:6px;letter-spacing:.06em;text-transform:uppercase}
      #carton{position:fixed;inset:0;z-index:100000;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:18px;
        background:radial-gradient(circle at 30% 20%,#173b5c,#0c1622 70%);color:#fff;font-family:system-ui,sans-serif;text-align:center;transition:opacity .7s}
      #carton h1{font-size:54px;margin:0;font-weight:800;letter-spacing:-.02em}
      #carton p{font-size:24px;margin:0;color:#c9d6e3}
      #carton .tag{font-size:15px;color:#F4B740;letter-spacing:.12em;text-transform:uppercase;font-weight:700}`;
    const installer = () => {
      if (!document.getElementById("style-video")) { const s = document.createElement("style"); s.id = "style-video"; s.textContent = css; document.head.appendChild(s); }
      for (const el of document.querySelectorAll(".mantine-Alert-root")) if (el.textContent.includes("Mode démonstration")) el.remove();
    };
    new MutationObserver(installer).observe(document, { childList: true, subtree: true });
  });
  const carton = (tag, titre, sous) => page.evaluate(([tag, titre, sous]) => {
    let c = document.getElementById("carton"); if (!c) { c = document.createElement("div"); c.id = "carton"; document.body.appendChild(c); }
    c.style.opacity = "1"; c.dir = "auto"; c.innerHTML = `<div class="tag">${tag}</div><h1>${titre}</h1><p>${sous}</p>`;
  }, [tag, titre, sous]);
  const sansCarton = () => page.evaluate(() => { const c = document.getElementById("carton"); if (c) { c.style.opacity = "0"; setTimeout(() => c.remove(), 800); } });
  // Chapitres : clé (tableau_de_bord, strategie…) → seconde où la légende apparaît.
  const legende = (cle, n = 0) => {
    if (!chapitres.some((c) => c[0] === cle)) chapitres.push([cle, Math.max(0, Math.round((Date.now() - debut) / 1000))]);
    const [etape, texte] = T.legendes[cle][n];
    return legende0(etape, texte);
  };
  const legende0 = (etape, texte) => page.evaluate(([etape, texte]) => {
    let l = document.getElementById("legende"); if (!l) { l = document.createElement("div"); l.id = "legende"; document.body.appendChild(l); }
    l.classList.remove("vue"); setTimeout(() => { l.dir = "auto"; l.innerHTML = `<small>${etape}</small>${texte}`; l.classList.add("vue"); }, 250);
  }, [etape, texte]);
  const aller = async (chemin) => { await page.evaluate((c) => { history.pushState({}, "", c); dispatchEvent(new PopStateEvent("popstate")); }, chemin); await pause(1200); };
  const defiler = (y, ms) => page.evaluate(([y, ms]) => new Promise((ok) => { const d = scrollY, t0 = performance.now();
    const f = (t) => { const k = Math.min(1, (t - t0) / ms); scrollTo(0, d + (y - d) * (0.5 - Math.cos(Math.PI * k) / 2)); k < 1 ? requestAnimationFrame(f) : ok(); }; requestAnimationFrame(f); }), [y, ms]);

  await page.goto(`${BASE}/`, { waitUntil: "domcontentloaded" });
  await carton(...T.debut);
  await page.waitForLoadState("networkidle"); await pause(3500);
  await sansCarton(); await pause(600);
  await legende("tableau_de_bord"); await pause(3500);
  await defiler(560, 3500); await pause(1500); await defiler(0, 800);
  await aller("/strategie"); await legende("strategie"); await pause(4500);
  await aller("/projets"); await legende("projets"); await pause(5000);
  await aller("/projets/16"); await legende("planification"); await pause(5500);
  await page.getByRole("tab", { name: tr("Cadre logique") }).first().click(); await pause(600);
  await legende("cadre_logique"); await pause(5000);
  await aller("/indicateurs"); await legende("indicateurs"); await pause(5500);
  const tuiles = () => page.waitForFunction(() => { const t = [...document.querySelectorAll(".leaflet-tile")]; return t.length > 0 && t.every((i) => i.complete && i.naturalWidth > 0); }, null, { timeout: 5000 }).catch(() => {});
  await aller("/carte"); await legende("carte"); await tuiles(); await pause(2000);
  const yCarte = await page.evaluate(() => { const c = document.querySelector(".leaflet-container"); return c ? c.getBoundingClientRect().top + scrollY - 90 : 600; });
  await defiler(yCarte, 2500); await tuiles(); await pause(1500);
  await legende("carte", 1);
  await page.evaluate(() => document.querySelector(".leaflet-control-zoom-in")?.click()); await pause(800); await tuiles(); await pause(2500);
  await page.evaluate(() => document.querySelector(".leaflet-control-zoom-in")?.click()); await pause(800); await tuiles(); await pause(3500);
  await defiler(0, 800);
  await aller("/plaintes/tableau-de-bord"); await legende("plaintes"); await pause(5500);
  await carton(...T.fin);
  await pause(5500);
  const chemin = await page.video().path(); await ctx.close(); await nav.close();
  fs.copyFileSync(chemin, `brut-${LANGUE}.webm`);
  fs.writeFileSync(`chapitres-${LANGUE}.json`, JSON.stringify(Object.fromEntries(chapitres)));
  console.log("CHAPITRES", JSON.stringify(chapitres));
  console.log("vidéo :", (fs.statSync(chemin).size / 1e6).toFixed(1), "Mo");
})().catch((e) => { console.error(e); process.exit(1); });
