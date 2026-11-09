const { ouvrir, capture, aller, bouton, zone, segment, pause } = require("./guide_commun");
(async () => {
  const { nav, page } = await ouvrir();
  const essai = async (nom, f) => { try { await f(); } catch (e) { console.log("✗", nom, e.message.split("\n")[0]); } };
  await aller(page, "/projets/16");
  await segment(page, "Arbre").click(); await pause(1200);
  const ligneIcone = async (classe) => {
    const i = await page.evaluate((c) => [...document.querySelectorAll("button")].findIndex((b) => b.querySelector(`svg.${c}`) && b.getBoundingClientRect().y > 550), classe);
    return page.locator("button").nth(i);
  };
  await essai("arbre", async () => {
    await capture(page, "planif-02-arbre", [{ loc: segment(page, "Arbre"), n: 1 }, { loc: await ligneIcone("lucide-plus"), n: 2 }, { loc: await ligneIcone("lucide-list-plus"), n: 3 }, { loc: bouton(page, "Éditer").first(), n: 4 }]);
  });
  await essai("edition", async () => {
    await bouton(page, "Éditer").first().click(); await pause(1000);
    await capture(page, "planif-02b-edition", [{ loc: bouton(page, "Terminer l'édition").first(), n: 1 }, { loc: await ligneIcone("lucide-pencil"), n: 2 }, { loc: await ligneIcone("lucide-trash-2"), n: 3 }]);
  });
  await essai("element", async () => {
    await (await ligneIcone("lucide-pencil")).click(); await pause(1200);
    await capture(page, "planif-03-element", [{ loc: zone(page, "Libellé"), n: 1 }, { loc: zone(page, "Description"), n: 2 }, { loc: zone(page, "Date de début prévue"), n: 3 }, { loc: zone(page, "Date de fin prévue"), n: 4 }]);
    await zone(page, "Budget alloué").scrollIntoViewIfNeeded(); await pause(400);
    await capture(page, "planif-04-element-suite", [{ loc: zone(page, "Budget alloué"), n: 1 }, { loc: zone(page, "Unité"), n: 2 }, { loc: zone(page, "Valeur de base"), n: 3 }, { loc: zone(page, "Quantité prévue"), n: 4 }]);
    await zone(page, "Services chargés").scrollIntoViewIfNeeded(); await pause(400);
    await capture(page, "planif-05-element-fin", [{ loc: zone(page, "Services chargés"), n: 1 }, { loc: zone(page, "Responsables"), n: 2 }, { loc: page.locator(".mantine-Modal-content button").filter({ hasText: /Enregistrer|Créer/ }).last(), n: 3 }]);
  });
  await nav.close();
})();
