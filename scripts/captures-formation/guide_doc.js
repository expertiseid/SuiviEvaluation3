const { ouvrir, capture, aller, onglet, zone, segment, pause, bouton } = require("./guide_commun");
(async () => {
  const { nav, page } = await ouvrir();
  try {
    await aller(page, "/projets/16"); await onglet(page, "Documents").click(); await pause(1500);
    await page.getByText("02 - Rapports").first().click(); await pause(1500);
    await capture(page, "m6-dans-dossier", [{ loc: page.getByRole("button", { name: "Actions" }).last(), n: 1 }]);
    await page.getByRole("button", { name: "Actions" }).last().click(); await pause(700);
    await capture(page, "m6-menu-document", [{ loc: page.getByRole("menuitem", { name: "Partager par lien" }), n: 1 }, { loc: page.getByRole("menuitem", { name: "Versions" }), n: 2 }, { loc: page.getByRole("menuitem", { name: "Supprimer" }), n: 3 }]);
    await page.getByRole("menuitem", { name: "Partager par lien" }).click(); await pause(1200);
    await page.getByLabel("Pour qui", { exact: false }).first().fill("Bailleur — rapport annuel");
    await capture(page, "m6-partager", [{ loc: segment(page, "Consulter seulement"), n: 1 }, { loc: zone(page, "Pour qui"), n: 2 }, { loc: segment(page, "7 jours"), n: 3 }, { loc: zone(page, "Mot de passe"), n: 4 }, { loc: bouton(page, "Créer le lien").first(), n: 5 }]);
  } catch (e) { console.log("✗", e.message.split("\n")[0]); }
  await nav.close();
})();
