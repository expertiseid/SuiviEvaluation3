import { useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { AlertTriangle, Link2, LayoutGrid, Network, Pencil, Search, Trash2 } from "lucide-react";
import {
  ActionIcon,
  Alert,
  Badge,
  Button,
  Card,
  Group,
  Modal,
  MultiSelect,
  Select,
  SimpleGrid,
  Stack,
  Text,
  Textarea,
  TextInput,
  Title,
  Tooltip,
} from "@mantine/core";
import { notifications } from "@mantine/notifications";
import {
  useCadresStrategiques,
  useCreateCadreStrategique,
  useDeleteCadreStrategique,
  useElementsStrategiques,
  useTypesDocuments,
  useUpdateCadreStrategique,
} from "../../api/strategy";
import { BoutonModeEdition } from "../../components/common/BoutonModeEdition";
import { EmptyState } from "../../components/common/EmptyState";
import { confirmerSuppression } from "../../components/common/confirmerSuppression";
import { correspond } from "../../utils/recherche";
import type { CadreStrategique, TypeDocument } from "../../types";
import { TitreRubrique } from "../../components/common/TitreRubrique";
import { voc } from "../../utils/vocabulaire";
import { messageErreurApi } from "../../utils/erreurs";
import { useAuth } from "../../auth/useAuth";
import { usePartiesPrenantes, useStructures } from "../../api/organisation";
import { optionsStructures } from "../../utils/organisation";
import { lienDocument, maillonsSautes, optionsDocumentsAuDessus, rangMaillon } from "../../utils/chaineDocuments";
import { ChaineDocumentsModal } from "./ChaineDocumentsModal";

/**
 * Création ou modification d'un document d'un maillon : nom, description et, hors premier
 * maillon, rattachement à un document au-dessus (et éventuellement à l'un de ses éléments),
 * avec l'avertissement des maillons sautés.
 */
function CadreModal({
  opened,
  onClose,
  cadreExistant,
  maillon,
  maillons,
}: {
  opened: boolean;
  onClose: () => void;
  cadreExistant?: CadreStrategique | null;
  maillon: TypeDocument | undefined;
  maillons: TypeDocument[];
}) {
  const createCadre = useCreateCadreStrategique();
  const updateCadre = useUpdateCadreStrategique();
  const [nom, setNom] = useState(cadreExistant?.nom ?? "");
  const [description, setDescription] = useState(cadreExistant?.description ?? "");
  const [structuresIds, setStructuresIds] = useState<string[]>((cadreExistant?.structures ?? []).map(String));
  const [partiesIds, setPartiesIds] = useState<string[]>((cadreExistant?.parties_prenantes ?? []).map(String));
  const [parentId, setParentId] = useState<string | null>(cadreExistant?.document_parent ? String(cadreExistant.document_parent) : null);
  const [elementId, setElementId] = useState<string | null>(cadreExistant?.element_parent ? String(cadreExistant.element_parent) : null);
  const { data: structures } = useStructures();
  const { data: partiesPrenantes } = usePartiesPrenantes();
  const { data: tousDocuments } = useCadresStrategiques();
  const { data: elementsParent } = useElementsStrategiques(parentId ? { cadre_strategique: Number(parentId) } : undefined, !!parentId);

  const rang = rangMaillon(maillon?.id, maillons);
  const parent = (tousDocuments ?? []).find((d) => String(d.id) === parentId);
  const sautes = parent ? maillonsSautes(rangMaillon(parent.type_document, maillons), rang, maillons) : [];

  function reinitialiser() {
    setNom(cadreExistant?.nom ?? "");
    setDescription(cadreExistant?.description ?? "");
    setStructuresIds((cadreExistant?.structures ?? []).map(String));
    setPartiesIds((cadreExistant?.parties_prenantes ?? []).map(String));
    setParentId(cadreExistant?.document_parent ? String(cadreExistant.document_parent) : null);
    setElementId(cadreExistant?.element_parent ? String(cadreExistant.element_parent) : null);
  }
  const champs = {
    structures: structuresIds.map(Number),
    parties_prenantes: partiesIds.map(Number),
    type_document: maillon?.id ?? null,
    document_parent: parentId ? Number(parentId) : null,
    element_parent: parentId && elementId ? Number(elementId) : null,
  };

  async function handleSave() {
    if (!nom.trim()) {
      notifications.show({ message: voc("Le nom est requis."), color: "orange" });
      return;
    }
    try {
      const enregistre = cadreExistant
        ? await updateCadre.mutateAsync({ id: cadreExistant.id, payload: { nom: nom.trim(), description, ...champs } })
        : await createCadre.mutateAsync({ nom: nom.trim(), description, ...champs });
      notifications.show({ message: voc("Document enregistré"), color: "green" });
      for (const message of enregistre?.alertes_chaine ?? []) notifications.show({ message: voc(message), color: "orange" });
      onClose();
    } catch (error) {
      notifications.show({ message: messageErreurApi(error, voc("Erreur lors de l'enregistrement")), color: "red" });
    }
  }

  const libelleMaillon = maillon?.nom ?? voc("Cadre stratégique");
  return (
    <Modal
      opened={opened}
      onClose={onClose}
      onExitTransitionEnd={reinitialiser}
      title={cadreExistant ? voc`Modifier — ${cadreExistant.nom}` : voc`Nouveau document — ${libelleMaillon}`}
    >
      <Stack gap="sm">
        <TextInput
          label={voc("Nom")}
          description={rang === 0 ? voc("Ex : « Cadre stratégique 2022-2026 »") : undefined}
          value={nom}
          onChange={(e) => setNom(e.currentTarget.value)}
          required
        />
        <Textarea label={voc("Description")} minRows={2} value={description} onChange={(e) => setDescription(e.currentTarget.value)} />
        {rang > 0 && (
          <>
            <Select
              label={voc("Rattaché à (document)")}
              description={voc("Document d'un maillon au-dessus. Sauter un maillon est permis.")}
              placeholder={voc("Aucun pour l'instant")}
              data={optionsDocumentsAuDessus(rang, tousDocuments ?? [], maillons, cadreExistant?.id)}
              value={parentId}
              onChange={(v) => {
                setParentId(v);
                setElementId(null);
              }}
              searchable
              clearable
            />
            {parentId && (
              <Select
                label={voc("Élément de ce document")}
                description={voc("Vide : rattaché au document lui-même.")}
                placeholder={voc("Le document lui-même")}
                data={(elementsParent ?? []).map((e) => ({ value: String(e.id), label: `${e.type_niveau_nom} : ${e.code ? `${e.code} — ` : ""}${e.nom}` }))}
                value={elementId}
                onChange={setElementId}
                searchable
                clearable
              />
            )}
            {sautes.length > 0 && (
              <Alert color="orange" variant="light" icon={<AlertTriangle size={16} />} py={6}>
                {voc`Maillon(s) sauté(s) : ${sautes.join(", ")}.`}
              </Alert>
            )}
          </>
        )}
        <MultiSelect
          label={voc("Services chargés")}
          placeholder={voc("Aucun")}
          data={optionsStructures(structures ?? [])}
          value={structuresIds}
          onChange={setStructuresIds}
          searchable
          clearable
        />
        <MultiSelect
          label={voc("Parties prenantes")}
          placeholder={voc("Aucune")}
          data={(partiesPrenantes ?? []).map((p) => ({ value: String(p.id), label: p.nom }))}
          value={partiesIds}
          onChange={setPartiesIds}
          searchable
          clearable
        />
        <Group justify="flex-end">
          <Button onClick={handleSave} loading={createCadre.isPending || updateCadre.isPending}>
            {cadreExistant ? voc("Enregistrer") : voc("Créer")}
          </Button>
        </Group>
      </Stack>
    </Modal>
  );
}

/**
 * Documents d'un maillon de la chaîne (rubrique du menu) : « /strategie » pour le premier
 * maillon (cadres stratégiques), « /strategie/type/:typeId » pour les suivants.
 */
export function CadresStrategiquesListPage() {
  const { typeId } = useParams();
  const { user } = useAuth();
  const { data: maillons = [] } = useTypesDocuments();
  const maillon = typeId ? maillons.find((m) => String(m.id) === typeId) : maillons[0];
  const rang = rangMaillon(maillon?.id, maillons);
  const { data: cadres, isLoading } = useCadresStrategiques(maillon?.id);
  const { data: tousDocuments } = useCadresStrategiques();
  const deleteCadre = useDeleteCadreStrategique();
  const [modalOuvert, setModalOuvert] = useState(false);
  const [chaineOuverte, setChaineOuverte] = useState(false);
  const [cadreEnEdition, setCadreEnEdition] = useState<CadreStrategique | null>(null);
  const [recherche, setRecherche] = useState("");
  const [editionActive, setEditionActive] = useState(false);

  const cadresFiltres = useMemo(
    () => (cadres ?? []).filter((c) => correspond(c.nom, recherche) || correspond(c.description, recherche)),
    [cadres, recherche],
  );

  function handleSupprimer(cadre: CadreStrategique) {
    confirmerSuppression({
      message: voc`Supprimer « ${cadre.nom} » ainsi que tous ses niveaux et éléments ? Cette action est irréversible.`,
      onConfirm: async () => {
        try {
          await deleteCadre.mutateAsync(cadre.id);
          notifications.show({ message: voc("Document supprimé"), color: "green" });
        } catch (error) {
          notifications.show({ message: messageErreurApi(error, voc("Erreur lors de la suppression")), color: "red" });
        }
      },
    });
  }

  const lienParent = (c: CadreStrategique) => {
    const parent = (tousDocuments ?? []).find((d) => d.id === c.document_parent);
    return parent ? lienDocument(parent, maillons) : "#";
  };

  return (
    <Stack gap="md">
      <Group justify="space-between">
        {rang === 0 ? (
          <TitreRubrique route="/strategie" defaut={voc("Cadres stratégiques")} />
        ) : (
          <Title order={2}>{maillon?.nom_pluriel}</Title>
        )}
        <Group gap="xs">
          <BoutonModeEdition actif={editionActive} onToggle={() => setEditionActive((v) => !v)} />
          {user?.role === "ADMIN" && (
            <Button variant="light" color="grape" leftSection={<Network size={16} />} onClick={() => setChaineOuverte(true)}>
              {voc("Chaîne des documents")}
            </Button>
          )}
          <Button onClick={() => setModalOuvert(true)}>
            {rang === 0 ? voc("Nouveau cadre stratégique") : voc`Nouveau document — ${maillon?.nom ?? ""}`}
          </Button>
        </Group>
      </Group>

      <TextInput
        placeholder={voc("Rechercher un document…")}
        leftSection={<Search size={15} />}
        value={recherche}
        onChange={(e) => setRecherche(e.currentTarget.value)}
        maw={400}
      />

      {isLoading ? (
        <Text c="dimmed">{voc("Chargement…")}</Text>
      ) : !cadres || cadres.length === 0 ? (
        <Card withBorder padding="md" radius="md">
          <EmptyState
            icon={<LayoutGrid size={32} strokeWidth={1.5} />}
            message={voc("Aucun document pour le moment — crée le premier pour définir sa structuration.")}
          />
        </Card>
      ) : cadresFiltres.length === 0 ? (
        <Card withBorder padding="md" radius="md">
          <EmptyState icon={<LayoutGrid size={32} strokeWidth={1.5} />} message={voc("Aucun document ne correspond à la recherche.")} />
        </Card>
      ) : (
        <SimpleGrid cols={{ base: 1, sm: 2, lg: 3 }}>
          {cadresFiltres.map((cadre) => (
            <Card key={cadre.id} withBorder padding="md" radius="md">
              <Group justify="space-between" align="flex-start" wrap="nowrap">
                <Text component={Link} to={lienDocument(cadre, maillons)} fw={700} size="md" c="teal.8" style={{ flex: 1 }}>
                  {cadre.nom}
                </Text>
                {editionActive && (
                  <Group gap={4} wrap="nowrap">
                    <Tooltip label={voc("Modifier")}>
                      <ActionIcon variant="subtle" onClick={() => setCadreEnEdition(cadre)}>
                        <Pencil size={15} />
                      </ActionIcon>
                    </Tooltip>
                    <Tooltip label={voc("Supprimer")}>
                      <ActionIcon variant="subtle" color="red" loading={deleteCadre.isPending} onClick={() => handleSupprimer(cadre)}>
                        <Trash2 size={15} />
                      </ActionIcon>
                    </Tooltip>
                  </Group>
                )}
              </Group>
              {cadre.document_parent && (
                <Group gap={4} mt={4} wrap="nowrap" align="flex-start">
                  <Link2 size={13} color="var(--mantine-color-dimmed)" style={{ marginTop: 3 }} />
                  <Text size="xs" c="dimmed">
                    {voc("Rattaché à")} {cadre.document_parent_type ? `${cadre.document_parent_type} ` : ""}
                    <Text component={Link} to={lienParent(cadre)} span size="xs" c="teal.8" fw={600}>{cadre.document_parent_nom}</Text>
                    {cadre.element_parent_nom ? ` › ${cadre.element_parent_nom}` : ""}
                  </Text>
                </Group>
              )}
              {(cadre.alertes_chaine ?? []).map((m) => (
                <Text key={m} size="xs" c="orange.8" mt={2}>⚠ {voc(m)}</Text>
              ))}
              {cadre.description && (
                <Text size="sm" c="dimmed" mt={4}>
                  {cadre.description}
                </Text>
              )}
              {(cadre.structures_noms?.length ?? 0) > 0 && (
                <Text size="xs" c="dimmed" mt={4}>{voc("Services")} : {cadre.structures_noms?.join(", ")}</Text>
              )}
              {(cadre.documents_rattaches?.length ?? 0) > 0 && (
                <Group gap={4} mt={6}>
                  <Badge size="sm" variant="light" color="grape">
                    {voc`${cadre.documents_rattaches!.length} document(s) rattaché(s)`}
                  </Badge>
                </Group>
              )}
              <Button component={Link} to={lienDocument(cadre, maillons)} variant="light" size="xs" mt="sm" fullWidth>
                {voc("Ouvrir")}
              </Button>
            </Card>
          ))}
        </SimpleGrid>
      )}

      <CadreModal opened={modalOuvert} onClose={() => setModalOuvert(false)} maillon={maillon} maillons={maillons} />
      <CadreModal
        key={cadreEnEdition?.id ?? "aucun"}
        opened={!!cadreEnEdition}
        onClose={() => setCadreEnEdition(null)}
        cadreExistant={cadreEnEdition}
        maillon={maillons.find((m) => m.id === cadreEnEdition?.type_document) ?? maillon}
        maillons={maillons}
      />
      <ChaineDocumentsModal opened={chaineOuverte} onClose={() => setChaineOuverte(false)} />
    </Stack>
  );
}
