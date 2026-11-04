import { type MouseEvent, useEffect, useMemo, useState } from "react";
import { Check, Mail, Pencil, Search, Trash2, UserPlus } from "lucide-react";
import {
  ActionIcon,
  Avatar,
  Badge,
  Button,
  Card,
  Group,
  SimpleGrid,
  UnstyledButton,
  Modal,
  PasswordInput,
  Select,
  Stack,
  Switch,
  Table,
  Tabs,
  Text,
  TextInput,
  Tooltip,
} from "@mantine/core";
import { notifications } from "@mantine/notifications";
import { useAuth } from "../../auth/useAuth";
import {
  useCreateRole,
  useCreateUtilisateur,
  useDeleteRole,
  useDeleteUtilisateur,
  useRoles,
  useUpdateUtilisateur,
  useUtilisateurs,
} from "../../api/accounts";
import { confirmerSuppression } from "../../components/common/confirmerSuppression";
import { messageErreurApi } from "../../utils/erreurs";
import type { NiveauModule, RoleUtilisateur, TypeStructureUtilisateur, User } from "../../types";
import { ModifierRoleModal, RolesTab } from "./RolesTab";
import { useIdentiteOrganisation } from "../../api/identite";
import { DemandesInscription } from "./DemandesInscription";
import { DroitsModules } from "./DroitsModules";
import { usePartiesPrenantes, useStructures, useTousPartenaires } from "../../api/organisation";
import { optionsStructures } from "../../utils/organisation";
import { TitreRubrique } from "../../components/common/TitreRubrique";
import { voc } from "../../utils/vocabulaire";
import { libelleRole } from "../../utils/roles";
import { correspond } from "../../utils/recherche";
import { initiales } from "../../utils/texte";

const PREFIXE_CREATION = "__creer__";

const TYPES_STRUCTURE: { value: TypeStructureUtilisateur; label: string }[] = [
  { value: "INTERNE", label: voc("Organisation (interne)") },
  { value: "CONSORTIUM", label: voc("Partenaire de consortium") },
  { value: "MISE_EN_OEUVRE", label: voc("Partenaire de mise en œuvre") },
  { value: "PARTIE_PRENANTE", label: voc("Partie prenante") },
  { value: "BAILLEUR", label: voc("Bailleur") },
];

type StructureUtilisateur = Pick<User, "type_structure" | "structure_interne" | "partenaire" | "partie_prenante">;

const droitsParModule = (u: User) => u.role !== "ADMIN" && Object.keys(u.acces_modules ?? {}).length > 0;
/** Compteurs du haut de la liste, qui servent aussi de filtre. */
const FILTRES = {
  tous: { libelle: voc("Tous les comptes"), couleur: "teal", garde: (_u: User) => true },
  actifs: { libelle: voc("Actifs"), couleur: "teal", garde: (u: User) => u.is_active },
  admins: { libelle: voc("Administrateurs"), couleur: "blue", garde: (u: User) => u.role === "ADMIN" },
  modules: { libelle: voc("Droits par module"), couleur: "orange", garde: droitsParModule },
  inactifs: { libelle: voc("Désactivés"), couleur: "gray", garde: (u: User) => !u.is_active },
} as const;

/** Structure de l'utilisateur : son type, puis le service, le partenaire ou la partie prenante concerné. */
function ChoixStructure({ value, onChange }: { value: StructureUtilisateur; onChange: (v: StructureUtilisateur) => void }) {
  const { data: structures } = useStructures();
  const { data: partenaires } = useTousPartenaires();
  const { data: parties } = usePartiesPrenantes();
  const type = value.type_structure || null;
  const vider = { structure_interne: null, partenaire: null, partie_prenante: null };
  const lien =
    type === "INTERNE"
      ? {
          label: voc("Direction / service"),
          data: optionsStructures(structures ?? []),
          champ: "structure_interne" as const,
        }
      : type === "PARTIE_PRENANTE"
        ? {
            label: voc("Partie prenante"),
            data: (parties ?? []).map((p) => ({ value: String(p.id), label: p.nom })),
            champ: "partie_prenante" as const,
          }
        : type
          ? {
              label: type === "BAILLEUR" ? voc("Bailleur") : voc("Partenaire"),
              data: (partenaires ?? [])
                .filter((p) => (type === "BAILLEUR" ? p.type === "BAILLEUR" : p.type !== "BAILLEUR"))
                .map((p) => ({ value: String(p.id), label: p.nom })),
              champ: "partenaire" as const,
            }
          : null;
  return (
    <Group grow align="flex-start">
      <Select
        label={voc("Structure de l'utilisateur")}
        placeholder={voc("Non précisée")}
        data={TYPES_STRUCTURE}
        value={type}
        onChange={(v) => onChange({ ...vider, type_structure: (v ?? "") as TypeStructureUtilisateur | "" })}
        clearable
      />
      {lien && (
        <Select
          label={lien.label}
          placeholder={voc("Choisir…")}
          data={lien.data}
          value={value[lien.champ] ? String(value[lien.champ]) : null}
          onChange={(v) => onChange({ ...value, ...vider, [lien.champ]: v ? Number(v) : null })}
          searchable
          clearable
          nothingFoundMessage={voc("À ajouter dans l'écran Organisation")}
        />
      )}
    </Group>
  );
}

/**
 * Liste « Rôle » (référentiel géré dans l'onglet « Rôles ») : taper un
 * libellé absent de la liste propose de le créer sur place (ex :
 * « Chauffeur »), avec la visibilité par défaut « projets affectés » —
 * modifiable ensuite dans l'onglet « Rôles ». Chaque rôle de la liste peut
 * aussi être modifié ou supprimé directement (mêmes règles que l'onglet
 * « Rôles » : un rôle système ou attribué à des utilisateurs reste).
 */
function RoleSelect({ value, onChange }: { value: string | null; onChange: (code: string | null) => void }) {
  const { data: roles } = useRoles();
  const createRole = useCreateRole();
  const deleteRole = useDeleteRole();
  const [recherche, setRecherche] = useState("");
  const [roleEnEdition, setRoleEnEdition] = useState<RoleUtilisateur | null>(null);
  const roleParCode = new Map(roles?.map((r) => [r.code, r]));

  const data = roles?.map((r) => ({ value: r.code, label: libelleRole(r.libelle) })) ?? [];
  const texte = recherche.trim();
  const dejaExistant = data.some((o) => o.label.toLowerCase() === texte.toLowerCase());
  if (texte && !dejaExistant) {
    data.push({ value: `${PREFIXE_CREATION}${texte}`, label: voc`+ Créer le rôle « ${texte} »` });
  }

  async function handleChange(v: string | null) {
    if (!v?.startsWith(PREFIXE_CREATION)) {
      onChange(v);
      return;
    }
    const libelle = v.slice(PREFIXE_CREATION.length);
    try {
      const cree = await createRole.mutateAsync({ libelle, visibilite_globale: false });
      onChange(cree.code);
      setRecherche(cree.libelle);
      notifications.show({ message: voc`Rôle « ${cree.libelle} » créé`, color: "green" });
    } catch (error) {
      notifications.show({ message: messageErreurApi(error, voc("Erreur lors de la création du rôle")), color: "red" });
    }
  }

  function handleSupprimer(role: RoleUtilisateur) {
    confirmerSuppression({
      message: voc`Supprimer le rôle "${role.libelle}" ?`,
      onConfirm: async () => {
        try {
          await deleteRole.mutateAsync(role.id);
          if (value === role.code) onChange(null);
          notifications.show({ message: voc("Rôle supprimé"), color: "green" });
        } catch (error) {
          notifications.show({ message: messageErreurApi(error, voc("Erreur lors de la suppression du rôle")), color: "red" });
        }
      },
    });
  }

  // Les icônes sont dans l'option : on bloque le clic pour qu'il ne
  // sélectionne pas le rôle en même temps.
  function actionOption(e: MouseEvent, action: () => void) {
    e.preventDefault();
    e.stopPropagation();
    action();
  }

  return (
    <>
      <Select
        label={voc("Rôle")}
        placeholder={voc("Choisir ou taper un nouveau rôle…")}
        data={data}
        value={value}
        onChange={handleChange}
        searchable
        searchValue={recherche}
        onSearchChange={setRecherche}
        nothingFoundMessage={voc("Tape le nom du rôle à créer")}
        disabled={createRole.isPending || deleteRole.isPending}
        renderOption={({ option, checked }) => {
          const role = roleParCode.get(option.value);
          if (!role) return <Text size="sm">{option.label}</Text>;
          const supprimable = !role.systeme && role.nb_utilisateurs === 0;
          return (
            <Group justify="space-between" wrap="nowrap" w="100%" gap="xs">
              <Group gap={6} wrap="nowrap">
                {checked && <Check size={14} />}
                <Text size="sm">{option.label}</Text>
              </Group>
              <Group gap={2} wrap="nowrap">
                <Tooltip label={voc("Modifier le rôle")}>
                  <ActionIcon
                    size="sm"
                    variant="subtle"
                    onMouseDown={(e) => e.preventDefault()}
                    onClick={(e) => actionOption(e, () => setRoleEnEdition(role))}
                  >
                    <Pencil size={13} />
                  </ActionIcon>
                </Tooltip>
                <Tooltip
                  label={
                    role.systeme
                      ? voc("Rôle système : non supprimable")
                      : role.nb_utilisateurs > 0
                        ? voc("Des utilisateurs ont ce rôle")
                        : voc("Supprimer le rôle")
                  }
                >
                  <ActionIcon
                    size="sm"
                    variant="subtle"
                    color="red"
                    data-disabled={!supprimable || undefined}
                    style={supprimable ? undefined : { opacity: 0.35, cursor: "not-allowed" }}
                    onMouseDown={(e) => e.preventDefault()}
                    onClick={(e) => actionOption(e, () => supprimable && handleSupprimer(role))}
                  >
                    <Trash2 size={13} />
                  </ActionIcon>
                </Tooltip>
              </Group>
            </Group>
          );
        }}
      />
      <ModifierRoleModal
        role={roleEnEdition}
        onClose={() => setRoleEnEdition(null)}
      />
    </>
  );
}

const NIVEAUX_ACCES = [
  { value: "LECTURE_SEULE", label: voc("Voir seulement") },
  { value: "LECTURE_ECRITURE", label: voc("Créer et modifier") },
];

const LIBELLES_NIVEAU_ACCES: Record<string, string> = {
  LECTURE_SEULE: voc("Voir seulement"),
  LECTURE_ECRITURE: voc("Créer et modifier"),
};

function ModifierUtilisateurModal({ utilisateur, onClose }: { utilisateur: User | null; onClose: () => void }) {
  const updateUtilisateur = useUpdateUtilisateur();

  const [prenom, setPrenom] = useState("");
  const [nom, setNom] = useState("");
  const [email, setEmail] = useState("");
  const [role, setRole] = useState<string | null>("ANIMATEUR_TERRAIN");
  const [niveauAcces, setNiveauAcces] = useState<string | null>("LECTURE_ECRITURE");
  const [actif, setActif] = useState(true);
  const [password, setPassword] = useState("");
  const [droits, setDroits] = useState<Record<string, NiveauModule>>({});
  const [structure, setStructure] = useState<StructureUtilisateur>({});

  // Le modal reste monté en permanence (seul `utilisateur` change à chaque
  // clic sur "Modifier") — un useEffect est donc nécessaire pour resynchroniser
  // les champs à chaque nouvel utilisateur, un useState initial ne suffit pas.
  useEffect(() => {
    if (!utilisateur) return;
    setPrenom(utilisateur.first_name);
    setNom(utilisateur.last_name);
    setEmail(utilisateur.email);
    setRole(utilisateur.role);
    setNiveauAcces(utilisateur.niveau_acces);
    setActif(utilisateur.is_active);
    setPassword("");
    setDroits(utilisateur.acces_modules ?? {});
    setStructure({
      type_structure: utilisateur.type_structure ?? "",
      structure_interne: utilisateur.structure_interne ?? null,
      partenaire: utilisateur.partenaire ?? null,
      partie_prenante: utilisateur.partie_prenante ?? null,
    });
  }, [utilisateur]);

  const estAdmin = role === "ADMIN";

  async function handleEnregistrer() {
    if (!utilisateur) return;
    try {
      await updateUtilisateur.mutateAsync({
        id: utilisateur.id,
        payload: {
          first_name: prenom,
          last_name: nom,
          email,
          role: role as never,
          niveau_acces: (estAdmin ? "LECTURE_ECRITURE" : niveauAcces) as never,
          is_active: actif,
          acces_modules: estAdmin ? {} : droits,
          ...structure,
          ...(password ? { password } : {}),
        },
      });
      notifications.show({ message: voc("Utilisateur modifié"), color: "green" });
      onClose();
    } catch {
      notifications.show({ message: voc("Erreur lors de la modification"), color: "red" });
    }
  }

  return (
    <Modal size="xl" opened={!!utilisateur} onClose={onClose} title={voc`Modifier — ${utilisateur?.username ?? ""}`}>
      <Stack gap="sm">
        <Group grow>
          <TextInput label={voc("Prénom")} value={prenom} onChange={(e) => setPrenom(e.currentTarget.value)} />
          <TextInput label={voc("Nom")} value={nom} onChange={(e) => setNom(e.currentTarget.value)} />
        </Group>
        <TextInput label={voc("Email")} value={email} onChange={(e) => setEmail(e.currentTarget.value)} />
        <RoleSelect value={role} onChange={setRole} />
        <ChoixStructure value={structure} onChange={setStructure} />
        <Select
          label={voc("Niveau d'accès par défaut")}
          data={NIVEAUX_ACCES}
          value={estAdmin ? "LECTURE_ECRITURE" : niveauAcces}
          onChange={setNiveauAcces}
          disabled={estAdmin}
          description={estAdmin ? voc("Toujours complet pour un Administrateur") : voc("Appliqué aux modules non réglés ci-dessous")}
        />
        {estAdmin ? (
          <Text size="xs" c="dimmed">{voc("Un Administrateur a toujours accès à tous les modules.")}</Text>
        ) : (
          <DroitsModules value={droits} onChange={setDroits} niveauAcces={niveauAcces} />
        )}
        <Switch label={voc("Compte actif")} checked={actif} onChange={(e) => setActif(e.currentTarget.checked)} />
        <PasswordInput
          label={voc("Nouveau mot de passe")}
          description={voc("Laisser vide pour ne pas le changer")}
          value={password}
          onChange={(e) => setPassword(e.currentTarget.value)}
        />
        <Group justify="flex-end" mt="sm">
          <Button onClick={handleEnregistrer} loading={updateUtilisateur.isPending}>{voc("Enregistrer")}</Button>
        </Group>
      </Stack>
    </Modal>
  );
}

export function UtilisateursPage() {
  const { user: utilisateurConnecte } = useAuth();
  // Plateforme multi-organisations : les demandes d'inscription se suivent dans la console Expertise-ID.
  const { data: plateforme } = useIdentiteOrganisation();
  const { data: utilisateurs, isLoading } = useUtilisateurs();
  const createUtilisateur = useCreateUtilisateur();
  const deleteUtilisateur = useDeleteUtilisateur();
  const [utilisateurEnEdition, setUtilisateurEnEdition] = useState<User | null>(null);

  function handleSupprimer(u: User) {
    confirmerSuppression({
      message: voc`Supprimer l'utilisateur "${u.username}" ? Cette action est irréversible.`,
      onConfirm: async () => {
        try {
          await deleteUtilisateur.mutateAsync(u.id);
          notifications.show({ message: voc("Utilisateur supprimé"), color: "green" });
        } catch (error) {
          notifications.show({
            message: messageErreurApi(error, voc("Erreur lors de la suppression de l'utilisateur")),
            color: "red",
          });
        }
      },
    });
  }

  const [username, setUsername] = useState("");
  const [prenom, setPrenom] = useState("");
  const [nom, setNom] = useState("");
  const [email, setEmail] = useState("");
  const [role, setRole] = useState<string | null>("ANIMATEUR_TERRAIN");
  const [niveauAcces, setNiveauAcces] = useState<string | null>("LECTURE_ECRITURE");
  const [password, setPassword] = useState("");
  const [creationOuverte, setCreationOuverte] = useState(false);
  const [recherche, setRecherche] = useState("");
  const [filtre, setFiltre] = useState<"tous" | "actifs" | "admins" | "modules" | "inactifs">("tous");
  const utilisateursFiltres = useMemo(
    () => (utilisateurs ?? []).filter((u) => FILTRES[filtre].garde(u)
      && [u.username, u.first_name, u.last_name, u.email, u.role_libelle ?? ""].some((t) => correspond(t ?? "", recherche))),
    [utilisateurs, filtre, recherche],

  );

  const estAdmin = role === "ADMIN";

  async function handleCreate() {
    if (!username || !password || !role) {
      notifications.show({ message: voc("Identifiant, mot de passe et rôle requis."), color: "orange" });
      return;
    }
    try {
      await createUtilisateur.mutateAsync({
        username,
        first_name: prenom,
        last_name: nom,
        email,
        role: role as never,
        niveau_acces: (estAdmin ? "LECTURE_ECRITURE" : niveauAcces) as never,
        password,
      });
      setUsername("");
      setPrenom("");
      setNom("");
      setEmail("");
      setPassword("");
      setCreationOuverte(false);
      notifications.show({ message: voc("Utilisateur créé"), color: "green" });
    } catch {
      notifications.show({ message: voc("Erreur lors de la création (identifiant déjà utilisé ?)"), color: "red" });
    }
  }

  return (
    <Stack gap="md">
      <Group justify="space-between" align="flex-start">
        <div>
          <TitreRubrique route="/utilisateurs" defaut={voc("Utilisateurs")} />
          <Text c="dimmed" size="sm" maw={820}>
            {voc("Un Administrateur a toujours accès à tout. Pour les autres, choisissez le rôle (les projets visibles) et le niveau d'accès (consulter seulement, ou créer et modifier dans son périmètre).")}</Text>
        </div>
        <Button leftSection={<UserPlus size={16} />} onClick={() => setCreationOuverte(true)}>{voc("Nouvel utilisateur")}</Button>
      </Group>

      <Tabs defaultValue="utilisateurs" keepMounted={false}>
        <Tabs.List>
          <Tabs.Tab value="utilisateurs">{voc("Utilisateurs")}</Tabs.Tab>
          <Tabs.Tab value="roles">{voc("Rôles")}</Tabs.Tab>
          {!plateforme?.multi_organisations && <Tabs.Tab value="inscriptions">{voc("Demandes d'inscription")}</Tabs.Tab>}
        </Tabs.List>

        <Tabs.Panel value="roles" pt="md">
          <RolesTab />
        </Tabs.Panel>

        <Tabs.Panel value="inscriptions" pt="md">
          <DemandesInscription />
        </Tabs.Panel>

        <Tabs.Panel value="utilisateurs" pt="md">
          <Stack gap="md">
            <SimpleGrid cols={{ base: 2, sm: 5 }} spacing="sm">
              {(Object.keys(FILTRES) as (keyof typeof FILTRES)[]).map((cle) => {
                const actif = filtre === cle;
                const { libelle, couleur, garde } = FILTRES[cle];
                return (
                  <UnstyledButton key={cle} onClick={() => setFiltre(cle)} aria-pressed={actif}>
                    <Card withBorder radius="md" padding="sm" bg={actif ? `${couleur}.0` : undefined}
                      style={{ borderColor: actif ? `var(--mantine-color-${couleur}-5)` : undefined }}>
                      <Text size="xs" c="dimmed" tt="uppercase" fw={600}>{libelle}</Text>
                      <Text fw={700} fz={26} c={`${couleur}.8`}>{(utilisateurs ?? []).filter(garde).length}</Text>
                    </Card>
                  </UnstyledButton>
                );
              })}
            </SimpleGrid>
            <TextInput placeholder={voc("Rechercher un utilisateur (nom, identifiant, email, rôle)…")} leftSection={<Search size={15} />}
              value={recherche} onChange={(e) => setRecherche(e.currentTarget.value)} w={420} maw="100%" />

            {isLoading ? (
              <div>{voc("Chargement…")}</div>
            ) : (
              <Card withBorder radius="md" padding="md">
              <Table.ScrollContainer minWidth={900}>
              <Table highlightOnHover verticalSpacing="sm">
                <Table.Thead>
                  <Table.Tr>
                    <Table.Th tt="uppercase" fz="xs" c="dimmed">{voc("Utilisateur")}</Table.Th>
                    <Table.Th tt="uppercase" fz="xs" c="dimmed">{voc("Email")}</Table.Th>
                    <Table.Th tt="uppercase" fz="xs" c="dimmed">{voc("Rôle")}</Table.Th>
                    <Table.Th tt="uppercase" fz="xs" c="dimmed">{voc("Structure")}</Table.Th>
                    <Table.Th tt="uppercase" fz="xs" c="dimmed">{voc("Accès")}</Table.Th>
                    <Table.Th tt="uppercase" fz="xs" c="dimmed">{voc("État")}</Table.Th>
                    <Table.Th w={70} />
                  </Table.Tr>
                </Table.Thead>
                <Table.Tbody>
                  {utilisateursFiltres.length === 0 && (
                    <Table.Tr><Table.Td colSpan={7}><Text size="sm" c="dimmed" ta="center" py="md">{voc("Aucun utilisateur ne correspond.")}</Text></Table.Td></Table.Tr>
                  )}
                  {utilisateursFiltres.map((u) => {
                    const nomComplet = `${u.first_name} ${u.last_name}`.trim();
                    return (
                    <Table.Tr key={u.id} opacity={u.is_active ? 1 : 0.6}>
                      <Table.Td>
                        <Group gap="sm" wrap="nowrap">
                          <Avatar size={34} radius="xl" variant="light" color={u.role === "ADMIN" ? "blue" : "teal"}>{initiales(nomComplet || u.username)}</Avatar>
                          <div>
                            <Text size="sm" fw={600} style={{ whiteSpace: "nowrap" }}>{nomComplet || u.username}</Text>
                            <Text size="xs" c="dimmed" ff="monospace">{u.username}{u.id === utilisateurConnecte?.id ? ` · ${voc("vous")}` : ""}</Text>
                          </div>
                        </Group>
                      </Table.Td>
                      <Table.Td>
                        {u.email ? (
                          <Group gap={6} wrap="nowrap">
                            <Mail size={13} color="var(--mantine-color-gray-6)" />
                            <Text size="sm" style={{ whiteSpace: "nowrap" }}>{u.email}</Text>
                          </Group>
                        ) : <Text size="sm" c="orange.8">{voc("Aucune adresse : connexion impossible")}</Text>}
                      </Table.Td>
                      <Table.Td>
                        <Badge variant="light" color={u.role === "ADMIN" ? "blue" : "teal"} tt="none" fw={600}>
                          {u.role_libelle ? libelleRole(u.role_libelle) : u.role}
                        </Badge>
                      </Table.Td>
                      <Table.Td><Text size="sm" c={u.structure_libelle ? undefined : "dimmed"}>{u.structure_libelle || "—"}</Text></Table.Td>
                      <Table.Td>
                        <Group gap={4} wrap="nowrap">
                          <Badge variant="dot" color={u.role === "ADMIN" || u.niveau_acces === "LECTURE_ECRITURE" ? "teal" : "gray"} tt="none" fw={500}>
                            {u.role === "ADMIN" ? voc("Complet") : LIBELLES_NIVEAU_ACCES[u.niveau_acces] ?? u.niveau_acces}
                          </Badge>
                          {droitsParModule(u) && (
                            <Badge variant="light" color="orange" tt="none" fw={500}>{voc("Droits par module")}</Badge>
                          )}
                        </Group>
                      </Table.Td>
                      <Table.Td>
                        <Badge variant="light" color={u.is_active ? "green" : "gray"} tt="none" fw={500}>{u.is_active ? voc("Actif") : voc("Désactivé")}</Badge>
                      </Table.Td>
                      <Table.Td>
                        <Group gap={4} wrap="nowrap">
                          <Tooltip label={voc("Modifier")}>
                            <ActionIcon size="sm" variant="subtle" onClick={() => setUtilisateurEnEdition(u)}>
                              <Pencil size={13} />
                            </ActionIcon>
                          </Tooltip>
                          <Tooltip label={u.id === utilisateurConnecte?.id ? voc("Impossible de supprimer ton propre compte") : voc("Supprimer")}>
                            <ActionIcon
                              size="sm"
                              variant="subtle"
                              color="red"
                              disabled={u.id === utilisateurConnecte?.id}
                              loading={deleteUtilisateur.isPending && deleteUtilisateur.variables === u.id}
                              onClick={() => handleSupprimer(u)}
                            >
                              <Trash2 size={13} />
                            </ActionIcon>
                          </Tooltip>
                        </Group>
                      </Table.Td>
                    </Table.Tr>
                    );
                  })}
                </Table.Tbody>
              </Table>
              </Table.ScrollContainer>
              </Card>
            )}
          </Stack>
        </Tabs.Panel>
      </Tabs>

      <Modal opened={creationOuverte} onClose={() => setCreationOuverte(false)} title={voc("Nouvel utilisateur")} size="lg">
        <Stack gap="sm">
          <TextInput label={voc("Identifiant")} required value={username} onChange={(e) => setUsername(e.currentTarget.value)} data-autofocus />
          <Group grow align="flex-start">
            <TextInput label={voc("Prénom")} value={prenom} onChange={(e) => setPrenom(e.currentTarget.value)} />
            <TextInput label={voc("Nom")} value={nom} onChange={(e) => setNom(e.currentTarget.value)} />
          </Group>
          <TextInput label={voc("Email")} description={voc("Le code de connexion est envoyé à cette adresse.")} value={email}
            onChange={(e) => setEmail(e.currentTarget.value)} />
          <Group grow align="flex-start">
            <RoleSelect value={role} onChange={setRole} />
            <Select
              label={voc("Niveau d'accès")}
              data={NIVEAUX_ACCES}
              value={estAdmin ? "LECTURE_ECRITURE" : niveauAcces}
              onChange={setNiveauAcces}
              disabled={estAdmin}
              description={estAdmin ? voc("Toujours complet pour un Administrateur") : undefined}
            />
          </Group>
          <PasswordInput label={voc("Mot de passe")} required value={password} onChange={(e) => setPassword(e.currentTarget.value)} />
          <Group justify="flex-end" mt="xs">
            <Button variant="default" onClick={() => setCreationOuverte(false)}>{voc("Annuler")}</Button>
            <Button leftSection={<UserPlus size={16} />} onClick={handleCreate} loading={createUtilisateur.isPending}>{voc("Créer")}</Button>
          </Group>
        </Stack>
      </Modal>

      <ModifierUtilisateurModal utilisateur={utilisateurEnEdition} onClose={() => setUtilisateurEnEdition(null)} />
    </Stack>
  );
}
