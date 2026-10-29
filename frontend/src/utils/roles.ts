import { voc } from "./vocabulaire";

/**
 * Nom d'un rôle envoyé par le serveur. Les rôles système gardent leur nom d'origine en base
 * (voir apps/accounts/constants.py) : on les traduit ; un rôle créé ou renommé par
 * l'organisation reste tel qu'elle l'a écrit.
 */
export function libelleRole(libelle: string): string {
  const systeme: Record<string, string> = {
    Administrateur: voc("Administrateur"),
    "Coordonnateur général": voc("Coordonnateur général"),
    "Chargé de Suivi-Évaluation": voc("Chargé de Suivi-Évaluation"),
    "Chef de projet": voc("Chef de projet"),
    "Chef de service": voc("Chef de service"),
    "Animateur de terrain": voc("Animateur de terrain"),
  };
  return systeme[libelle] ?? libelle;
}
