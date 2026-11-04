/*
 * Pages « Notre actualité » et « Nos partenaires » : contenus gérés par Expertise-ID dans la console
 * de la plateforme, lus ici dans la langue choisie (le français si la traduction manque).
 * actualites.html?id=12 : une actualité en entier.
 */
(function () {
  var S = window.SITE || {};
  var T = function (t) { return window.traduire ? window.traduire(t) : t; };
  var langue = function () { return document.documentElement.lang || "fr"; };
  var echapper = function (t) {
    return String(t == null ? "" : t).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  };
  var dateLongue = function (d) {
    try { return new Date(d + "T12:00:00").toLocaleDateString(langue(), { day: "numeric", month: "long", year: "numeric" }); }
    catch (e) { return d; }
  };
  var lire = function (chemin) {
    var sep = chemin.indexOf("?") === -1 ? "?" : "&";
    return fetch(S.API + chemin + sep + "langue=" + langue()).then(function (r) {
      if (!r.ok) throw new Error(r.status);
      return r.json();
    });
  };
  var message = function (el, texte) { el.innerHTML = '<p class="vide">' + echapper(T(texte)) + "</p>"; };

  // --- Actualités ---
  var liste = document.getElementById("liste-actualites");
  var detail = document.getElementById("detail-actualite");
  function afficherActualites() {
    var id = new URLSearchParams(window.location.search).get("id");
    if (id) {
      liste.classList.add("cache");
      detail.classList.remove("cache");
      lire("/public/site/actualites/" + encodeURIComponent(id) + "/").then(function (a) {
        var paragraphes = (a.contenu || "").split(/\n\s*\n/).filter(Boolean).map(function (p) {
          return "<p>" + echapper(p).replace(/\n/g, "<br>") + "</p>";
        }).join("");
        detail.innerHTML =
          '<a class="retour" href="actualites.html">← ' + echapper(T("Toutes les actualités")) + "</a>" +
          '<p class="date">' + echapper(dateLongue(a.date)) + "</p>" +
          "<h2>" + echapper(a.titre) + "</h2>" +
          (a.resume ? '<p class="chapeau">' + echapper(a.resume) + "</p>" : "") +
          (a.image ? '<img src="' + echapper(a.image) + '" alt="">' : "") +
          '<div class="texte">' + paragraphes + "</div>" +
          (a.lien ? '<p><a class="bouton bouton-plein" href="' + echapper(a.lien) + '" target="_blank" rel="noopener">' + echapper(T("En savoir plus")) + " ↗</a></p>" : "");
        document.title = a.titre + " — Expertise-ID Monitora";
      }).catch(function () { message(detail, "Cette actualité n'existe pas ou n'est plus publiée."); });
      return;
    }
    lire("/public/site/actualites/").then(function (actus) {
      if (!actus.length) { message(liste, "Aucune actualité pour le moment : revenez bientôt."); return; }
      liste.innerHTML = actus.map(function (a) {
        return '<a class="actualite" href="actualites.html?id=' + a.id + '">' +
          (a.image ? '<img src="' + echapper(a.image) + '" alt="" loading="lazy">' : '<div class="sans-image"></div>') +
          '<div class="corps"><p class="date">' + echapper(dateLongue(a.date)) + "</p>" +
          "<h3>" + echapper(a.titre) + "</h3>" +
          (a.resume ? "<p>" + echapper(a.resume) + "</p>" : "") +
          '<span class="suite">' + echapper(T("Lire la suite")) + " →</span></div></a>";
      }).join("");
    }).catch(function () { message(liste, "Les actualités ne peuvent pas être chargées pour le moment."); });
  }

  // --- Partenaires ---
  var partenaires = document.getElementById("liste-partenaires");
  var CATEGORIES = [["FINANCIER", "Partenaires financiers"], ["TECHNIQUE", "Partenaires techniques"],
    ["INSTITUTION", "Institutions"], ["CLIENT", "Organisations utilisatrices"]];
  function afficherPartenaires() {
    lire("/public/site/partenaires/").then(function (tous) {
      if (!tous.length) { message(partenaires, "La liste de nos partenaires sera bientôt en ligne."); return; }
      partenaires.innerHTML = CATEGORIES.map(function (c) {
        var groupe = tous.filter(function (p) { return p.categorie === c[0]; });
        if (!groupe.length) return "";
        return '<section class="groupe-partenaires"><h2>' + echapper(T(c[1])) + '</h2><div class="grille-partenaires">' +
          groupe.map(function (p) {
            var logo = p.logo ? '<img src="' + echapper(p.logo) + '" alt="' + echapper(p.nom) + '" loading="lazy">' : '<div class="initiale">' + echapper(p.nom.charAt(0)) + "</div>";
            var contenu = logo + "<h3>" + echapper(p.nom) + "</h3>" + (p.description ? "<p>" + echapper(p.description) + "</p>" : "");
            return p.site_web
              ? '<a class="partenaire" href="' + echapper(p.site_web) + '" target="_blank" rel="noopener">' + contenu + "</a>"
              : '<div class="partenaire">' + contenu + "</div>";
          }).join("") + "</div></section>";
      }).join("");
    }).catch(function () { message(partenaires, "La liste des partenaires ne peut pas être chargée pour le moment."); });
  }

  var afficher = function () {
    if (liste) afficherActualites();
    if (partenaires) afficherPartenaires();
  };
  afficher();
  document.addEventListener("langue-site", afficher);
})();
