import { Link } from "react-router-dom";
import { Alert, Button, Group, Text } from "@mantine/core";
import { CalendarClock } from "lucide-react";
import { useAbonnement } from "../../api/console";
import { useAuth } from "../../auth/useAuth";
import { locale } from "../../utils/i18n";
import { voc } from "../../utils/vocabulaire";

const jour = (d: string | null) => (d ? new Date(`${d}T12:00:00`).toLocaleDateString(locale(), { day: "numeric", month: "long" }) : "");

/**
 * Fin d'abonnement proche (7 derniers jours) ou passée (7 jours de grâce) : bandeau en haut de chaque page.
 * Essai gratuit : rappelé pendant tout l'essai, avec sa date de fin.
 */
export function BandeauAbonnement() {
  const { user } = useAuth();
  const { data: page } = useAbonnement();
  const essai = !!page?.essai && (page.statut === "ACTIF" || page.statut === "BIENTOT");
  if (!page || (!essai && page.statut !== "BIENTOT" && page.statut !== "GRACE")) return null;
  const admin = user?.role === "ADMIN";
  const texte = essai
    ? voc`Essai gratuit jusqu'au ${jour(page.fin)} (100 Mo de stockage). Ensuite, l'accès est bloqué jusqu'au choix d'une offre.`
    : page.statut === "BIENTOT"
    ? voc`L'abonnement de votre organisation se termine le ${jour(page.fin)}.`
    : voc`L'abonnement de votre organisation est terminé : l'accès sera bloqué le ${jour(page.fin_grace)}.`;
  return (
    <Alert color={essai && page.statut === "ACTIF" ? "blue" : page.statut === "GRACE" ? "orange" : "yellow"} variant="light" mb="md" icon={<CalendarClock size={18} />}>
      <Group justify="space-between" gap="sm">
        <Text size="sm">{texte} {!admin && voc("Prévenez l'administrateur de votre organisation.")}</Text>
        {admin && <Button size="xs" component={Link} to="/mon-abonnement">{essai ? voc("Choisir une offre") : voc("Renouveler")}</Button>}
      </Group>
    </Alert>
  );
}
