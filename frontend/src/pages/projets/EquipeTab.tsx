import { useEffect, useMemo, useState } from "react";
import { Pencil, Trash2, UserRound, UserX, Users } from "lucide-react";
import { Badge, ActionIcon, Button, Card, Divider, Group, Select, Stack, Table, Text, TextInput, Tooltip } from "@mantine/core";
import { DateInput } from "@mantine/dates";
import { notifications } from "@mantine/notifications";
import { useCreateIntervenant, useDeleteIntervenant, useIntervenants, useUpdateIntervenant } from "../../api/intervenants";
import { useDeleteEquipe, useEquipes, useProjet, useUpdateEquipe } from "../../api/projects";
import { BoutonModeEdition } from "../../components/common/BoutonModeEdition";
import { EmptyState } from "../../components/common/EmptyState";
import { confirmerSuppression } from "../../components/common/confirmerSuppression";
import { IntervenantsMultiples } from "../../components/common/IntervenantsMultiples";
import { messageErreurApi } from "../../utils/erreurs";
import type { Activite, Equipe, Intervenant } from "../../types";
import { voc } from "../../utils/vocabulaire";

function LigneEquipe({
  equipe,
  projetId,
  intervenants,
  editionActive,
}: {
  equipe: Equipe;
  projetId: number;
  intervenants: Intervenant[];
  editionActive: boolean;
}) {
  const updateEquipe = useUpdateEquipe();
  const deleteEquipe = useDeleteEquipe();
  const createIntervenant = useCreateIntervenant();
  const [enEdition, setEnEdition] = useState(false);
  const [nom, setNom] = useState(equipe.nom);
  const [membres, setMembres] = useState<number[]>(equipe.membres);
  const [dateDebutContrat, setDateDebutContrat] = useState<string | null>(equipe.date_debut_contrat);
  const [dateFinContrat, setDateFinContrat] = useState<string | null>(equipe.date_fin_contrat);

  async function creerIntervenant(nomP: string, prenom: string): Promise<Intervenant | null> {
    try {
      return await createIntervenant.mutateAsync({ nom: nomP, prenom, projets_associes: [projetId], activites_associees: [] });
    } catch {
      notifications.show({ message: "Erreur lors de la création de la personne", color: "red" });
      return null;
    }
  }

  async function enregistrer() {
    if (!nom.trim()) {
      notifications.show({ message: "Le nom de l'équipe est requis.", color: "orange" });
      return;
    }
    try {
      await updateEquipe.mutateAsync({
        id: equipe.id,
        payload: { nom: nom.trim(), membres, date_debut_contrat: dateDebutContrat, date_fin_contrat: dateFinContrat },
      });
      notifications.show({ message: "Équipe modifiée", color: "green" });
      setEnEdition(false);
    } catch (error) {
      notifications.show({ message: messageErreurApi(error, "Erreur lors de la modification de l'équipe"), color: "red" });
    }
  }

  function supprimer() {
    confirmerSuppression({
      message: `Supprimer définitivement l'équipe "${equipe.nom}" ? Les activités qui l'utilisent perdront ce rattachement. Cette action est irréversible.`,
      onConfirm: async () => {
        try {
          await deleteEquipe.mutateAsync(equipe.id);
          notifications.show({ message: "Équipe supprimée", color: "green" });
        } catch {
          notifications.show({ message: "Erreur lors de la suppression de l'équipe", color: "red" });
        }
      },
    });
  }

  if (enEdition) {
    return (
      <Stack gap={4}>
        <TextInput size="xs" label="Nom de l'équipe" value={nom} onChange={(e) => setNom(e.currentTarget.value)} />
        <IntervenantsMultiples
          label="Membres"
          value={membres}
          onChange={setMembres}
          intervenants={intervenants}
          onCreerNouveau={creerIntervenant}
          creating={createIntervenant.isPending}
        />
        <Group grow>
          <DateInput size="xs" label="Date de début de contrat" value={dateDebutContrat} onChange={setDateDebutContrat} />
          <DateInput size="xs" label="Date de fin de contrat" value={dateFinContrat} onChange={setDateFinContrat} />
        </Group>
        <Group gap={6}>
          <Button size="xs" onClick={enregistrer} loading={updateEquipe.isPending}>Enregistrer</Button>
          <Button
            size="xs"
            variant="subtle"
            color="gray"
            onClick={() => {
              setNom(equipe.nom);
              setMembres(equipe.membres);
              setDateDebutContrat(equipe.date_debut_contrat);
              setDateFinContrat(equipe.date_fin_contrat);
              setEnEdition(false);
            }}
          >
            Annuler
          </Button>
        </Group>
      </Stack>
    );
  }

  return (
    <div>
      <Group gap={6} justify="space-between" wrap="nowrap">
        <Text size="sm" fw={500}>{equipe.nom}</Text>
        {editionActive && (
        <Group gap={4} wrap="nowrap">
          <Tooltip label="Modifier l'équipe">
            <ActionIcon size="sm" variant="subtle" onClick={() => setEnEdition(true)}>
              <Pencil size={13} />
            </ActionIcon>
          </Tooltip>
          <Tooltip label="Supprimer l'équipe">
            <ActionIcon size="sm" variant="subtle" color="red" loading={deleteEquipe.isPending} onClick={supprimer}>
              <Trash2 size={13} />
            </ActionIcon>
          </Tooltip>
        </Group>
        )}
      </Group>
      {(equipe.date_debut_contrat || equipe.date_fin_contrat) && (
        <Text size="xs" c="dimmed">
          Contrat : {equipe.date_debut_contrat ?? "?"} → {equipe.date_fin_contrat ?? "?"}
        </Text>
      )}
      {equipe.membres_noms.length > 0 ? (
        <Group gap={4} mt={4}>
          {equipe.membres_noms.map((membre) => (
            <Badge key={membre} variant="light" size="sm">{membre}</Badge>
          ))}
        </Group>
      ) : (
        <Text size="xs" c="dimmed">Aucun membre renseigné pour cette équipe.</Text>
      )}
    </div>
  );
}

function LigneMembre({
  membre,
  projetId,
  editionActive,
}: {
  membre: Intervenant;
  projetId: number;
  editionActive: boolean;
}) {
  const updateIntervenant = useUpdateIntervenant();
  const deleteIntervenant = useDeleteIntervenant();
  const [enEdition, setEnEdition] = useState(false);
  const [nom, setNom] = useState(membre.nom);
  const [prenom, setPrenom] = useState(membre.prenom);
  const [fonction, setFonction] = useState(membre.fonction);
  const [contact, setContact] = useState(membre.contact);

  async function enregistrer() {
    if (!nom.trim() || !prenom.trim()) {
      notifications.show({ message: "Nom et prénom requis.", color: "orange" });
      return;
    }
    try {
      await updateIntervenant.mutateAsync({
        id: membre.id,
        payload: { nom: nom.trim(), prenom: prenom.trim(), fonction, contact },
      });
      notifications.show({ message: "Membre modifié", color: "green" });
      setEnEdition(false);
    } catch {
      notifications.show({ message: "Erreur lors de la modification", color: "red" });
    }
  }

  async function retirerDuProjet() {
    try {
      await updateIntervenant.mutateAsync({
        id: membre.id,
        payload: { projets_associes: membre.projets_associes.filter((id) => id !== projetId) },
      });
      notifications.show({ message: voc("Retiré de l'équipe du projet"), color: "green" });
    } catch {
      notifications.show({ message: "Erreur lors du retrait", color: "red" });
    }
  }

  function supprimerDefinitivement() {
    confirmerSuppression({
      message: voc`Supprimer définitivement "${membre.nom} ${membre.prenom}" de l'équipe (tous projets confondus) ? Cette action est irréversible.`,
      onConfirm: async () => {
        try {
          await deleteIntervenant.mutateAsync(membre.id);
          notifications.show({ message: "Membre supprimé", color: "green" });
        } catch {
          notifications.show({ message: "Erreur lors de la suppression", color: "red" });
        }
      },
    });
  }

  if (enEdition) {
    return (
      <Table.Tr>
        <Table.Td colSpan={5}>
          <Group align="flex-end" wrap="wrap">
            <TextInput size="xs" label="Nom" value={nom} onChange={(e) => setNom(e.currentTarget.value)} />
            <TextInput size="xs" label="Prénom" value={prenom} onChange={(e) => setPrenom(e.currentTarget.value)} />
            <TextInput size="xs" label="Fonction" value={fonction} onChange={(e) => setFonction(e.currentTarget.value)} />
            <TextInput size="xs" label="Contact" value={contact} onChange={(e) => setContact(e.currentTarget.value)} />
            <Button size="xs" onClick={enregistrer} loading={updateIntervenant.isPending}>Enregistrer</Button>
            <Button size="xs" variant="subtle" color="gray" onClick={() => setEnEdition(false)}>Annuler</Button>
          </Group>
        </Table.Td>
      </Table.Tr>
    );
  }

  return (
    <Table.Tr>
      <Table.Td>{membre.nom} {membre.prenom}</Table.Td>
      <Table.Td>{membre.fonction || "—"}</Table.Td>
      <Table.Td>{membre.contact || "—"}</Table.Td>
      <Table.Td>{membre.utilisateur_nom || "—"}</Table.Td>
      <Table.Td>
        <Group gap={4} wrap="nowrap">
          {editionActive && (
            <Tooltip label="Modifier">
              <ActionIcon variant="subtle" onClick={() => setEnEdition(true)}>
                <Pencil size={15} />
              </ActionIcon>
            </Tooltip>
          )}
          <Tooltip label={voc("Retirer de ce projet (reste dans les autres)")}>
            <ActionIcon variant="subtle" color="orange" loading={updateIntervenant.isPending} onClick={retirerDuProjet}>
              <UserX size={15} />
            </ActionIcon>
          </Tooltip>
          {editionActive && (
            <Tooltip label="Supprimer définitivement">
              <ActionIcon variant="subtle" color="red" loading={deleteIntervenant.isPending} onClick={supprimerDefinitivement}>
                <Trash2 size={15} />
              </ActionIcon>
            </Tooltip>
          )}
        </Group>
      </Table.Td>
    </Table.Tr>
  );
}

export function EquipeTab({ projetId }: { projetId: number }) {
  const { data: equipe, isLoading } = useIntervenants(projetId);
  const { data: tousIntervenants } = useIntervenants();
  const { data: projet } = useProjet(projetId);
  const { data: toutesEquipes } = useEquipes();
  const createIntervenant = useCreateIntervenant();
  const updateIntervenant = useUpdateIntervenant();
  const updateEquipe = useUpdateEquipe();

  const [selection, setSelection] = useState<string | null>(null);
  const [nom, setNom] = useState("");
  const [prenom, setPrenom] = useState("");
  const [fonction, setFonction] = useState("");
  const [contact, setContact] = useState("");
  const [equipeCible, setEquipeCible] = useState<string | null>(null);
  const [editionActive, setEditionActive] = useState(false);

  const equipesDuProjet = useMemo(() => {
    const idsUtilises = new Set<number>();
    // Tous les éléments de la planification, à n'importe quel niveau.
    const parcourir = (elements: Activite[]) => {
      for (const act of elements) {
        if (act.equipe_responsable) idsUtilises.add(act.equipe_responsable);
        parcourir(act.enfants);
      }
    };
    parcourir(projet?.activites ?? []);
    return (toutesEquipes ?? []).filter((e) => idsUtilises.has(e.id));
  }, [projet, toutesEquipes]);

  const equipeCibleObj = useMemo(
    () => toutesEquipes?.find((e) => String(e.id) === equipeCible) ?? null,
    [toutesEquipes, equipeCible],
  );

  // Si une équipe cible est choisie, on propose toute personne pas encore
  // MEMBRE DE CETTE ÉQUIPE (même si déjà dans la liste générale du projet) —
  // sinon on retombe sur la liste générale du projet, comme avant.
  const nonMembres = useMemo(
    () =>
      (tousIntervenants ?? [])
        .filter((i) => (equipeCibleObj ? !equipeCibleObj.membres.includes(i.id) : !equipe?.some((m) => m.id === i.id)))
        .map((i) => ({ value: String(i.id), label: `${i.nom} ${i.prenom}${i.fonction ? " — " + i.fonction : ""}` })),
    [tousIntervenants, equipe, equipeCibleObj],
  );

  // Présélectionne une équipe par défaut (la seule s'il n'y en a qu'une, sinon
  // la première) dès qu'elles sont chargées — pour que « créer et ajouter » y
  // rattache la personne immédiatement, sans étape manuelle supplémentaire.
  useEffect(() => {
    if (equipeCible === null && equipesDuProjet.length > 0) {
      setEquipeCible(String(equipesDuProjet[0].id));
    }
  }, [equipesDuProjet, equipeCible]);

  async function rattacherAEquipeCible(intervenantId: number) {
    if (!equipeCibleObj) return;
    if (equipeCibleObj.membres.includes(intervenantId)) return;
    try {
      await updateEquipe.mutateAsync({ id: equipeCibleObj.id, payload: { membres: [...equipeCibleObj.membres, intervenantId] } });
    } catch {
      notifications.show({ message: voc("Ajouté au projet, mais erreur lors du rattachement à l'équipe."), color: "orange" });
    }
  }

  async function ajouterExistant() {
    if (!selection) return;
    const intervenant = tousIntervenants?.find((i) => String(i.id) === selection);
    if (!intervenant) return;
    if (equipeCibleObj?.membres.includes(intervenant.id)) {
      notifications.show({ message: "Cette personne est déjà dans l'équipe.", color: "orange" });
      return;
    }
    try {
      await updateIntervenant.mutateAsync({
        id: intervenant.id,
        payload: { projets_associes: [...intervenant.projets_associes, projetId] },
      });
      await rattacherAEquipeCible(intervenant.id);
      notifications.show({ message: voc("Ajouté à l'équipe du projet"), color: "green" });
      setSelection(null);
    } catch {
      notifications.show({ message: "Erreur lors de l'ajout", color: "red" });
    }
  }

  async function creerEtAjouter() {
    if (!nom.trim() || !prenom.trim()) {
      notifications.show({ message: "Nom et prénom requis.", color: "orange" });
      return;
    }
    try {
      const cree = await createIntervenant.mutateAsync({
        nom: nom.trim(),
        prenom: prenom.trim(),
        fonction,
        contact,
        projets_associes: [projetId],
        activites_associees: [],
      });
      await rattacherAEquipeCible(cree.id);
      notifications.show({ message: "Membre ajouté à l'équipe", color: "green" });
      setNom("");
      setPrenom("");
      setFonction("");
      setContact("");
    } catch {
      notifications.show({ message: "Erreur lors de la création", color: "red" });
    }
  }

  return (
    <Stack gap="md">
      <Group justify="flex-end">
        <BoutonModeEdition actif={editionActive} onToggle={() => setEditionActive((v) => !v)} />
      </Group>
      {equipesDuProjet.length > 0 && (
        <Card withBorder padding="md" radius="md">
          <Group gap={6} mb="xs">
            <Users size={16} />
            <Text size="sm" fw={600}>{voc("Équipes rattachées aux activités de ce projet")}</Text>
          </Group>
          <Stack gap="sm">
            {equipesDuProjet.map((e) => (
              <LigneEquipe key={e.id} equipe={e} projetId={projetId} intervenants={tousIntervenants ?? []} editionActive={editionActive} />
            ))}
          </Stack>
        </Card>
      )}

      <Card withBorder padding="md" radius="md">
        <Text size="sm" fw={600} mb="xs">Ajouter un membre existant</Text>
        {equipesDuProjet.length > 0 && (
          <Select
            label="Rattacher aussi à une équipe"
            description="Présélectionnée automatiquement — change-la ou vide-la si tu ne veux pas rattacher la personne à une équipe précise."
            placeholder="Aucune équipe précise…"
            data={equipesDuProjet.map((e) => ({ value: String(e.id), label: e.nom }))}
            value={equipeCible}
            onChange={setEquipeCible}
            clearable
            searchable
            mb="sm"
          />
        )}
        <Group align="flex-end">
          <Select
            placeholder="Choisir une personne déjà enregistrée…"
            data={nonMembres}
            value={selection}
            onChange={setSelection}
            searchable
            style={{ flex: 1 }}
          />
          <Button onClick={ajouterExistant} loading={updateIntervenant.isPending}>Ajouter à l'équipe</Button>
        </Group>

        <Divider my="sm" label="ou créer une nouvelle personne" labelPosition="left" />
        <Group align="flex-end" wrap="wrap">
          <TextInput label="Nom" value={nom} onChange={(e) => setNom(e.currentTarget.value)} />
          <TextInput label="Prénom" value={prenom} onChange={(e) => setPrenom(e.currentTarget.value)} />
          <TextInput label="Fonction" value={fonction} onChange={(e) => setFonction(e.currentTarget.value)} />
          <TextInput label="Contact" value={contact} onChange={(e) => setContact(e.currentTarget.value)} />
          <Button variant="light" onClick={creerEtAjouter} loading={createIntervenant.isPending}>
            Créer et ajouter
          </Button>
        </Group>
      </Card>

      <Card withBorder padding="md" radius="md">
        {isLoading ? (
          <Text c="dimmed">Chargement…</Text>
        ) : !equipe || equipe.length === 0 ? (
          <EmptyState icon={<UserRound size={32} strokeWidth={1.5} />} message={voc("Aucun membre affecté à ce projet pour le moment.")} />
        ) : (
          <Table striped highlightOnHover>
            <Table.Thead>
              <Table.Tr>
                <Table.Th tt="uppercase" fz="xs" c="dimmed">Nom</Table.Th>
                <Table.Th tt="uppercase" fz="xs" c="dimmed">Fonction</Table.Th>
                <Table.Th tt="uppercase" fz="xs" c="dimmed">Contact</Table.Th>
                <Table.Th tt="uppercase" fz="xs" c="dimmed">Compte lié</Table.Th>
                <Table.Th />
              </Table.Tr>
            </Table.Thead>
            <Table.Tbody>
              {equipe.map((m) => (
                <LigneMembre key={m.id} membre={m} projetId={projetId} editionActive={editionActive} />
              ))}
            </Table.Tbody>
          </Table>
        )}
      </Card>
    </Stack>
  );
}
