const { ouvrir, capture, aller, bouton, onglet, zone, segment, pause } = require("./guide_commun");
(async () => {
  const { nav, page } = await ouvrir();
  const essai = async (nom, f) => { try { await f(); } catch (e) { console.log("✗", nom, e.message.split("\n")[0]); await page.keyboard.press("Escape").catch(() => {}); } };
  const echap = async () => { await page.keyboard.press("Escape"); await pause(600); };
  const modale = () => page.locator(".mantine-Modal-content").last();
  await essai("strategie-detail", async () => {
    await aller(page, "/strategie/1");
    await capture(page, "m2-detail", [{ loc: page.getByRole("tablist").first(), n: 1 }, { loc: bouton(page, "Exporter le canevas Excel").or(bouton(page, "Exporter")).first(), n: 2 }, { loc: bouton(page, "Importer depuis Excel").first(), n: 3 }]);
    await onglet(page, "Configuration des niveaux").click(); await pause(1000);
    await capture(page, "m2-niveaux", [{ loc: onglet(page, "Configuration des niveaux"), n: 1 }, { loc: bouton(page, "Ajouter un niveau").first(), n: 2 }]);
    await onglet(page, "Arborescence").click(); await pause(1000);
    await capture(page, "m2-arborescence", [{ loc: onglet(page, "Arborescence"), n: 1 }, { loc: bouton(page, "Ajouter un élément").or(bouton(page, "Ajouter")).first(), n: 2 }]);
    await bouton(page, "Importer depuis Excel").first().click(); await pause(1000);
    await capture(page, "m2-import", [{ loc: modale().getByText("Télécharger le modèle", { exact: false }).first(), n: 1 }, { loc: modale().locator(".mantine-FileInput-input, input[type=file]").first(), n: 2 }]);
    await echap();
  });
  await essai("planif-04", async () => {
    await aller(page, "/projets/16"); await segment(page, "Arbre").click(); await pause(1000);
    await bouton(page, "Éditer").first().click(); await pause(800);
    const i = await page.evaluate(() => [...document.querySelectorAll("button")].findIndex((b) => b.querySelector("svg.lucide-pencil") && b.getBoundingClientRect().y > 550));
    await page.locator("button").nth(i).click(); await pause(1200);
    await zone(page, "Unité").scrollIntoViewIfNeeded(); await page.mouse.wheel(0, 120); await pause(400);
    await capture(page, "planif-04-element-suite", [{ loc: zone(page, "Unité"), n: 1 }, { loc: zone(page, "Valeur de base"), n: 2 }, { loc: zone(page, "Quantité prévue"), n: 3 }, { loc: zone(page, "Méthode de calcul"), n: 4 }]);
    await echap();
  });
  await essai("documents-projet", async () => {
    await aller(page, "/projets/16"); await onglet(page, "Documents").click(); await pause(1500);
    await capture(page, "m6-documents-projet", [{ loc: onglet(page, "Documents"), n: 1 }, { loc: bouton(page, "Nouveau dossier").first(), n: 2 }, { loc: bouton(page, "Ajouter un document").first(), n: 3 }]);
    await page.getByRole("button", { name: "Actions" }).last().click(); await pause(700);
    await capture(page, "m6-menu-document", [{ loc: page.getByRole("menuitem", { name: "Partager par lien" }), n: 1 }, { loc: page.getByRole("menuitem", { name: "Versions" }), n: 2 }, { loc: page.getByRole("menuitem", { name: "Supprimer" }), n: 3 }]);
    await page.getByRole("menuitem", { name: "Partager par lien" }).click(); await pause(1000);
    await page.getByLabel("Pour qui", { exact: false }).first().fill("Bailleur — rapport annuel");
    await capture(page, "m6-partager", [{ loc: segment(page, "Consulter seulement"), n: 1 }, { loc: zone(page, "Pour qui"), n: 2 }, { loc: segment(page, "7 jours"), n: 3 }, { loc: zone(page, "Mot de passe"), n: 4 }, { loc: bouton(page, "Créer le lien").first(), n: 5 }]);
    await echap();
  });
  await essai("suivi-indicateurs", async () => {
    await aller(page, "/suivi/16"); await pause(800);
    await page.getByText("Indicateurs", { exact: true }).last().scrollIntoViewIfNeeded().catch(() => {}); await pause(600);
    await capture(page, "m4-suivi-indicateurs", [{ loc: bouton(page, "Saisir une valeur").first(), n: 1 }]);
    await bouton(page, "Saisir une valeur").first().click(); await pause(1000);
    await capture(page, "m4-saisir-valeur", [{ loc: modale(), n: 1 }]); await echap();
    await aller(page, "/suivi/16");
    await bouton(page, "Saisie par Excel").first().click(); await pause(1000);
    await capture(page, "m4-saisie-excel", [{ loc: modale(), n: 1 }]); await echap();
  });
  await essai("cloturer", async () => {
    await aller(page, "/plaintes/dossiers/37");
    await bouton(page, "Clôturer").first().click(); await pause(1000);
    await capture(page, "m7-cloturer", [{ loc: modale(), n: 1 }]); await echap();
    await bouton(page, "Classer").first().click(); await pause(1000);
    await capture(page, "m7-classer", [{ loc: modale(), n: 1 }]); await echap();
  });
  await essai("menu", async () => {
    await aller(page, "/");
    await page.getByText("Personnaliser le menu", { exact: false }).first().click(); await pause(1000);
    await capture(page, "m8-menu", [{ loc: modale(), n: 1 }]); await echap();
  });
  await nav.close();
})();
