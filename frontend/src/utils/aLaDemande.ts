import { lazy } from "react";

const CLE = "rechargement-apres-mise-a-jour";
type Chargeur = Parameters<typeof lazy>[0];

/**
 * Page chargée à la demande (React.lazy). Après une mise en ligne, une page restée ouverte peut demander un
 * morceau de l'ancienne version, qui n'existe plus : la page est alors rechargée une fois, sur la nouvelle.
 */
export function aLaDemande(charger: Chargeur) {
  return lazy(() =>
    charger()
      .then((module) => {
        try { sessionStorage.removeItem(CLE); } catch { /* navigation privée */ }
        return module;
      })
      .catch((erreur) => {
        let dejaFait = false;
        try { dejaFait = sessionStorage.getItem(CLE) === "1"; sessionStorage.setItem(CLE, "1"); } catch { /* navigation privée */ }
        if (!dejaFait) {
          window.location.reload();
          return new Promise<never>(() => {});  // la page se recharge
        }
        throw erreur;
      }),
  );
}
