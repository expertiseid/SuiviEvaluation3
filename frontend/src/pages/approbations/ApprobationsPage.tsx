import { useState } from "react";
import { Link } from "react-router-dom";
import { Check, X } from "lucide-react";
import { Badge, Button, Card, Group, Modal, Stack, Table, Text, Textarea, Title } from "@mantine/core";
import { notifications } from "@mantine/notifications";
import { useApprobations, useTraiterDemande, useTraiterSaisie } from "../../api/approbations";
import { TitreRubrique } from "../../components/common/TitreRubrique";
import { messageErreurApi } from "../../utils/erreurs";
import { voc } from "../../utils/vocabulaire";
import type { DemandeModification, SaisieAApprouver } from "../../types";

const TYPES_SAISIE: Record<SaisieAApprouver["type"], string> = {
  point: "Suivi",
  valeur: "Valeur d'indicateur",
  taux: "Taux manuel",
};

const COULEURS_ACTION: Record<DemandeModification["action"], string> = {
  CREATION: "teal",
  MODIFICATION: "blue",
  SUPPRESSION: "red",
};

function fmtDateHeure(iso: string) {
  return new Date(iso).toLocaleString("fr-FR", { dateStyle: "short", timeStyle: "short" });
}

function texte(valeur: unknown): string {
  if (valeur === null || valeur === undefined || valeur === "") return "—";
  if (Array.isArray(valeur)) return valeur.join(", ") || "—";
  return String(valeur);
}

function EtatBadge({ etat, motif }: { etat: string; motif: string }) {
  if (etat === "REJETEE") return <Badge color="red" variant="light" title={motif}>Rejetée</Badge>;
  return <Badge color="orange" variant="light">En attente</Badge>;
}

/** Détail d'une demande : champs changés (avant → après), ou valeurs d'un ajout. */
function DetailDemande({ demande }: { demande: DemandeModification }) {
  if (demande.action === "SUPPRESSION") return <Text size="xs" c="dimmed">Suppression de l'élément et de tout ce qui est en dessous.</Text>;
  const lignes =
    demande.action === "MODIFICATION"
      ? demande.changements.map((c) => `${c.champ} : ${texte(c.avant)} → ${texte(c.apres)}`)
      : demande.valeurs.map((v) => `${v.champ} : ${texte(v.valeur)}`);
  return (
    <Stack gap={0}>
      {lignes.map((l) => (
        <Text key={l} size="xs">{l}</Text>
      ))}
    </Stack>
  );
}

/**
 * Écran « Approbations » : saisies de réalisations et changements de planification des projets
 * qui exigent une approbation. L'approbateur approuve ou rejette (avec un motif, montré à
 * l'auteur) ; les autres utilisateurs y suivent leurs propres demandes.
 */
export function ApprobationsPage() {
  const { data, isLoading } = useApprobations();
  const traiterSaisie = useTraiterSaisie();
  const traiterDemande = useTraiterDemande();
  const [rejet, setRejet] = useState<{ saisie?: SaisieAApprouver; demande?: DemandeModification } | null>(null);
  const [motif, setMotif] = useState("");

  if (isLoading || !data) return <Text>Chargement…</Text>;
  const approbateur = data.peut_approuver;

  const resultat = (message: string) => ({
    onSuccess: () => {
      notifications.show({ message, color: "green" });
      setRejet(null);
      setMotif("");
    },
    onError: (error: unknown) => notifications.show({ message: messageErreurApi(error, "Erreur"), color: "red" }),
  });

  function confirmerRejet() {
    if (!motif.trim()) {
      notifications.show({ message: "Indique le motif du rejet.", color: "orange" });
      return;
    }
    if (rejet?.saisie) {
      traiterSaisie.mutate({ type: rejet.saisie.type, id: rejet.saisie.id, approuver: false, motif }, resultat("Saisie rejetée"));
    } else if (rejet?.demande) {
      traiterDemande.mutate({ id: rejet.demande.id, approuver: false, motif }, resultat("Demande rejetée"));
    }
  }

  const boutons = (approuver: () => void, rejeter: () => void) => (
    <Group gap={4} wrap="nowrap">
      <Button size="xs" color="teal" leftSection={<Check size={14} />} onClick={approuver}>
        Approuver
      </Button>
      <Button size="xs" variant="light" color="red" leftSection={<X size={14} />} onClick={rejeter}>
        Rejeter
      </Button>
    </Group>
  );

  return (
    <Stack gap="md">
      <div>
        <TitreRubrique route="/approbations" defaut="Approbations" />
        <Text size="sm" c="dimmed">
          {approbateur
            ? voc("Saisies et changements en attente sur les projets qui exigent une approbation : ils ne comptent (ou ne s'appliquent) qu'une fois approuvés. Un rejet demande un motif, montré à l'auteur.")
            : voc("Vos saisies et demandes de changement en attente d'approbation, et celles qui ont été rejetées (avec le motif). Une saisie rejetée peut être corrigée depuis la page Suivi : elle repart alors en approbation.")}
        </Text>
      </div>

      <Card withBorder padding="md">
        <Title order={4} mb="xs">{voc("Saisies de réalisations")} ({data.saisies.length})</Title>
        {data.saisies.length === 0 ? (
          <Text size="sm" c="dimmed">Rien en attente.</Text>
        ) : (
          <Table fz="sm" verticalSpacing={6} highlightOnHover>
            <Table.Thead>
              <Table.Tr>
                <Table.Th>{voc("Projet")}</Table.Th>
                <Table.Th>Élément</Table.Th>
                <Table.Th>Saisie</Table.Th>
                <Table.Th>Période</Table.Th>
                <Table.Th>Valeur</Table.Th>
                <Table.Th>Par</Table.Th>
                <Table.Th />
              </Table.Tr>
            </Table.Thead>
            <Table.Tbody>
              {data.saisies.map((s) => (
                <Table.Tr key={`${s.type}-${s.id}`}>
                  <Table.Td>
                    {s.projet_id ? <Link to={`/suivi/${s.projet_id}`}>{s.projet_code}</Link> : "—"}
                  </Table.Td>
                  <Table.Td>
                    <Text size="sm">{s.element}</Text>
                    {s.commentaire && <Text size="xs" c="dimmed" fs="italic">{s.commentaire}</Text>}
                  </Table.Td>
                  <Table.Td>{TYPES_SAISIE[s.type]}</Table.Td>
                  <Table.Td style={{ whiteSpace: "nowrap" }}>{s.periode}</Table.Td>
                  <Table.Td>
                    {s.valeur || "—"}
                    {s.budget && <Text size="xs" c="dimmed">{Number(s.budget).toLocaleString("fr-FR")} FCFA</Text>}
                  </Table.Td>
                  <Table.Td>
                    <Text size="sm">{s.saisi_par_nom}</Text>
                    <Text size="xs" c="dimmed">{fmtDateHeure(s.date)}</Text>
                  </Table.Td>
                  <Table.Td>
                    {approbateur ? (
                      boutons(
                        () => traiterSaisie.mutate({ type: s.type, id: s.id, approuver: true }, resultat("Saisie approuvée")),
                        () => setRejet({ saisie: s }),
                      )
                    ) : (
                      <Stack gap={2}>
                        <EtatBadge etat={s.etat} motif={s.motif_rejet} />
                        {s.motif_rejet && <Text size="xs" c="red">{s.motif_rejet}</Text>}
                      </Stack>
                    )}
                  </Table.Td>
                </Table.Tr>
              ))}
            </Table.Tbody>
          </Table>
        )}
      </Card>

      <Card withBorder padding="md">
        <Title order={4} mb="xs">{voc("Changements de planification")} ({data.demandes.length})</Title>
        {data.demandes.length === 0 ? (
          <Text size="sm" c="dimmed">Rien en attente.</Text>
        ) : (
          <Table fz="sm" verticalSpacing={6} highlightOnHover>
            <Table.Thead>
              <Table.Tr>
                <Table.Th>{voc("Projet")}</Table.Th>
                <Table.Th>Demande</Table.Th>
                <Table.Th>Élément</Table.Th>
                <Table.Th>Détail</Table.Th>
                <Table.Th>Par</Table.Th>
                <Table.Th />
              </Table.Tr>
            </Table.Thead>
            <Table.Tbody>
              {data.demandes.map((d) => (
                <Table.Tr key={d.id}>
                  <Table.Td>
                    <Link to={`/projets/${d.projet_id}`}>{d.projet_code}</Link>
                  </Table.Td>
                  <Table.Td>
                    <Badge variant="light" color={COULEURS_ACTION[d.action]}>{d.action_libelle}</Badge>
                    <Text size="xs" c="dimmed">{d.cible}</Text>
                  </Table.Td>
                  <Table.Td>{d.libelle}</Table.Td>
                  <Table.Td><DetailDemande demande={d} /></Table.Td>
                  <Table.Td>
                    <Text size="sm">{d.demandeur_nom}</Text>
                    <Text size="xs" c="dimmed">{fmtDateHeure(d.date)}</Text>
                  </Table.Td>
                  <Table.Td>
                    {approbateur ? (
                      boutons(
                        () => traiterDemande.mutate({ id: d.id, approuver: true }, resultat("Changement approuvé et appliqué")),
                        () => setRejet({ demande: d }),
                      )
                    ) : (
                      <Stack gap={2}>
                        <EtatBadge etat={d.etat} motif={d.motif_rejet} />
                        {d.motif_rejet && <Text size="xs" c="red">{d.motif_rejet}</Text>}
                      </Stack>
                    )}
                  </Table.Td>
                </Table.Tr>
              ))}
            </Table.Tbody>
          </Table>
        )}
      </Card>

      <Modal opened={rejet !== null} onClose={() => setRejet(null)} title="Rejeter">
        <Stack gap="sm">
          <Text size="sm">
            {rejet?.saisie ? `${TYPES_SAISIE[rejet.saisie.type]} — ${rejet.saisie.element}` : `${rejet?.demande?.action_libelle} — ${rejet?.demande?.libelle}`}
          </Text>
          <Textarea
            label="Motif du rejet"
            description="Montré à l'auteur, pour qu'il corrige."
            autosize
            minRows={2}
            value={motif}
            onChange={(e) => setMotif(e.currentTarget.value)}
            data-autofocus
          />
          <Group justify="flex-end">
            <Button color="red" onClick={confirmerRejet} loading={traiterSaisie.isPending || traiterDemande.isPending}>
              Rejeter
            </Button>
          </Group>
        </Stack>
      </Modal>
    </Stack>
  );
}
