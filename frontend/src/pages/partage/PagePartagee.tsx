import { Suspense, useState } from "react";
import { useParams } from "react-router-dom";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { isAxiosError } from "axios";
import { Eye, Lock } from "lucide-react";
import { Alert, Box, Button, Container, Group, Paper, PasswordInput, Stack, Text, Title } from "@mantine/core";
import { apiClient } from "../../api/client";
import { ouvrirLienProtege } from "../../api/partage";
import { messageErreurApi } from "../../utils/erreurs";
import { useConfigurationMenu, useConfigurationTableauDeBord, useDashboardConsolide } from "../../api/dashboard";
import type { FiltresDashboard } from "../../types";
import { PartageContext, usePartage, type Partage } from "../../utils/partage";
import { definirVocabulaire } from "../../utils/vocabulaire";
import { aLaDemande } from "../../utils/aLaDemande";

import { locale } from "../../utils/i18n";
import { voc } from "../../utils/vocabulaire";
interface DescriptionLien {
  type: Partage["type"];
  contenu: Partage["contenu"];
  libelle: string;
  expire_le: string | null;
  projet: { id: number; code: string; nom: string } | null;
  filtres: Record<string, unknown>;
  partage_par: string;
}

// Seule la page partagée est téléchargée (tableau de bord ou suivi d'un projet), pas les deux.
const DashboardConsolidePage = aLaDemande(() => import("../DashboardConsolidePage").then((m) => ({ default: m.DashboardConsolidePage })));
const SuiviProjetDashboard = aLaDemande(() => import("../suivi/SuiviProjetDashboard").then((m) => ({ default: m.SuiviProjetDashboard })));

/** Chiffres du tableau de bord demandés en même temps que le vocabulaire, au lieu d'attendre ce dernier. */
function PrechargementTableau() {
  const partage = usePartage()!;
  useDashboardConsolide(partage.filtres as FiltresDashboard);
  useConfigurationTableauDeBord();
  return null;
}

/** Contenu de la page, une fois le vocabulaire de l'organisation chargé. */
function Contenu() {
  const partage = usePartage()!;
  const { data: menu, isLoading } = useConfigurationMenu();
  definirVocabulaire(menu?.vocabulaire);
  if (isLoading) {
    return (
      <>
        {partage.type === "TABLEAU_DE_BORD" && <PrechargementTableau />}
        <Text c="dimmed">{voc("Chargement…")}</Text>
      </>
    );
  }
  return (
    <Suspense fallback={<Text c="dimmed">{voc("Chargement…")}</Text>}>
      {partage.type === "TABLEAU_DE_BORD" ? <DashboardConsolidePage /> : <SuiviProjetDashboard />}
    </Suspense>
  );
}

/** Lien protégé : le mot de passe donné par la personne qui a partagé la page. */
function MotDePasseLien({ jeton, libelle, partagePar }: { jeton: string; libelle?: string; partagePar?: string }) {
  const queryClient = useQueryClient();
  const [motDePasse, setMotDePasse] = useState("");
  const [erreur, setErreur] = useState("");
  const [envoi, setEnvoi] = useState(false);

  async function valider(event: React.FormEvent) {
    event.preventDefault();
    setErreur("");
    setEnvoi(true);
    try {
      await ouvrirLienProtege(jeton, motDePasse);
      await queryClient.invalidateQueries({ queryKey: ["partage", jeton] });
    } catch (error) {
      setErreur(messageErreurApi(error, voc("Mot de passe incorrect.")));
    } finally {
      setEnvoi(false);
    }
  }

  return (
    <Paper withBorder radius="md" p="lg" maw={420} mx="auto" mt="xl">
      <form onSubmit={valider}>
        <Stack gap="sm">
          <Group gap="xs"><Lock size={18} /><Title order={4}>{voc("Page protégée")}</Title></Group>
          <Text size="sm" c="dimmed">
            {libelle ? voc`« ${libelle} »` + " — " : ""}
            {partagePar ? voc`partagée par ${partagePar}. ` : ""}
            {voc("Saisissez le mot de passe qui vous a été communiqué avec le lien.")}
          </Text>
          <PasswordInput label={voc("Mot de passe")} value={motDePasse} onChange={(e) => setMotDePasse(e.currentTarget.value)}
            error={erreur || undefined} autoFocus required />
          <Button type="submit" loading={envoi} disabled={!motDePasse}>{voc("Ouvrir la page")}</Button>
        </Stack>
      </form>
    </Paper>
  );
}

/** Page ouverte par un lien de partage : lecture seule, sans compte (mot de passe si le lien en a un). */
export function PagePartagee() {
  const { jeton = "" } = useParams();
  const { data, isLoading, isError, error } = useQuery({
    queryKey: ["partage", jeton],
    queryFn: async () => (await apiClient.get<DescriptionLien>(`/public/partage/${jeton}/`)).data,
    retry: false,
    staleTime: Infinity,
  });

  return (
    <Box bg="gray.0" mih="100vh">
      <Box bg="teal.9" c="white" px="md" py="sm">
        <Group justify="space-between" wrap="nowrap">
          <Text fw={700} size="sm">Expertise-ID Monitora</Text>
          <Group gap={6} wrap="nowrap">
            <Eye size={15} />
            <Text size="xs" c="teal.1">{voc("Lecture seule")}{data?.partage_par ? voc` · partagé par ${data.partage_par}` : ""}</Text>
          </Group>
        </Group>
      </Box>
      <Container size="xl" py="md" px={{ base: "sm", sm: "lg" }}>
        {isLoading && <Text c="dimmed">{voc("Chargement…")}</Text>}
        {isError && isAxiosError(error) && error.response?.data?.code === "mot_de_passe_requis" ? (
          <MotDePasseLien jeton={jeton} libelle={error.response.data.libelle} partagePar={error.response.data.partage_par} />
        ) : isError && (
          <Alert color="orange" title={voc("Lien indisponible")}>
            {voc("Ce lien de partage n'existe pas, a expiré ou a été désactivé. Demandez un nouveau lien à la personne qui vous l'a envoyé.")}
          </Alert>
        )}
        {data && (
          <PartageContext.Provider
            value={{ jeton, type: data.type, contenu: data.contenu, projetId: data.projet?.id ?? null, filtres: data.filtres }}
          >
            {data.expire_le && (
              <Text size="xs" c="dimmed" mb="xs">{voc("Lien valable jusqu'au")} {new Date(data.expire_le).toLocaleDateString(locale())}.</Text>
            )}
            <Contenu />
          </PartageContext.Provider>
        )}
      </Container>
    </Box>
  );
}
