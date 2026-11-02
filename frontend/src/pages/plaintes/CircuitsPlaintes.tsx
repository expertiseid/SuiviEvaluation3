import { useState } from "react";
import { ArrowDown, ArrowUp, CircleAlert, CircleCheck, Lock, Plus, Trash2 } from "lucide-react";
import {
  ActionIcon,
  Alert,
  Badge,
  Button,
  Card,
  Checkbox,
  Group,
  List,
  NumberInput,
  Select,
  Stack,
  Switch,
  Table,
  Text,
  TextInput,
  Tooltip,
} from "@mantine/core";
import { notifications } from "@mantine/notifications";
import { useRoles, useUtilisateurs } from "../../api/accounts";
import {
  useHabilitesActifs,
  type CircuitPlainte,
  type EtapeCircuit,
  useCircuitsPlainte,
  useEnregistrerCircuit,
  useEnregistrerEtape,
  useMecanisme,
  useSupprimerCircuit,
  useSupprimerEtape,
} from "../../api/plaintes";
import { confirmerSuppression } from "../../components/common/confirmerSuppression";
import { messageErreurApi } from "../../utils/erreurs";
import { voc } from "../../utils/vocabulaire";

/** Une étape : nom, délai, responsable (rôle ou personne ; personne seulement en circuit confidentiel), clôture. */
function LigneEtape({
  etape,
  circuit,
  rang,
  total,
  modifiable,
  onDeplacer,
}: {
  etape: EtapeCircuit;
  circuit: CircuitPlainte;
  rang: number;
  total: number;
  modifiable: boolean;
  onDeplacer: (sens: -1 | 1) => void;
}) {
  const enregistrer = useEnregistrerEtape();
  const supprimer = useSupprimerEtape();
  const { data: roles = [] } = useRoles();
  const { data: utilisateurs = [] } = useUtilisateurs();
  const { data: habilites = [] } = useHabilitesActifs();
  const [nom, setNom] = useState(etape.nom);

  async function sauver(champs: Partial<EtapeCircuit>) {
    try {
      await enregistrer.mutateAsync({ id: etape.id, ...champs });
    } catch (error) {
      notifications.show({ message: messageErreurApi(error, voc("Erreur lors de l'enregistrement")), color: "red" });
    }
  }

  // Responsable : « r<id> » pour un rôle, « u<id> » pour une personne.
  const choix = [
    ...(circuit.sensible ? [] : [{ group: voc("Rôles"), items: roles.map((r) => ({ value: `r${r.id}`, label: r.libelle })) }]),
    {
      group: voc("Personnes"),
      // Circuit confidentiel : seulement les personnes habilitées (et l'Administrateur), voir l'onglet Habilitations.
      items: utilisateurs
        .filter((u) => !circuit.sensible || u.role === "ADMIN" || habilites.includes(u.id) || u.id === etape.responsable)
        .map((u) => ({ value: `u${u.id}`, label: `${u.first_name} ${u.last_name}`.trim() || u.username })),
    },
  ];
  const valeur = etape.responsable ? `u${etape.responsable}` : etape.role ? `r${etape.role}` : null;
  const sansResponsable = !etape.responsable && !(etape.role && !circuit.sensible);

  return (
    <Table.Tr>
      <Table.Td w={40}><Badge variant="light" circle>{rang + 1}</Badge></Table.Td>
      <Table.Td>
        {modifiable ? (
          <TextInput size="xs" value={nom} onChange={(e) => setNom(e.currentTarget.value)} onBlur={() => nom.trim() && nom !== etape.nom && sauver({ nom: nom.trim() })} />
        ) : etape.nom}
      </Table.Td>
      <Table.Td w={110}>
        {modifiable ? (
          <NumberInput size="xs" min={0} value={etape.delai_jours ?? ""} placeholder="—" onChange={(v) => sauver({ delai_jours: v === "" ? null : Number(v) })} />
        ) : etape.delai_jours ?? "—"}
      </Table.Td>
      <Table.Td w={260}>
        {modifiable ? (
          <Select
            size="xs"
            data={choix}
            value={valeur}
            placeholder={circuit.sensible ? voc("Choisir une personne…") : voc("Choisir un rôle ou une personne…")}
            error={sansResponsable ? true : undefined}
            onChange={(v) =>
              sauver(v?.startsWith("u") ? { responsable: Number(v.slice(1)), role: null } : { role: v ? Number(v.slice(1)) : null, responsable: null })
            }
            searchable
            clearable
          />
        ) : etape.responsable_nom ?? etape.role_libelle ?? "—"}
      </Table.Td>
      <Table.Td w={90} ta="center">
        <Checkbox
          checked={etape.est_cloture}
          disabled={!modifiable}
          aria-label={voc("Étape de clôture")}
          onChange={(e) => sauver({ est_cloture: e.currentTarget.checked })}
        />
      </Table.Td>
      {modifiable && (
        <Table.Td w={100}>
          <Group gap={2} wrap="nowrap">
            <ActionIcon size="sm" variant="subtle" disabled={rang === 0} onClick={() => onDeplacer(-1)} aria-label={voc("Monter")}><ArrowUp size={13} /></ActionIcon>
            <ActionIcon size="sm" variant="subtle" disabled={rang === total - 1} onClick={() => onDeplacer(1)} aria-label={voc("Descendre")}><ArrowDown size={13} /></ActionIcon>
            <ActionIcon
              size="sm"
              variant="subtle"
              color="red"
              aria-label={voc("Supprimer")}
              onClick={() => confirmerSuppression({ message: voc`Supprimer l'étape « ${etape.nom} » ?`, onConfirm: () => supprimer.mutateAsync(etape.id) })}
            >
              <Trash2 size={13} />
            </ActionIcon>
          </Group>
        </Table.Td>
      )}
    </Table.Tr>
  );
}

/** Un circuit : réglages, étapes dans l'ordre, et ce qui l'empêche d'être utilisé. */
function CarteCircuit({ circuit, modifiable }: { circuit: CircuitPlainte; modifiable: boolean }) {
  const enregistrer = useEnregistrerCircuit();
  const supprimer = useSupprimerCircuit();
  const enregistrerEtape = useEnregistrerEtape();
  const { data: mecanisme } = useMecanisme();
  const [nouvelleEtape, setNouvelleEtape] = useState("");
  const etapes = [...circuit.etapes].sort((a, b) => a.ordre - b.ordre || a.id - b.id);

  async function sauver(champs: Partial<CircuitPlainte>) {
    try {
      await enregistrer.mutateAsync({ id: circuit.id, ...champs });
    } catch (error) {
      notifications.show({ message: messageErreurApi(error, voc("Erreur lors de l'enregistrement")), color: "red" });
    }
  }

  async function deplacer(i: number, sens: -1 | 1) {
    const [a, b] = [etapes[i], etapes[i + sens]];
    // Ordres explicites (1, 2, 3…) puis échange des deux étapes.
    await Promise.all(etapes.map((e, j) => (e.ordre === j + 1 ? null : enregistrerEtape.mutateAsync({ id: e.id, ordre: j + 1 }))));
    await enregistrerEtape.mutateAsync({ id: a.id, ordre: i + sens + 1 });
    await enregistrerEtape.mutateAsync({ id: b.id, ordre: i + 1 });
  }

  async function ajouterEtape() {
    if (!nouvelleEtape.trim()) return;
    try {
      await enregistrerEtape.mutateAsync({ circuit: circuit.id, nom: nouvelleEtape.trim(), ordre: etapes.length + 1 });
      setNouvelleEtape("");
    } catch (error) {
      notifications.show({ message: messageErreurApi(error, voc("Erreur lors de l'enregistrement")), color: "red" });
    }
  }

  return (
    <Card withBorder radius="md" padding="md">
      <Group justify="space-between" mb="xs" wrap="nowrap" align="flex-start">
        <Stack gap={4}>
          <Group gap="xs">
            <Text fw={700}>{circuit.nom}</Text>
            {circuit.sensible && (
              <Badge color="grape" variant="light" leftSection={<Lock size={11} />}>{voc("Confidentiel")}</Badge>
            )}
            {circuit.par_defaut && <Badge variant="outline">{voc("Par défaut")}</Badge>}
            {mecanisme?.circuit_alternatif === circuit.id && <Badge color="grape" variant="outline">{voc("Circuit alternatif")}</Badge>}
            {!circuit.actif && <Badge color="gray">{voc("Désactivé")}</Badge>}
            {circuit.erreurs.length === 0 ? (
              <Badge color="teal" variant="light" leftSection={<CircleCheck size={11} />}>{voc("Valide")}</Badge>
            ) : (
              <Badge color="orange" variant="light" leftSection={<CircleAlert size={11} />}>{voc("À compléter")}</Badge>
            )}
          </Group>
          {circuit.description && <Text size="sm" c="dimmed">{circuit.description}</Text>}
          {circuit.nb_categories > 0 && <Text size="xs" c="dimmed">{voc`Utilisé par ${circuit.nb_categories} catégorie(s)`}</Text>}
        </Stack>
        {modifiable && (
          <Group gap="md" wrap="nowrap">
            <Switch size="xs" label={voc("Par défaut")} checked={circuit.par_defaut} onChange={(e) => sauver({ par_defaut: e.currentTarget.checked })} />
            <Switch size="xs" label={voc("Actif")} checked={circuit.actif} onChange={(e) => sauver({ actif: e.currentTarget.checked })} />
            <Tooltip label={voc("Supprimer le circuit")}>
              <ActionIcon
                variant="subtle"
                color="red"
                aria-label={voc("Supprimer le circuit")}
                onClick={() =>
                  confirmerSuppression({
                    message: voc`Supprimer le circuit « ${circuit.nom} » et ses étapes ? Les catégories qui l'utilisent passeront par le circuit par défaut.`,
                    onConfirm: () => supprimer.mutateAsync(circuit.id),
                  })
                }
              >
                <Trash2 size={15} />
              </ActionIcon>
            </Tooltip>
          </Group>
        )}
      </Group>
      {circuit.sensible && (
        <Text size="xs" c="dimmed" mb="xs">
          <Lock size={11} style={{ verticalAlign: -1 }} /> {voc("Ce réglage protège les personnes et ne peut pas être modifié : chaque étape d'un circuit confidentiel est confiée à une personne nommément désignée, jamais à un rôle entier.")}
        </Text>
      )}
      <Table withTableBorder verticalSpacing={4} fz="sm">
        <Table.Thead>
          <Table.Tr>
            <Table.Th />
            <Table.Th>{voc("Étape")}</Table.Th>
            <Table.Th>{voc("Délai (jours)")}</Table.Th>
            <Table.Th>{voc("Responsable")}</Table.Th>
            <Table.Th ta="center">{voc("Clôture")}</Table.Th>
            {modifiable && <Table.Th />}
          </Table.Tr>
        </Table.Thead>
        <Table.Tbody>
          {etapes.map((e, i) => (
            <LigneEtape
              key={`${e.id}-${e.nom}`}
              etape={e}
              circuit={circuit}
              rang={i}
              total={etapes.length}
              modifiable={modifiable}
              onDeplacer={(sens) => deplacer(i, sens)}
            />
          ))}
        </Table.Tbody>
      </Table>
      {modifiable && (
        <Group gap="xs" mt="xs">
          <TextInput
            size="xs"
            placeholder={voc("Nouvelle étape, ex : Vérification")}
            value={nouvelleEtape}
            onChange={(e) => setNouvelleEtape(e.currentTarget.value)}
            onKeyDown={(e) => e.key === "Enter" && ajouterEtape()}
          />
          <Button size="xs" variant="light" leftSection={<Plus size={13} />} onClick={ajouterEtape}>{voc("Ajouter une étape")}</Button>
        </Group>
      )}
      {circuit.erreurs.length > 0 && (
        <Alert color="orange" variant="light" mt="sm" p="xs" icon={<CircleAlert size={16} />}>
          <List size="sm">{circuit.erreurs.map((m) => <List.Item key={m}>{voc(m)}</List.Item>)}</List>
        </Alert>
      )}
    </Card>
  );
}

/** Circuits de traitement : plusieurs circuits, un par défaut pour chaque nature (ordinaire, confidentiel). */
export function CircuitsPlaintes({ modifiable }: { modifiable: boolean }) {
  const { data: circuits = [] } = useCircuitsPlainte();
  const enregistrer = useEnregistrerCircuit();
  const [nom, setNom] = useState("");
  const [sensible, setSensible] = useState(false);

  async function ajouter() {
    if (!nom.trim()) return;
    try {
      await enregistrer.mutateAsync({ nom: nom.trim(), sensible });
      setNom("");
    } catch (error) {
      notifications.show({ message: messageErreurApi(error, voc("Erreur lors de l'enregistrement")), color: "red" });
    }
  }

  return (
    <Stack gap="md">
      <Text size="sm" c="dimmed">
        {voc("Un circuit est la suite des étapes que suit un dossier, de la réception à la clôture. Chaque catégorie utilise le circuit par défaut de sa nature, ou un circuit qui lui est propre.")}
      </Text>
      {circuits.map((c) => <CarteCircuit key={c.id} circuit={c} modifiable={modifiable} />)}
      {modifiable && (
        <Group gap="xs" align="flex-end">
          <TextInput label={voc("Nouveau circuit")} placeholder={voc("Ex : Circuit des plaintes urgentes")} value={nom} onChange={(e) => setNom(e.currentTarget.value)} />
          <Checkbox label={voc("Confidentiel")} checked={sensible} onChange={(e) => setSensible(e.currentTarget.checked)} mb={8} />
          <Button leftSection={<Plus size={14} />} variant="light" onClick={ajouter} loading={enregistrer.isPending}>{voc("Ajouter un circuit")}</Button>
        </Group>
      )}
    </Stack>
  );
}
