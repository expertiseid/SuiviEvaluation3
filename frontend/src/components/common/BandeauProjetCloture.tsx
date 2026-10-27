import { Alert, Button } from "@mantine/core";
import { notifications } from "@mantine/notifications";
import { Lock } from "lucide-react";
import { useUpdateProjet } from "../../api/projects";
import { useAuth } from "../../auth/useAuth";
import { messageErreurApi } from "../../utils/erreurs";
import { voc } from "../../utils/vocabulaire";

/**
 * Projet clôturé : lecture seule (le serveur refuse toute modification, voir
 * apps/projects/verrou.py). Seul l'administrateur peut le rouvrir.
 */
export function BandeauProjetCloture({ projetId }: { projetId: number }) {
  const { user } = useAuth();
  const maj = useUpdateProjet();
  return (
    <Alert color="gray" icon={<Lock size={18} />} title={voc("Projet clôturé")}>
      {voc("Ce projet est en lecture seule : sa planification, son suivi, ses indicateurs, ses bénéficiaires et ses documents ne peuvent plus être modifiés.")}
      {user?.role === "ADMIN" ? (
        <Button
          mt="xs"
          size="xs"
          variant="light"
          loading={maj.isPending}
          onClick={() =>
            maj.mutate(
              { id: projetId, payload: { statut: "EN_COURS" } },
              {
                onSuccess: () => notifications.show({ message: voc("Projet rouvert"), color: "green" }),
                onError: (error) => notifications.show({ message: messageErreurApi(error, "Erreur"), color: "red" }),
              },
            )
          }
        >
          {voc("Rouvrir le projet")}
        </Button>
      ) : (
        <> {voc("Seul un administrateur peut le rouvrir.")}</>
      )}
    </Alert>
  );
}
