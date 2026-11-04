/*
 * Inscription d'une organisation, branchée sur l'API de la plateforme :
 *  1. POST {API}/public/inscription/        → profil créé, renvoie une référence ;
 *  2. POST {API}/public/inscription/offre/  → offre choisie, transmise à Expertise-ID ;
 *  3. confirmation (l'espace est activé par Expertise-ID, qui prévient par courriel ; connexion par courriel et mot de passe).
 */
(function () {
  var S = window.SITE || {};
  var CLE = "inscription-site";
  var form1 = document.getElementById("etape-1");
  var form2 = document.getElementById("etape-2");
  var bloc3 = document.getElementById("etape-3");
  var params = new URLSearchParams(window.location.search);

  function etape(n) {
    [form1, form2, bloc3].forEach(function (el, i) { el.classList.toggle("cache", i !== n - 1); });
    for (var i = 1; i <= 3; i++) {
      var pas = document.getElementById("pas-" + i);
      pas.classList.toggle("actif", i === n);
      pas.classList.toggle("fait", i < n);
    }
    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  function lire(cle) { try { return JSON.parse(sessionStorage.getItem(cle) || "null"); } catch (e) { return null; } }
  function garder(cle, valeur) { try { sessionStorage.setItem(cle, JSON.stringify(valeur)); } catch (e) { /* navigation privée */ } }

  function envoyer(chemin, donnees) {
    return fetch(S.API + chemin, {
      method: "POST",
      headers: { "Content-Type": "application/json", "Accept": "application/json" },
      body: JSON.stringify(donnees),
    }).then(function (r) {
      return r.json().catch(function () { return {}; }).then(function (corps) {
        if (!r.ok) { var e = new Error("refus"); e.statut = r.status; e.corps = corps; throw e; }
        return corps;
      });
    });
  }

  // Messages traduits dans la langue choisie (vitrine/langues.js), y compris ceux du serveur.
  var T = function (t) { return window.traduire ? window.traduire(t) : t; };
  function texte(v) { return Array.isArray(v) ? v.map(function (x) { return T(String(x)); }).join(" ") : T(String(v)); }

  function effacerErreurs(form) {
    form.querySelectorAll(".champ.en-erreur").forEach(function (c) { c.classList.remove("en-erreur"); });
    form.querySelectorAll(".champ .erreur").forEach(function (e) { e.remove(); });
    form.querySelector(".message-global").classList.remove("visible");
  }

  function afficherErreurs(form, erreurs, messageGeneral) {
    var premier = null, restes = [];
    Object.keys(erreurs || {}).forEach(function (cle) {
      var champ = form.querySelector("[name='" + cle + "']") || document.getElementById(cle);
      var bloc = champ && champ.closest(".champ");
      if (!bloc) { restes.push(texte(erreurs[cle])); return; }
      bloc.classList.add("en-erreur");
      var p = document.createElement("span");
      p.className = "erreur";
      p.textContent = texte(erreurs[cle]);
      bloc.appendChild(p);
      premier = premier || champ;
    });
    var global = form.querySelector(".message-global");
    var msg = restes.join(" ") || (messageGeneral && T(messageGeneral));
    if (msg) { global.textContent = msg; global.classList.add("visible"); }
    (premier || global).scrollIntoView({ behavior: "smooth", block: "center" });
  }

  function erreurReseau(e) {
    if (e && e.statut === 429) return { detail: "Trop d'envois depuis votre connexion : réessayez dans un moment." };
    if (e && e.corps && typeof e.corps === "object") return e.corps;
    return { detail: "La demande n'a pas pu être envoyée. Vérifiez votre connexion, puis réessayez." };
  }

  // Étape 1 : profil.
  form1.addEventListener("submit", function (ev) {
    ev.preventDefault();
    effacerErreurs(form1);
    var d = {};
    ["organisation", "type_organisation", "pays", "secteur", "taille", "contact_nom", "contact_fonction",
      "courriel", "telephone", "mot_de_passe", "message", "site_web"].forEach(function (cle) {
      var el = form1.querySelector("[name='" + cle + "']");
      d[cle] = el ? el.value.trim() : "";
    });
    d.mot_de_passe = form1.querySelector("[name='mot_de_passe']").value;
    d.conditions = document.getElementById("conditions").checked;
    var locales = {};
    ["organisation", "type_organisation", "pays", "contact_nom", "courriel", "telephone", "mot_de_passe"].forEach(function (cle) {
      if (!d[cle]) locales[cle] = "Champ obligatoire.";
    });
    if (d.mot_de_passe && d.mot_de_passe !== document.getElementById("confirmation").value) locales.confirmation = "Les deux mots de passe ne sont pas identiques.";
    if (!d.conditions) locales.conditions = "Votre accord est nécessaire pour créer le profil.";
    if (Object.keys(locales).length) { afficherErreurs(form1, locales, "Complétez les champs signalés."); return; }

    var bouton = document.getElementById("bouton-1");
    bouton.disabled = true; bouton.textContent = T("Envoi en cours…");
    envoyer("/public/inscription/", d).then(function (resume) {
      garder(CLE, { reference: resume.reference, organisation: resume.organisation });
      montrerEtape2(resume.organisation);
    }).catch(function (e) {
      afficherErreurs(form1, erreurReseau(e), "Certaines informations sont à corriger.");
    }).finally(function () {
      bouton.disabled = false; bouton.textContent = T("Continuer vers le choix de l'offre");
    });
  });

  function montrerEtape2(organisation) {
    document.getElementById("nom-organisation").textContent = organisation || "";
    var voulue = params.get("offre");
    if (voulue) { var r = form2.querySelector("input[value='" + voulue + "']"); if (r) r.checked = true; }
    etape(2);
  }

  // Étape 2 : offre.
  form2.addEventListener("submit", function (ev) {
    ev.preventDefault();
    effacerErreurs(form2);
    var choix = form2.querySelector("input[name='offre']:checked");
    var enCours = lire(CLE);
    if (!enCours) { etape(1); return; }
    if (!choix) { afficherErreurs(form2, {}, "Choisissez une offre."); return; }
    var bouton = document.getElementById("bouton-2");
    bouton.disabled = true; bouton.textContent = T("Envoi en cours…");
    envoyer("/public/inscription/offre/", { reference: enCours.reference, offre: choix.value, message: document.getElementById("message-offre").value })
      .then(function () {
        try { sessionStorage.removeItem(CLE); } catch (e) { /* rien */ }
        etape(3);
      }).catch(function (e) {
        afficherErreurs(form2, erreurReseau(e), "L'offre n'a pas pu être enregistrée.");
      }).finally(function () {
        bouton.disabled = false; bouton.textContent = T("Envoyer ma demande");
      });
  });

  // Profil déjà créé dans cet onglet (retour sur la page) : on reprend au choix de l'offre.
  var enCours = lire(CLE);
  if (enCours && enCours.reference) montrerEtape2(enCours.organisation);
})();
