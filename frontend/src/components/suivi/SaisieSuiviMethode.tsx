import { Divider, Loader, Text } from "@mantine/core";
import { useActivite } from "../../api/projects";
import { AvancementModal } from "../../pages/projets/AvancementModal";
import { voc } from "../../utils/vocabulaire";
import { SaisiePointSuiviForm } from "./SaisiePointSuiviForm";

const STATUTS_ACTIVITE = [
  { value: "NON_REALISEE", label: "Non réalisée" },
  { value: "EN_COURS", label: "En cours" },
  { value: "REALISEE", label: "Réalisée" },
];

/**
 * « Saisir un suivi » pour une activité dont le taux ne se calcule pas par quantité :
 * d'abord la saisie propre à sa méthode (tâches, jalons, livrables, taux manuel),
 * puis, comme toujours, la période avec budget, statut et commentaire.
 */
export function SaisieSuiviMethode({
  activiteId,
  modifiable,
  onDone,
}: {
  activiteId: number;
  modifiable: boolean;
  onDone: () => void;
}) {
  const { data: activite, isLoading } = useActivite(activiteId);
  if (isLoading || !activite) return <Loader size="sm" />;
  const binaire = activite.methode_calcul_effective === "BINAIRE";
  return (
    <>
      <AvancementModal element={activite} modifiable={modifiable} />
      <Divider
        my="md"
        label={binaire ? voc("Marquer l'activité comme réalisée") : voc("Saisie de la période : budget, statut, commentaire")}
        labelPosition="left"
      />
      <Text size="xs" c="dimmed" mb="xs">
        {binaire
          ? voc("Méthode binaire : choisis le statut « Réalisée » pour passer l'activité à 100 %.")
          : voc("Facultatif — le taux de cette activité vient de la saisie ci-dessus ; cette partie enregistre le budget dépensé, le statut et un commentaire pour la période.")}
      </Text>
      <SaisiePointSuiviForm
        activiteId={activiteId}
        statutsDisponibles={STATUTS_ACTIVITE}
        avecBudget
        avecQuantite={false}
        onDone={onDone}
      />
    </>
  );
}
