/*
 * Studio des vidéos Expertise-ID Monitora : 3 compositions (lancement, presentation, offres), 2 formats
 * (h : 1920×1080, v : 1080×1920), 5 langues. Le découpage en scènes vient de la voix (DONNEES.scenes).
 * Tout est piloté par une frise GSAP en pause : window.seek(t) dessine l'image à l'instant t.
 */
const params = new URLSearchParams(location.search);
const VIDEO = params.get("v") || "lancement";
const FORMAT = params.get("f") || "h";
const D = window.DONNEES; // { t: textes de la langue, scenes: {s1: [debut, fin]…}, langue }
const T = D.t;
const L = D.langue;
const W = FORMAT === "h" ? 1920 : 1080;
const H = FORMAT === "h" ? 1080 : 1920;
const U = Math.min(W, H) / 100;
const V = FORMAT === "v";

const scene = document.getElementById("scene");
scene.style.width = W + "px";
scene.style.height = H + "px";
scene.style.setProperty("--u", U + "px");
scene.className = `${FORMAT} ${L}`;
if (L === "ar") scene.dir = "rtl";

const tl = gsap.timeline({ paused: true });
const S = (k) => D.scenes[k];
const actions = []; // effets calculés à chaque image (compteurs, frappe)

function el(tag, cls, parent, html = "", style = {}) {
  const e = document.createElement(tag);
  if (cls) e.className = cls;
  if (html) e.innerHTML = html;
  Object.assign(e.style, style);
  (parent || scene).appendChild(e);
  return e;
}
const px = (n) => `${n}px`;
function hasard(graine) {
  let s = graine;
  return () => ((s = (s * 9301 + 49297) % 233280) / 233280);
}

/** Mots qui montent depuis un masque. */
function motsMasques(parent, texte) {
  const spans = [];
  texte.split(" ").forEach((mot, i, tous) => {
    const m = el("span", "masque", parent);
    const s = el("span", "", m, mot);
    spans.push(s);
    if (i < tous.length - 1) parent.appendChild(document.createTextNode(" "));
  });
  return spans;
}
function revelerMots(spans, quand, duree = 0.7, ecart = 0.07) {
  tl.fromTo(spans, { yPercent: 115 }, { yPercent: 0, duration: duree, ease: "power4.out", stagger: ecart }, quand);
}
function lettres(parent, texte) {
  return [...texte].map((c) => el("span", "", parent, c === " " ? "&nbsp;" : c, { display: "inline-block" }));
}

/* ---------------------------------------------------------------- Fond animé */
function fond(couleurs = ["#1f8fc9", "#3ccf9a", "#f4b740"]) {
  const f = el("div", "calque", scene);
  const g = el("div", "grille", f);
  tl.fromTo(g, { x: 0, y: 0 }, { x: -8 * U, y: -8 * U, duration: 30, ease: "none" }, 0);
  const pos = [[-15, -20, 70], [60, 55, 80], [70, -25, 55]];
  couleurs.forEach((c, i) => {
    const h = el("div", "halo", f, "", {
      width: px(pos[i][2] * U), height: px(pos[i][2] * U), left: `${pos[i][0]}%`, top: `${pos[i][1]}%`,
      background: `radial-gradient(circle, ${c} 0%, transparent 70%)`,
    });
    tl.to(h, { x: (i % 2 ? -1 : 1) * 12 * U, y: (i === 1 ? -1 : 1) * 10 * U, duration: 15, ease: "sine.inOut", repeat: 1, yoyo: true }, 0);
  });
  const r = hasard(42);
  for (let i = 0; i < 38; i++) {
    const t = 2 + r() * 4;
    const p = el("div", "point", f, "", { width: px(t), height: px(t), left: `${r() * 100}%`, top: `${r() * 100}%`, opacity: 0.08 + r() * 0.25 });
    tl.to(p, { y: -(10 + r() * 30) * U, duration: 30, ease: "none" }, 0);
  }
  return f;
}

/* ---------------------------------------------------------------- Pièces réutilisables */
function pastille(parent, taille) {
  return el("div", "pastille", parent, `<img src="logo-plateforme.svg">`, { width: px(taille), height: px(taille) });
}
function marque(parent, taille, couleur = "#fff") {
  return el("div", "serif", parent, "Expertise-ID <span style='color:var(--safran)'>Monitora</span>", {
    fontSize: px(taille), color: couleur, direction: "ltr", unicodeBidi: "isolate",
  });
}
function signature(parent, couleur) {
  const s = el("div", "signature", parent, `<img src="logo-expertise-id.png"><span>${T.commun.signature}</span>`);
  if (couleur) s.style.color = couleur;
  return s;
}
function portable(parent, largeur, images) {
  const p = el("div", "portable", parent, "", { width: px(largeur) });
  const ecran = el("div", "ecran", p);
  const vue = el("div", "vue", ecran);
  const imgs = images.map((nom) => el("img", "", vue, "", {}));
  imgs.forEach((im, i) => { im.src = `../ecrans/${L}/${images[i]}.png`; });
  el("div", "socle", p);
  return { p, vue, imgs };
}
function apparaitre(cible, quand, de = { y: 40 }, duree = 0.8, ease = "power3.out") {
  tl.fromTo(cible, { opacity: 0, ...de }, { opacity: 1, x: 0, y: 0, scale: 1, rotation: 0, duration: duree, ease }, quand);
}
function disparaitre(cible, quand, vers = { y: -40 }, duree = 0.5) {
  tl.to(cible, { opacity: 0, ...vers, duration: duree, ease: "power2.in" }, quand);
}
/** Volet coloré qui s'ouvre en cercle depuis le centre. */
function volet(couleur, quand, duree = 0.9) {
  const v = el("div", "calque", scene, "", { background: couleur, clipPath: "circle(0% at 50% 50%)" });
  tl.to(v, { clipPath: "circle(150% at 50% 50%)", duration: duree, ease: "power3.inOut" }, quand);
  return v;
}
/** Le calque d'une scène n'est visible que pendant sa fenêtre (rien ne déborde sur les autres scènes). */
function fenetre(calque, a, b) {
  tl.set(calque, { visibility: "hidden" }, 0);
  tl.set(calque, { visibility: "visible" }, Math.max(0.001, a - 0.4));
  tl.set(calque, { visibility: "hidden" }, b + 0.8);
}
function frappe(cible, texte, debut, duree) {
  actions.push((t) => {
    const n = Math.max(0, Math.min(texte.length, Math.round(((t - debut) / duree) * texte.length)));
    cible.textContent = texte.slice(0, n);
    cible.style.borderInlineEnd = t > debut && t < debut + duree + 0.6 && Math.floor(t * 2.5) % 2 ? `${0.25 * U}px solid currentColor` : "0";
  });
}
function compteur(cible, valeur, debut, duree, format = (n) => n) {
  actions.push((t) => {
    const p = Math.max(0, Math.min(1, (t - debut) / duree));
    cible.textContent = format(Math.round(valeur * (1 - Math.pow(1 - p, 3))));
  });
}
function fin_noire() {
  const n = el("div", "voile", scene, "", { background: "#000", opacity: 0 });
  tl.to(n, { opacity: 1, duration: 0.45, ease: "power1.in" }, 29.55);
}

/* ================================================================ LANCEMENT */
function lancement() {
  const t = T.lancement;
  fond();

  // S1 : « Vos projets. Vos indicateurs. Vos communautés. »
  const [a1, b1] = S("s1");
  const c1 = el("div", "calque centre", scene, "", { gap: px(1.5 * U) });
  fenetre(c1, a1, typeof b1 !== "undefined" ? b1 : 30);
  const couleurs = ["#fff", "var(--safran)", "var(--menthe)"];
  const pas = (b1 - a1 - 1.0) / 3;
  t.s1.ecran.forEach((ligne, i) => {
    const l = el("div", "serif", c1, "", { fontSize: px((V ? 10.5 : 9.5) * U), color: couleurs[i], lineHeight: 1.05 });
    revelerMots(motsMasques(l, ligne), a1 + 0.25 + i * pas, 0.8);
  });
  tl.to(c1.children, { yPercent: -60, opacity: 0, filter: "blur(10px)", duration: 0.5, ease: "power2.in", stagger: 0.06 }, b1 - 0.55);

  // S2 : « Encore éparpillés ? » et les outils dispersés, aspirés au centre.
  const [a2, b2] = S("s2");
  const c2 = el("div", "calque", scene);
  fenetre(c2, a2, typeof b2 !== "undefined" ? b2 : 30);
  const icones = ["tableur", "courriel", "rapport", "cahier", "message"];
  const places = V
    ? [[12, 18], [58, 12], [8, 70], [55, 78], [30, 88]]
    : [[8, 16], [66, 12], [6, 72], [70, 74], [38, 84]];
  const r = hasard(7);
  const puces = t.s2.mots.map((mot, i) => {
    const p = el("div", "puce", c2, `${icone(icones[i], "var(--safran)")}<span>${mot}</span>`, {
      position: "absolute", left: `${places[i][0]}%`, top: `${places[i][1]}%`, fontSize: px(3 * U),
    });
    const rot = (r() - 0.5) * 18;
    tl.fromTo(p, { opacity: 0, scale: 0.4, rotation: rot * 3 }, { opacity: 1, scale: 1, rotation: rot, duration: 0.6, ease: "back.out(1.8)" }, a2 + 0.15 + i * 0.22);
    tl.to(p, { y: (r() - 0.5) * 6 * U, x: (r() - 0.5) * 6 * U, duration: b2 - a2 - 1.5, ease: "sine.inOut" }, a2 + 0.8);
    return p;
  });
  const q = el("div", "calque centre", c2);
  const qt = el("div", "serif italique", q, "", { fontSize: px((V ? 11 : 10) * U), maxWidth: "80%", lineHeight: 1.05 });
  revelerMots(motsMasques(qt, t.s2.ecran), a2 + 0.5, 0.8, 0.09);
  tl.to(puces, { left: "50%", top: "50%", xPercent: -50, yPercent: -50, scale: 0.1, opacity: 0, rotation: 0, duration: 0.55, ease: "power3.in", stagger: 0.04 }, b2 - 0.85);
  tl.to(qt, { scale: 0.6, opacity: 0, duration: 0.45, ease: "power3.in" }, b2 - 0.6);
  const eclair = el("div", "voile", scene, "", { background: "radial-gradient(circle at 50% 50%, #fff 0%, transparent 55%)", opacity: 0 });
  tl.to(eclair, { opacity: 0.9, duration: 0.18, ease: "power2.out" }, b2 - 0.15).to(eclair, { opacity: 0, duration: 0.6 }, b2 + 0.05);

  // S3 : apparition du logo.
  const [a3, b3] = S("s3");
  const c3 = el("div", "calque centre", scene, "", { gap: px(3 * U) });
  fenetre(c3, a3, typeof b3 !== "undefined" ? b3 : 30);
  const voici = el("div", "", c3, t.s3.ecran, { fontSize: px(3.4 * U), letterSpacing: ".3em", textTransform: "uppercase", color: "var(--menthe)", fontWeight: 600 });
  const zone = el("div", "", c3, "", { position: "relative", width: px(28 * U), height: px(28 * U), display: "grid", placeItems: "center" });
  for (let i = 0; i < 3; i++) {
    const a = el("div", "anneau", zone, "", { width: "100%", height: "100%", opacity: 0, borderColor: i % 2 ? "var(--safran)" : "var(--menthe)" });
    tl.fromTo(a, { scale: 0.7, opacity: 0.9 }, { scale: 2.4, opacity: 0, duration: 1.6, ease: "power2.out", immediateRender: false }, a3 + 0.45 + i * 0.3);
  }
  const pa = pastille(zone, 26 * U);
  const nom = el("div", "serif", c3, "", { fontSize: px((V ? 8.5 : 8) * U), direction: "ltr" });
  const lt = lettres(nom, "Expertise-ID Monitora");
  lt.slice(13).forEach((s) => (s.style.color = "var(--safran)"));
  const slogan = el("div", "", c3, T.commun.slogan, { fontSize: px(3.2 * U), color: "rgba(255,255,255,.8)", letterSpacing: ".04em" });
  apparaitre(voici, a3 + 0.05, { y: 20 }, 0.6);
  tl.fromTo(pa, { scale: 0, rotation: -120 }, { scale: 1, rotation: 0, duration: 1.1, ease: "back.out(1.6)" }, a3 + 0.3);
  tl.fromTo(lt, { y: 60, opacity: 0 }, { y: 0, opacity: 1, duration: 0.6, ease: "power3.out", stagger: 0.035 }, a3 + 0.9);
  apparaitre(slogan, a3 + 1.7, { y: 20 }, 0.7);
  tl.to(c3, { scale: 0.85, opacity: 0, filter: "blur(12px)", duration: 0.55, ease: "power2.in" }, b3 - 0.55);

  // S4 : fonctionnalités et la plateforme sur un ordinateur.
  const [a4, b4] = S("s4");
  const c4 = el("div", "calque", scene);
  fenetre(c4, a4, typeof b4 !== "undefined" ? b4 : 30);
  const col = el("div", "", c4, "", V
    ? { position: "absolute", left: "7%", right: "7%", top: "9%" }
    : { position: "absolute", insetInlineStart: "5%", top: "16%", width: "37%" });
  const titre = el("div", "serif", col, "", { fontSize: px((V ? 7 : 5.2) * U), lineHeight: 1.08, marginBottom: px(4 * U) });
  revelerMots(motsMasques(titre, t.s4.ecran), a4 + 0.2, 0.8, 0.06);
  const grillePuces = el("div", "", V ? c4 : col, "", V
    ? { position: "absolute", left: "6%", right: "6%", bottom: "11%", display: "grid", gridTemplateColumns: "1fr 1fr", gap: px(2.4 * U) }
    : { display: "grid", gridTemplateColumns: "1fr 1fr", gap: px(1.8 * U) });
  const ic = ["planification", "indicateurs", "beneficiaires", "carte", "plaintes", "langues"];
  const coul = ["var(--safran)", "var(--menthe)", "#7cc4ff", "var(--menthe)", "var(--corail)", "var(--safran)"];
  const pc = t.s4.puces.map((m, i) => el("div", "puce", grillePuces, `${icone(ic[i], coul[i])}<span>${m}</span>`, { fontSize: px((V ? 3.6 : 2.4) * U), whiteSpace: "normal" }));
  tl.fromTo(pc, { opacity: 0, scale: 0.6, y: 30 }, { opacity: 1, scale: 1, y: 0, duration: 0.55, ease: "back.out(1.7)", stagger: (b4 - a4 - 4) / 6 }, a4 + 1.2);
  const larg = V ? 0.94 * W : 0.52 * W;
  const pt = portable(c4, larg, ["tableau-de-bord", "carte"]);
  Object.assign(pt.p.style, V ? { left: `${(W - larg) / 2}px`, top: "31%" } : { insetInlineEnd: "4%", top: "21%" });
  tl.fromTo(pt.p, { opacity: 0, x: (L === "ar" ? -1 : 1) * 20 * U, rotationY: -18, scale: 0.92 }, { opacity: 1, x: 0, rotationY: 0, scale: 1, duration: 1.3, ease: "power3.out" }, a4 + 0.5);
  const milieu = a4 + (b4 - a4) * 0.55;
  tl.fromTo(pt.imgs[0], { scale: 1 }, { scale: 1.18, x: -6 * U, duration: milieu - a4 + 0.6, ease: "none" }, a4);
  tl.fromTo(pt.imgs[1], { opacity: 0, scale: 1.2 }, { opacity: 1, scale: 1, duration: 0.8, ease: "power2.out" }, milieu);
  tl.to(pt.imgs[1], { scale: 1.12, x: -4 * U, y: -6 * U, duration: b4 - milieu, ease: "none" }, milieu + 0.8);
  tl.to(c4, { opacity: 0, duration: 0.4 }, b4 - 0.2);

  // S5 : « Maintenant en ligne », sur fond safran.
  const [a5] = S("s5");
  volet("linear-gradient(135deg, #f8c766 0%, #f4b740 55%, #e9a224 100%)", a5 - 0.35, 0.9);
  const c5 = el("div", "calque centre", scene, "", { gap: px(3 * U), color: "var(--encre)" });
  fenetre(c5, a5, typeof b5 !== "undefined" ? b5 : 30);
  const haut = el("div", "", c5, "", { display: "flex", alignItems: "center", gap: px(2 * U), direction: "ltr" });
  const ps = pastille(haut, 11 * U);
  marque(haut, 4.6 * U, "var(--encre)").querySelector("span").style.color = "var(--bleu-fonce)";
  const enLigne = el("div", "serif", c5, "", { fontSize: px((V ? 12 : 11) * U), lineHeight: 1, maxWidth: "88%" });
  const btn = el("div", "bouton", c5, `<span>${t.s5.bouton}</span>${icone("fleche", "#fff", 2.2)}`);
  const url = el("div", "adresse", c5, "", { fontSize: px(4 * U), direction: "ltr", minHeight: px(5 * U) });
  const sig = signature(c5, "rgba(12,22,34,.75)");
  tl.fromTo(ps, { scale: 0 }, { scale: 1, duration: 0.7, ease: "back.out(2)" }, a5 + 0.3);
  apparaitre(haut.lastChild, a5 + 0.45, { x: (L === "ar" ? -1 : 1) * 4 * U, y: 0 }, 0.7);
  revelerMots(motsMasques(enLigne, t.s5.ecran), a5 + 0.6, 0.9, 0.1);
  tl.fromTo(btn, { scale: 0, opacity: 0 }, { scale: 1, opacity: 1, duration: 0.7, ease: "back.out(2)" }, a5 + 1.5);
  tl.to(btn, { scale: 1.06, duration: 0.45, ease: "sine.inOut", repeat: 3, yoyo: true }, a5 + 2.4);
  frappe(url, T.commun.url, a5 + 2.0, 1.4);
  apparaitre(sig, a5 + 3.0, { y: 20 }, 0.6);
  fin_noire();
}

/* ================================================================ PRÉSENTATION */
const ETAPES = [
  ["s2", "tableau-de-bord", [0.62, 0.3]],
  ["s3", "strategie", [0.55, 0.3]],
  ["s4", "suivi", [0.6, 0.35]],
  ["s5", "carte", [0.6, 0.72]],
  ["s6", "plaintes", [0.7, 0.45]],
];
function presentation() {
  const t = T.presentation;
  fond(["#1f8fc9", "#3ccf9a", "#123d82"]);

  // S1 : titre.
  const [a1, b1] = S("s1");
  const c1 = el("div", "calque centre", scene, "", { gap: px(2.5 * U) });
  fenetre(c1, a1, typeof b1 !== "undefined" ? b1 : 30);
  const titre = el("div", "serif", c1, "", { fontSize: px((V ? 9 : 8.5) * U), lineHeight: 1.05, maxWidth: "86%" });
  revelerMots(motsMasques(titre, t.s1.ecran), a1 + 0.2, 0.8, 0.08);
  const sous = el("div", "", c1, "", { display: "flex", alignItems: "center", gap: px(1.5 * U), fontSize: px(3.4 * U), color: "var(--menthe)", fontWeight: 600 });
  sous.innerHTML = `<svg viewBox="0 0 40 40" width="${4.6 * U}" height="${4.6 * U}"><circle cx="20" cy="20" r="16" fill="none" stroke="rgba(255,255,255,.2)" stroke-width="4"/><circle id="minuteur" cx="20" cy="20" r="16" fill="none" stroke="#3ccf9a" stroke-width="4" stroke-linecap="round" stroke-dasharray="100.5" stroke-dashoffset="100.5" transform="rotate(-90 20 20)"/></svg><span>${t.s1.sous}</span>`;
  apparaitre(sous, a1 + 0.9, { y: 20 }, 0.6);
  tl.to("#minuteur", { strokeDashoffset: 0, duration: 1.6, ease: "power2.inOut" }, a1 + 1.0);
  tl.to(c1, { opacity: 0, y: -6 * U, duration: 0.45, ease: "power2.in" }, b1 - 0.45);

  // Écran (ordinateur en paysage, carte arrondie en portrait) et légendes.
  const [debutEtapes] = S("s2");
  const [, finEtapes] = S("s6");
  let cadre, vue;
  const largeurEcran = V ? 0.88 * W : 0.6 * W;
  if (V) {
    cadre = el("div", "carte-ecran", scene, "", { left: `${(W - largeurEcran) / 2}px`, top: "7%", width: px(largeurEcran), height: px(0.56 * H) });
    vue = cadre;
  } else {
    const p = portable(scene, largeurEcran, []);
    Object.assign(p.p.style, { insetInlineEnd: "5%", top: "13%" });
    cadre = p.p;
    vue = p.vue;
  }
  tl.fromTo(cadre, { opacity: 0, y: 12 * U, scale: 0.9 }, { opacity: 1, y: 0, scale: 1, duration: 1, ease: "power3.out" }, debutEtapes - 0.2);
  tl.to(cadre, { opacity: 0, scale: 0.92, y: -4 * U, duration: 0.5, ease: "power2.in" }, finEtapes - 0.35);

  const zoneLegende = el("div", "", scene, "", V
    ? { position: "absolute", left: "8%", right: "8%", top: "68%" }
    : { position: "absolute", insetInlineStart: "6%", top: "32%", width: "28%" });
  const barre = el("div", "barre-etapes", scene, "", V
    ? { position: "absolute", left: "8%", right: "8%", bottom: "6%" }
    : { position: "absolute", insetInlineStart: "6%", bottom: "12%", width: "28%" });
  const segments = ETAPES.map(() => { const i = el("i", "", barre, "<b></b>", { flex: 1 }); return i.firstChild; });
  apparaitre(barre, debutEtapes, { y: 10 }, 0.5);
  disparaitre(barre, finEtapes - 0.3, { y: 10 }, 0.4);

  ETAPES.forEach(([k, image, focus], i) => {
    const [a, b] = S(k);
    // Image : glisse en entrée, puis lent zoom vers la zone utile (effet « Ken Burns »).
    const im = el("img", "", vue, "", V ? { height: "100%", width: "auto" } : {});
    im.src = `../ecrans/${L}/${image}.png`;
    const largeurVue = largeurEcran - (V ? 0 : 2 * U);
    const hauteurVue = V ? 0.56 * H : largeurVue * 10 / 16;
    const largeurImage = V ? hauteurVue * 1.6 : largeurVue;
    const decalage = V ? -Math.min(largeurImage - largeurVue, Math.max(0, focus[0] * largeurImage - largeurVue / 2)) : 0;
    const zoom = 1.32;
    const cibleX = decalage - (focus[0] * largeurImage) * (zoom - 1) * 0.6;
    const cibleY = -(focus[1] * hauteurVue) * (zoom - 1) * 0.6;
    tl.set(im, { opacity: 0 }, 0);
    tl.fromTo(im, { opacity: 0, x: decalage + (L === "ar" ? -1 : 1) * 10 * U, scale: 1.04 }, { opacity: 1, x: decalage, scale: 1, duration: 0.7, ease: "power3.out" }, a);
    tl.to(im, { x: cibleX, y: cibleY, scale: zoom, duration: b - a - 0.4, ease: "sine.inOut" }, a + 0.7);
    if (i < ETAPES.length - 1) tl.to(im, { opacity: 0, duration: 0.4 }, b + 0.3);
    // Légende : numéro et texte.
    const lg = el("div", "", zoneLegende, "", { position: "absolute", inset: 0 });
    const num = el("div", "numero", lg, String(i + 1).padStart(2, "0"), { fontSize: px((V ? 7 : 6) * U), lineHeight: 1 });
    const txt = el("div", "serif", lg, "", { fontSize: px((V ? 6 : 4.8) * U), lineHeight: 1.1, marginTop: px(1.5 * U) });
    apparaitre(num, a + 0.1, { y: 20 }, 0.5);
    revelerMots(motsMasques(txt, t[k].ecran), a + 0.2, 0.7, 0.06);
    tl.to(lg, { opacity: 0, y: -3 * U, duration: 0.35, ease: "power2.in" }, b - 0.3);
    tl.fromTo(segments[i], { width: "0%" }, { width: "100%", duration: b - a, ease: "none" }, a);
  });

  // S7 : signature finale.
  const [a7] = S("s7");
  const c7 = el("div", "calque centre", scene, "", { gap: px(3 * U) });
  fenetre(c7, a7, typeof b7 !== "undefined" ? b7 : 30);
  const pa = pastille(c7, 20 * U);
  const m = marque(c7, (V ? 7.5 : 7) * U);
  const sl = el("div", "", c7, "", { fontSize: px(3.6 * U), color: "rgba(255,255,255,.85)" });
  const mots = motsMasques(sl, T.commun.slogan);
  const url = el("div", "adresse", c7, T.commun.url, { fontSize: px(3.4 * U), color: "var(--safran)", direction: "ltr" });
  tl.fromTo(pa, { scale: 0, rotation: -90 }, { scale: 1, rotation: 0, duration: 0.9, ease: "back.out(1.7)" }, a7 + 0.1);
  apparaitre(m, a7 + 0.5, { y: 30 }, 0.7);
  revelerMots(mots, a7 + 0.9, 0.6, 0.12);
  apparaitre(url, a7 + 1.6, { y: 15 }, 0.6);
  fin_noire();
}

/* ================================================================ OFFRES */
function offres() {
  const t = T.offres;
  fond(["#f4b740", "#3ccf9a", "#1f8fc9"]);

  // S1 : la question.
  const [a1, b1] = S("s1");
  const c1 = el("div", "calque centre", scene);
  fenetre(c1, a1, typeof b1 !== "undefined" ? b1 : 30);
  const qbloc = el("div", "", c1, "", { display: "flex", alignItems: "center", gap: px(4 * U), flexDirection: V ? "column" : "row", maxWidth: "88%" });
  const q = el("div", "serif", qbloc, "", { fontSize: px((V ? 8 : 7) * U), lineHeight: 1.08 });
  revelerMots(motsMasques(q, t.s1.ecran), a1 + 0.2, 0.75, 0.06);
  const point = el("div", "serif italique", qbloc, "?", { fontSize: px(26 * U), color: "var(--safran)", lineHeight: 0.8, order: V ? -1 : 0 });
  tl.fromTo(point, { scale: 0, rotation: -180 }, { scale: 1, rotation: 12, duration: 1, ease: "back.out(1.8)" }, a1 + 0.6);
  tl.to(point, { rotation: -8, duration: 0.9, ease: "sine.inOut", repeat: 2, yoyo: true }, a1 + 1.6);
  tl.to(c1, { opacity: 0, y: -8 * U, duration: 0.45, ease: "power2.in" }, b1 - 0.45);

  // S2 : la réponse, soulignée.
  const [a2, b2] = S("s2");
  const c2 = el("div", "calque centre", scene);
  fenetre(c2, a2, typeof b2 !== "undefined" ? b2 : 30);
  const rep = el("div", "serif italique", c2, "", { fontSize: px((V ? 10 : 9) * U), color: "var(--menthe)", maxWidth: "88%", lineHeight: 1.05 });
  revelerMots(motsMasques(rep, t.s2.ecran), a2 + 0.1, 0.7, 0.07);
  const trait = el("div", "", c2, `<svg viewBox="0 0 300 20" width="${50 * U}" height="${3.4 * U}"><path id="trait" d="M5 14 C 80 4, 180 4, 295 12" fill="none" stroke="#f4b740" stroke-width="6" stroke-linecap="round" pathLength="1" stroke-dasharray="1" stroke-dashoffset="1"/></svg>`, { marginTop: px(2 * U) });
  tl.to("#trait", { strokeDashoffset: 0, duration: 0.8, ease: "power2.inOut" }, a2 + 0.9);
  tl.to(c2, { opacity: 0, scale: 0.9, duration: 0.4, ease: "power2.in" }, b2 - 0.4);

  // S3 : les trois offres, prix qui défilent.
  const [a3, b3] = S("s3");
  const c3 = el("div", "calque centre", scene);
  fenetre(c3, a3, typeof b3 !== "undefined" ? b3 : 30);
  const rangee = el("div", "", c3, "", V
    ? { display: "flex", flexDirection: "column", gap: px(3 * U), width: "86%" }
    : { display: "flex", gap: px(3 * U), width: "86%", alignItems: "stretch" });
  const OFFRES = [["25", 34, "20 000"], ["50", 52, "30 000"], ["100", 86, "50 000"]];
  const pas = (b3 - a3 - 1.2) / 3;
  OFFRES.forEach(([go, usd, fcfa], i) => {
    const c = el("div", `prix ${i === 1 ? "vedette" : ""}`, rangee, "", V
      ? { display: "grid", gridTemplateColumns: "1fr auto", alignItems: "center", gap: px(1.2 * U) }
      : { flex: 1, display: "flex", flexDirection: "column", gap: px(1.6 * U) });
    el("div", "go", c, `Standard ${go} Go`, { fontSize: px((V ? 4 : 3.6) * U), direction: "ltr", textAlign: "start" });
    const ligne = el("div", "", c, "", { display: "flex", alignItems: "baseline", gap: px(1 * U), direction: "ltr", justifyContent: V ? "flex-end" : "flex-start" });
    const m = el("span", "montant", ligne, "0", { fontSize: px((V ? 11 : 13) * U) });
    el("span", "montant", ligne, "$", { fontSize: px((V ? 6 : 7) * U), color: "var(--safran)" });
    el("div", "fcfa", c, `<bdi dir="ltr">${fcfa} FCFA</bdi> · ${t.s3.par_mois}`, { fontSize: px((V ? 3 : 2.8) * U), gridColumn: V ? "1 / -1" : "auto" });
    const j = el("div", "jauge", c, "<b></b>", { gridColumn: V ? "1 / -1" : "auto" });
    const quand = a3 + 0.3 + i * pas;
    tl.fromTo(c, { opacity: 0, y: 10 * U, rotationX: 35 }, { opacity: 1, y: 0, rotationX: 0, duration: 0.8, ease: "power3.out" }, quand);
    compteur(m, usd, quand + 0.2, 1.0);
    tl.fromTo(j.firstChild, { width: "0%" }, { width: `${[25, 50, 100][i]}%`, duration: 1.1, ease: "power2.out" }, quand + 0.3);
  });
  tl.to(rangee.children, { opacity: 0, y: -6 * U, duration: 0.4, ease: "power2.in", stagger: 0.05 }, b3 - 0.5);

  // S4 : paiement et mise en service.
  const [a4, b4] = S("s4");
  const c4 = el("div", "calque centre", scene);
  fenetre(c4, a4, typeof b4 !== "undefined" ? b4 : 30);
  const grille = el("div", "", c4, "", { display: "grid", gridTemplateColumns: V ? "1fr" : "1fr 1fr", gap: px(4 * U), width: V ? "84%" : "82%" });
  const ic = [["telephone", "var(--menthe)"], ["carteBancaire", "var(--safran)"], ["horloge", "#7cc4ff"], ["formation", "var(--corail)"]];
  const items = t.s4.points.map((txt, i) => {
    const it = el("div", "", grille, "", { display: "flex", alignItems: "center", gap: px(2.4 * U) });
    el("div", "icone-rond", it, icone(ic[i][0], ic[i][1], 2), { width: px(11 * U), height: px(11 * U), flex: "none", background: "rgba(255,255,255,.08)", border: "1px solid rgba(255,255,255,.18)" });
    el("div", "", it, txt, { fontSize: px((V ? 4.4 : 4) * U), fontWeight: 600, lineHeight: 1.15 });
    return it;
  });
  tl.fromTo(items, { opacity: 0, scale: 0.7, y: 4 * U }, { opacity: 1, scale: 1, y: 0, duration: 0.6, ease: "back.out(1.8)", stagger: Math.min(0.6, (b4 - a4 - 1.5) / 4) }, a4 + 0.2);
  tl.to(items, { opacity: 0, x: (L === "ar" ? 1 : -1) * 6 * U, duration: 0.35, ease: "power2.in", stagger: 0.04 }, b4 - 0.45);

  // S5 : inscription.
  const [a5] = S("s5");
  volet("linear-gradient(135deg, #3ccf9a 0%, #1fae7d 60%, #148a62 100%)", a5 - 0.35, 0.9);
  const c5 = el("div", "calque centre", scene, "", { gap: px(3.2 * U), color: "var(--encre)" });
  fenetre(c5, a5, typeof b5 !== "undefined" ? b5 : 30);
  const ps = pastille(c5, 14 * U);
  const ins = el("div", "serif", c5, "", { fontSize: px((V ? 12 : 11) * U), lineHeight: 1 });
  const boite = el("div", "bouton", c5, `<span class="adresse" style="direction:ltr"></span>${icone("fleche", "#fff", 2.2)}`, { fontSize: px(3.6 * U) });
  const sig = signature(c5, "rgba(12,22,34,.75)");
  tl.fromTo(ps, { scale: 0, rotation: -90 }, { scale: 1, rotation: 0, duration: 0.8, ease: "back.out(1.8)" }, a5 + 0.3);
  revelerMots(motsMasques(ins, t.s5.ecran), a5 + 0.55, 0.8, 0.1);
  tl.fromTo(boite, { scale: 0, opacity: 0 }, { scale: 1, opacity: 1, duration: 0.7, ease: "back.out(2)" }, a5 + 1.2);
  frappe(boite.firstChild, T.commun.url, a5 + 1.6, 1.4);
  tl.to(boite, { scale: 1.05, duration: 0.45, ease: "sine.inOut", repeat: 3, yoyo: true }, a5 + 3.1);
  apparaitre(sig, a5 + 2.4, { y: 20 }, 0.6);
  fin_noire();
}

({ lancement, presentation, offres })[VIDEO]();
tl.set({}, {}, 30);

window.duree = 30;
window.seek = (t) => {
  tl.seek(t, false);
  actions.forEach((a) => a(t));
};
window.pret = (async () => {
  await document.fonts.ready;
  await Promise.all([...document.images].map((im) => (im.complete ? im.decode().catch(() => {}) : new Promise((r) => { im.onload = im.onerror = r; }))));
  window.seek(0);
  return true;
})();
