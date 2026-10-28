import { useState } from "react";
import { Link } from "react-router-dom";
import { Building2, FolderKanban, Link2, Network, Pencil, Plus, Search, Trash2, Users } from "lucide-react";
import {
  ActionIcon,
  Autocomplete,
  Avatar,
  Badge,
  Button,
  Card,
  Divider,
  Group,
  Modal,
  MultiSelect,
  Pill,
  Popover,
  SegmentedControl,
  Select,
  SimpleGrid,
  Stack,
  Table,
  Tabs,
  Text,
  Textarea,
  TextInput,
  Tooltip,
  UnstyledButton,
} from "@mantine/core";
import { notifications } from "@mantine/notifications";
import {
  useAffectationsStructure,
  useEnregistrerAffectationsStructure,
  useCategoriesPartiesPrenantes,
  useEnregistrerCategoriePartiePrenante,
  useEnregistrerPartenaire,
  useEnregistrerPartiePrenante,
  useEnregistrerStructure,
  usePartiesPrenantes,
  useStructures,
  useSupprimerCategoriePartiePrenante,
  useSupprimerPartenaire,
  useSupprimerPartiePrenante,
  useSupprimerStructure,
  useTousPartenaires,
} from "../../api/organisation";
import { confirmerSuppression } from "../../components/common/confirmerSuppression";
import { TitreRubrique } from "../../components/common/TitreRubrique";
import { messageErreurApi } from "../../utils/erreurs";
import { voc } from "../../utils/vocabulaire";
import { libelleStructure, structuresEnArbre } from "../../utils/organisation";
import type { Partenaire, PartiePrenante, StructureOrganisation } from "../../types";

const TYPES_STRUCTURE_SUGGERES = ["Organisation", "Direction", "Service", "Secteur", "Division", "Cellule", "Antenne régionale"];
const TYPES_PARTENAIRE = [
  { value: "MISE_EN_OEUVRE", label: "Partenaire de mise en œuvre" },
  { value: "CONSORTIUM", label: "Partenaire de consortium" },
  { value: "BAILLEUR", label: "Bailleur" },
];
const LIBELLES_TYPE_PARTENAIRE: Record<string, { label: string; couleur: string }> = {
  MISE_EN_OEUVRE: { label: "Mise en œuvre", couleur: "blue" },
  CONSORTIUM: { label: "Consortium", couleur: "teal" },
  BAILLEUR: { label: "Bailleur", couleur: "grape" },
};

// Option « + Ajouter » d'un nouveau type de structure.
const PREFIXE_AJOUT = "\u2795 ";

function erreur(error: unknown, defaut: string) {
  notifications.show({ message: messageErreurApi(error, defaut), color: "red" });
}

// ---------------------------------------------------------------------------------- Structure

function StructureModal({
  structure,
  onClose,
}: {
  structure: Partial<StructureOrganisation> | null;
  onClose: () => void;
}) {
  const { data: structures = [] } = useStructures();
  const enregistrer = useEnregistrerStructure();
  const [valeurs, setValeurs] = useState<Partial<StructureOrganisation>>({});
  const [cle, setCle] = useState<unknown>(null);
  if (structure !== cle) {
    setCle(structure);
    setValeurs(structure ?? {});
  }
  const types = Array.from(new Set([...TYPES_STRUCTURE_SUGGERES, ...structures.map((s) => s.type).filter(Boolean)]));
  const parents = structuresEnArbre(structures)
    .filter(({ structure: s }) => s.id !== structure?.id)
    .map(({ structure: s, profondeur }) => ({ value: String(s.id), label: `${"— ".repeat(profondeur)}${libelleStructure(s)}` }));

  async function valider() {
    if (!valeurs.nom?.trim()) {
      notifications.show({ message: "Indique le nom.", color: "orange" });
      return;
    }
    try {
      await enregistrer.mutateAsync(valeurs);
      notifications.show({ message: "Structure enregistrée", color: "green" });
      onClose();
    } catch (e) {
      erreur(e, "Erreur lors de l'enregistrement");
    }
  }

  return (
    <Modal
      opened={structure !== null}
      onClose={onClose}
      title={
        structure?.id
          ? `Modifier — ${structure.nom}`
          : structure?.parent
            ? `Nouveau service de « ${structures.find((x) => x.id === structure.parent)?.nom ?? ""} »`
            : "Nouvelle organisation"
      }
    >
      <Stack gap="sm">
        <TextInput label="Nom" required value={valeurs.nom ?? ""} onChange={(e) => setValeurs({ ...valeurs, nom: e.currentTarget.value })} data-autofocus />
        <Group grow>
          <TextInput label="Sigle" value={valeurs.sigle ?? ""} onChange={(e) => setValeurs({ ...valeurs, sigle: e.currentTarget.value })} />
          <Autocomplete
            label="Type"
            description="Choisir, ou taper un nouveau type"
            placeholder="Direction, Service…"
            data={
              valeurs.type?.trim() && !types.some((t) => t.toLowerCase() === valeurs.type!.trim().toLowerCase())
                ? [...types, `${PREFIXE_AJOUT}${valeurs.type.trim()}`]
                : types
            }
            value={valeurs.type ?? ""}
            onChange={(type) => setValeurs({ ...valeurs, type: type.startsWith(PREFIXE_AJOUT) ? type.slice(PREFIXE_AJOUT.length) : type })}
            renderOption={({ option }) =>
              option.value.startsWith(PREFIXE_AJOUT) ? (
                <Text size="sm" c="teal" fw={500}>+ Ajouter « {option.value.slice(PREFIXE_AJOUT.length)} »</Text>
              ) : (
                <Text size="sm">{option.value}</Text>
              )
            }
          />
        </Group>
        <Select
          label="Rattachée à"
          placeholder="Aucune (premier niveau)"
          data={parents}
          value={valeurs.parent ? String(valeurs.parent) : null}
          onChange={(v) => setValeurs({ ...valeurs, parent: v ? Number(v) : null })}
          clearable
          searchable
        />
        <TextInput
          label="Responsable"
          value={valeurs.responsable ?? ""}
          onChange={(e) => setValeurs({ ...valeurs, responsable: e.currentTarget.value })}
        />
        <Group justify="flex-end">
          <Button onClick={valider} loading={enregistrer.isPending}>Enregistrer</Button>
        </Group>
      </Stack>
    </Modal>
  );
}

function AffectationsModal({ structure, onClose }: { structure: StructureOrganisation | null; onClose: () => void }) {
  const { data } = useAffectationsStructure(structure?.id ?? null);
  const enregistrer = useEnregistrerAffectationsStructure();
  const [projets, setProjets] = useState<string[]>([]);
  const [utilisateurs, setUtilisateurs] = useState<string[]>([]);
  const [charge, setCharge] = useState<unknown>(null);
  if (data && data !== charge) {
    setCharge(data);
    setProjets(data.projets.map(String));
    setUtilisateurs(data.utilisateurs.map(String));
  }

  async function valider() {
    if (!structure) return;
    try {
      await enregistrer.mutateAsync({ id: structure.id, projets: projets.map(Number), utilisateurs: utilisateurs.map(Number) });
      notifications.show({ message: "Affectations enregistrées", color: "green" });
      onClose();
    } catch (e) {
      erreur(e, "Erreur lors de l'enregistrement");
    }
  }

  return (
    <Modal
      opened={structure !== null}
      onClose={() => {
        setCharge(null);
        onClose();
      }}
      size="lg"
      title={structure ? `Affectations — ${libelleStructure(structure)}` : ""}
    >
      {!data ? (
        <Text>Chargement…</Text>
      ) : (
        <Stack gap="sm">
          <MultiSelect
            label={voc("Projets")}
            description={voc("Projets dont cette structure est chargée (un projet peut relever de plusieurs services). Une partie d'un projet s'affecte depuis sa planification.")}
            placeholder="Aucun"
            data={data.choix_projets ?? []}
            value={projets}
            onChange={setProjets}
            searchable
            clearable
          />
          <MultiSelect
            label={voc("Utilisateurs")}
            description={voc("Membres de cette structure. Un utilisateur n'appartient qu'à une structure : l'ajouter ici le retire de son ancienne structure.")}
            placeholder="Aucun"
            data={data.choix_utilisateurs ?? []}
            value={utilisateurs}
            onChange={setUtilisateurs}
            searchable
            clearable
          />
          <Group justify="flex-end">
            <Button onClick={valider} loading={enregistrer.isPending}>Enregistrer</Button>
          </Group>
        </Stack>
      )}
    </Modal>
  );
}

/** Bloc d'une structure dans l'organigramme : ses projets, ses membres, puis ses services. */
function BlocStructure({
  structure,
  structures,
  profondeur,
  onEditer,
  onAffecter,
  onSupprimer,
}: {
  structure: StructureOrganisation;
  structures: StructureOrganisation[];
  profondeur: number;
  onEditer: (s: Partial<StructureOrganisation>) => void;
  onAffecter: (s: StructureOrganisation) => void;
  onSupprimer: (s: StructureOrganisation) => void;
}) {
  const enfants = structures.filter((x) => x.parent === structure.id);
  const racine = profondeur === 0;
  const contenu = (
    <>
      <Group justify="space-between" align="flex-start" wrap="nowrap">
        <div>
          <Group gap={8}>
            {racine ? <Building2 size={20} /> : <Network size={16} />}
            <Text fw={racine ? 700 : 600} size={racine ? "lg" : "md"}>{libelleStructure(structure)}</Text>
            {structure.type && <Badge variant="light" size="sm">{structure.type}</Badge>}
          </Group>
          {structure.responsable && (
            <Text size="xs" c="dimmed" mt={2}>Responsable : {structure.responsable}</Text>
          )}
        </div>
        <Group gap={4} wrap="nowrap">
          <Button size="compact-xs" variant="light" leftSection={<Plus size={12} />} onClick={() => onEditer({ parent: structure.id, type: "Service" })}>
            {racine ? "Ajouter un service" : "Sous-service"}
          </Button>
          <Button size="compact-xs" variant="light" color="indigo" leftSection={<Link2 size={12} />} onClick={() => onAffecter(structure)}>
            {voc("Projets et membres")}
          </Button>
          <Tooltip label="Modifier">
            <ActionIcon size="sm" variant="subtle" onClick={() => onEditer(structure)}>
              <Pencil size={13} />
            </ActionIcon>
          </Tooltip>
          <Tooltip label="Supprimer">
            <ActionIcon size="sm" variant="subtle" color="red" onClick={() => onSupprimer(structure)}>
              <Trash2 size={13} />
            </ActionIcon>
          </Tooltip>
        </Group>
      </Group>

      {(structure.projets_resume.length > 0 || structure.utilisateurs_resume.length > 0) && (
        <SimpleGrid cols={{ base: 1, md: 2 }} mt="xs" spacing="xs">
          <div>
            <Text size="xs" fw={600} c="dimmed" mb={2}>
              <FolderKanban size={12} style={{ verticalAlign: -2 }} /> {voc("Projets")} ({structure.projets_resume.length})
            </Text>
            <Group gap={4}>
              {structure.projets_resume.map((p) => (
                <Tooltip key={p.id} label={p.nom}>
                  <Badge component={Link} to={`/projets/${p.id}`} variant="outline" color="teal" style={{ cursor: "pointer" }}>
                    {p.code}
                  </Badge>
                </Tooltip>
              ))}
              {structure.projets_resume.length === 0 && <Text size="xs" c="dimmed">—</Text>}
            </Group>
          </div>
          <div>
            <Text size="xs" fw={600} c="dimmed" mb={2}>
              <Users size={12} style={{ verticalAlign: -2 }} /> {voc("Membres")} ({structure.utilisateurs_resume.length})
            </Text>
            <Group gap={4}>
              {structure.utilisateurs_resume.map((u) => (
                <Badge key={u.id} variant="light" color="gray" leftSection={<Avatar size={14} radius="xl">{u.nom[0]}</Avatar>}>
                  {u.nom}
                </Badge>
              ))}
              {structure.utilisateurs_resume.length === 0 && <Text size="xs" c="dimmed">—</Text>}
            </Group>
          </div>
        </SimpleGrid>
      )}
      {structure.projets_resume.length === 0 && structure.utilisateurs_resume.length === 0 && (
        <Text size="xs" c="dimmed" mt={4}>{voc("Aucun projet ni membre pour l'instant — bouton « Projets et membres ».")}</Text>
      )}

      {enfants.length > 0 && (
        <Stack gap="xs" mt="sm">
          {enfants.map((e) => (
            <BlocStructure
              key={e.id}
              structure={e}
              structures={structures}
              profondeur={profondeur + 1}
              onEditer={onEditer}
              onAffecter={onAffecter}
              onSupprimer={onSupprimer}
            />
          ))}
        </Stack>
      )}
    </>
  );
  return racine ? (
    <Card withBorder padding="md" radius="md" shadow="xs" style={{ borderTop: "4px solid var(--mantine-color-teal-6)" }}>
      {contenu}
    </Card>
  ) : (
    <Card withBorder padding="sm" radius="sm" bg="gray.0" style={{ borderLeft: "4px solid var(--mantine-color-indigo-4)" }}>
      {contenu}
    </Card>
  );
}

/** Vue « par projet » : pour chaque projet, les services qui y travaillent et leurs membres. */
function VueParProjet({ structures }: { structures: StructureOrganisation[] }) {
  const projets = new Map<number, { code: string; nom: string; services: StructureOrganisation[] }>();
  for (const s of structures) {
    for (const p of s.projets_resume) {
      const entree = projets.get(p.id) ?? { code: p.code, nom: p.nom, services: [] };
      entree.services.push(s);
      projets.set(p.id, entree);
    }
  }
  const lignes = [...projets.entries()].sort((a, b) => a[1].code.localeCompare(b[1].code));
  if (lignes.length === 0) {
    return <Card withBorder><Text size="sm" c="dimmed">{voc("Aucun projet affecté à un service pour l'instant.")}</Text></Card>;
  }
  return (
    <Table highlightOnHover verticalSpacing={8}>
      <Table.Thead>
        <Table.Tr>
          <Table.Th>{voc("Projet")}</Table.Th>
          <Table.Th>Services</Table.Th>
          <Table.Th>{voc("Membres qui y participent")}</Table.Th>
        </Table.Tr>
      </Table.Thead>
      <Table.Tbody>
        {lignes.map(([id, p]) => (
          <Table.Tr key={id}>
            <Table.Td>
              <Link to={`/projets/${id}`}><Text size="sm" fw={600}>{p.code}</Text></Link>
              <Text size="xs" c="dimmed">{p.nom}</Text>
            </Table.Td>
            <Table.Td>
              <Group gap={4}>
                {p.services.map((s) => (
                  <Badge key={s.id} variant="light" color="indigo">{libelleStructure(s)}</Badge>
                ))}
              </Group>
            </Table.Td>
            <Table.Td>
              <Text size="sm">
                {[...new Set(p.services.flatMap((s) => s.utilisateurs_resume.map((u) => u.nom)))].join(", ") || "—"}
              </Text>
            </Table.Td>
          </Table.Tr>
        ))}
      </Table.Tbody>
    </Table>
  );
}

function StructureTab() {
  const { data: structures = [], isLoading } = useStructures();
  const supprimer = useSupprimerStructure();
  const [edition, setEdition] = useState<Partial<StructureOrganisation> | null>(null);
  const [affectation, setAffectation] = useState<StructureOrganisation | null>(null);
  const [vue, setVue] = useState("organigramme");

  function handleSupprimer(s: StructureOrganisation) {
    confirmerSuppression({
      message: `Supprimer « ${s.nom} » ?`,
      onConfirm: async () => {
        try {
          await supprimer.mutateAsync(s.id);
        } catch (e) {
          erreur(e, "Suppression impossible : la structure a des services rattachés.");
        }
      },
    });
  }

  if (isLoading) return <Text>Chargement…</Text>;
  return (
    <Stack gap="sm">
      <Group justify="space-between" align="flex-end">
        <Text size="sm" c="dimmed" maw={760}>
          {voc("Créez l'organisation, puis ses services (directions, secteurs…). Affectez à chaque service ses projets et ses membres pour voir qui travaille sur quoi.")}
        </Text>
        <Group>
          <SegmentedControl
            value={vue}
            onChange={setVue}
            data={[
              { value: "organigramme", label: "Organigramme" },
              { value: "projets", label: voc("Par projet") },
            ]}
          />
          <Button leftSection={<Plus size={16} />} onClick={() => setEdition({ type: "Organisation" })}>
            Nouvelle organisation
          </Button>
        </Group>
      </Group>
      {structures.length === 0 ? (
        <Card withBorder><Text c="dimmed" size="sm">{voc("Aucune organisation pour l'instant : commencez par « Nouvelle organisation ».")}</Text></Card>
      ) : vue === "organigramme" ? (
        <Stack gap="md">
          {structures
            .filter((s) => s.parent === null)
            .map((s) => (
              <BlocStructure
                key={s.id}
                structure={s}
                structures={structures}
                profondeur={0}
                onEditer={setEdition}
                onAffecter={setAffectation}
                onSupprimer={handleSupprimer}
              />
            ))}
        </Stack>
      ) : (
        <VueParProjet structures={structures} />
      )}
      <StructureModal structure={edition} onClose={() => setEdition(null)} />
      <AffectationsModal structure={affectation} onClose={() => setAffectation(null)} />
    </Stack>
  );
}

// -------------------------------------------------------------------------- Parties prenantes

function CategoriesParties() {
  const { data: categories = [] } = useCategoriesPartiesPrenantes();
  const enregistrer = useEnregistrerCategoriePartiePrenante();
  const supprimer = useSupprimerCategoriePartiePrenante();
  const [nom, setNom] = useState("");

  async function ajouter() {
    if (!nom.trim()) return;
    try {
      await enregistrer.mutateAsync({ nom: nom.trim() });
      setNom("");
    } catch (e) {
      erreur(e, "Catégorie déjà existante ?");
    }
  }

  return (
    <Card withBorder padding="sm">
      <Text size="sm" fw={600} mb={4}>Catégories</Text>
      <Group gap="xs" align="center">
        {categories.map((c) => (
          <Pill key={c.id} withRemoveButton onRemove={() => supprimer.mutate(c.id)}>
            {c.nom}
          </Pill>
        ))}
        <TextInput
          size="xs"
          placeholder="Nouvelle catégorie (Entrée)"
          value={nom}
          onChange={(e) => setNom(e.currentTarget.value)}
          onKeyDown={(e) => e.key === "Enter" && ajouter()}
          w={220}
        />
      </Group>
    </Card>
  );
}

function PartiePrenanteModal({ partie, onClose }: { partie: Partial<PartiePrenante> | null; onClose: () => void }) {
  const { data: categories = [] } = useCategoriesPartiesPrenantes();
  const enregistrer = useEnregistrerPartiePrenante();
  const [valeurs, setValeurs] = useState<Partial<PartiePrenante>>({});
  const [cle, setCle] = useState<unknown>(null);
  if (partie !== cle) {
    setCle(partie);
    setValeurs(partie ?? {});
  }

  async function valider() {
    if (!valeurs.nom?.trim()) {
      notifications.show({ message: "Indique le nom.", color: "orange" });
      return;
    }
    try {
      await enregistrer.mutateAsync(valeurs);
      notifications.show({ message: "Partie prenante enregistrée", color: "green" });
      onClose();
    } catch (e) {
      erreur(e, "Erreur lors de l'enregistrement");
    }
  }

  return (
    <Modal opened={partie !== null} onClose={onClose} title={partie?.id ? "Modifier la partie prenante" : "Nouvelle partie prenante"}>
      <Stack gap="sm">
        <TextInput label="Nom" required value={valeurs.nom ?? ""} onChange={(e) => setValeurs({ ...valeurs, nom: e.currentTarget.value })} data-autofocus />
        <Select
          label="Catégorie"
          data={categories.map((c) => ({ value: String(c.id), label: c.nom }))}
          value={valeurs.categorie ? String(valeurs.categorie) : null}
          onChange={(v) => setValeurs({ ...valeurs, categorie: v ? Number(v) : null })}
          clearable
        />
        <Group grow>
          <TextInput label="Contact" value={valeurs.contact ?? ""} onChange={(e) => setValeurs({ ...valeurs, contact: e.currentTarget.value })} />
          <TextInput label="Téléphone" value={valeurs.telephone ?? ""} onChange={(e) => setValeurs({ ...valeurs, telephone: e.currentTarget.value })} />
        </Group>
        <TextInput label="Email" value={valeurs.email ?? ""} onChange={(e) => setValeurs({ ...valeurs, email: e.currentTarget.value })} />
        <Textarea
          label="Description"
          description="Intérêt, influence, attentes…"
          autosize
          minRows={2}
          value={valeurs.description ?? ""}
          onChange={(e) => setValeurs({ ...valeurs, description: e.currentTarget.value })}
        />
        <Group justify="flex-end">
          <Button onClick={valider} loading={enregistrer.isPending}>Enregistrer</Button>
        </Group>
      </Stack>
    </Modal>
  );
}

function PartiesPrenantesTab() {
  const { data: parties = [], isLoading } = usePartiesPrenantes();
  const supprimer = useSupprimerPartiePrenante();
  const [edition, setEdition] = useState<Partial<PartiePrenante> | null>(null);

  if (isLoading) return <Text>Chargement…</Text>;
  return (
    <Stack gap="sm">
      <Group justify="space-between">
        <Text size="sm" c="dimmed">
          {voc("Enregistrées une fois, puis sélectionnées sur les projets et les éléments du cadre stratégique.")}
        </Text>
        <Button leftSection={<Plus size={16} />} onClick={() => setEdition({})}>
          Ajouter
        </Button>
      </Group>
      <CategoriesParties />
      <Table highlightOnHover verticalSpacing={6}>
        <Table.Thead>
          <Table.Tr>
            <Table.Th>Nom</Table.Th>
            <Table.Th>Catégorie</Table.Th>
            <Table.Th>Contact</Table.Th>
            <Table.Th>{voc("Projets")}</Table.Th>
            <Table.Th w={80} />
          </Table.Tr>
        </Table.Thead>
        <Table.Tbody>
          {parties.map((p) => (
            <Table.Tr key={p.id}>
              <Table.Td>
                <Text size="sm">{p.nom}</Text>
                {p.description && <Text size="xs" c="dimmed">{p.description}</Text>}
              </Table.Td>
              <Table.Td>{p.categorie_nom && <Badge variant="light">{p.categorie_nom}</Badge>}</Table.Td>
              <Table.Td>
                <Text size="sm">{[p.contact, p.telephone, p.email].filter(Boolean).join(" · ")}</Text>
              </Table.Td>
              <Table.Td>{p.nb_projets}</Table.Td>
              <Table.Td>
                <Group gap={4} wrap="nowrap" justify="flex-end">
                  <ActionIcon size="sm" variant="subtle" onClick={() => setEdition(p)}>
                    <Pencil size={13} />
                  </ActionIcon>
                  <ActionIcon
                    size="sm"
                    variant="subtle"
                    color="red"
                    onClick={() =>
                      confirmerSuppression({
                        message: `Supprimer « ${p.nom} » ?`,
                        onConfirm: () => supprimer.mutateAsync(p.id).catch((e) => erreur(e, "Suppression impossible")),
                      })
                    }
                  >
                    <Trash2 size={13} />
                  </ActionIcon>
                </Group>
              </Table.Td>
            </Table.Tr>
          ))}
        </Table.Tbody>
      </Table>
      <PartiePrenanteModal partie={edition} onClose={() => setEdition(null)} />
    </Stack>
  );
}

// -------------------------------------------------------------------------------- Partenaires

function PartenaireModal({ partenaire, onClose }: { partenaire: Partial<Partenaire> | null; onClose: () => void }) {
  const enregistrer = useEnregistrerPartenaire();
  const [valeurs, setValeurs] = useState<Partial<Partenaire>>({});
  const [cle, setCle] = useState<unknown>(null);
  if (partenaire !== cle) {
    setCle(partenaire);
    setValeurs({ type: "MISE_EN_OEUVRE", ...partenaire });
  }

  async function valider() {
    if (!valeurs.nom?.trim()) {
      notifications.show({ message: "Indique le nom.", color: "orange" });
      return;
    }
    try {
      await enregistrer.mutateAsync(valeurs);
      notifications.show({ message: "Partenaire enregistré", color: "green" });
      onClose();
    } catch (e) {
      erreur(e, "Erreur lors de l'enregistrement");
    }
  }

  return (
    <Modal opened={partenaire !== null} onClose={onClose} title={partenaire?.id ? "Modifier le partenaire" : "Nouveau partenaire"}>
      <Stack gap="sm">
        <TextInput label="Nom" required value={valeurs.nom ?? ""} onChange={(e) => setValeurs({ ...valeurs, nom: e.currentTarget.value })} data-autofocus />
        <Select
          label="Type"
          data={TYPES_PARTENAIRE}
          value={valeurs.type ?? "MISE_EN_OEUVRE"}
          onChange={(v) => setValeurs({ ...valeurs, type: (v ?? "MISE_EN_OEUVRE") as Partenaire["type"] })}
          allowDeselect={false}
        />
        <Group grow>
          <TextInput label="Contact" value={valeurs.contact ?? ""} onChange={(e) => setValeurs({ ...valeurs, contact: e.currentTarget.value })} />
          <TextInput label="Téléphone" value={valeurs.telephone ?? ""} onChange={(e) => setValeurs({ ...valeurs, telephone: e.currentTarget.value })} />
        </Group>
        <TextInput label="Email" value={valeurs.email ?? ""} onChange={(e) => setValeurs({ ...valeurs, email: e.currentTarget.value })} />
        <Group justify="flex-end">
          <Button onClick={valider} loading={enregistrer.isPending}>Enregistrer</Button>
        </Group>
      </Stack>
    </Modal>
  );
}

/** Nombre de projets d'un rôle ; un clic montre lesquels. */
function StatProjets({ libelle, codes, couleur }: { libelle: string; codes: string[]; couleur: string }) {
  const contenu = (
    <UnstyledButton disabled={codes.length === 0} style={{ textAlign: "left" }}>
      <Text size="xl" fw={700} c={codes.length ? `${couleur}.7` : "dimmed"} lh={1.1}>{codes.length}</Text>
      <Text size="xs" c="dimmed">{libelle}</Text>
    </UnstyledButton>
  );
  if (codes.length === 0) return contenu;
  return (
    <Popover width={260} position="bottom-start" shadow="md" withArrow>
      <Popover.Target>{contenu}</Popover.Target>
      <Popover.Dropdown>
        <Text size="xs" fw={600} mb={6}>{libelle}</Text>
        <Group gap={4}>
          {codes.map((c) => (
            <Badge key={c} size="sm" variant="light" color={couleur}>{c}</Badge>
          ))}
        </Group>
      </Popover.Dropdown>
    </Popover>
  );
}

function PartenairesTab() {
  const { data: partenaires = [], isLoading } = useTousPartenaires();
  const supprimer = useSupprimerPartenaire();
  const [edition, setEdition] = useState<Partial<Partenaire> | null>(null);
  const [filtre, setFiltre] = useState("TOUS");
  const [recherche, setRecherche] = useState("");

  if (isLoading) return <Text>Chargement…</Text>;
  // Filtre sur le rôle réel dans les projets (ou, à défaut, sur le type du partenaire).
  const joue = (p: Partenaire, role: string) =>
    role === "TOUS" ||
    p.type === role ||
    (role === "MISE_EN_OEUVRE" && (p.projets_mise_en_oeuvre_codes?.length ?? 0) > 0) ||
    (role === "CONSORTIUM" && (p.projets_consortium_codes?.length ?? 0) > 0);
  const compte = (role: string) => partenaires.filter((p) => joue(p, role)).length;
  const visibles = partenaires.filter(
    (p) => joue(p, filtre) && p.nom.toLowerCase().includes(recherche.trim().toLowerCase()),
  );

  return (
    <Stack gap="md">
      <Text size="sm" c="dimmed">
        {voc("Une même organisation peut être de mise en œuvre sur un projet et du consortium sur un autre : son rôle se précise dans l'onglet « Partenaires » de chaque projet.")}
      </Text>
      <Group justify="space-between">
        <Group>
          <TextInput
            placeholder="Rechercher un partenaire…"
            leftSection={<Search size={14} />}
            value={recherche}
            onChange={(e) => setRecherche(e.currentTarget.value)}
            w={260}
          />
          <SegmentedControl
            value={filtre}
            onChange={setFiltre}
            data={[
              { value: "TOUS", label: `Tous (${partenaires.length})` },
              { value: "MISE_EN_OEUVRE", label: `Mise en œuvre (${compte("MISE_EN_OEUVRE")})` },
              { value: "CONSORTIUM", label: `Consortium (${compte("CONSORTIUM")})` },
              { value: "BAILLEUR", label: `Bailleurs (${compte("BAILLEUR")})` },
            ]}
          />
        </Group>
        <Button leftSection={<Plus size={16} />} onClick={() => setEdition({ type: filtre === "TOUS" ? "MISE_EN_OEUVRE" : (filtre as Partenaire["type"]) })}>
          Ajouter un partenaire
        </Button>
      </Group>

      {visibles.length === 0 ? (
        <Card withBorder><Text size="sm" c="dimmed">Aucun partenaire.</Text></Card>
      ) : (
        <SimpleGrid cols={{ base: 1, sm: 2, lg: 3 }} spacing="md">
          {visibles.map((p) => {
            const type = LIBELLES_TYPE_PARTENAIRE[p.type];
            const contact = [p.contact, p.telephone, p.email].filter(Boolean).join(" · ");
            return (
              <Card key={p.id} withBorder radius="md" padding="md" style={{ borderTop: `3px solid var(--mantine-color-${type?.couleur ?? "gray"}-5)` }}>
                <Group justify="space-between" align="flex-start" wrap="nowrap">
                  <div style={{ minWidth: 0 }}>
                    <Text fw={600} truncate>{p.nom}</Text>
                    <Badge size="xs" variant="light" color={type?.couleur} mt={4}>{type?.label ?? p.type}</Badge>
                  </div>
                  <Group gap={2} wrap="nowrap">
                    <ActionIcon size="sm" variant="subtle" color="gray" onClick={() => setEdition(p)}>
                      <Pencil size={13} />
                    </ActionIcon>
                    <ActionIcon
                      size="sm"
                      variant="subtle"
                      color="gray"
                      onClick={() =>
                        confirmerSuppression({
                          message: `Supprimer « ${p.nom} » ?`,
                          onConfirm: () =>
                            supprimer.mutateAsync(p.id).catch((e) => erreur(e, voc("Suppression impossible : ce partenaire est utilisé par un projet."))),
                        })
                      }
                    >
                      <Trash2 size={13} />
                    </ActionIcon>
                  </Group>
                </Group>
                <Text size="xs" c="dimmed" mt={6} truncate>{contact || "Pas de contact renseigné"}</Text>
                <Divider my="sm" />
                {p.type === "BAILLEUR" ? (
                  <StatProjets libelle={voc("projets financés")} codes={p.projets_bailleur_codes ?? []} couleur="grape" />
                ) : (
                  <Group grow>
                    <StatProjets libelle={voc("en mise en œuvre")} codes={p.projets_mise_en_oeuvre_codes ?? []} couleur="blue" />
                    <StatProjets libelle={voc("en consortium")} codes={p.projets_consortium_codes ?? []} couleur="teal" />
                  </Group>
                )}
              </Card>
            );
          })}
        </SimpleGrid>
      )}
      <PartenaireModal partenaire={edition} onClose={() => setEdition(null)} />
    </Stack>
  );
}

/** Écran « Organisation » (Administrateur) : structure interne, parties prenantes, partenaires. */
export function OrganisationPage() {
  return (
    <Stack gap="md">
      <TitreRubrique route="/organisation" defaut="Organisation" />
      <Tabs defaultValue="structure" keepMounted={false}>
        <Tabs.List>
          <Tabs.Tab value="structure">Structure de l'organisation</Tabs.Tab>
          <Tabs.Tab value="parties">Parties prenantes</Tabs.Tab>
          <Tabs.Tab value="partenaires">Partenaires</Tabs.Tab>
        </Tabs.List>
        <Tabs.Panel value="structure" pt="md">
          <StructureTab />
        </Tabs.Panel>
        <Tabs.Panel value="parties" pt="md">
          <PartiesPrenantesTab />
        </Tabs.Panel>
        <Tabs.Panel value="partenaires" pt="md">
          <PartenairesTab />
        </Tabs.Panel>
      </Tabs>
    </Stack>
  );
}

