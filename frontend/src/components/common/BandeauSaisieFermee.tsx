import { Alert } from "@mantine/core";
import { CalendarX } from "lucide-react";
import { useAuth } from "../../auth/useAuth";
import type { Projet } from "../../types";
import { voc } from "../../utils/vocabulaire";

/**
 * Saisie fermée hors période de rapportage (voir Paramètres > Périodes de rapportage) :
 * explique ce qui est fermé et quand la prochaine période s'ouvre.
 */
export function BandeauSaisieFermee({ projet }: { projet: Projet }) {
  const { user } = useAuth();
  if (projet.etat_saisie.ouverte) return null;
  return (
    <Alert color="orange" icon={<CalendarX size={18} />} title={voc("Saisie fermée")}>
      {projet.etat_saisie.message}
      {user?.role === "ADMIN" && voc(" En tant qu'administrateur, vous pouvez quand même corriger.")}
    </Alert>
  );
}
