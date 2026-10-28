import { type MouseEvent, useEffect, useState } from "react";
import { Check, Pencil, Trash2 } from "lucide-react";
import {
  ActionIcon,
  Badge,
  Button,
  Group,
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
import type { NiveauModule, RoleUtilisateur, User } from "../../types";
import { ModifierRoleModal, RolesTab } from "./RolesTab";
import { DroitsModules } from "./DroitsModules";
import { TitreRubrique } from "../../components/common/TitreRubrique";
import { voc } from "../../utils/vocabulaire";

const PREFIXE_CREATION = "__creer__";

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

  const data = roles?.map((r) => ({ value: r.code, label: r.libelle })) ?? [];
  const texte = recherche.trim();
  const dejaExistant = data.some((o) => o.label.toLowerCase() === texte.toLowerCase());
  if (texte && !dejaExistant) {
    data.push({ value: `${PREFIXE_CREATION}${texte}`, label: `+ Créer le rôle « ${texte} »` });
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
      notifications.show({ message: `Rôle « ${cree.libelle} » créé`, color: "green" });
    } catch (error) {
      notifications.show({ message: messageErreurApi(error, "Erreur lors de la création du rôle"), color: "red" });
    }
  }

  function handleSupprimer(role: RoleUtilisateur) {
    confirmerSuppression({
      message: `Supprimer le rôle "${role.libelle}" ?`,
      onConfirm: async () => {
        try {
          await deleteRole.mutateAsync(role.id);
          if (value === role.code) onChange(null);
          notifications.show({ message: "Rôle supprimé", color: "green" });
        } catch (error) {
          notifications.show({ message: messageErreurApi(error, "Erreur lors de la suppression du rôle"), color: "red" });
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
        label="Rôle"
        placeholder="Choisir ou taper un nouveau rôle…"
        data={data}
        value={value}
        onChange={handleChange}
        searchable
        searchValue={recherche}
        onSearchChange={setRecherche}
        nothingFoundMessage="Tape le nom du rôle à créer"
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
                <Tooltip label="Modifier le rôle">
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
                      ? "Rôle système : non supprimable"
                      : role.nb_utilisateurs > 0
                        ? voc("Des utilisateurs ont ce rôle")
                        : "Supprimer le rôle"
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
  { value: "LECTURE_SEULE", label: "Voir seulement" },
  { value: "LECTURE_ECRITURE", label: "Créer et modifier" },
];

const LIBELLES_NIVEAU_ACCES: Record<string, string> = {
  LECTURE_SEULE: "Voir seulement",
  LECTURE_ECRITURE: "Créer et modifier",
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
          ...(password ? { password } : {}),
        },
      });
      notifications.show({ message: voc("Utilisateur modifié"), color: "green" });
      onClose();
    } catch {
      notifications.show({ message: "Erreur lors de la modification", color: "red" });
    }
  }

  return (
    <Modal size="xl" opened={!!utilisateur} onClose={onClose} title={`Modifier — ${utilisateur?.username ?? ""}`}>
      <Stack gap="sm">
        <Group grow>
          <TextInput label="Prénom" value={prenom} onChange={(e) => setPrenom(e.currentTarget.value)} />
          <TextInput label="Nom" value={nom} onChange={(e) => setNom(e.currentTarget.value)} />
        </Group>
        <TextInput label="Email" value={email} onChange={(e) => setEmail(e.currentTarget.value)} />
        <RoleSelect value={role} onChange={setRole} />
        <Select
          label="Niveau d'accès par défaut"
          data={NIVEAUX_ACCES}
          value={estAdmin ? "LECTURE_ECRITURE" : niveauAcces}
          onChange={setNiveauAcces}
          disabled={estAdmin}
          description={estAdmin ? "Toujours complet pour un Administrateur" : "Appliqué aux modules non réglés ci-dessous"}
        />
        {estAdmin ? (
          <Text size="xs" c="dimmed">Un Administrateur a toujours accès à tous les modules.</Text>
        ) : (
          <DroitsModules value={droits} onChange={setDroits} niveauAcces={niveauAcces} />
        )}
        <Switch label="Compte actif" checked={actif} onChange={(e) => setActif(e.currentTarget.checked)} />
        <PasswordInput
          label="Nouveau mot de passe"
          description="Laisser vide pour ne pas le changer"
          value={password}
          onChange={(e) => setPassword(e.currentTarget.value)}
        />
        <Group justify="flex-end" mt="sm">
          <Button onClick={handleEnregistrer} loading={updateUtilisateur.isPending}>Enregistrer</Button>
        </Group>
      </Stack>
    </Modal>
  );
}

export function UtilisateursPage() {
  const { user: utilisateurConnecte } = useAuth();
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

  const estAdmin = role === "ADMIN";

  async function handleCreate() {
    if (!username || !password || !role) {
      notifications.show({ message: "Identifiant, mot de passe et rôle requis.", color: "orange" });
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
      notifications.show({ message: voc("Utilisateur créé"), color: "green" });
    } catch {
      notifications.show({ message: "Erreur lors de la création (identifiant déjà utilisé ?)", color: "red" });
    }
  }

  return (
    <Stack gap="md">
      <div>
        <TitreRubrique route="/utilisateurs" defaut="Utilisateurs" />
        <Text c="dimmed" size="sm">
          {voc("Un Administrateur a toujours accès à tout. Pour les autres, choisis le rôle (détermine les projets visibles) et le niveau d'accès (voir seulement, ou créer et modifier dans son périmètre).")}</Text>
      </div>

      <Tabs defaultValue="utilisateurs" keepMounted={false}>
        <Tabs.List>
          <Tabs.Tab value="utilisateurs">{voc("Utilisateurs")}</Tabs.Tab>
          <Tabs.Tab value="roles">Rôles</Tabs.Tab>
        </Tabs.List>

        <Tabs.Panel value="roles" pt="md">
          <RolesTab />
        </Tabs.Panel>

        <Tabs.Panel value="utilisateurs" pt="md">
          <Stack gap="md">
            <Stack gap="xs">
              <Group align="flex-end">
                <TextInput label="Identifiant" value={username} onChange={(e) => setUsername(e.currentTarget.value)} />
                <TextInput label="Prénom" value={prenom} onChange={(e) => setPrenom(e.currentTarget.value)} />
                <TextInput label="Nom" value={nom} onChange={(e) => setNom(e.currentTarget.value)} />
                <TextInput label="Email" value={email} onChange={(e) => setEmail(e.currentTarget.value)} />
              </Group>
              <Group align="flex-end">
                <RoleSelect value={role} onChange={setRole} />
                <Select
                  label="Niveau d'accès"
                  data={NIVEAUX_ACCES}
                  value={estAdmin ? "LECTURE_ECRITURE" : niveauAcces}
                  onChange={setNiveauAcces}
                  disabled={estAdmin}
                  description={estAdmin ? "Toujours complet pour un Administrateur" : undefined}
                />
                <PasswordInput label="Mot de passe" value={password} onChange={(e) => setPassword(e.currentTarget.value)} />
                <Button onClick={handleCreate} loading={createUtilisateur.isPending}>Créer</Button>
              </Group>
            </Stack>

            {isLoading ? (
              <div>Chargement…</div>
            ) : (
              <Table striped highlightOnHover>
                <Table.Thead>
                  <Table.Tr>
                    <Table.Th>Identifiant</Table.Th>
                    <Table.Th>Nom</Table.Th>
                    <Table.Th>Email</Table.Th>
                    <Table.Th>Rôle</Table.Th>
                    <Table.Th>Accès</Table.Th>
                    <Table.Th>Actif</Table.Th>
                    <Table.Th w={40} />
                  </Table.Tr>
                </Table.Thead>
                <Table.Tbody>
                  {utilisateurs?.map((u) => (
                    <Table.Tr key={u.id}>
                      <Table.Td>{u.username}</Table.Td>
                      <Table.Td>{u.first_name} {u.last_name}</Table.Td>
                      <Table.Td>{u.email}</Table.Td>
                      <Table.Td><Badge variant="light">{u.role_libelle || u.role}</Badge></Table.Td>
                      <Table.Td>
                        <Badge variant="light" color={u.role === "ADMIN" || u.niveau_acces === "LECTURE_ECRITURE" ? "teal" : "gray"}>
                          {u.role === "ADMIN" ? "Complet" : LIBELLES_NIVEAU_ACCES[u.niveau_acces] ?? u.niveau_acces}
                        </Badge>
                        {u.role !== "ADMIN" && Object.keys(u.acces_modules ?? {}).length > 0 && (
                          <Badge variant="light" color="orange" ml={4}>Droits par module</Badge>
                        )}
                      </Table.Td>
                      <Table.Td>{u.is_active ? "Oui" : "Non"}</Table.Td>
                      <Table.Td>
                        <Group gap={4} wrap="nowrap">
                          <Tooltip label="Modifier">
                            <ActionIcon size="sm" variant="subtle" onClick={() => setUtilisateurEnEdition(u)}>
                              <Pencil size={13} />
                            </ActionIcon>
                          </Tooltip>
                          <Tooltip label={u.id === utilisateurConnecte?.id ? "Impossible de supprimer ton propre compte" : "Supprimer"}>
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
                  ))}
                </Table.Tbody>
              </Table>
            )}
          </Stack>
        </Tabs.Panel>
      </Tabs>

      <ModifierUtilisateurModal utilisateur={utilisateurEnEdition} onClose={() => setUtilisateurEnEdition(null)} />
    </Stack>
  );
}
