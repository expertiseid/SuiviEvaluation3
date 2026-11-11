/*
 * Affiches Expertise-ID Monitora : 7 modèles × formats (publication 1080×1350, story 1080×1920,
 * A4 à imprimer 1240×1754 rendu en ×2) × 5 langues. ?type=…&format=…, textes dans window.DONNEES.
 */
const params = new URLSearchParams(location.search);
const TYPE = params.get("type");
const FORMAT = params.get("format");
const D = window.DONNEES;
const T = D.t;
const L = D.langue;
const TAILLES = { publication: [1080, 1350], story: [1080, 1920], a4: [1240, 1754] };
const [W, H] = TAILLES[FORMAT];
const U = W / 100;
const HAUT = H / W > 1.5; // story : plus de place en hauteur
const scene = document.getElementById("scene");
Object.assign(scene.style, { width: W + "px", height: H + "px" });
scene.style.setProperty("--u", U + "px");
scene.className = `affiche ${L}`;
if (L === "ar") scene.dir = "rtl";

function el(tag, cls, parent, html = "", style = {}) {
  const e = document.createElement(tag);
  if (cls) e.className = cls;
  if (html) e.innerHTML = html;
  Object.assign(e.style, style);
  (parent || scene).appendChild(e);
  return e;
}
const px = (n) => `${n}px`;
function hasard(graine) { let s = graine; return () => ((s = (s * 9301 + 49297) % 233280) / 233280); }

function fond(couleurs = ["#1f8fc9", "#3ccf9a", "#f4b740"]) {
  const f = el("div", "calque", scene);
  el("div", "grille", f);
  [[-25, -15, 90], [45, 55, 95], [60, -20, 70]].forEach(([x, y, t], i) => el("div", "halo", f, "", {
    width: px(t * U), height: px(t * U), left: `${x}%`, top: `${y}%`, background: `radial-gradient(circle, ${couleurs[i]} 0%, transparent 70%)`,
  }));
  const r = hasard(11);
  for (let i = 0; i < 40; i++) {
    const t = 2 + r() * 4;
    el("div", "point", f, "", { width: px(t), height: px(t), left: `${r() * 100}%`, top: `${r() * 100}%`, opacity: 0.08 + r() * 0.25 });
  }
}
function entete(parent, taille = 9) {
  const e = el("div", "entete", parent);
  el("div", "pastille", e, `<img src="logo-plateforme.svg">`, { width: px(taille * U), height: px(taille * U) });
  el("div", "serif", e, "Expertise-ID <span style='color:var(--safran)'>Monitora</span>", { fontSize: px(taille * 0.42 * U) });
  return e;
}
function pied() {
  const p = el("div", "pied", scene);
  el("div", "signature", p, `<img src="logo-expertise-id.png"><span>${T.commun.signature}</span>`, { fontSize: px(2.4 * U) });
  el("div", "adresse", p, T.commun.url);
  return p;
}
function bloc(top, gauche = 6, droite = 6) {
  return el("div", "", scene, "", { position: "absolute", top: `${top}%`, insetInlineStart: `${gauche}%`, insetInlineEnd: `${droite}%` });
}
function capture(image, style, position = "top left", echelle = 1) {
  const c = el("div", "capture", scene, "", style);
  const im = el("img", "", c);
  im.src = `../ecrans/${L}/${image}.png`;
  im.style.objectPosition = position;
  if (echelle !== 1) Object.assign(im.style, { transform: `scale(${echelle})`, transformOrigin: position });
  return c;
}

const MODELES = {
  lancement() {
    const a = T.affiches.lancement;
    fond();
    const b = bloc(5);
    entete(b);
    const c = bloc(HAUT ? 17 : 19);
    el("div", "badge", c, a.surtitre);
    el("div", "titre", c, a.titre, { fontSize: px((HAUT ? 11 : 10) * U), marginTop: px(3 * U) });
    el("div", "texte", c, a.texte, { fontSize: px(3.4 * U), marginTop: px(2.4 * U), maxWidth: "92%" });
    el("div", "bouton", c, `<span>${a.cta}</span>${icone("fleche", "#0c1622", 2.2)}`, { marginTop: px(3.4 * U), background: "var(--safran)", color: "var(--encre)", fontSize: px(3 * U) });
    capture("tableau-de-bord", { left: HAUT ? "6%" : "12%", right: "-14%", top: HAUT ? "50%" : "62%", height: HAUT ? "38%" : "24%", transform: "rotate(-4deg)" });
    pied();
  },

  fonctionnalites() {
    const a = T.affiches.fonctionnalites;
    fond(["#1f8fc9", "#3ccf9a", "#123d82"]);
    entete(bloc(5));
    el("div", "titre", bloc(HAUT ? 15 : 14.5), a.titre, { fontSize: px((HAUT ? 8.6 : 6.8) * U) });
    const g = bloc(HAUT ? 37 : 31);
    Object.assign(g.style, { display: "grid", gridTemplateColumns: "1fr 1fr", gap: px((HAUT ? 2.4 : 1.8) * U) });
    const ic = [["planification", "var(--safran)"], ["indicateurs", "var(--menthe)"], ["beneficiaires", "#7cc4ff"], ["carte", "var(--menthe)"], ["plaintes", "var(--corail)"], ["langues", "var(--safran)"]];
    a.items.forEach(([titre, texte], i) => {
      const c = el("div", "carte-f", g, "", HAUT ? { padding: px(3.4 * U) } : { padding: px(2.1 * U) });
      el("div", "icone-rond", c, icone(ic[i][0], ic[i][1], 2), HAUT ? {} : { width: px(6.4 * U), height: px(6.4 * U), marginBottom: px(1.1 * U) });
      el("b", "", c, titre, HAUT ? {} : { fontSize: px(3 * U) });
      el("span", "", c, texte, HAUT ? {} : { fontSize: px(2.4 * U) });
    });
    pied();
  },

  tableau() {
    const a = T.affiches.tableau;
    fond();
    entete(bloc(5));
    const c = bloc(HAUT ? 16 : 17);
    el("div", "surtitre", c, a.surtitre);
    el("div", "titre", c, a.titre, { fontSize: px((HAUT ? 10 : 9) * U), marginTop: px(1.6 * U) });
    el("div", "texte", c, a.texte, { fontSize: px(3.3 * U), marginTop: px(2.4 * U) });
    capture("tableau-de-bord", { left: "6%", right: "6%", top: HAUT ? "48%" : "52%", height: HAUT ? "40%" : "36%" }, "40% 0%", 1);
    pied();
  },

  plaintes() {
    const a = T.affiches.plaintes;
    fond(["#e8613c", "#3ccf9a", "#1f8fc9"]);
    entete(bloc(5));
    const c = bloc(HAUT ? 16 : 17);
    el("div", "surtitre", c, a.surtitre);
    el("div", "titre", c, a.titre, { fontSize: px((HAUT ? 10.5 : 9.5) * U), marginTop: px(1.6 * U) });
    el("div", "texte", c, a.texte, { fontSize: px(3.3 * U), marginTop: px(2.4 * U) });
    const l = el("div", "", c, "", { display: "grid", gap: px(1.8 * U), marginTop: px(3.4 * U) });
    a.points.forEach((p) => el("div", "point-liste", l, `<i>${icone("valide", "#0c1622", 3)}</i><span>${p}</span>`));
    capture("plaintes", { left: "6%", right: "-10%", top: HAUT ? "62%" : "70%", height: HAUT ? "28%" : "18%" }, "30% 30%");
    pied();
  },

  carte() {
    const a = T.affiches.carte;
    fond(["#3ccf9a", "#1f8fc9", "#f4b740"]);
    entete(bloc(5));
    const c = bloc(HAUT ? 16 : 17);
    el("div", "surtitre", c, a.surtitre);
    el("div", "titre", c, a.titre, { fontSize: px((HAUT ? 11 : 10) * U), marginTop: px(1.6 * U) });
    el("div", "texte", c, a.texte, { fontSize: px(3.3 * U), marginTop: px(2.4 * U) });
    capture("carte", { left: "6%", right: "6%", top: HAUT ? "45%" : "47%", height: HAUT ? "44%" : "40%" }, "65% 100%", 1.6);
    pied();
  },

  offres() {
    const a = T.affiches.offres;
    fond(["#f4b740", "#3ccf9a", "#1f8fc9"]);
    entete(bloc(5));
    const c = bloc(HAUT ? 15 : 16);
    el("div", "titre", c, a.titre, { fontSize: px((HAUT ? 11 : 9.5) * U) });
    el("div", "texte", c, a.sous, { fontSize: px(3.2 * U), marginTop: px(1 * U) });
    const l = bloc(HAUT ? 31 : 32);
    Object.assign(l.style, { display: "grid", gap: px((HAUT ? 3 : 2.2) * U) });
    [["25", 34, "20 000"], ["50", 52, "30 000"], ["100", 86, "50 000"]].forEach(([go, usd, fcfa], i) => {
      const p = el("div", `prix ${i === 1 ? "vedette" : ""}`, l, "", { display: "grid", gridTemplateColumns: "1fr auto", alignItems: "center", padding: px((HAUT ? 4 : 3) * U) });
      const g = el("div", "", p);
      el("div", "go", g, `Standard ${go} Go`, { fontSize: px(3.8 * U), direction: "ltr", textAlign: "start" });
      el("div", "fcfa", g, `${fcfa} FCFA`, { fontSize: px(3 * U), marginTop: px(0.6 * U), direction: "ltr", textAlign: "start" });
      el("div", "montant", p, `${usd}<span style="color:var(--safran);font-size:.55em"> $</span>`, { fontSize: px((HAUT ? 13 : 11) * U), direction: "ltr" });
    });
    el("div", "texte", bloc(HAUT ? 79 : 81), a.pied, { fontSize: px(2.9 * U), textAlign: "center" });
    pied();
  },

  qr() {
    const a = T.affiches.qr;
    fond(["#1f8fc9", "#f4b740", "#3ccf9a"]);
    entete(bloc(5));
    const c = bloc(HAUT ? 18 : 17);
    c.style.textAlign = "center";
    el("div", "titre", c, a.titre, { fontSize: px((HAUT ? 10 : 9) * U) });
    el("div", "texte", c, a.texte, { fontSize: px(3.4 * U), marginTop: px(2 * U) });
    const q = el("div", "qr", scene, `<img src="qr.svg">`, { position: "absolute", left: "50%", top: HAUT ? "38%" : "40%", width: px(58 * U), transform: "translateX(-50%)" });
    el("div", "adresse", scene, T.commun.url, { position: "absolute", left: 0, right: 0, top: HAUT ? "73%" : "86%", textAlign: "center", fontSize: px(4.4 * U), color: "var(--safran)" });
    el("div", "texte", scene, T.commun.slogan, { position: "absolute", left: 0, right: 0, top: HAUT ? "79%" : "91.5%", textAlign: "center", fontSize: px(3 * U), display: HAUT ? "block" : "none" });
    if (HAUT) pied(); else el("div", "", scene);
    return q;
  },
};

MODELES[TYPE]();
window.pret = (async () => {
  await document.fonts.ready;
  await Promise.all([...document.images].map((im) => (im.complete ? im.decode().catch(() => {}) : new Promise((r) => { im.onload = im.onerror = r; }))));
  return true;
})();
