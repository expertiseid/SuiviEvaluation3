const { ouvrir, capture, aller, bouton, onglet, zone, segment, pause } = require("./guide_commun");
const lien = (page, nom) => page.getByRole("link", { name: nom }).first();
(async () => {
  const { nav, page } = await ouvrir();
  const essai = async (nom, f) => { try { await f(); } catch (e) { console.log("✗", nom, e.message.split("\n")[0]); await page.keyboard.press("Escape").catch(() => {}); } };
  const echap = async () => { await page.keyboard.press("Escape"); await pause(600); };
  const modale = () => page.locator(".mantine-Modal-content").last();

  // ---- Module 1 : prise en main ----
  await essai("ecran", async () => {
    await aller(page, "/");
    await capture(page, "m1-ecran", [{ loc: page.locator("nav").first(), n: 1 }, { loc: page.getByRole("button", { name: /FR/ }).first(), n: 2 },
      { loc: page.locator("button:has(svg.lucide-bell)").first(), n: 3 }, { loc: bouton(page, "Déconnexion").first(), n: 4 }]);
    await capture(page, "m1-tableau-filtres", [{ loc: segment(page, "Toutes"), n: 1 }, { loc: zone(page, "Statut des projets"), n: 2 }, { loc: bouton(page, "Partager").first(), n: 3 }, { loc: bouton(page, "Personnaliser").first(), n: 4 }]);
    await page.getByRole("button", { name: /FR/ }).first().click(); await pause(600);
    await capture(page, "m1-langue", [{ loc: page.locator(".mantine-Menu-dropdown, .mantine-Popover-dropdown").first(), n: 1 }]);
    await echap();
  });
  await essai("partager-tdb", async () => {
    await bouton(page, "Partager").first().click(); await pause(900);
    await capture(page, "m1-partager", [{ loc: modale(), n: 1 }]); await echap();
    await bouton(page, "Personnaliser").first().click(); await pause(900);
    await capture(page, "m1-personnaliser", [{ loc: modale(), n: 1 }]); await echap();
  });

  // ---- Module 2 : stratégies ----
  await essai("strategies", async () => {
    await aller(page, "/strategie");
    await capture(page, "m2-liste", [{ loc: lien(page, "Stratégies"), n: 1 }, { loc: bouton(page, "Nouveau document").first(), n: 2 }, { loc: bouton(page, "Chaîne des documents").first(), n: 3 }, { loc: bouton(page, "Ouvrir").first(), n: 4 }]);
    await bouton(page, "Nouveau document").first().click(); await pause(900);
    await capture(page, "m2-nouveau", [{ loc: modale().locator("input").first(), n: 1 }, { loc: modale().locator("textarea").first(), n: 2 }, { loc: modale().locator("button").filter({ hasText: /Créer|Enregistrer/ }).last(), n: 3 }]);
    await echap();
    await bouton(page, "Ouvrir").first().click(); await pause(1500);
    await capture(page, "m2-detail", [{ loc: page.getByRole("tablist").first(), n: 1 }, { loc: bouton(page, "Configuration").first(), n: 2 }, { loc: bouton(page, "Ajouter un élément").or(bouton(page, "Ajouter")).first(), n: 3 }, { loc: bouton(page, "Importer").first(), n: 4 }]);
  });
  await essai("strategie-import", async () => {
    await bouton(page, "Importer").first().click(); await pause(900);
    await capture(page, "m2-import", [{ loc: modale().getByText("Télécharger le modèle", { exact: false }).first(), n: 1 }, { loc: modale().locator("button, input").filter({ hasText: /xlsx|Choisir/ }).first().or(modale().locator(".mantine-FileInput-input")).first(), n: 2 }]);
    await echap();
  });
  await essai("programme", async () => {
    await aller(page, "/strategie/5");
    await capture(page, "m2-programme", [{ loc: page.getByRole("tablist").first(), n: 1 }]);
  });

  // ---- Module 4 : indicateurs et suivi ----
  await essai("indicateurs", async () => {
    await aller(page, "/indicateurs");
    await capture(page, "m4-liste", [{ loc: lien(page, "Indicateurs"), n: 1 }, { loc: bouton(page, "Nouvel indicateur").first(), n: 2 }, { loc: bouton(page, "Importer").first(), n: 3 }]);
    await bouton(page, "Nouvel indicateur").first().click(); await pause(900);
    await capture(page, "m4-nouveau", [{ loc: zone(page, "Libellé"), n: 1 }, { loc: zone(page, "Unité"), n: 2 }, { loc: zone(page, "Valeur de référence"), n: 3 }, { loc: zone(page, "Valeur cible"), n: 4 }]);
    await zone(page, "Fréquence").scrollIntoViewIfNeeded().catch(() => {}); await pause(300);
    await capture(page, "m4-nouveau-suite", [{ loc: zone(page, "Fréquence"), n: 1 }, { loc: zone(page, "Projet"), n: 2 }, { loc: modale().locator("button").filter({ hasText: /Créer|Enregistrer/ }).last(), n: 3 }]);
    await echap();
  });
  await essai("indicateur-detail", async () => {
    await aller(page, "/indicateurs/154");
    await capture(page, "m4-fiche", [{ loc: bouton(page, "Saisir une valeur").first(), n: 1 }]);
    await bouton(page, "Saisir une valeur").first().click(); await pause(900);
    await capture(page, "m4-saisir-valeur", [{ loc: modale(), n: 1 }]); await echap();
  });
  await essai("suivi", async () => {
    await aller(page, "/suivi");
    await capture(page, "m4-suivi-liste", [{ loc: lien(page, "Suivi"), n: 1 }, { loc: page.locator("table tbody tr, .mantine-Card-root").first(), n: 2 }]);
    await aller(page, "/suivi/16");
    await capture(page, "m4-suivi-projet", [{ loc: page.getByRole("tab", { name: "Suivi global" }).first(), n: 1 }, { loc: page.getByRole("tab", { name: "Suivi par période" }).first(), n: 2 }, { loc: bouton(page, "Saisir un suivi").first(), n: 3 }]);
    await bouton(page, "Saisir un suivi").first().click(); await pause(900);
    await capture(page, "m4-saisir-suivi", [{ loc: modale(), n: 1 }]); await echap();
    await page.getByRole("tab", { name: "Suivi par période" }).first().click(); await pause(1200);
    await capture(page, "m4-suivi-periode", [{ loc: page.getByRole("tab", { name: "Suivi par période" }).first(), n: 1 }, { loc: bouton(page, "canevas").or(bouton(page, "Excel")).first(), n: 2 }]);
  });
  await essai("approbations", async () => {
    await aller(page, "/approbations");
    await capture(page, "m4-approbations", [{ loc: lien(page, "Approbations"), n: 1 }, { loc: bouton(page, "Approuver").first(), n: 2 }]);
    await aller(page, "/parametres-alerte");
    await capture(page, "m4-seuils", [{ loc: lien(page, "Paramètres d'alerte"), n: 1 }]);
  });

  // ---- Module 5 : bénéficiaires et carte ----
  await essai("beneficiaires", async () => {
    await aller(page, "/beneficiaires");
    await capture(page, "m5-liste", [{ loc: lien(page, "Bénéficiaires"), n: 1 }, { loc: bouton(page, "Nouveau bénéficiaire").first(), n: 2 }, { loc: bouton(page, "Importer").first(), n: 3 }, { loc: bouton(page, "Variables à collecter").first(), n: 4 }]);
    await bouton(page, "Nouveau bénéficiaire").first().click(); await pause(900);
    await capture(page, "m5-nouveau", [{ loc: zone(page, "Nom"), n: 1 }, { loc: zone(page, "Prénom"), n: 2 }, { loc: zone(page, "Sexe"), n: 3 }, { loc: zone(page, "Téléphone"), n: 4 }]);
    await echap();
    await bouton(page, "Importer").first().click(); await pause(900);
    await capture(page, "m5-import", [{ loc: modale().getByText("Télécharger le modèle", { exact: false }).first(), n: 1 }, { loc: modale().locator(".mantine-FileInput-input, input[type=file]").first(), n: 2 }]);
    await echap();
    await aller(page, "/doublons");
    await capture(page, "m5-doublons", [{ loc: lien(page, "Doublons"), n: 1 }]);
  });
  await essai("carte", async () => {
    await aller(page, "/carte");
    await capture(page, "m5-carte", [{ loc: segment(page, "Toutes"), n: 1 }, { loc: page.getByPlaceholder("Tous les projets").first(), n: 2 }, { loc: bouton(page, "Importer une couche").first(), n: 3 }, { loc: bouton(page, "Télécharger la carte").first(), n: 4 }]);
    await bouton(page, "Télécharger la carte").first().click(); await pause(1200);
    await capture(page, "m5-carte-telecharger", [{ loc: modale(), n: 1 }]); await echap();
  });

  // ---- Module 6 : documents ----
  await essai("documents", async () => {
    await aller(page, "/documents");
    await capture(page, "m6-documents", [{ loc: lien(page, "Documents"), n: 1 }, { loc: bouton(page, "Nouveau dossier").first(), n: 2 }, { loc: bouton(page, "Ajouter un document").first(), n: 3 }]);
    await bouton(page, "Ajouter un document").first().click(); await pause(900);
    await capture(page, "m6-ajouter", [{ loc: modale(), n: 1 }]); await echap();
    const menu = page.getByRole("button", { name: "Actions" }).nth(1);
    await menu.click(); await pause(600);
    await capture(page, "m6-menu-document", [{ loc: page.getByRole("menuitem", { name: "Partager par lien" }), n: 1 }, { loc: page.getByRole("menuitem", { name: "Versions" }), n: 2 }]);
    await page.getByRole("menuitem", { name: "Partager par lien" }).click(); await pause(1000);
    await capture(page, "m6-partager", [{ loc: segment(page, "Consulter seulement"), n: 1 }, { loc: zone(page, "Pour qui"), n: 2 }, { loc: segment(page, "7 jours"), n: 3 }, { loc: bouton(page, "Créer le lien").first(), n: 4 }]);
    await echap();
    await aller(page, "/corbeille");
    await capture(page, "m6-corbeille", [{ loc: lien(page, "Corbeille"), n: 1 }]);
  });

  // ---- Module 7 : plaintes ----
  await essai("plaintes", async () => {
    await aller(page, "/plaintes");
    await capture(page, "m7-dossiers", [{ loc: lien(page, "Plaintes et retours"), n: 1 }, { loc: bouton(page, "Enregistrer un retour").first(), n: 2 }]);
    await bouton(page, "Enregistrer un retour").first().click(); await pause(1000);
    await capture(page, "m7-enregistrer", [{ loc: modale(), n: 1 }]); await echap();
    await aller(page, "/plaintes/dossiers/37");
    await capture(page, "m7-dossier", [{ loc: bouton(page, "Classer").first(), n: 1 }, { loc: bouton(page, "Affecter").first(), n: 2 }, { loc: bouton(page, "Changer d'étape").first(), n: 3 }, { loc: bouton(page, "Clôturer").first(), n: 4 }]);
    await bouton(page, "Affecter").first().click(); await pause(900);
    await capture(page, "m7-affecter", [{ loc: modale(), n: 1 }]); await echap();
    await aller(page, "/plaintes/tableau-de-bord");
    await capture(page, "m7-tableau", [{ loc: page.getByRole("tab").first(), n: 1 }]);
    await aller(page, "/plainte?org=demo");
    await capture(page, "m7-formulaire-public", []);
  });

  // ---- Module 8 : administration ----
  await essai("utilisateurs", async () => {
    await aller(page, "/accueil?demo=1"); await page.waitForURL((u) => !u.pathname.startsWith("/accueil"), { timeout: 30000 }).catch(() => {});
    await aller(page, "/utilisateurs");
    await capture(page, "m8-utilisateurs", [{ loc: lien(page, "Utilisateurs"), n: 1 }, { loc: bouton(page, "Nouvel utilisateur").first(), n: 2 }, { loc: page.getByRole("tab", { name: "Rôles" }).first(), n: 3 }]);
    await bouton(page, "Nouvel utilisateur").first().click(); await pause(900);
    await capture(page, "m8-nouvel-utilisateur", [{ loc: zone(page, "Adresse courriel").or(zone(page, "Courriel")), n: 1 }, { loc: zone(page, "Rôle"), n: 2 }, { loc: zone(page, "Niveau d'accès"), n: 3 }, { loc: zone(page, "Mot de passe"), n: 4 }]);
    await echap();
    await aller(page, "/organisation?onglet=identite");
    await capture(page, "m8-identite", [{ loc: lien(page, "Organisation"), n: 1 }, { loc: bouton(page, "Nouveau logo").first(), n: 2 }]);
    await aller(page, "/journal-audit");
    await capture(page, "m8-journal", [{ loc: lien(page, "Journal d'audit"), n: 1 }, { loc: bouton(page, "Exporter").first(), n: 2 }]);
  });
  await nav.close();
})();
