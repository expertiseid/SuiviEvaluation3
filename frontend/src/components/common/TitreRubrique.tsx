import { Title } from "@mantine/core";
import { useConfigurationMenu } from "../../api/dashboard";
import { langue } from "../../utils/i18n";
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
  // Les noms personnalisés sont en français : dans une autre langue, on garde la traduction.
  const titre = (langue() === "fr" && data?.libelles[route]) || voc(defaut);
  return <Title order={2}>{majuscules ? titre.toUpperCase() : titre}</Title>;
}
