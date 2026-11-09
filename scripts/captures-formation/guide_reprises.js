const { ouvrir, capture, aller, bouton, onglet, zone, segment, pause } = require("./guide_commun");
(async () => {
  const { nav, page } = await ouvrir();
  const essai = async (nom, f) => { try { await f(); } catch (e) { console.log("✗", nom, e.message.split("\n")[0]); await page.keyboard.press("Escape").catch(() => {}); } };
  const echap = async () => { await page.keyboard.press("Escape"); await pause(600); };
  const modale = () => page.locator(".mantine-Modal-content").last();
  await essai("langue", async () => {
    await aller(page, "/");
    await page.getByRole("button", { name: /FR/ }).first().click(); await pause(700);
    await capture(page, "m1-langue", [{ loc: page.locator("[role=menu], .mantine-Menu-dropdown, .mantine-Popover-dropdown, .mantine-Combobox-dropdown").first(), n: 1 }]);
    await echap();
  });
  await essai("m2-liste", async () => {
    await aller(page, "/strategie");
    await capture(page, "m2-liste", [{ loc: page.getByRole("link", { name: "Stratégies" }).first(), n: 1 }, { loc: bouton(page, "Nouveau document").first(), n: 2 }, { loc: bouton(page, "Chaîne des documents").first(), n: 3 }, { loc: page.getByText("Ouvrir", { exact: true }).first(), n: 4 }]);
  });
  await essai("m2-niveaux", async () => {
    await aller(page, "/strategie/1"); await onglet(page, "Configuration des niveaux").click(); await pause(1000);
    await capture(page, "m2-niveaux", [{ loc: onglet(page, "Configuration des niveaux"), n: 1 }, { loc: page.getByPlaceholder("Ex : Orientation", { exact: false }).first(), n: 2 }]);
  });
  await essai("m4", async () => {
    await aller(page, "/indicateurs");
    await bouton(page, "Nouvel indicateur").first().click(); await pause(900);
    await capture(page, "m4-nouveau", [{ loc: zone(page, "Libellé"), n: 1 }, { loc: zone(page, "Unité"), n: 2 }, { loc: zone(page, "Valeur de base"), n: 3 }, { loc: zone(page, "Valeur cible"), n: 4 }]);
    await capture(page, "m4-nouveau-suite", [{ loc: zone(page, "Fréquence"), n: 1 }, { loc: zone(page, "Rattaché"), n: 2 }, { loc: modale().locator("button").filter({ hasText: /Créer|Enregistrer/ }).last(), n: 3 }]);
    await echap();
    await aller(page, "/indicateurs/154");
    await capture(page, "m4-fiche", [{ loc: page.getByPlaceholder("Ex : Année", { exact: false }).first(), n: 1 }, { loc: zone(page, "Du"), n: 2 }, { loc: zone(page, "Au"), n: 3 }, { loc: zone(page, "Cible"), n: 4 }, { loc: bouton(page, "Ajouter").first(), n: 5 }]);
  });
  await essai("m8", async () => {
    await aller(page, "/utilisateurs");
    await bouton(page, "Nouvel utilisateur").first().click(); await pause(900);
    await capture(page, "m8-nouvel-utilisateur", [{ loc: zone(page, "Adresse courriel"), n: 1 }, { loc: zone(page, "Rôle"), n: 2 }, { loc: zone(page, "Niveau d'accès"), n: 3 }, { loc: zone(page, "Mot de passe"), n: 4 }]);
    await echap();
  });
  await essai("corbeille", async () => {
    await aller(page, "/corbeille");
    await capture(page, "m6-corbeille", [{ loc: page.getByRole("link", { name: "Corbeille" }).first(), n: 1 }]);
  });
  await nav.close();
})();
