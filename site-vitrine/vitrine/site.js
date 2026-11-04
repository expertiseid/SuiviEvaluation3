/* Comportements communs du site vitrine : en-tête, menu, apparitions, liens, vidéo, documentation. */
(function () {
  var S = window.SITE || {};

  // Liens vers la plateforme (démo, connexion) : réglés dans config.js, avec la langue choisie sur le
  // site (la démo et la connexion s'ouvrent dans cette langue). Refaits après un changement de langue.
  function majLiens() {
    var langue = document.documentElement.lang || "fr";
    document.querySelectorAll("[data-lien]").forEach(function (a) {
      var cible = S[a.getAttribute("data-lien")];
      if (cible) a.setAttribute("href", cible + (cible.indexOf("?") === -1 ? "?" : "&") + "lang=" + langue);
    });
  }
  majLiens();
  document.addEventListener("langue-site", majLiens);

  // En-tête : trait sous l'en-tête une fois la page défilée ; menu sur téléphone.
  var entete = document.querySelector(".entete");
  var majEntete = function () { if (entete) entete.classList.toggle("defile", window.scrollY > 8); };
  window.addEventListener("scroll", majEntete, { passive: true });
  majEntete();
  var bascule = document.querySelector(".bascule");
  var menu = document.querySelector(".menu");
  if (bascule && menu) {
    bascule.addEventListener("click", function () {
      var ouvert = menu.classList.toggle("ouvert");
      bascule.setAttribute("aria-expanded", ouvert ? "true" : "false");
    });
    menu.querySelectorAll("a").forEach(function (a) { a.addEventListener("click", function () { menu.classList.remove("ouvert"); }); });
  }

  // Apparition douce des blocs au défilement.
  if ("IntersectionObserver" in window) {
    var obs = new IntersectionObserver(function (entrees) {
      entrees.forEach(function (e) { if (e.isIntersecting) { e.target.classList.add("vu"); obs.unobserve(e.target); } });
    }, { threshold: 0.12 });
    document.querySelectorAll(".apparait").forEach(function (el) { obs.observe(el); });
  } else {
    document.querySelectorAll(".apparait").forEach(function (el) { el.classList.add("vu"); });
  }

  // Vidéo : boutons de chapitres.
  var video = document.querySelector(".lecteur video");
  document.querySelectorAll("[data-temps]").forEach(function (b) {
    b.addEventListener("click", function () {
      if (!video) return;
      video.currentTime = Number(b.getAttribute("data-temps"));
      video.play();
    });
  });

  // Documentation : agrandir une capture.
  var zoom = document.querySelector(".zoom");
  if (zoom) {
    var imageZoom = zoom.querySelector("img");
    document.querySelectorAll(".contenu-doc figure img").forEach(function (img) {
      img.addEventListener("click", function () { imageZoom.src = img.src; imageZoom.alt = img.alt; zoom.classList.add("ouvert"); });
    });
    zoom.addEventListener("click", function () { zoom.classList.remove("ouvert"); });
    document.addEventListener("keydown", function (e) { if (e.key === "Escape") zoom.classList.remove("ouvert"); });
  }

  // Documentation : rubrique en cours surlignée dans le sommaire, et recherche dans le sommaire.
  var liens = Array.prototype.slice.call(document.querySelectorAll(".sommaire a[href^='#']"));
  if (liens.length && "IntersectionObserver" in window) {
    var parId = {};
    liens.forEach(function (a) { parId[a.getAttribute("href").slice(1)] = a; });
    var suivi = new IntersectionObserver(function (entrees) {
      entrees.forEach(function (e) {
        if (!e.isIntersecting) return;
        liens.forEach(function (a) { a.classList.remove("actif"); });
        var lien = parId[e.target.id];
        if (lien) lien.classList.add("actif");
      });
    }, { rootMargin: "-20% 0px -70% 0px" });
    document.querySelectorAll(".contenu-doc section[id]").forEach(function (s) { suivi.observe(s); });
  }
  var recherche = document.querySelector(".sommaire input");
  if (recherche) {
    var sans = function (t) { return t.normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase(); };
    recherche.addEventListener("input", function () {
      var q = sans(recherche.value.trim());
      document.querySelectorAll(".contenu-doc section[id]").forEach(function (s) {
        var visible = !q || sans(s.textContent).indexOf(q) !== -1;
        s.classList.toggle("cache", !visible);
        var lien = document.querySelector(".sommaire a[href='#" + s.id + "']");
        if (lien) lien.classList.toggle("cache", !visible);
      });
    });
  }
})();
