/*
 * Inscription d'une organisation, branchée sur l'API de la plateforme :
 *  1. POST {API}/public/inscription/        → profil créé, renvoie une référence ;
 *  2. offre Standard ou Standard + stockage : POST {API}/public/inscription/paiement/ → page de paiement de CinetPay,
 *     qui ramène ici (?paiement=…) ; GET {API}/public/inscription/paiement/<réf>/ jusqu'à « payé » : l'espace est
 *     alors créé aussitôt, sans validation d'Expertise-ID. Offre Partenariat (ou paiement en ligne indisponible) :
 *     POST {API}/public/inscription/offre/ → demande transmise à Expertise-ID ;
 *  3. confirmation (connexion par courriel et mot de passe).
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
    return fetch(S.API + chemin, donnees === undefined ? { headers: { "Accept": "application/json" } } : {
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
      var champ = form.querySelector("[data-champ='" + cle + "']") || document.getElementById(cle);
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

  // Pays : liste déroulante, noms dans la langue du site (Intl.DisplayNames) ; la valeur envoyée reste
  // le nom en français. Pays d'Afrique de l'Ouest et du Centre les plus fréquents en tête.
  var PAYS = ("AF ZA AL DZ DE AD AO AG SA AR AM AU AT AZ BS BH BD BB BE BZ BJ BT BY MM BO BA BW BR BN BG BF BI KH CM CA CV " +
    "CF CL CN CY CO KM CG CD KR KP CR CI HR CU DK DJ DM EG AE EC ER ES EE SZ US ET FJ FI FR GA GM GE GH GR GD GT GN GQ GW GY " +
    "HT HN HU IN ID IQ IR IE IS IL IT JM JP JO KZ KE KG KI XK KW LA LS LV LB LR LY LI LT LU MK MG MY MW MV ML MT MA MH MU MR " +
    "MX FM MD MC MN ME MZ NA NR NP NI NE NG NO NZ OM UG UZ PK PW PS PA PG PY NL PE PH PL PT QA RO GB RU RW KN SM VC LC SB SV " +
    "WS ST SN RS SC SL SG SK SI SO SD SS LK SE CH SR SY TJ TZ TD CZ TH TL TG TO TT TN TM TR TV UA UY VU VA VE VN YE ZM ZW").split(" ");
  var EN_TETE = ["BF", "CI", "ML", "NE", "SN", "TG", "BJ", "GN", "CM", "TD"];
  function remplirPays() {
    var select = document.getElementById("pays");
    if (!select || typeof Intl.DisplayNames !== "function") return;
    var langue = document.documentElement.lang || "fr", choisi = select.value;
    var noms = new Intl.DisplayNames([langue], { type: "region" }), fr = new Intl.DisplayNames(["fr"], { type: "region" });
    var option = function (code) {
      var o = document.createElement("option");
      o.value = fr.of(code); o.textContent = noms.of(code);
      return o;
    };
    select.innerHTML = "";
    var vide = document.createElement("option");
    vide.value = ""; vide.textContent = T("Choisir…");
    select.appendChild(vide);
    EN_TETE.forEach(function (code) { select.appendChild(option(code)); });
    var tous = document.createElement("optgroup");
    tous.label = T("Tous les pays");
    PAYS.filter(function (c) { return EN_TETE.indexOf(c) === -1; })
      .sort(function (a, b) { return noms.of(a).localeCompare(noms.of(b), langue); })
      .forEach(function (code) { tous.appendChild(option(code)); });
    select.appendChild(tous);
    select.value = choisi;
  }
  remplirPays();
  document.addEventListener("langue-site", remplirPays);

  // Étape 1 : profil.
  form1.addEventListener("submit", function (ev) {
    ev.preventDefault();
    effacerErreurs(form1);
    var d = {};
    ["organisation", "type_organisation", "pays", "secteur", "taille", "contact_nom", "contact_fonction",
      "courriel", "telephone", "mot_de_passe", "message"].forEach(function (cle) {
      var el = form1.querySelector("[data-champ='" + cle + "']");
      d[cle] = el ? el.value.trim() : "";
    });
    d.mot_de_passe = form1.querySelector("[data-champ='mot_de_passe']").value;
    d.site_web = document.getElementById("site_web").value;
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
      garder(CLE, { reference: resume.reference, organisation: resume.organisation, tarifs: resume.tarifs });
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
    // Offre demandée dans l'adresse (?offre=…) : comparée aux choix proposés, jamais insérée telle quelle.
    form2.querySelectorAll("input[name='offre']").forEach(function (r) { if (r.value === voulue) r.checked = true; });
    afficherTarifs();
    etape(2);
  }

  // Tarifs et montant (envoyés par la plateforme avec le profil) ; « 50000 » → « 50 000 FCFA ».
  function tarifs() { var t = (lire(CLE) || {}).tarifs; return t && t.paiement ? t : null; }
  function somme(n, t) { return String(n).replace(/\B(?=(\d{3})+(?!\d))/g, " ") + " " + (t.devise === "XOF" ? "FCFA" : t.devise); }
  function offreChoisie() { var c = form2.querySelector("input[name='offre']:checked"); return c ? c.value : ""; }
  var PAYANTES = ["STANDARD_25", "STANDARD_50", "STANDARD", "STOCKAGE_PLUS"];
  function enLigne() { return !!tarifs() && PAYANTES.indexOf(offreChoisie()) >= 0; }
  // Prix d'un mois de l'offre (Standard + stockage : celui de Standard), en FCFA ou en dollars.
  function prixMois(t, o, usd) {
    var p = (t.offres || {})[o];
    if (p) return usd ? p.usd : p.mois;
    return usd ? t.usd.mois : t.mois;
  }
  // « Standard + stockage » n'est plus proposée (stockage augmenté sur demande) : aucune tranche ajoutée ici.
  function tranches() { return 0; }
  // Moyen de paiement : mobile money (FCFA, payé en ligne) ou carte bancaire (dollars, finalisée avec Expertise-ID).
  function parCarte() { var m = form2.querySelector("input[name='moyen']:checked"); return !!m && m.value === "carte"; }
  function dollars(n) { return String(n).replace(/\B(?=(\d{3})+(?!\d))/g, " ") + " $"; }

  function afficherTarifs() {
    var t = tarifs();
    if (t && t.usd) {
      // Prix en dollars, avec l'équivalent en FCFA (payé par mobile money).
      ["STANDARD_25", "STANDARD_50", "STANDARD"].forEach(function (code) {
        var p = (t.offres || {})[code] || (code === "STANDARD" ? { mois: t.mois, usd: t.usd.mois } : null);
        if (p) form2.querySelector("[data-prix='" + code + "']").textContent = dollars(p.usd) + " " + T("HT par mois") + " (" + somme(p.mois, t) + ")";
      });
    }
    var o = offreChoisie(), paye = enLigne();
    document.getElementById("options-paiement").classList.toggle("cache", !paye);
    document.getElementById("aide-partenariat").classList.toggle("cache", o !== "PARTENARIAT");
    // Formation gratuite : selon l'offre, à partir d'1 an ou de 2 ans de licence.
    var minimum = paye && t.formation ? t.formation[o] : null, duree = parseInt(document.getElementById("duree").value, 10);
    document.getElementById("formation-oui").classList.toggle("cache", !minimum || duree < minimum);
    document.getElementById("formation-24").classList.toggle("cache", minimum !== 24 || duree >= 24);
    document.getElementById("formation-12").classList.toggle("cache", minimum !== 12 || duree >= 12);
    var carte = parCarte();
    document.getElementById("aide-mobile").classList.toggle("cache", carte);
    document.getElementById("aide-carte").classList.toggle("cache", !carte);
    if (paye) {
      var mois = parseInt(document.getElementById("duree").value, 10), n = o === "STOCKAGE_PLUS" ? tranches() : 0;
      document.getElementById("montant").textContent = carte && t.usd
        ? dollars(mois * (prixMois(t, o, true) + n * t.usd.tranche)) : somme(mois * (prixMois(t, o, false) + n * t.tranche), t);
    }
    document.getElementById("bouton-2").textContent = T(!paye ? "Envoyer ma demande" : carte ? "Continuer avec la carte bancaire" : "Payer et créer mon espace");
  }
  form2.addEventListener("change", afficherTarifs);

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
    if (enLigne() && parCarte()) {
      // Carte bancaire : demande transmise à Expertise-ID, qui finalise le paiement avec le client.
      envoyer("/public/inscription/offre/", {
        reference: enCours.reference, offre: choix.value, moyen: "carte", mois: parseInt(document.getElementById("duree").value, 10),
        tranches: choix.value === "STOCKAGE_PLUS" ? tranches() : 0, message: document.getElementById("message-offre").value,
      }).then(function () { fin("fin-carte"); }).catch(function (e) {
        afficherErreurs(form2, erreurReseau(e), "L'offre n'a pas pu être enregistrée.");
      }).finally(function () { bouton.disabled = false; afficherTarifs(); });
      return;
    }
    if (enLigne()) {
      envoyer("/public/inscription/paiement/", {
        reference: enCours.reference, offre: choix.value, mois: parseInt(document.getElementById("duree").value, 10),
        tranches: choix.value === "STOCKAGE_PLUS" ? tranches() : 0, message: document.getElementById("message-offre").value,
        langue: document.documentElement.lang || "fr",
      }).then(function (suite) {
        // Lien renvoyé par CinetPay : sa page de paiement, qui ramène ensuite ici (?paiement=…).
        if (!/^https:\/\/[a-z0-9.-]*cinetpay\.(net|co|com)\//.test(suite.lien || "")) throw { corps: {} };
        window.location.assign(suite.lien);
      }).catch(function (e) {
        afficherErreurs(form2, erreurReseau(e), "Le paiement n'a pas pu être préparé. Réessayez dans un moment.");
        bouton.disabled = false; afficherTarifs();
      });
      return;
    }
    envoyer("/public/inscription/offre/", { reference: enCours.reference, offre: choix.value, message: document.getElementById("message-offre").value })
      .then(function () {
        try { sessionStorage.removeItem(CLE); } catch (e) { /* rien */ }
        fin("fin-demande");
      }).catch(function (e) {
        afficherErreurs(form2, erreurReseau(e), "L'offre n'a pas pu être enregistrée.");
      }).finally(function () {
        bouton.disabled = false; afficherTarifs();
      });
  });

  // Retour de la page de paiement : statut redemandé toutes les 3 secondes (la plateforme le vérifie auprès de CinetPay).
  function fin(id) {
    ["fin-demande", "fin-attente", "fin-paye", "fin-echec", "fin-carte"].forEach(function (f) { document.getElementById(f).classList.toggle("cache", f !== id); });
    etape(3);
  }
  function suivrePaiement(reference) {
    var essais = 0;
    fin("fin-attente");
    (function demander() {
      envoyer("/public/inscription/paiement/" + encodeURIComponent(reference) + "/").then(function (etat) {
        if (etat.statut === "PAYE") {
          try { sessionStorage.removeItem(CLE); } catch (e) { /* rien */ }
          fin("fin-paye");
        } else if (etat.statut === "ECHOUE") {
          fin("fin-echec");
        } else {
          essais += 1;
          if (essais === 40) document.getElementById("attente-longue").classList.remove("cache");
          setTimeout(demander, essais < 40 ? 3000 : 15000);
        }
      }).catch(function () { essais += 1; setTimeout(demander, 6000); });
    })();
  }
  // Lien dans un texte traduit (remplacé au changement de langue) : écouté au niveau du document.
  document.addEventListener("click", function (ev) {
    if (!ev.target.closest || !ev.target.closest("#vers-mobile")) return;
    ev.preventDefault();
    form2.querySelector("input[name='moyen'][value='mobile']").checked = true;
    var enCours = lire(CLE);
    if (enCours && enCours.reference) montrerEtape2(enCours.organisation); else etape(1);
  });
  document.getElementById("reessayer").addEventListener("click", function () {
    var enCours = lire(CLE);
    history.replaceState(null, "", "inscription.html");
    if (enCours && enCours.reference) montrerEtape2(enCours.organisation); else etape(1);
  });

  // Profil déjà créé dans cet onglet (retour sur la page) : on reprend au choix de l'offre.
  var enCours = lire(CLE);
  if (params.get("paiement")) suivrePaiement(params.get("paiement"));
  else if (enCours && enCours.reference) montrerEtape2(enCours.organisation);
})();
