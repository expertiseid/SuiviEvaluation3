const { ouvrir, capture, aller, bouton, onglet, zone, segment, pause } = require("./guide_commun");
(async () => {
  const { nav, page } = await ouvrir();
  const essai = async (nom, f) => { try { await f(); } catch (e) { console.log("✗", nom, e.message.split("\n")[0]); } };
  const fermer = async () => { await page.keyboard.press("Escape"); await pause(600); };
  await aller(page, "/projets/16");
  await essai("ajouter-element", async () => {
    await page.getByPlaceholder("Nouveau", { exact: false }).first().fill("Améliorer l'accès à l'eau potable dans les écoles");
    await capture(page, "planif-01-ajouter", [{ loc: segment(page, "Planification"), n: 1 }, { loc: page.getByPlaceholder("Nouveau", { exact: false }).first(), n: 2 }, { loc: bouton(page, "Ajouter").first(), n: 3 }]);
    await page.getByPlaceholder("Nouveau", { exact: false }).first().fill("");
  });
  await essai("arbre", async () => {
    await segment(page, "Arbre").click(); await pause(1200);
    const ligne = page.locator("button:has(svg.lucide-pencil)").first();
    await capture(page, "planif-02-arbre", [{ loc: segment(page, "Arbre"), n: 1 }, { loc: ligne, n: 2 }, { loc: page.locator("button:has(svg.lucide-plus)").first(), n: 3 }, { loc: page.locator("button:has(svg.lucide-list-plus)").first(), n: 4 }]);
  });
  await essai("modifier-element", async () => {
    await page.locator("button:has(svg.lucide-pencil)").first().click(); await pause(1000);
    await capture(page, "planif-03-element", [{ loc: zone(page, "Libellé"), n: 1 }, { loc: zone(page, "Code"), n: 2 }, { loc: zone(page, "Date de début prévue"), n: 3 }, { loc: zone(page, "Budget alloué"), n: 4 }]);
    const corps = page.locator(".mantine-Modal-body"); await corps.evaluate((m) => m.scrollTo(0, 650)); await pause(400);
    await capture(page, "planif-04-element-suite", [{ loc: zone(page, "Unité"), n: 1 }, { loc: zone(page, "Quantité prévue"), n: 2 }, { loc: zone(page, "Méthode de calcul"), n: 3 }]);
    await corps.evaluate((m) => m.scrollTo(0, 1500)); await pause(400);
    await capture(page, "planif-05-element-fin", [{ loc: zone(page, "Services chargés"), n: 1 }, { loc: zone(page, "Responsables"), n: 2 }]);
    await fermer();
  });
  await essai("sous-activite", async () => {
    await page.locator("button:has(svg.lucide-list-plus)").first().click(); await pause(1000);
    await capture(page, "planif-06-sous-activite", [{ loc: page.locator(".mantine-Modal-body input").first(), n: 1 }]);
    await fermer();
  });
  await essai("niveaux", async () => {
    await segment(page, "Configuration des niveaux").click(); await pause(1000);
    await capture(page, "planif-07-niveaux", [{ loc: segment(page, "Configuration des niveaux"), n: 1 }, { loc: page.locator("button:has(svg.lucide-pencil)").first(), n: 2 }, { loc: bouton(page, "Ajouter un niveau").first(), n: 3 }]);
  });
  await essai("periode", async () => {
    await segment(page, "Planification par période").click(); await pause(1200);
    await capture(page, "planif-08-periode", [{ loc: segment(page, "Planification par période"), n: 1 }, { loc: bouton(page, "Nouvelle période").first(), n: 2 }]);
  });
  await essai("cadre-logique", async () => {
    await onglet(page, "Cadre logique").click(); await pause(1500);
    await capture(page, "planif-09-cadre-logique", [{ loc: onglet(page, "Cadre logique"), n: 1 }, { loc: bouton(page, "Exporter").first(), n: 2 }, { loc: page.getByRole("tab", { name: "Risques" }).or(segment(page, "Risques")).first(), n: 3 }]);
    await page.getByRole("tab", { name: "Risques" }).or(segment(page, "Risques")).first().click(); await pause(1000);
    await capture(page, "planif-10-risques", [{ loc: bouton(page, "Nouveau risque").first(), n: 1 }]);
  });
  await essai("equipe", async () => {
    await onglet(page, "Équipe").click(); await pause(1200);
    await capture(page, "planif-11-equipe", [{ loc: onglet(page, "Équipe"), n: 1 }, { loc: bouton(page, "Nouvelle équipe").first(), n: 2 }]);
  });
  await essai("financement", async () => {
    await onglet(page, "Financement").click(); await pause(1200);
    await capture(page, "planif-12-financement", [{ loc: onglet(page, "Financement"), n: 1 }, { loc: bouton(page, "Ajouter un financement").or(bouton(page, "Ajouter un bailleur")).first(), n: 2 }]);
  });
  await essai("planification-complete", async () => {
    await aller(page, "/planification");
    await capture(page, "planif-13-complete", [{ loc: page.getByRole("link", { name: "Planification complète" }).first(), n: 1 }, { loc: bouton(page, "Télécharger le modèle Excel complet").first(), n: 2 }, { loc: bouton(page, "Importer").first(), n: 3 }]);
  });
  await nav.close();
})();
