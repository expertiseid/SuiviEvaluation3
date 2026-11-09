/**
 * Droits par module, réglés utilisateur par utilisateur (écran Utilisateurs) : masqué,
 * consultation, ou création et modification. Un module non réglé suit le niveau d'accès de
 * l'utilisateur ; l'Administrateur a toujours tout. Les onglets ne peuvent qu'être cachés.
 * Les mêmes règles sont appliquées côté serveur (apps/core/modules.py).
 */
import { useAuth } from "../auth/useAuth";
import { usePartage } from "./partage";
import type { NiveauModule, User } from "../types";
import { voc } from "./vocabulaire";

export interface ModuleReglable {
  cle: string;
  label: string;
  /** Distingue consultation et création / modification (sinon : visible ou masqué). */
  ecriture: boolean;
}

export function modulesReglables(): { group: string; items: ModuleReglable[] }[] {
  return [
    {
      group: voc("Menu"),
      items: [
        { cle: "/planification", label: voc("Planification complète"), ecriture: true },
        { cle: "/strategie", label: voc("Cadre stratégique"), ecriture: true },
        { cle: "/projets", label: voc("Projets et planification"), ecriture: true },
        { cle: "/indicateurs", label: voc("Indicateurs"), ecriture: true },
        { cle: "/suivi", label: voc("Suivi"), ecriture: true },
        { cle: "/beneficiaires", label: voc("Bénéficiaires"), ecriture: true },
        { cle: "/carte", label: voc("Cartographie"), ecriture: true },
        { cle: "/documents", label: voc("Documents"), ecriture: true },
        { cle: "/plaintes", label: voc("Plaintes et retours"), ecriture: true },
        { cle: "/zones-administratives", label: voc("Zones administratives"), ecriture: true },
        { cle: "/approbations", label: voc("Approbations"), ecriture: false },
        { cle: "/doublons", label: voc("Doublons d'enregistrement"), ecriture: false },
      ],
    },
    {
      group: voc("Onglets d'un projet"),
      items: [
        { cle: "projet:equipe", label: voc("Équipe de projet"), ecriture: true },
        { cle: "projet:financement", label: voc("Financement"), ecriture: true },
        { cle: "projet:partenaires", label: voc("Partenaires"), ecriture: false },
        { cle: "projet:niveaux", label: voc("Configuration des niveaux"), ecriture: false },
        { cle: "projet:periode", label: voc("Planification par période"), ecriture: false },
        { cle: "projet:indicateurs", label: voc("Indicateurs"), ecriture: false },
        { cle: "projet:documents", label: voc("Documents"), ecriture: false },
        { cle: "projet:cadre-logique", label: voc("Cadre logique"), ecriture: false },
        { cle: "projet:risques", label: voc("Risques"), ecriture: true },
        { cle: "projet:coherence", label: voc("Contrôle de cohérence"), ecriture: false },
        { cle: "projet:historique", label: voc("Historique"), ecriture: false },
      ],
    },
    { group: voc("Suivi"), items: [{ cle: "suivi:periode", label: voc("Suivi par période"), ecriture: false }] },
  ];
}

// Cacher un module cache aussi ce qui en dépend (le serveur refuse ses données).
export const DEPENDANCES: Record<string, string[]> = {
  "/documents": ["projet:documents"],
  "/beneficiaires": ["/doublons"],
};

/** Niveau appliqué à un module non réglé : celui du niveau d'accès de l'utilisateur. */
export function niveauParDefaut(niveauAcces: string | null | undefined): NiveauModule {
  return niveauAcces === "LECTURE_SEULE" ? "LECTURE" : "ECRITURE";
}

export function niveauModule(user: User | null | undefined, cle: string): NiveauModule {
  if (!user) return "LECTURE";
  if (user.role === "ADMIN") return "ECRITURE";
  const regle = user.acces_modules?.[cle];
  if (regle) return regle;
  const sourceMasquee = Object.entries(DEPENDANCES).some(
    ([source, dependants]) => dependants.includes(cle) && user.acces_modules?.[source] === "MASQUE",
  );
  return sourceMasquee ? "MASQUE" : niveauParDefaut(user.niveau_acces);
}

/** Droits de l'utilisateur connecté : estMasque(clé) et peutEcrire(clé). */
export function useAccesModules() {
  const { user } = useAuth();
  const partage = usePartage();
  if (partage) {
    // Lien de partage : lecture seule, sans les vues qui demandent un compte (suivi par période).
    return { estMasque: (cle: string) => cle.startsWith("suivi:"), peutEcrire: () => false };
  }
  return {
    estMasque: (cle: string) => niveauModule(user, cle) === "MASQUE",
    peutEcrire: (cle: string) => niveauModule(user, cle) === "ECRITURE",
  };
}
