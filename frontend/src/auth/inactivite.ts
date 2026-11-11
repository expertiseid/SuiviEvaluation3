import { notifications } from "@mantine/notifications";
import { apiClient, tokenStorage } from "../api/client";
import { voc } from "../utils/vocabulaire";

/**
 * Déconnexion après une période d'inactivité (le serveur la décide : apps/core/inactivite.py).
 *
 * - La durée, en minutes, est écrite par le serveur dans le jeton (marque « inactivite » ; 0 : jamais).
 * - L'activité (clavier, souris, toucher, défilement) est partagée entre les onglets du navigateur.
 * - Une saisie longue sans enregistrement compte comme une activité : on la signale au serveur
 *   (/session/activite/) pour qu'il ne ferme pas la session.
 * - Une minute avant la fin : avertissement ; à la fin : session fermée, retour à la connexion.
 */
const CLE_ACTIVITE = "se_derniere_activite";
const VERIFICATION_MS = 15_000;
const SIGNAL_SERVEUR_MS = 4 * 60_000;
const ECRITURE_MS = 10_000;
const EVENEMENTS = ["keydown", "mousedown", "mousemove", "touchstart", "scroll", "wheel"] as const;

let demarre = false;
let derniereEcriture = 0;
let dernierSignal = Date.now();
let avertissement: string | null = null;

/** Durée d'inactivité, en minutes, lue dans le jeton ; 0 sans session ou si le serveur ne déconnecte pas. */
function dureeMinutes(): number {
  const jeton = tokenStorage.getAccess();
  if (!jeton) return 0;
  try {
    const charge = JSON.parse(atob(jeton.split(".")[1].replace(/-/g, "+").replace(/_/g, "/")));
    return typeof charge.inactivite === "number" && charge.inactivite > 0 ? charge.inactivite : 0;
  } catch {
    return 0;
  }
}

function lireActivite(): number {
  try {
    return Number(localStorage.getItem(CLE_ACTIVITE)) || Date.now();
  } catch {
    return Date.now();
  }
}

function noterActivite() {
  const maintenant = Date.now();
  if (maintenant - derniereEcriture < ECRITURE_MS) return;
  derniereEcriture = maintenant;
  try {
    localStorage.setItem(CLE_ACTIVITE, String(maintenant));
  } catch {
    /* navigation privée : seul cet onglet compte */
  }
  if (avertissement) {
    notifications.hide(avertissement);
    avertissement = null;
  }
}

/** Ferme la session et renvoie à l'écran de connexion, avec le message « déconnecté pour inactivité ». */
export function deconnecterPourInactivite() {
  tokenStorage.clear();
  window.location.href = "/login?inactif=1";
}

function verifier() {
  const minutes = dureeMinutes();
  if (!minutes) return;
  const ecoule = Date.now() - lireActivite();
  const limite = minutes * 60_000;
  if (ecoule >= limite) {
    deconnecterPourInactivite();
    return;
  }
  if (ecoule >= limite - 60_000 && !avertissement) {
    avertissement = notifications.show({
      title: voc("Session bientôt fermée"),
      message: voc("Sans activité de votre part, vous serez déconnecté dans une minute. Bougez la souris ou appuyez sur une touche pour rester connecté."),
      color: "orange",
      autoClose: false,
    });
  }
  // Activité récente sans échange avec le serveur (saisie longue) : on la lui signale.
  if (ecoule < VERIFICATION_MS * 2 && Date.now() - dernierSignal > SIGNAL_SERVEUR_MS) {
    dernierSignal = Date.now();
    apiClient.post("/session/activite/").catch(() => undefined);
  }
}

/** Démarre la surveillance (une seule fois par onglet), dès qu'une session est ouverte. */
export function surveillerInactivite() {
  if (demarre) return;
  demarre = true;
  derniereEcriture = 0;
  noterActivite();
  for (const evenement of EVENEMENTS) window.addEventListener(evenement, noterActivite, { passive: true });
  window.setInterval(verifier, VERIFICATION_MS);
}
