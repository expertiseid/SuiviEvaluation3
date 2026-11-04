/*
 * Langues du site vitrine (les mêmes que la plateforme) : français, anglais, arabe, espagnol, allemand.
 *
 * Les pages sont écrites en français ; chaque traduction est cherchée par son texte français dans
 * window.TRADUCTIONS_SITE[langue] (vitrine/traductions.js). Un « bloc » est le plus grand élément dont
 * tout le contenu est du texte et des balises de mise en forme (b, a, span…) : il est traduit d'un
 * seul tenant (son HTML), ce qui garde le gras et les liens. S'y ajoutent les textes isolés à côté
 * d'une icône, les attributs (placeholder, alt, title, aria-label), le titre et la description.
 *
 * Choix : sélecteur dans l'en-tête, gardé dans le navigateur (localStorage) ; à la première visite,
 * la langue du navigateur si elle est proposée. ?lang=en dans l'adresse force une langue.
 * window.traduire(texte) traduit aussi les messages affichés par les scripts (inscription).
 */
(function () {
  var LANGUES = [["fr", "Français"], ["en", "English"], ["ar", "العربية"], ["es", "Español"], ["de", "Deutsch"]];
  var CLE = "langue-site";
  var EN_LIGNE = { B: 1, STRONG: 1, I: 1, EM: 1, A: 1, SPAN: 1, CODE: 1, BR: 1, SMALL: 1, SUP: 1, SUB: 1, ABBR: 1, U: 1, MARK: 1 };
  var IGNORES = { SCRIPT: 1, STYLE: 1, SVG: 1, VIDEO: 1, NOSCRIPT: 1, SELECT: 0, TEXTAREA: 1 };
  var ATTRIBUTS = ["placeholder", "alt", "title", "aria-label"];
  var normaliser = function (t) { return t.replace(/\s+/g, " ").trim(); };

  var langue = "fr";
  var dico = function () { return (window.TRADUCTIONS_SITE || {})[langue] || {}; };
  window.traduire = function (texte) { return (langue !== "fr" && dico()[normaliser(texte)]) || texte; };

  // Relevé des éléments à traduire (une fois) : [élément, clé française, type].
  var releves = null;
  function estBloc(el) {
    if (!normaliser(el.textContent)) return false;
    var tous = el.getElementsByTagName("*");
    for (var i = 0; i < tous.length; i++) if (!EN_LIGNE[tous[i].tagName]) return false;
    return true;
  }
  function visiter(el, sortie) {
    if (IGNORES[el.tagName] || el.hasAttribute("data-sans-traduction")) return;
    ATTRIBUTS.forEach(function (a) {
      var v = el.getAttribute(a);
      if (v && normaliser(v)) sortie.push([el, normaliser(v), "attr:" + a]);
    });
    if (el !== document.body && estBloc(el)) { sortie.push([el, normaliser(el.innerHTML), "html"]); return; }
    for (var n = el.firstChild; n; n = n.nextSibling) {
      if (n.nodeType === 3 && normaliser(n.nodeValue)) sortie.push([n, normaliser(n.nodeValue), "texte"]);
      else if (n.nodeType === 1) visiter(n, sortie);
    }
  }
  function relever() {
    if (releves) return releves;
    // Listes déroulantes : la valeur envoyée reste le texte français, quelle que soit la langue affichée.
    document.querySelectorAll("option:not([value])").forEach(function (o) { o.value = o.textContent; });
    releves = [];
    visiter(document.body, releves);
    var meta = document.querySelector("meta[name='description']");
    if (meta) releves.push([meta, normaliser(meta.getAttribute("content")), "attr:content"]);
    releves.push([document, normaliser(document.title), "titre"]);
    return releves;
  }
  // Textes français de la page (pour préparer traductions.js).
  window.textesDuSite = function () {
    var vus = {};
    return relever().map(function (r) { return r[1]; }).filter(function (k) { return k && !vus[k] && (vus[k] = 1); });
  };

  function appliquer(code) {
    langue = code;
    var d = dico();
    relever().forEach(function (r) {
      var el = r[0], fr = r[1], type = r[2], t = (code !== "fr" && d[fr]) || null;
      if (type === "html") el.innerHTML = t || fr;
      else if (type === "texte") el.nodeValue = " " + (t || fr) + " ";
      else if (type === "titre") document.title = t || fr;
      else el.setAttribute(type.slice(5), t || fr);
    });
    document.documentElement.lang = code;
    document.documentElement.dir = code === "ar" ? "rtl" : "ltr";
    var choix = document.getElementById("choix-langue");
    if (choix) choix.value = code;
    document.dispatchEvent(new CustomEvent("langue-site", { detail: code }));
  }

  function langueVoulue() {
    var codes = LANGUES.map(function (l) { return l[0]; });
    var dansAdresse = new URLSearchParams(window.location.search).get("lang");
    if (codes.indexOf(dansAdresse) !== -1) return dansAdresse;
    try { var gardee = localStorage.getItem(CLE); if (codes.indexOf(gardee) !== -1) return gardee; } catch (e) { /* rien */ }
    var nav = (navigator.language || "fr").slice(0, 2).toLowerCase();
    return codes.indexOf(nav) !== -1 ? nav : "fr";
  }

  // Sélecteur de langue dans l'en-tête (visible aussi sur téléphone).
  function ajouterSelecteur() {
    var conteneur = document.querySelector(".entete .conteneur");
    if (!conteneur) return;
    var select = document.createElement("select");
    select.id = "choix-langue";
    select.className = "choix-langue";
    select.setAttribute("data-sans-traduction", "");
    select.setAttribute("aria-label", "Langue / Language");
    LANGUES.forEach(function (l) { var o = document.createElement("option"); o.value = l[0]; o.textContent = l[1]; select.appendChild(o); });
    select.addEventListener("change", function () {
      try { localStorage.setItem(CLE, select.value); } catch (e) { /* rien */ }
      appliquer(select.value);
    });
    // Avant le bouton du menu de téléphone (caché sur ordinateur) : à droite de l'en-tête.
    conteneur.insertBefore(select, conteneur.querySelector(".bascule"));
  }

  relever();  // avant d'ajouter le sélecteur : ses noms de langues ne se traduisent pas
  ajouterSelecteur();
  var code = langueVoulue();
  if (code !== "fr") appliquer(code);
  else { var c = document.getElementById("choix-langue"); if (c) c.value = "fr"; }
})();
