import { useEffect, useState } from "react";
import { Lock, Pencil, Trash2 } from "lucide-react";
import { ActionIcon, Badge, Button, Group, Modal, Stack, Switch, Table, Text, TextInput, Tooltip } from "@mantine/core";
import { notifications } from "@mantine/notifications";
import { useCreateRole, useDeleteRole, useRoles, useUpdateRole } from "../../api/accounts";
import { confirmerSuppression } from "../../components/common/confirmerSuppression";
import { messageErreurApi } from "../../utils/erreurs";
import type { RoleUtilisateur } from "../../types";
import { voc } from "../../utils/vocabulaire";

const LIBELLE_VISIBILITE = voc("Voit tous les projets");
const LIBELLE_TABLEAU_DE_BORD = voc("Peut personnaliser le tableau de bord");
const AIDE_TABLEAU_DE_BORD = voc("Choisir les blocs affichés et les types de graphiques, pour tous les utilisateurs.");
const LIBELLE_APPROUVER = "Peut approuver";
const AIDE_APPROUVER = voc("Approuve ou rejette les saisies et les changements de planification des projets qui exigent une approbation (écran Approbations).");
const AIDE_VISIBILITE =
  voc("Sinon, l'utilisateur ne voit que les projets (et zones) auxquels il est affecté. Ce qu'il peut faire ") +
  voc("(voir seulement, ou créer et modifier) se règle par utilisateur, avec son niveau d'accès.");

export function ModifierRoleModal({ role, onClose }: { role: RoleUtilisateur | null; onClose: () => void }) {
  const updateRole = useUpdateRole();
  const [libelle, setLibelle] = useState("");
  const [visibiliteGlobale, setVisibiliteGlobale] = useState(false);
  const [tableauDeBord, setTableauDeBord] = useState(false);
  const [approuver, setApprouver] = useState(false);

  useEffect(() => {
    if (!role) return;
    setLibelle(role.libelle);
    setVisibiliteGlobale(role.visibilite_globale);
    setTableauDeBord(role.peut_personnaliser_tableau_de_bord);
    setApprouver(role.peut_approuver);
  }, [role]);

  const estAdmin = role?.code === "ADMIN";

  async function handleEnregistrer() {
    if (!role || !libelle.trim()) return;
    try {
      await updateRole.mutateAsync({
        id: role.id,
        payload: {
          libelle: libelle.trim(),
          visibilite_globale: visibiliteGlobale,
          peut_personnaliser_tableau_de_bord: tableauDeBord,
          peut_approuver: approuver,
        },
      });
      notifications.show({ message: "Rôle modifié", color: "green" });
      onClose();
    } catch (error) {
      notifications.show({ message: messageErreurApi(error, "Erreur lors de la modification du rôle"), color: "red" });
    }
  }

  return (
    <Modal opened={!!role} onClose={onClose} title={`Modifier le rôle — ${role?.libelle ?? ""}`}>
      <Stack gap="sm">
        <TextInput label="Libellé" value={libelle} onChange={(e) => setLibelle(e.currentTarget.value)} required />
        <Switch
          label={LIBELLE_VISIBILITE}
          description={estAdmin ? "Toujours actif pour l'Administrateur" : AIDE_VISIBILITE}
          checked={estAdmin || visibiliteGlobale}
          disabled={estAdmin}
          onChange={(e) => setVisibiliteGlobale(e.currentTarget.checked)}
        />
        <Switch
          label={LIBELLE_TABLEAU_DE_BORD}
          description={estAdmin ? "Toujours actif pour l'Administrateur" : AIDE_TABLEAU_DE_BORD}
          checked={estAdmin || tableauDeBord}
          disabled={estAdmin}
          onChange={(e) => setTableauDeBord(e.currentTarget.checked)}
        />
        <Switch
          label={LIBELLE_APPROUVER}
          description={estAdmin ? "Toujours actif pour l'Administrateur" : AIDE_APPROUVER}
          checked={estAdmin || approuver}
          disabled={estAdmin}
          onChange={(e) => setApprouver(e.currentTarget.checked)}
        />
        <Group justify="flex-end" mt="sm">
          <Button onClick={handleEnregistrer} loading={updateRole.isPending}>Enregistrer</Button>
        </Group>
      </Stack>
    </Modal>
  );
}

/** Onglet « Rôles » de l'écran Utilisateurs : référentiel des rôles, géré par l'Administrateur. */
export function RolesTab() {
  const { data: roles, isLoading } = useRoles();
  const createRole = useCreateRole();
  const deleteRole = useDeleteRole();
  const [libelle, setLibelle] = useState("");
  const [visibiliteGlobale, setVisibiliteGlobale] = useState(false);
  const [tableauDeBord, setTableauDeBord] = useState(false);
  const [approuver, setApprouver] = useState(false);
  const [roleEnEdition, setRoleEnEdition] = useState<RoleUtilisateur | null>(null);

  async function handleCreer() {
    if (!libelle.trim()) {
      notifications.show({ message: "Indique le libellé du rôle.", color: "orange" });
      return;
    }
    try {
      await createRole.mutateAsync({
        libelle: libelle.trim(),
        visibilite_globale: visibiliteGlobale,
        peut_personnaliser_tableau_de_bord: tableauDeBord,
        peut_approuver: approuver,
      });
      setLibelle("");
      setVisibiliteGlobale(false);
      setTableauDeBord(false);
      setApprouver(false);
      notifications.show({ message: "Rôle créé", color: "green" });
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
          notifications.show({ message: "Rôle supprimé", color: "green" });
        } catch (error) {
          notifications.show({ message: messageErreurApi(error, "Erreur lors de la suppression du rôle"), color: "red" });
        }
      },
    });
  }

  return (
    <Stack gap="md">
      <Text c="dimmed" size="sm">
        {voc("Les rôles système (cadenas) sont utilisés par la plateforme : ils peuvent être renommés, pas supprimés. Un rôle ajouté peut être supprimé tant qu'aucun utilisateur ne l'a.")}</Text>

      <Group align="flex-end">
        <TextInput
          label="Nouveau rôle"
          placeholder="Ex : Superviseur régional"
          value={libelle}
          onChange={(e) => setLibelle(e.currentTarget.value)}
          onKeyDown={(e) => e.key === "Enter" && handleCreer()}
          w={300}
        />
        <Switch
          label={LIBELLE_VISIBILITE}
          checked={visibiliteGlobale}
          onChange={(e) => setVisibiliteGlobale(e.currentTarget.checked)}
          mb={8}
        />
        <Switch
          label={LIBELLE_TABLEAU_DE_BORD}
          checked={tableauDeBord}
          onChange={(e) => setTableauDeBord(e.currentTarget.checked)}
          mb={8}
        />
        <Switch label={LIBELLE_APPROUVER} checked={approuver} onChange={(e) => setApprouver(e.currentTarget.checked)} mb={8} />
        <Button onClick={handleCreer} loading={createRole.isPending}>Ajouter</Button>
      </Group>

      {isLoading ? (
        <div>Chargement…</div>
      ) : (
        <Table striped highlightOnHover>
          <Table.Thead>
            <Table.Tr>
              <Table.Th>Libellé</Table.Th>
              <Table.Th>Code</Table.Th>
              <Table.Th>Visibilité</Table.Th>
              <Table.Th>{voc("Tableau de bord")}</Table.Th>
              <Table.Th>Approbations</Table.Th>
              <Table.Th>{voc("Utilisateurs")}</Table.Th>
              <Table.Th w={40} />
            </Table.Tr>
          </Table.Thead>
          <Table.Tbody>
            {roles?.map((r) => (
              <Table.Tr key={r.id}>
                <Table.Td>
                  <Group gap={6} wrap="nowrap">
                    {r.systeme && (
                      <Tooltip label="Rôle système">
                        <Lock size={13} />
                      </Tooltip>
                    )}
                    <Text size="sm">{r.libelle}</Text>
                  </Group>
                </Table.Td>
                <Table.Td><Text size="xs" c="dimmed">{r.code}</Text></Table.Td>
                <Table.Td>
                  <Badge variant="light" color={r.visibilite_globale ? "teal" : "gray"}>
                    {r.visibilite_globale ? voc("Tous les projets") : voc("Projets affectés")}
                  </Badge>
                </Table.Td>
                <Table.Td>
                  <Badge variant="light" color={r.code === "ADMIN" || r.peut_personnaliser_tableau_de_bord ? "indigo" : "gray"}>
                    {r.code === "ADMIN" || r.peut_personnaliser_tableau_de_bord ? "Peut personnaliser" : "Consultation"}
                  </Badge>
                </Table.Td>
                <Table.Td>
                  {(r.code === "ADMIN" || r.peut_approuver) && (
                    <Badge variant="light" color="grape">Approuve</Badge>
                  )}
                </Table.Td>
                <Table.Td>{r.nb_utilisateurs}</Table.Td>
                <Table.Td>
                  <Group gap={4} wrap="nowrap">
                    <Tooltip label="Modifier">
                      <ActionIcon size="sm" variant="subtle" onClick={() => setRoleEnEdition(r)}>
                        <Pencil size={13} />
                      </ActionIcon>
                    </Tooltip>
                    <Tooltip
                      label={
                        r.systeme
                          ? "Rôle système : non supprimable"
                          : r.nb_utilisateurs > 0
                            ? voc("Des utilisateurs ont ce rôle")
                            : "Supprimer"
                      }
                    >
                      <ActionIcon
                        size="sm"
                        variant="subtle"
                        color="red"
                        disabled={r.systeme || r.nb_utilisateurs > 0}
                        loading={deleteRole.isPending && deleteRole.variables === r.id}
                        onClick={() => handleSupprimer(r)}
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

      <ModifierRoleModal role={roleEnEdition} onClose={() => setRoleEnEdition(null)} />
    </Stack>
  );
}
