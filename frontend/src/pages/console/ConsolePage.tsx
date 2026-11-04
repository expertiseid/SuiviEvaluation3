import { useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  Alert, Anchor, Badge, Box, Button, Checkbox, Container, Group, Loader, Modal, Stack, Table, Tabs, Text, TextInput, Title, Tooltip,
} from "@mantine/core";
import { notifications } from "@mantine/notifications";
import { Building2, CirclePause, CirclePlay, Handshake, LogOut, Newspaper, Rocket, UserPlus } from "lucide-react";
import { useActiverDemande, useDemandesConsole, useOrganisationsConsole, useStatutOrganisation } from "../../api/console";
import { type DemandeInscription, useIdentiteOrganisation } from "../../api/identite";
import { useAuth } from "../../auth/useAuth";
import { LogoPlateforme, PiedDePage } from "../../components/common/Logos";
import { messageErreurApi } from "../../utils/erreurs";
import { locale } from "../../utils/i18n";
import { voc } from "../../utils/vocabulaire";
import { erreursParChamp } from "../plaintes/saisieRetour";
import { ActualitesSite, PartenairesSite } from "./SiteVitrine";

const COULEUR_DEMANDE: Record<string, string> = {
  ABONNEMENT_REQUIS: "orange", OFFRE_CHOISIE: "blue", EN_ACTIVATION: "grape", ACTIVEE: "teal", REFUSEE: "gray",
};
const date = (d: string | null) => (d ? new Date(d).toLocaleDateString(locale()) : "—");

/** Création de l'espace d'une organisation inscrite : identifiant interne (nom de sa base), référentiel des zones. */
function ActiverModal({ demande, onClose }: { demande: DemandeInscription; onClose: () => void }) {
  const activer = useActiverDemande();
  const [sousDomaine, setSousDomaine] = useState(demande.sous_domaine);
  const [zones, setZones] = useState(true);
  const [erreur, setErreur] = useState<string | null>(null);
  const valider = async () => {
    setErreur(null);
    try {
      await activer.mutateAsync({ id: demande.id, sous_domaine: sousDomaine, zones });
      notifications.show({ color: "teal", message: voc("Création de l'espace lancée : elle prend jusqu'à une minute.") });
      onClose();
    } catch (error) {
      setErreur(erreursParChamp(error).sous_domaine ?? messageErreurApi(error, voc("L'activation n'a pas abouti.")));
    }
  };
  return (
    <Modal opened onClose={onClose} title={voc`Activer l'espace de ${demande.organisation}`} size="lg">
      <Stack>
        <Text size="sm" c="dimmed">
          {voc("La plateforme crée la base de données de l'organisation, ses tables et son compte administrateur (adresse courriel et mot de passe choisis à l'inscription), puis envoie le courriel « Votre espace est prêt ».")}
        </Text>
        <TextInput label={voc("Identifiant interne")} value={sousDomaine} onChange={(e) => setSousDomaine(e.currentTarget.value.toLowerCase())}
          description={voc("Sert à nommer la base de l'organisation ; les utilisateurs ne le voient pas.")} error={erreur} dir="ltr" />
        <Checkbox checked={zones} onChange={(e) => setZones(e.currentTarget.checked)}
          label={voc("Installer le référentiel des zones du Burkina Faso (régions et provinces)")} />
        <Group justify="flex-end">
          <Button variant="default" onClick={onClose}>{voc("Annuler")}</Button>
          <Button leftSection={<Rocket size={16} />} onClick={valider} loading={activer.isPending}>{voc("Créer et ouvrir l'espace")}</Button>
        </Group>
      </Stack>
    </Modal>
  );
}

function Demandes() {
  const { data: demandes = [], isLoading } = useDemandesConsole();
  const [aActiver, setAActiver] = useState<DemandeInscription | null>(null);
  if (isLoading) return <Loader size="sm" />;
  return (
    <>
      <Table.ScrollContainer minWidth={980}>
        <Table withTableBorder striped verticalSpacing="sm">
          <Table.Thead>
            <Table.Tr>
              <Table.Th>{voc("Reçue le")}</Table.Th>
              <Table.Th>{voc("Organisation")}</Table.Th>
              <Table.Th>{voc("Contact")}</Table.Th>
              <Table.Th>{voc("Identifiant interne")}</Table.Th>
              <Table.Th>{voc("Offre")}</Table.Th>
              <Table.Th>{voc("État")}</Table.Th>
              <Table.Th w={150} />
            </Table.Tr>
          </Table.Thead>
          <Table.Tbody>
            {demandes.map((d) => (
              <Table.Tr key={d.id} style={{ verticalAlign: "top" }}>
                <Table.Td><Text size="sm">{date(d.cree_le)}</Text></Table.Td>
                <Table.Td>
                  <Text size="sm" fw={600}>{d.organisation}</Text>
                  <Text size="xs" c="dimmed">{[d.type_organisation, d.pays, d.taille].filter(Boolean).join(" · ")}</Text>
                </Table.Td>
                <Table.Td>
                  <Text size="sm">{d.contact_nom}</Text>
                  <Text size="xs"><Anchor href={`mailto:${d.courriel}`} size="xs">{d.courriel}</Anchor> · {d.telephone}</Text>
                </Table.Td>
                <Table.Td><Text size="sm" ff="monospace">{d.sous_domaine || "—"}</Text></Table.Td>
                <Table.Td>{d.offre_libelle ? <Badge variant="light">{d.offre_libelle}</Badge> : <Text size="sm" c="dimmed">—</Text>}</Table.Td>
                <Table.Td>
                  <Badge variant="light" color={COULEUR_DEMANDE[d.statut]} tt="none" leftSection={d.statut === "EN_ACTIVATION" ? <Loader size={10} color="grape" /> : undefined}>
                    {d.statut_libelle}
                  </Badge>
                  {d.erreur_activation && (
                    <Tooltip label={d.erreur_activation} multiline w={320}><Text size="xs" c="red" mt={4}>{voc("Échec de la dernière activation")}</Text></Tooltip>
                  )}
                </Table.Td>
                <Table.Td>
                  {(d.statut === "ABONNEMENT_REQUIS" || d.statut === "OFFRE_CHOISIE") && (
                    <Button size="xs" leftSection={<Rocket size={14} />} onClick={() => setAActiver(d)}>{voc("Activer")}</Button>
                  )}
                </Table.Td>
              </Table.Tr>
            ))}
            {demandes.length === 0 && (
              <Table.Tr><Table.Td colSpan={7}><Text size="sm" c="dimmed">{voc("Aucune demande pour l'instant.")}</Text></Table.Td></Table.Tr>
            )}
          </Table.Tbody>
        </Table>
      </Table.ScrollContainer>
      {aActiver && <ActiverModal demande={aActiver} onClose={() => setAActiver(null)} />}
    </>
  );
}

function Organisations() {
  const { data: organisations = [], isLoading } = useOrganisationsConsole();
  const changer = useStatutOrganisation();
  const basculer = async (id: number, statut: "ACTIVE" | "SUSPENDUE") => {
    try {
      await changer.mutateAsync({ id, statut });
      notifications.show({ color: statut === "ACTIVE" ? "teal" : "orange", message: statut === "ACTIVE" ? voc("Espace réactivé") : voc("Espace suspendu") });
    } catch (error) {
      notifications.show({ color: "red", message: messageErreurApi(error, voc("Erreur lors de l'enregistrement")) });
    }
  };
  if (isLoading) return <Loader size="sm" />;
  return (
    <Table.ScrollContainer minWidth={900}>
      <Table withTableBorder striped verticalSpacing="sm">
        <Table.Thead>
          <Table.Tr>
            <Table.Th>{voc("Organisation")}</Table.Th>
            <Table.Th>{voc("Comptes")}</Table.Th>
            <Table.Th>{voc("Offre")}</Table.Th>
            <Table.Th>{voc("Ouvert le")}</Table.Th>
            <Table.Th>{voc("État")}</Table.Th>
            <Table.Th w={150} />
          </Table.Tr>
        </Table.Thead>
        <Table.Tbody>
          {organisations.map((o) => (
            <Table.Tr key={o.id}>
              <Table.Td>
                <Text size="sm" fw={600}>{o.nom}</Text>
                {o.mode_demo && <Badge size="xs" variant="light" color="orange">{voc("Démonstration")}</Badge>}
              </Table.Td>
              <Table.Td><Text size="sm">{o.comptes}</Text></Table.Td>
              <Table.Td><Text size="sm">{o.offre || "—"}</Text></Table.Td>
              <Table.Td><Text size="sm">{date(o.active_le)}</Text></Table.Td>
              <Table.Td><Badge variant="light" tt="none" color={o.statut === "ACTIVE" ? "teal" : o.statut === "SUSPENDUE" ? "red" : "gray"}>{o.statut_libelle}</Badge></Table.Td>
              <Table.Td>
                {o.statut === "ACTIVE" && (
                  <Button size="xs" variant="light" color="orange" leftSection={<CirclePause size={14} />} onClick={() => basculer(o.id, "SUSPENDUE")}>{voc("Suspendre")}</Button>
                )}
                {o.statut === "SUSPENDUE" && (
                  <Button size="xs" variant="light" leftSection={<CirclePlay size={14} />} onClick={() => basculer(o.id, "ACTIVE")}>{voc("Réactiver")}</Button>
                )}
              </Table.Td>
            </Table.Tr>
          ))}
          {organisations.length === 0 && (
            <Table.Tr><Table.Td colSpan={6}><Text size="sm" c="dimmed">{voc("Aucune organisation pour l'instant.")}</Text></Table.Td></Table.Tr>
          )}
        </Table.Tbody>
      </Table>
    </Table.ScrollContainer>
  );
}

/** Console Expertise-ID (plateforme multi-organisations), ouverte depuis sa page de connexion /expertise-id. */
export function ConsolePage() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const { data: plateforme } = useIdentiteOrganisation();
  return (
    <Box bg="gray.0" mih="100vh" style={{ display: "flex", flexDirection: "column" }}>
      <Box bg="teal.9" c="white">
        <Container size="xl" py="sm">
          <Group justify="space-between">
            <Group gap="sm"><LogoPlateforme taille={30} clair /><Badge color="white" c="teal.9" variant="filled">{voc("Console Expertise-ID")}</Badge></Group>
            <Group gap="sm">
              <Text size="sm">{user?.first_name || user?.username}</Text>
              <Button size="xs" variant="subtle" color="gray.0" leftSection={<LogOut size={14} />} onClick={() => { logout(); navigate("/expertise-id"); }}>{voc("Déconnexion")}</Button>
            </Group>
          </Group>
        </Container>
      </Box>
      <Container size="xl" py="lg" style={{ flex: 1, width: "100%" }}>
        {!plateforme ? <Loader /> : !plateforme.multi_organisations ? (
          <Alert color="gray">{voc("La console Expertise-ID n'est disponible que sur la plateforme multi-organisations.")}</Alert>
        ) : !user?.est_operateur ? (
          <Alert color="orange">{voc("Réservé aux opérateurs Expertise-ID.")}</Alert>
        ) : (
          <Stack gap="md">
            <Title order={2}>{voc("Organisations de la plateforme")}</Title>
            <Tabs defaultValue="demandes" keepMounted={false}>
              <Tabs.List>
                <Tabs.Tab value="demandes" leftSection={<UserPlus size={15} />}>{voc("Demandes d'inscription")}</Tabs.Tab>
                <Tabs.Tab value="organisations" leftSection={<Building2 size={15} />}>{voc("Espaces des organisations")}</Tabs.Tab>
                <Tabs.Tab value="actualites" leftSection={<Newspaper size={15} />}>{voc("Site : actualités")}</Tabs.Tab>
                <Tabs.Tab value="partenaires" leftSection={<Handshake size={15} />}>{voc("Site : partenaires")}</Tabs.Tab>
              </Tabs.List>
              <Tabs.Panel value="demandes" pt="md"><Demandes /></Tabs.Panel>
              <Tabs.Panel value="organisations" pt="md"><Organisations /></Tabs.Panel>
              <Tabs.Panel value="actualites" pt="md"><ActualitesSite /></Tabs.Panel>
              <Tabs.Panel value="partenaires" pt="md"><PartenairesSite /></Tabs.Panel>
            </Tabs>
          </Stack>
        )}
      </Container>
      <PiedDePage />
    </Box>
  );
}
