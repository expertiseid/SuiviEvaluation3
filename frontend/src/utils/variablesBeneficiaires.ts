import type { Beneficiaire, VariableBeneficiaire } from "../types";

type Reponses = Beneficiaire["reponses"];

/** La variable concerne-t-elle un de ces projets ? */
export function concerne(variable: VariableBeneficiaire, projetIds: number[]) {
  return variable.tous_les_projets || variable.projets.some((id) => projetIds.includes(id));
}

/** Réponse lisible (fiche bénéficiaire). */
export function reponseLisible(variable: VariableBeneficiaire, valeur: Reponses[string] | undefined) {
  if (valeur === undefined || valeur === null || valeur === "") return "—";
  if (variable.type === "OUI_NON") return valeur ? "Oui" : "Non";
  if (Array.isArray(valeur)) return valeur.join(", ");
  if (variable.type === "DATE") return new Date(String(valeur)).toLocaleDateString("fr-FR");
  if (variable.type === "NOMBRE") return `${Number(valeur).toLocaleString("fr-FR")}${variable.unite ? ` ${variable.unite}` : ""}`;
  return String(valeur);
}
