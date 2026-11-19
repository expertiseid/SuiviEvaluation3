import { notifications } from "@mantine/notifications";
import { voc } from "./vocabulaire";

/**
 * Exports du compte connecté (réglés par l'Administrateur dans la fiche de l'utilisateur) : désactivés, tout
 * téléchargement d'export est arrêté avant d'être demandé (le serveur le refuse aussi : apps.core.exports).
 */
let autorise = true;

export function definirExportAutorise(valeur: boolean) {
  autorise = valeur;
}

export function exportAutorise() {
  return autorise;
}

/** Téléchargements permis même sans export : modèles d'import vierges, attestation de formation, sauvegarde de l'espace. */
export const TELECHARGEMENT_PERMIS = /modele|^\/?transfert\/|^\/?formation\//;

export const MESSAGE_EXPORT_DESACTIVE = "L'export est désactivé pour votre compte : demandez l'autorisation à l'administrateur.";

export function signalerExportDesactive() {
  notifications.show({ id: "export-desactive", title: voc("Export désactivé"), message: voc(MESSAGE_EXPORT_DESACTIVE), color: "orange" });
}
