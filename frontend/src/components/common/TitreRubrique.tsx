import { Title } from "@mantine/core";
import { useConfigurationMenu } from "../../api/dashboard";
import { voc } from "../../utils/vocabulaire";

/**
 * Titre d'une page principale : reprend le nom donné à sa rubrique dans
 * « Personnaliser le menu » (commun à tous), sinon le titre par défaut adapté
 * au vocabulaire de l'organisation.
 */
export function TitreRubrique({
  route,
  defaut,
  majuscules = false,
}: {
  route: string;
  defaut: string;
  majuscules?: boolean;
}) {
  const { data } = useConfigurationMenu();
  const titre = data?.libelles[route] || voc(defaut);
  return <Title order={2}>{majuscules ? titre.toUpperCase() : titre}</Title>;
}
