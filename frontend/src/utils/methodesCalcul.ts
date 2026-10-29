import type { MethodeAgregation, MethodeCalcul } from "../types";
import { voc } from "./vocabulaire";

/** Libellés des méthodes de calcul du taux d'exécution (voir backend apps/projects/taux.py). */
export const LIBELLES_METHODE: Record<MethodeCalcul, string> = {
  QUANTITE: voc("Par quantité"),
  TACHES: voc("Par tâches pondérées"),
  JALONS: voc("Par jalons pondérés"),
  LIVRABLES: voc("Par livrables"),
  BINAIRE: voc("Binaire (achevé / non achevé)"),
  MANUELLE: voc("Saisie manuelle"),
};

export const AIDES_METHODE: Record<MethodeCalcul, string> = {
  QUANTITE: voc("Quantité réalisée ÷ quantité prévue (saisies de suivi). Un dépassement de cible reste affiché (ex : 130 %)."),
  TACHES: voc("Σ (poids × avancement) des sous-activités, les poids totalisant 100 %."),
  JALONS: voc("Σ (poids × achèvement) des jalons, les poids totalisant 100 %."),
  LIVRABLES: voc("Somme des poids des livrables validés."),
  BINAIRE: voc("0 % tant que l'élément n'est pas « Réalisée », 100 % ensuite."),
  MANUELLE: voc("Taux saisi directement (0 à 100 %), jamais recalculé."),
};

export const LIBELLES_AGREGATION: Record<MethodeAgregation, string> = {
  MOYENNE: voc("Moyenne simple"),
  PONDEREE_BUDGET: voc("Moyenne pondérée par le budget"),
  PONDEREE_POIDS: voc("Moyenne pondérée par les poids"),
};

export const AIDES_AGREGATION: Record<MethodeAgregation, string> = {
  MOYENNE: voc("Moyenne des taux des éléments du dernier niveau en dessous."),
  PONDEREE_BUDGET: voc("Même moyenne, pondérée par le budget alloué de chaque élément."),
  PONDEREE_POIDS: voc("Moyenne des éléments directement en dessous, pondérée par leur poids."),
};

/** Options d'un sélecteur, avec « Hériter » en tête (valeur vide) quand `heritage` est fourni. */
export function optionsMethode(heritage?: string) {
  return [
    ...(heritage ? [{ value: "", label: heritage }] : []),
    ...Object.entries(LIBELLES_METHODE).map(([value, label]) => ({ value, label })),
  ];
}

export function optionsAgregation(heritage?: string) {
  return [
    ...(heritage ? [{ value: "", label: heritage }] : []),
    ...Object.entries(LIBELLES_AGREGATION).map(([value, label]) => ({ value, label })),
  ];
}

export function libelleMethodeEffective(methode: MethodeCalcul | "AGREGATION") {
  return methode === "AGREGATION" ? voc("Agrégé des éléments en dessous") : LIBELLES_METHODE[methode];
}
