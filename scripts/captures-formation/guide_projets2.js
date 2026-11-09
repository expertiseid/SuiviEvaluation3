const { ouvrir, capture, aller, bouton, onglet, zone, pause } = require("./guide_commun");
(async () => {
  const { nav, page } = await ouvrir();
  try {
    await aller(page, "/projets");
    await bouton(page, "Nouveau projet").first().click(); await pause(900);
    await zone(page, "Chef de projet").scrollIntoViewIfNeeded(); await page.mouse.wheel(0, 60); await pause(400);
    await capture(page, "projets-03-general-suite", [{ loc: zone(page, "Chef de projet"), n: 1 }, { loc: zone(page, "Utilisateurs affectés"), n: 2 }, { loc: bouton(page, "Ajouter un bailleur").first(), n: 3 }, { loc: zone(page, "Partenaire de mise en œuvre"), n: 4 }]);
    await zone(page, "Pays d'intervention").scrollIntoViewIfNeeded(); await pause(400);
    await capture(page, "projets-03b-zones", [{ loc: zone(page, "Pays d'intervention"), n: 1 }, { loc: page.locator(".mantine-Checkbox-root", { hasText: "Tout le pays" }).first(), n: 2 }]);
    await onglet(page, "Stratégie & capitalisation").click(); await pause(600);
    await zone(page, "Les saisies de réalisations").scrollIntoViewIfNeeded(); await pause(400);
    await capture(page, "projets-05b-approbations", [{ loc: zone(page, "Les saisies de réalisations"), n: 1 }, { loc: zone(page, "Les changements de planification"), n: 2 }, { loc: zone(page, "Éléments de capitalisation"), n: 3 }]);
  } catch (e) { console.log("✗", e.message.split("\n")[0]); }
  await nav.close();
})();
