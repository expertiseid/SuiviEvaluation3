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

  // Année du pied de page, remise après chaque changement de langue.
  // Prix des offres (page d'accueil) en dollars, avec l'équivalent en FCFA : envoyés par la plateforme (ABONNEMENT_PRIX_*).
  // Les prix ne passent pas par la traduction des blocs (data-sans-traduction) : réécrits ici à chaque changement de langue.
  var tarifs = null;
  function chiffres(n) { return String(n).replace(/\B(?=(\d{3})+(?!\d))/g, " "); }
  function majTarifs() {
    var T = function (t) { return window.traduire ? window.traduire(t) : t; };
    majPopulaire(T);
    // Plateforme injoignable (site seul en ligne) : prix écrits dans la page, seul « HT par mois » est traduit.
    if (!tarifs || !tarifs.usd) {
      document.querySelectorAll(".prix[data-tarif] small").forEach(function (s) { s.textContent = T("HT par mois"); });
      return;
    }
    var prix = { mois: [tarifs.mois, tarifs.usd.mois] };
    Object.keys(tarifs.offres || {}).forEach(function (code) { prix[code] = [tarifs.offres[code].mois, tarifs.offres[code].usd]; });
    Object.keys(prix).forEach(function (code) {
      document.querySelectorAll("[data-tarif='" + code + "']").forEach(function (p) {
        p.innerHTML = chiffres(prix[code][1]) + " $ <small>" + T("HT par mois") + "</small><span class=\"prix-dollars\">" + chiffres(prix[code][0]) + " FCFA</span>";
      });
    });
    document.querySelectorAll("[data-tarif='tranche'] b").forEach(function (b) {
      b.textContent = "+ " + chiffres(tarifs.usd.tranche) + " $ (" + chiffres(tarifs.tranche) + " FCFA) " + T("HT pour chaque tranche de 10 Go ajoutée");
    });
  }
  // Offre la plus achetée (« populaire », calculée par la plateforme) : bordure et étiquette sur sa carte.
  function majPopulaire(T) {
    document.querySelectorAll(".offre .ruban-populaire").forEach(function (r) { r.remove(); });
    document.querySelectorAll(".offre.populaire").forEach(function (o) { o.classList.remove("populaire"); });
    var code = tarifs && tarifs.populaire;
    var prix = code && document.querySelector(".offre [data-tarif='" + (code === "STANDARD" ? "mois" : code) + "']");
    var carte = prix && prix.closest(".offre");
    if (!carte) return;
    var ruban = document.createElement("span");
    ruban.className = "ruban-populaire";
    ruban.textContent = T("La plus populaire");
    carte.classList.add("populaire");
    carte.insertBefore(ruban, carte.firstChild);
  }
  if (document.querySelector("[data-tarif]")) {
    fetch(S.API + "/public/inscription/tarifs/").then(function (r) { return r.json(); })
      .then(function (t) { tarifs = t; majTarifs(); }).catch(majTarifs);
    document.addEventListener("langue-site", majTarifs);
  }

  // Cookies de mesure d'audience et de publicité : seulement avec l'accord du visiteur (bandeau à la première
  // visite, bouton « Modifier mon choix » de la page Cookies). Le choix est gardé dans ce navigateur ; un outil
  // de mesure ou de publicité ajouté au site doit d'abord vérifier window.cookiesAcceptes().
  var CLE_COOKIES = "cookies-site";
  function choixCookies() { try { return localStorage.getItem(CLE_COOKIES); } catch (e) { return null; } }
  window.cookiesAcceptes = function () { return choixCookies() === "accepte"; };
  function majEtatCookies() {
    var T = function (t) { return window.traduire ? window.traduire(t) : t; };
    var choix = choixCookies();
    document.querySelectorAll(".etat-cookies").forEach(function (e) {
      e.textContent = choix ? T(choix === "accepte" ? "Votre choix : cookies acceptés." : "Votre choix : cookies refusés.") : "";
    });
  }
  function bandeauCookies() {
    var T = function (t) { return window.traduire ? window.traduire(t) : t; };
    var ancien = document.getElementById("bandeau-cookies");
    if (ancien) ancien.remove();
    var bandeau = document.createElement("div");
    bandeau.id = "bandeau-cookies";
    bandeau.className = "bandeau-cookies";
    bandeau.setAttribute("role", "region");
    bandeau.setAttribute("aria-label", T("Choix des cookies"));
    var texte = document.createElement("p");
    texte.textContent = T("Nous utilisons des cookies de mesure d'audience et de publicité seulement si vous l'acceptez.") + " ";
    var lien = document.createElement("a");
    lien.href = "cookies.html";
    lien.textContent = T("En savoir plus");
    texte.appendChild(lien);
    var actions = document.createElement("div");
    actions.className = "actions";
    [["refuse", "Refuser", "bouton-contour"], ["accepte", "Accepter", "bouton-plein"]].forEach(function (c) {
      var bouton = document.createElement("button");
      bouton.type = "button";
      bouton.className = "bouton " + c[2];
      bouton.textContent = T(c[1]);
      bouton.addEventListener("click", function () {
        try { localStorage.setItem(CLE_COOKIES, c[0]); } catch (e) { /* navigation privée : le bandeau reviendra */ }
        bandeau.remove();
        majEtatCookies();
        document.dispatchEvent(new CustomEvent("cookies-choix", { detail: c[0] }));
      });
      actions.appendChild(bouton);
    });
    bandeau.appendChild(texte);
    bandeau.appendChild(actions);
    document.body.appendChild(bandeau);
  }
  if (!choixCookies()) bandeauCookies();
  document.querySelectorAll(".choix-cookies").forEach(function (b) {
    var etat = document.createElement("span");
    etat.className = "etat-cookies";
    b.parentNode.appendChild(etat);
    b.addEventListener("click", bandeauCookies);
  });
  majEtatCookies();
  document.addEventListener("langue-site", function () {
    if (document.getElementById("bandeau-cookies")) bandeauCookies();
    majEtatCookies();
  });

  // Newsletter (pied de chaque page et page newsletter.html) : inscription avec confirmation par courriel ;
  // les liens des courriels ouvrent newsletter.html?confirmer=… ou ?desinscrire=….
  function envoyerNewsletter(chemin, corps) {
    return fetch(S.API + "/public/site/newsletter/" + chemin, {
      method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(corps),
    }).then(function (r) {
      return r.json().catch(function () { return {}; }).then(function (d) { return { ok: r.ok, statut: r.status, donnees: d }; });
    });
  }
  function premierMessage(d) {
    var champ = d.courriel || d.accord || d.detail || d.jeton;
    return Array.isArray(champ) ? champ[0] : champ;
  }
  document.querySelectorAll(".form-newsletter").forEach(function (form) {
    var message = form.querySelector(".message-newsletter");
    var montrer = function (texte, erreur) { message.textContent = texte; message.classList.toggle("erreur", !!erreur); };
    form.addEventListener("submit", function (ev) {
      ev.preventDefault();
      var T = function (t) { return window.traduire ? window.traduire(t) : t; };
      var courriel = form.courriel.value.trim();
      if (!/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(courriel)) { montrer(T("Indiquez une adresse courriel valide."), true); return; }
      if (!form.accord.checked) { montrer(T("Votre accord est nécessaire pour recevoir la newsletter."), true); return; }
      var bouton = form.querySelector("button");
      bouton.disabled = true;
      montrer(T("Envoi en cours…"));
      envoyerNewsletter("", { courriel: courriel, accord: true, langue: document.documentElement.lang || "fr", site_web: form.site_web.value })
        .then(function (r) {
          if (r.ok) { montrer(T(r.donnees.detail)); form.courriel.value = ""; form.accord.checked = false; }
          else if (r.statut === 429) montrer(T("Trop d'envois depuis votre connexion : réessayez dans un moment."), true);
          else montrer(T(premierMessage(r.donnees) || "La demande n'a pas pu être envoyée. Vérifiez votre connexion, puis réessayez."), true);
        })
        .catch(function () { montrer(T("La demande n'a pas pu être envoyée. Vérifiez votre connexion, puis réessayez."), true); })
        .finally(function () { bouton.disabled = false; });
    });
  });
  var resultat = document.getElementById("resultat-newsletter");
  if (resultat) {
    var params = new URLSearchParams(window.location.search);
    var chemin = params.get("confirmer") ? "confirmer/" : params.get("desinscrire") ? "desinscrire/" : "";
    if (chemin) {
      var T0 = function (t) { return window.traduire ? window.traduire(t) : t; };
      envoyerNewsletter(chemin, { jeton: params.get("confirmer") || params.get("desinscrire") }).then(function (r) {
        resultat.textContent = T0(r.ok ? r.donnees.detail : (premierMessage(r.donnees) || "Ce lien n'est plus valable."));
        resultat.classList.toggle("erreur", !r.ok);
        resultat.classList.remove("cache");
      }).catch(function () {
        resultat.textContent = T0("La demande n'a pas pu être envoyée. Vérifiez votre connexion, puis réessayez.");
        resultat.classList.add("erreur");
        resultat.classList.remove("cache");
      });
    }
  }

  function annee() { var e = document.getElementById("annee"); if (e) e.textContent = new Date().getFullYear(); }
  annee();
  document.addEventListener("langue-site", annee);

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

  // Vidéo de présentation dans la langue de la page (une vidéo par langue, servie par la plateforme),
  // avec les temps de ses chapitres (chapitres.json, écrit au tournage des vidéos).
  var video = document.querySelector(".lecteur video");
  var chapitres = null;
  function majVideo() {
    if (!video || !S.VIDEOS) return;
    var langue = document.documentElement.lang || "fr";
    var src = S.VIDEOS + "/presentation-" + langue + ".webm";
    if (video.getAttribute("src") !== src) {
      video.pause();
      video.setAttribute("src", src);
      video.setAttribute("poster", S.VIDEOS + "/affiche-" + langue + ".webp");
      video.load();
    }
    var temps = chapitres && (chapitres[langue] || chapitres.fr);
    if (temps) document.querySelectorAll("[data-chapitre]").forEach(function (b) {
      var t = temps[b.getAttribute("data-chapitre")];
      if (t != null) b.setAttribute("data-temps", t);
    });
  }
  if (video && S.VIDEOS) {
    fetch(S.VIDEOS + "/chapitres.json").then(function (r) { return r.json(); }).then(function (c) { chapitres = c; majVideo(); }).catch(function () {});
    majVideo();
    document.addEventListener("langue-site", majVideo);
  }
  // Boutons de chapitres.
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
