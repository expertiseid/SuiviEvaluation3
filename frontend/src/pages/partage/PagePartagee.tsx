import { useParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { Eye } from "lucide-react";
import { Alert, Box, Container, Group, Text } from "@mantine/core";
import { apiClient } from "../../api/client";
import { useConfigurationMenu } from "../../api/dashboard";
import { DashboardConsolidePage } from "../DashboardConsolidePage";
import { SuiviProjetDashboard } from "../suivi/SuiviProjetDashboard";
import { PartageContext, usePartage, type Partage } from "../../utils/partage";
import { definirVocabulaire } from "../../utils/vocabulaire";

interface DescriptionLien {
  type: Partage["type"];
  contenu: Partage["contenu"];
  libelle: string;
  expire_le: string | null;
  projet: { id: number; code: string; nom: string } | null;
  filtres: Record<string, unknown>;
  partage_par: string;
}

/** Contenu de la page, une fois le vocabulaire de l'organisation chargé. */
function Contenu() {
  const partage = usePartage()!;
  const { data: menu, isLoading } = useConfigurationMenu();
  definirVocabulaire(menu?.vocabulaire);
  if (isLoading) return <Text c="dimmed">Chargement…</Text>;
  return partage.type === "TABLEAU_DE_BORD" ? <DashboardConsolidePage /> : <SuiviProjetDashboard />;
}

/** Page ouverte par un lien de partage : lecture seule, sans compte. */
export function PagePartagee() {
  const { jeton = "" } = useParams();
  const { data, isLoading, isError } = useQuery({
    queryKey: ["partage", jeton],
    queryFn: async () => (await apiClient.get<DescriptionLien>(`/public/partage/${jeton}/`)).data,
    retry: false,
    staleTime: Infinity,
  });

  return (
    <Box bg="gray.0" mih="100vh">
      <Box bg="teal.9" c="white" px="md" py="sm">
        <Group justify="space-between" wrap="nowrap">
          <Text fw={700} size="sm">Plateforme de Suivi-Évaluation</Text>
          <Group gap={6} wrap="nowrap">
            <Eye size={15} />
            <Text size="xs" c="teal.1">Lecture seule{data?.partage_par ? ` · partagé par ${data.partage_par}` : ""}</Text>
          </Group>
        </Group>
      </Box>
      <Container size="xl" py="md" px={{ base: "sm", sm: "lg" }}>
        {isLoading && <Text c="dimmed">Chargement…</Text>}
        {isError && (
          <Alert color="orange" title="Lien indisponible">
            Ce lien de partage n'existe pas, a expiré ou a été désactivé. Demandez un nouveau lien à la personne qui vous l'a envoyé.
          </Alert>
        )}
        {data && (
          <PartageContext.Provider
            value={{ jeton, type: data.type, contenu: data.contenu, projetId: data.projet?.id ?? null, filtres: data.filtres }}
          >
            {data.expire_le && (
              <Text size="xs" c="dimmed" mb="xs">Lien valable jusqu'au {new Date(data.expire_le).toLocaleDateString("fr-FR")}.</Text>
            )}
            <Contenu />
          </PartageContext.Provider>
        )}
      </Container>
    </Box>
  );
}
