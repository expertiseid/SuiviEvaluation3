const { ouvrir, capture, aller, bouton, onglet, champ, pause } = require("./guide_commun");
(async () => {
  const { nav, page } = await ouvrir();
  const essai = async (nom, f) => { try { await f(); } catch (e) { console.log("✗", nom, e.message.split("\n")[0]); } };
  await essai("liste", async () => {
    await aller(page, "/projets");
    await capture(page, "projets-01-liste", [{ loc: page.getByRole("link", { name: "Projets" }).first(), n: 1 }, { loc: bouton(page, "Nouveau projet"), n: 2 }, { loc: bouton(page, "Importer"), n: 3 }]);
  });
  await essai("nouveau", async () => {
    await bouton(page, "Nouveau projet").first().click(); await pause(900);
    await champ(page, "Nom du projet").first().fill("Projet d'appui à l'éducation des filles — Koulsé");
    await champ(page, "Code").first().fill("PEF-KOU-2026");
    await capture(page, "projets-02-general", [
      { loc: onglet(page, "Général"), n: 1 }, { loc: champ(page, "Nom du projet"), n: 2 }, { loc: champ(page, "Code"), n: 3 },
      { loc: champ(page, "Date de début prévue"), n: 4 }, { loc: champ(page, "Date de fin prévue"), n: 5 }, { loc: champ(page, "Statut"), n: 6 }]);
    const modal = page.locator(".mantine-Modal-content");
    await modal.evaluate((m) => m.querySelector(".mantine-Modal-body")?.scrollTo(0, 400)); await pause(300);
    await capture(page, "projets-03-general-suite", [
      { loc: champ(page, "Fonds propres"), n: 1 }, { loc: champ(page, "Type de mise en œuvre"), n: 2 }, { loc: champ(page, "Chef de projet"), n: 3 },
      { loc: champ(page, "Utilisateurs affectés"), n: 4 }, { loc: champ(page, "Pays d'intervention"), n: 5 }]);
    await onglet(page, "Cibles bénéficiaires").click(); await pause(500);
    await champ(page, "Cible totale").first().fill("1200"); await champ(page, "Dont femmes").first().fill("800");
    await capture(page, "projets-04-cibles", [{ loc: onglet(page, "Cibles bénéficiaires"), n: 1 }, { loc: champ(page, "Cible totale"), n: 2 }, { loc: champ(page, "Dont femmes"), n: 3 }]);
    await onglet(page, "Stratégie & capitalisation").click(); await pause(500);
    await capture(page, "projets-05-strategie", [{ loc: onglet(page, "Stratégie & capitalisation"), n: 1 }, { loc: champ(page, "Cadre stratégique"), n: 2 },
      { loc: champ(page, "Rattachement dans le cadre stratégique"), n: 3 }, { loc: champ(page, "Méthode de calcul des taux"), n: 4 }]);
    await onglet(page, "Organisation").click(); await pause(500);
    await capture(page, "projets-06-organisation", [{ loc: onglet(page, "Organisation"), n: 1 }, { loc: champ(page, "Services chargés du projet"), n: 2 },
      { loc: champ(page, "Les saisies de réalisations doivent être approuvées"), n: 3 }, { loc: page.locator(".mantine-Modal-content button[type=submit], .mantine-Modal-content button:has-text('Créer'), .mantine-Modal-content button:has-text('Enregistrer')").last(), n: 4 }]);
    await page.keyboard.press("Escape"); await pause(500);
  });
  await essai("import", async () => {
    await aller(page, "/projets");
    await bouton(page, "Importer").first().click(); await pause(900);
    await capture(page, "projets-07-import", [{ loc: page.getByText("Télécharger le modèle", { exact: false }), n: 1 }, { loc: page.locator(".mantine-Modal-content input[type=file], .mantine-Modal-content .mantine-FileInput-input, .mantine-Modal-content [class*=Dropzone]"), n: 2 }]);
    await page.keyboard.press("Escape");
  });
  await essai("detail", async () => {
    await aller(page, "/projets/16");
    await capture(page, "projets-08-onglets", [{ loc: page.getByRole("tablist").first(), n: 1 }, { loc: onglet(page, "Planification"), n: 2 }]);
    await capture(page, "projets-09-planification", [{ loc: bouton(page, "Configuration des niveaux"), n: 1 }, { loc: bouton(page, "Ajouter un niveau").or(bouton(page, "Ajouter")), n: 2 }, { loc: page.getByRole("radio", { name: "Arbre" }).or(page.getByText("Arbre", { exact: true })), n: 3 }]);
  });
  await essai("niveaux", async () => {
    await bouton(page, "Configuration des niveaux").first().click(); await pause(900);
    await capture(page, "projets-10-niveaux", [{ loc: page.locator(".mantine-Modal-content input").first(), n: 1 }, { loc: page.getByRole("button", { name: "Ajouter un niveau" }), n: 2 }, { loc: page.locator(".mantine-Modal-content").getByRole("button", { name: "Enregistrer" }), n: 3 }]);
    await page.keyboard.press("Escape"); await pause(500);
  });
  await nav.close();
})();
