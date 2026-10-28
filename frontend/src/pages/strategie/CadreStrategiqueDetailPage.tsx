import { useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { ArrowDown, ArrowLeft, ArrowUp, ChevronDown, ChevronRight, Download, FileSpreadsheet, Gauge, Layers, ListTree, Pencil, Plus, Search, Settings2, Trash2, Wallet } from "lucide-react";
import {
  ActionIcon,
  Badge,
  Box,
  Button,
  Card,
  Collapse,
  Group,
  Modal,
  MultiSelect,
  Progress,
  Select,
  SimpleGrid,
  Stack,
  Switch,
  Table,
  Tabs,
  Text,
  Textarea,
  TextInput,
  Title,
  Tooltip,
} from "@mantine/core";
import { notifications } from "@mantine/notifications";
import {
  useCadreStrategique,
  useCreateElementStrategique,
  useCreateTypeNiveau,
  useDeleteElementStrategique,
  useDeleteTypeNiveau,
  useElementsStrategiques,
  useRecapCadreStrategique,
  useTypesNiveaux,
  useUpdateElementStrategique,
  useUpdateTypeNiveau,
  telechargerExportStructuration,
} from "../../api/strategy";
import { BoutonModeEdition } from "../../components/common/BoutonModeEdition";
import { EmptyState } from "../../components/common/EmptyState";
import { StatCard } from "../../components/common/StatCard";
import { STATUS_HEX } from "../../components/common/statusPalette";
import { confirmerSuppression } from "../../components/common/confirmerSuppression";
import { toneDeTaux } from "../../components/suivi/BarreProgression";
import { correspond } from "../../utils/recherche";
import { AxesBudgetsTab } from "./AxesBudgetsTab";
import { ImportStructurationModal } from "./ImportStructurationModal";
import type { ElementStrategique, RecapCadreStrategique, TypeNiveau } from "../../types";
import { voc } from "../../utils/vocabulaire";
import { messageErreurApi } from "../../utils/erreurs";
import { usePartiesPrenantes, useStructures } from "../../api/organisation";
import { optionsStructures } from "../../utils/organisation";

// Une couleur par rang de niveau (pas par nom) — fixe et cohérente sur tout
// l'écran, pour distinguer visuellement "à quel niveau appartient ce nœud"
// d'un coup d'œil, quel que soit le nom que l'organisation lui a donné.
const PALETTE_NIVEAUX = ["teal", "blue", "grape", "orange", "cyan", "pink", "indigo", "lime"];

function useCouleursParNiveau(niveaux: TypeNiveau[]) {
  return useMemo(() => {
    const tries = [...niveaux].sort((a, b) => a.ordre - b.ordre);
    const map = new Map<number, string>();
    tries.forEach((n, i) => map.set(n.id, PALETTE_NIVEAUX[i % PALETTE_NIVEAUX.length]));
    return map;
  }, [niveaux]);
}

function messageErreurSuppression(defaut: string) {
  return `${defaut} — vérifie qu'aucun élément n'en dépend encore.`;
}

function formatNombre(valeur: string | number): string {
  return Number(valeur).toLocaleString("fr-FR", { maximumFractionDigits: 2 });
}

// ================== Onglet 1 : Configuration des niveaux ==================
// Le paramétrage du gabarit (noms, ordre, saut de niveau) est totalement
// séparé de la saisie de l'arbre — deux préoccupations distinctes, deux
// onglets, pour ne jamais les mélanger sur le même écran. Tout est scopé au
// cadre stratégique courant : ses niveaux n'apparaissent jamais dans un
// autre cadre, et réciproquement.

function NiveauModal({
  opened,
  onClose,
  niveauExistant,
}: {
  opened: boolean;
  onClose: () => void;
  niveauExistant?: TypeNiveau | null;
}) {
  const updateNiveau = useUpdateTypeNiveau();
  const [nomNiveau, setNomNiveau] = useState(niveauExistant?.nom_niveau ?? "");
  const [sautAutorise, setSautAutorise] = useState(niveauExistant?.saut_niveau_autorise ?? false);
  const [aideCode, setAideCode] = useState(niveauExistant?.aide_code ?? "");

  function reinitialiser() {
    setNomNiveau(niveauExistant?.nom_niveau ?? "");
    setSautAutorise(niveauExistant?.saut_niveau_autorise ?? false);
    setAideCode(niveauExistant?.aide_code ?? "");
  }

  async function handleSave() {
    if (!nomNiveau.trim() || !niveauExistant) return;
    try {
      await updateNiveau.mutateAsync({
        id: niveauExistant.id,
        payload: { nom_niveau: nomNiveau.trim(), saut_niveau_autorise: sautAutorise, aide_code: aideCode },
      });
      notifications.show({ message: "Niveau modifié", color: "green" });
      onClose();
    } catch {
      notifications.show({ message: "Erreur lors de la modification du niveau", color: "red" });
    }
  }

  return (
    <Modal opened={opened} onClose={onClose} onExitTransitionEnd={reinitialiser} title="Modifier le niveau">
      <Stack gap="sm">
        <TextInput
          label="Nom du niveau"
          description="Ex : « Orientation stratégique », « Priorité », « Pilier »..."
          value={nomNiveau}
          onChange={(e) => setNomNiveau(e.currentTarget.value)}
          required
        />
        <TextInput
          label="Aide à la saisie du code"
          description="Exemple affiché comme indication (facultatif)"
          placeholder="Ex : OS1"
          value={aideCode}
          onChange={(e) => setAideCode(e.currentTarget.value)}
        />
        <Switch
          label="Autoriser à sauter ce niveau"
          description="Un élément du niveau suivant pourra alors être rattaché directement à un ancêtre plus haut, sans passer par ce niveau."
          checked={sautAutorise}
          onChange={(e) => setSautAutorise(e.currentTarget.checked)}
        />
        <Group justify="flex-end">
          <Button onClick={handleSave} loading={updateNiveau.isPending}>Enregistrer</Button>
        </Group>
      </Stack>
    </Modal>
  );
}

function ConfigurationNiveaux({
  cadreStrategiqueId,
  niveaux,
  editionActive,
}: {
  cadreStrategiqueId: number;
  niveaux: TypeNiveau[];
  editionActive: boolean;
}) {
  const createNiveau = useCreateTypeNiveau();
  const updateNiveau = useUpdateTypeNiveau();
  const deleteNiveau = useDeleteTypeNiveau();
  const [nomNouveauNiveau, setNomNouveauNiveau] = useState("");
  const [niveauEnEdition, setNiveauEnEdition] = useState<TypeNiveau | null>(null);

  const tries = useMemo(() => [...niveaux].sort((a, b) => a.ordre - b.ordre), [niveaux]);

  async function deplacer(index: number, direction: -1 | 1) {
    const autre = tries[index + direction];
    const courant = tries[index];
    if (!autre) return;

    // La chaîne niveau_parent doit toujours refléter l'ordre affiché — sinon
    // le niveau "racine" réel (niveau_parent=null) se désynchronise de la
    // position 1 à l'écran, et les boutons "Ajouter" affichent le mauvais nom.
    // On recalcule donc toute la chaîne à partir du nouvel ordre, pas
    // seulement les deux niveaux échangés.
    const apresEchange = tries
      .map((n) => {
        if (n.id === courant.id) return { ...n, ordre: autre.ordre };
        if (n.id === autre.id) return { ...n, ordre: courant.ordre };
        return n;
      })
      .sort((a, b) => a.ordre - b.ordre);

    try {
      await Promise.all(
        apresEchange.map((niveau, i) => {
          const original = tries.find((n) => n.id === niveau.id)!;
          const parentAttendu = i === 0 ? null : apresEchange[i - 1].id;
          const payload: Partial<TypeNiveau> = {};
          if (niveau.ordre !== original.ordre) payload.ordre = niveau.ordre;
          if (parentAttendu !== original.niveau_parent) payload.niveau_parent = parentAttendu;
          return Object.keys(payload).length > 0
            ? updateNiveau.mutateAsync({ id: niveau.id, payload })
            : Promise.resolve();
        }),
      );
    } catch {
      notifications.show({ message: "Erreur lors du réordonnancement", color: "red" });
    }
  }

  async function ajouterNiveau() {
    if (!nomNouveauNiveau.trim()) {
      notifications.show({ message: "Le nom du niveau est requis.", color: "orange" });
      return;
    }
    const dernier = tries[tries.length - 1];
    try {
      await createNiveau.mutateAsync({
        cadre_strategique: cadreStrategiqueId,
        nom_niveau: nomNouveauNiveau.trim(),
        ordre: dernier ? dernier.ordre + 1 : 1,
        niveau_parent: dernier ? dernier.id : null,
      });
      notifications.show({ message: "Niveau ajouté", color: "green" });
      setNomNouveauNiveau("");
    } catch {
      notifications.show({ message: "Erreur lors de l'ajout du niveau", color: "red" });
    }
  }

  function supprimerNiveau(niveau: TypeNiveau) {
    confirmerSuppression({
      message: `Supprimer le niveau « ${niveau.nom_niveau} » ? Cette action est irréversible.`,
      onConfirm: async () => {
        try {
          await deleteNiveau.mutateAsync(niveau.id);
          notifications.show({ message: "Niveau supprimé", color: "green" });
        } catch {
          notifications.show({
            message: messageErreurSuppression("Impossible de supprimer ce niveau"),
            color: "red",
          });
        }
      },
    });
  }

  return (
    <Card withBorder padding="lg" radius="md">
      <Text fw={600} mb="xs">Configuration de la structuration</Text>
      <Text size="sm" c="dimmed" mb="sm">
        {voc("Nous définissons ici les niveaux propres à ce cadre stratégique (nombre, noms, ordre) — par exemple « Plan » → « Orientation » → « Axe » → « Activité », ou « Priorité » → « Sous-priorité ». Cette structuration reste propre à ce cadre, sans effet sur les autres.")}</Text>

      {tries.length === 0 ? (
        <EmptyState icon={<ListTree size={32} strokeWidth={1.5} />} message="Aucun niveau défini pour l'instant — commence par en ajouter un ci-dessous." />
      ) : (
        <Stack gap={6} mb="sm">
          {tries.map((niveau, index) => (
            <Group key={niveau.id} gap={6} wrap="nowrap" justify="space-between">
              <Group gap={6} wrap="nowrap">
                <Text size="sm" c="dimmed" w={20}>{niveau.ordre}.</Text>
                <Text size="sm" fw={500}>{niveau.nom_niveau}</Text>
              </Group>
              <Group gap={2} wrap="nowrap">
                <Tooltip label="Monter">
                  <ActionIcon size="sm" variant="subtle" disabled={index === 0} onClick={() => deplacer(index, -1)}>
                    <ArrowUp size={13} />
                  </ActionIcon>
                </Tooltip>
                <Tooltip label="Descendre">
                  <ActionIcon size="sm" variant="subtle" disabled={index === tries.length - 1} onClick={() => deplacer(index, 1)}>
                    <ArrowDown size={13} />
                  </ActionIcon>
                </Tooltip>
                {editionActive && (
                <Group gap={2} wrap="nowrap">
                  <Tooltip label="Modifier">
                    <ActionIcon size="sm" variant="subtle" onClick={() => setNiveauEnEdition(niveau)}>
                      <Pencil size={13} />
                    </ActionIcon>
                  </Tooltip>
                  <Tooltip label="Supprimer">
                    <ActionIcon size="sm" variant="subtle" color="red" loading={deleteNiveau.isPending} onClick={() => supprimerNiveau(niveau)}>
                      <Trash2 size={13} />
                    </ActionIcon>
                  </Tooltip>
                </Group>
                )}
              </Group>
            </Group>
          ))}
        </Stack>
      )}

      <Group gap="xs" align="flex-end">
        <TextInput
          size="xs"
          label="Ajouter un niveau"
          placeholder="Ex : Orientation stratégique"
          value={nomNouveauNiveau}
          onChange={(e) => setNomNouveauNiveau(e.currentTarget.value)}
          style={{ flex: 1 }}
        />
        <Button size="xs" variant="light" onClick={ajouterNiveau} loading={createNiveau.isPending}>
          Ajouter
        </Button>
      </Group>

      <NiveauModal
        key={niveauEnEdition?.id ?? "aucun"}
        opened={!!niveauEnEdition}
        onClose={() => setNiveauEnEdition(null)}
        niveauExistant={niveauEnEdition}
      />
    </Card>
  );
}

// ================== Onglet 2 : Arborescence & saisie ==================
// Chaque nœud lit, via la chaîne niveau_parent de son propre TypeNiveau, le
// niveau immédiatement suivant (rang + 1) pour générer dynamiquement le
// libellé du bouton d'ajout — jamais de nom de niveau codé en dur.

function ElementModal({
  opened,
  onClose,
  typeNiveau,
  elementParent,
  elementExistant,
  niveaux,
  elements,
}: {
  opened: boolean;
  onClose: () => void;
  typeNiveau: TypeNiveau | null;
  elementParent: ElementStrategique | null;
  elementExistant?: ElementStrategique | null;
  niveaux: TypeNiveau[];
  elements: ElementStrategique[];
}) {
  const createElement = useCreateElementStrategique();
  const updateElement = useUpdateElementStrategique();
  const [code, setCode] = useState(elementExistant?.code ?? "");
  const [nom, setNom] = useState(elementExistant?.nom ?? "");
  const [description, setDescription] = useState(elementExistant?.description ?? "");
  const [parentId, setParentId] = useState<string | null>(
    elementExistant?.element_parent ? String(elementExistant.element_parent) : null,
  );
  const [parentsSecondaires, setParentsSecondaires] = useState<string[]>((elementExistant?.parents_secondaires ?? []).map(String));
  const [structuresIds, setStructuresIds] = useState<string[]>((elementExistant?.structures ?? []).map(String));
  const [partiesIds, setPartiesIds] = useState<string[]>((elementExistant?.parties_prenantes ?? []).map(String));
  const { data: structures } = useStructures();
  const { data: partiesPrenantes } = usePartiesPrenantes();
  const { data: tousElements } = useElementsStrategiques();

  function reinitialiser() {
    setParentsSecondaires((elementExistant?.parents_secondaires ?? []).map(String));
    setStructuresIds((elementExistant?.structures ?? []).map(String));
    setPartiesIds((elementExistant?.parties_prenantes ?? []).map(String));
    setCode(elementExistant?.code ?? "");
    setNom(elementExistant?.nom ?? "");
    setDescription(elementExistant?.description ?? "");
    setParentId(elementExistant?.element_parent ? String(elementExistant.element_parent) : null);
  }

  // En édition, on retrouve le niveau de l'élément pour savoir si un
  // rattachement est requis (et à quel niveau) — permet de changer le
  // parent d'un élément déjà créé (ex : rattacher une Orientation existante
  // à un nouveau Plan stratégique ajouté après coup).
  const niveauDeLElement = elementExistant ? niveaux.find((n) => n.id === elementExistant.type_niveau) : typeNiveau;
  const niveauParentAttendu = niveauDeLElement
    ? niveaux.find((n) => n.id === niveauDeLElement.niveau_parent)
    : undefined;
  const optionsParent = niveauParentAttendu
    ? elements
        .filter((e) => e.type_niveau === niveauParentAttendu.id && e.id !== elementExistant?.id)
        .map((e) => ({ value: String(e.id), label: e.code ? `${e.code} — ${e.nom}` : e.nom }))
    : [];

  // « Contribue aussi à » : éléments d'un niveau supérieur de ce cadre, ou de n'importe quel autre document.
  const idsDuCadre = new Set(elements.map((e) => e.id));
  const ordreDuNiveau = niveauDeLElement?.ordre ?? 0;
  const parentPrincipal = elementExistant ? parentId : elementParent ? String(elementParent.id) : null;
  const optionsSecondaires = (() => {
    const groupes = new Map<string, { value: string; label: string }[]>();
    for (const e of tousElements ?? []) {
      if (String(e.id) === parentPrincipal || e.id === elementExistant?.id) continue;
      if (idsDuCadre.has(e.id)) {
        const niveau = niveaux.find((n) => n.id === e.type_niveau);
        if (!niveau || niveau.ordre >= ordreDuNiveau) continue;
      }
      const groupe = idsDuCadre.has(e.id) ? e.type_niveau_nom : `${e.type_niveau_nom} (autre cadre)`;
      const liste = groupes.get(groupe) ?? [];
      liste.push({ value: String(e.id), label: e.code ? `${e.code} — ${e.nom}` : e.nom });
      groupes.set(groupe, liste);
    }
    return [...groupes.entries()].map(([group, items]) => ({ group, items }));
  })();
  const liensOrganisation = {
    parents_secondaires: parentsSecondaires.filter((id) => id !== parentPrincipal).map(Number),
    structures: structuresIds.map(Number),
    parties_prenantes: partiesIds.map(Number),
  };

  async function handleSave() {
    if (!nom.trim()) {
      notifications.show({ message: "Le nom est requis.", color: "orange" });
      return;
    }
    if (elementExistant && niveauParentAttendu && !parentId) {
      notifications.show({ message: `Choisis un « ${niveauParentAttendu.nom_niveau} » de rattachement.`, color: "orange" });
      return;
    }
    try {
      if (elementExistant) {
        await updateElement.mutateAsync({
          id: elementExistant.id,
          payload: {
            code: code.trim(),
            nom: nom.trim(),
            description,
            element_parent: parentId ? Number(parentId) : null,
            ...liensOrganisation,
          },
        });
        notifications.show({ message: "Élément modifié", color: "green" });
      } else if (typeNiveau) {
        await createElement.mutateAsync({
          type_niveau: typeNiveau.id,
          element_parent: elementParent?.id ?? null,
          code: code.trim(),
          nom: nom.trim(),
          description,
          ...liensOrganisation,
        });
        notifications.show({ message: "Élément ajouté", color: "green" });
      }
      onClose();
    } catch (error) {
      notifications.show({ message: messageErreurApi(error, "Erreur lors de l'enregistrement"), color: "red" });
    }
  }

  const niveauActif = elementExistant ? null : typeNiveau;

  return (
    <Modal
      opened={opened}
      onClose={onClose}
      onExitTransitionEnd={reinitialiser}
      title={elementExistant ? "Modifier l'élément" : niveauActif ? `Ajouter — ${niveauActif.nom_niveau}` : "Ajouter un élément"}
    >
      <Stack gap="sm">
        <TextInput
          label="Code"
          placeholder={(elementExistant ? undefined : niveauActif?.aide_code) || "Ex : 1.1"}
          value={code}
          onChange={(e) => setCode(e.currentTarget.value)}
        />
        <TextInput label="Nom" value={nom} onChange={(e) => setNom(e.currentTarget.value)} required />
        <Textarea label="Description" minRows={2} value={description} onChange={(e) => setDescription(e.currentTarget.value)} />
        {elementExistant && niveauParentAttendu && (
          <Select
            label={`Rattaché à (${niveauParentAttendu.nom_niveau})`}
            data={optionsParent}
            value={parentId}
            onChange={setParentId}
            searchable
            required
          />
        )}
        <MultiSelect
          label="Contribue aussi à"
          description={voc("Autres éléments d'un niveau supérieur (de ce cadre ou d'un autre document) auxquels celui-ci contribue. Seul le rattachement principal compte dans les totaux.")}
          placeholder="Aucun"
          data={optionsSecondaires}
          value={parentsSecondaires}
          onChange={setParentsSecondaires}
          searchable
          clearable
        />
        <MultiSelect
          label={voc("Services chargés")}
          placeholder="Aucun"
          data={optionsStructures(structures ?? [])}
          value={structuresIds}
          onChange={setStructuresIds}
          searchable
          clearable
        />
        <MultiSelect
          label="Parties prenantes"
          placeholder="Aucune"
          data={(partiesPrenantes ?? []).map((p) => ({ value: String(p.id), label: p.nom }))}
          value={partiesIds}
          onChange={setPartiesIds}
          searchable
          clearable
        />
        <Group justify="flex-end">
          <Button onClick={handleSave} loading={createElement.isPending || updateElement.isPending}>
            {elementExistant ? "Enregistrer" : "Ajouter"}
          </Button>
        </Group>
      </Stack>
    </Modal>
  );
}

function NoeudElement({
  element,
  niveaux,
  couleurs,
  profondeur,
  enfantsParParent,
  niveauEnfant,
  onAjouter,
  onModifier,
  idsVisibles,
  editionActive,
}: {
  element: ElementStrategique;
  niveaux: TypeNiveau[];
  couleurs: Map<number, string>;
  profondeur: number;
  enfantsParParent: Map<number | null, ElementStrategique[]>;
  niveauEnfant: TypeNiveau | undefined;
  onAjouter: (typeNiveau: TypeNiveau, parent: ElementStrategique) => void;
  onModifier: (element: ElementStrategique) => void;
  idsVisibles: Set<number> | null;
  editionActive: boolean;
}) {
  const deleteElement = useDeleteElementStrategique();
  const [ouvert, setOuvert] = useState(true);
  const enfants = (enfantsParParent.get(element.id) ?? []).filter((e) => !idsVisibles || idsVisibles.has(e.id));
  const enChercheOuvert = idsVisibles ? true : ouvert;
  // Niveau à proposer aux ENFANTS de cet élément pour LEUR propre bouton
  // "Ajouter" — un rang plus bas que niveauEnfant (le niveau des enfants de
  // cet élément), donc dérivé de niveauEnfant et non de element.type_niveau
  // (sinon on repasse le même rang à chaque génération au lieu d'avancer).
  const niveauPourEnfantsDesEnfants = niveauEnfant
    ? niveaux.find((n) => n.niveau_parent === niveauEnfant.id)
    : undefined;
  const couleur = couleurs.get(element.type_niveau) ?? "gray";

  function supprimer() {
    confirmerSuppression({
      message: `Supprimer « ${element.nom} » ? Cette action est irréversible.`,
      onConfirm: async () => {
        try {
          await deleteElement.mutateAsync(element.id);
          notifications.show({ message: "Élément supprimé", color: "green" });
        } catch {
          notifications.show({
            message: messageErreurSuppression("Impossible de supprimer cet élément"),
            color: "red",
          });
        }
      },
    });
  }

  const estRacine = profondeur === 0;

  return (
    <Card
      withBorder
      padding={estRacine ? "md" : "sm"}
      radius="sm"
      mt={estRacine ? 0 : "xs"}
      ml={profondeur * 24}
      shadow={estRacine ? "xs" : undefined}
      style={{
        borderLeft: `${estRacine ? 6 : 4}px solid var(--mantine-color-${couleur}-6)`,
        background: profondeur > 0 ? `var(--mantine-color-${couleur}-0)` : undefined,
      }}
    >
      <Group justify="space-between" gap={6} wrap="nowrap">
        <Group gap={6} wrap="nowrap">
          {enfants.length > 0 && (
            <ActionIcon size="sm" variant="subtle" color="gray" onClick={() => setOuvert((v) => !v)}>
              {ouvert ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
            </ActionIcon>
          )}
          <Badge color={couleur} variant={estRacine ? "filled" : "light"} size="sm">{element.type_niveau_nom}</Badge>
          <div>
            <Text size={estRacine ? "md" : "sm"} fw={estRacine ? 700 : 400}>
              {element.code && <Text span fw={700}>{element.code} — </Text>}
              {element.nom}
            </Text>
            {(element.parents_secondaires_noms?.length ?? 0) > 0 && (
              <Text size="xs" c="dimmed">Contribue aussi à : {element.parents_secondaires_noms?.join(" · ")}</Text>
            )}
            {((element.structures_noms?.length ?? 0) > 0 || (element.parties_prenantes_noms?.length ?? 0) > 0) && (
              <Group gap={4} mt={2}>
                {element.structures_noms?.map((n) => (
                  <Badge key={`s-${n}`} size="xs" variant="light" color="indigo">{n}</Badge>
                ))}
                {element.parties_prenantes_noms?.map((n) => (
                  <Badge key={`p-${n}`} size="xs" variant="outline" color="gray">{n}</Badge>
                ))}
              </Group>
            )}
          </div>
        </Group>
        {editionActive && (
        <Group gap={4} wrap="nowrap">
          <Tooltip label="Modifier">
            <ActionIcon size="sm" variant="subtle" onClick={() => onModifier(element)}>
              <Pencil size={13} />
            </ActionIcon>
          </Tooltip>
          <Tooltip label="Supprimer">
            <ActionIcon size="sm" variant="subtle" color="red" loading={deleteElement.isPending} onClick={supprimer}>
              <Trash2 size={13} />
            </ActionIcon>
          </Tooltip>
        </Group>
        )}
      </Group>

      {niveauEnfant && (
        <Button size="xs" variant="subtle" leftSection={<Plus size={13} />} mt={6} onClick={() => onAjouter(niveauEnfant, element)}>
          {`Ajouter ${niveauEnfant.nom_niveau}`}
        </Button>
      )}

      <Collapse expanded={enChercheOuvert}>
        {enfants.map((enfant) => (
          <NoeudElement
            key={enfant.id}
            element={enfant}
            niveaux={niveaux}
            couleurs={couleurs}
            profondeur={profondeur + 1}
            enfantsParParent={enfantsParParent}
            niveauEnfant={niveauPourEnfantsDesEnfants}
            onAjouter={onAjouter}
            onModifier={onModifier}
            idsVisibles={idsVisibles}
            editionActive={editionActive}
          />
        ))}
      </Collapse>
    </Card>
  );
}

function Arborescence({
  niveaux,
  elements,
  editionActive,
}: {
  niveaux: TypeNiveau[];
  elements: ElementStrategique[];
  editionActive: boolean;
}) {
  const [modalAjout, setModalAjout] = useState<{ typeNiveau: TypeNiveau; parent: ElementStrategique | null } | null>(null);
  const [elementEnEdition, setElementEnEdition] = useState<ElementStrategique | null>(null);
  const [recherche, setRecherche] = useState("");
  const couleurs = useCouleursParNiveau(niveaux);

  // Niveau racine = celui sans niveau_parent (rang 1 de la chaîne).
  const niveauRacine = niveaux.find((n) => n.niveau_parent === null);

  const enfantsParParent = useMemo(() => {
    const map = new Map<number | null, ElementStrategique[]>();
    for (const el of elements) {
      const cle = el.element_parent;
      if (!map.has(cle)) map.set(cle, []);
      map.get(cle)!.push(el);
    }
    return map;
  }, [elements]);

  const racines = enfantsParParent.get(null) ?? [];
  const arbreVide = racines.length === 0;

  // Un élément est visible s'il correspond lui-même à la recherche, ou si un
  // de ses descendants y correspond — pour ne jamais masquer le chemin vers
  // un résultat trouvé en profondeur.
  const idsVisibles = useMemo(() => {
    if (!recherche.trim()) return null;
    const visibles = new Set<number>();
    function visiter(element: ElementStrategique): boolean {
      const enfants = enfantsParParent.get(element.id) ?? [];
      const unEnfantVisible = enfants.map(visiter).some(Boolean);
      const soiMatch = correspond(element.nom, recherche) || correspond(element.code ?? "", recherche);
      if (soiMatch || unEnfantVisible) {
        visibles.add(element.id);
        return true;
      }
      return false;
    }
    racines.forEach(visiter);
    return visibles;
  }, [racines, enfantsParParent, recherche]);

  const racinesFiltrees = idsVisibles ? racines.filter((r) => idsVisibles.has(r.id)) : racines;

  return (
    <Card withBorder padding="lg" radius="md" mih={480}>
      <Group justify="space-between" mb="sm">
        <Text fw={600}>Arborescence</Text>
        {niveauRacine && (
          <Button size="sm" leftSection={<Plus size={14} />} onClick={() => setModalAjout({ typeNiveau: niveauRacine, parent: null })}>
            {arbreVide ? `Créer ${niveauRacine.nom_niveau}` : `Ajouter ${niveauRacine.nom_niveau}`}
          </Button>
        )}
      </Group>

      {!arbreVide && (
        <TextInput
          placeholder="Rechercher un élément…"
          leftSection={<Search size={15} />}
          value={recherche}
          onChange={(e) => setRecherche(e.currentTarget.value)}
          maw={400}
          mb="sm"
        />
      )}

      {!niveauRacine ? (
        <EmptyState
          icon={<ListTree size={32} strokeWidth={1.5} />}
          message="Aucun niveau n'est configuré — passe d'abord par l'onglet « Configuration des niveaux »."
        />
      ) : arbreVide ? (
        <EmptyState icon={<ListTree size={32} strokeWidth={1.5} />} message={`Aucun élément « ${niveauRacine.nom_niveau} » pour le moment.`} />
      ) : racinesFiltrees.length === 0 ? (
        <EmptyState icon={<ListTree size={32} strokeWidth={1.5} />} message="Aucun élément ne correspond à la recherche." />
      ) : (
        <Box style={{ overflowX: "auto" }}>
          <Stack gap="lg">
          {racinesFiltrees.map((racine) => (
            <NoeudElement
              key={racine.id}
              element={racine}
              niveaux={niveaux}
              couleurs={couleurs}
              profondeur={0}
              enfantsParParent={enfantsParParent}
              niveauEnfant={niveaux.find((n) => n.niveau_parent === racine.type_niveau)}
              onAjouter={(typeNiveau, parent) => setModalAjout({ typeNiveau, parent })}
              onModifier={setElementEnEdition}
              idsVisibles={idsVisibles}
              editionActive={editionActive}
            />
          ))}
          </Stack>
        </Box>
      )}

      <ElementModal
        opened={!!modalAjout}
        onClose={() => setModalAjout(null)}
        typeNiveau={modalAjout?.typeNiveau ?? null}
        elementParent={modalAjout?.parent ?? null}
        niveaux={niveaux}
        elements={elements}
      />
      <ElementModal
        key={elementEnEdition?.id ?? "aucun"}
        opened={!!elementEnEdition}
        onClose={() => setElementEnEdition(null)}
        typeNiveau={null}
        elementParent={null}
        elementExistant={elementEnEdition}
        niveaux={niveaux}
        elements={elements}
      />
    </Card>
  );
}

// ================== Onglet 3 : Récapitulatif projets & budgets ==================

function TauxCell({ taux }: { taux: number | null }) {
  if (taux === null) return <Text size="sm" c="dimmed" ta="right">—</Text>;
  return (
    <Group gap={6} wrap="nowrap" justify="flex-end">
      <Text size="sm" fw={600}>{taux}%</Text>
      <Progress value={Math.min(100, taux)} color={STATUS_HEX[toneDeTaux(taux)]} size={6} w={54} radius="xl" />
    </Group>
  );
}

function tauxSur(realise: number, cible: number | null): number | null {
  if (cible === null || cible === 0) return null;
  return Math.round((realise / cible) * 1000) / 10;
}

function moyenne(valeurs: (number | null)[]): number | null {
  const definies = valeurs.filter((v): v is number => v !== null);
  return definies.length ? Math.round((definies.reduce((s, v) => s + v, 0) / definies.length) * 10) / 10 : null;
}

const ENTETE = { tt: "uppercase", fz: "xs", c: "dimmed" } as const;
const CHIFFRE = { ta: "right", style: { whiteSpace: "nowrap" } } as const;

/**
 * Tableau des activités d'un projet : cible, réalisé et taux, en physique
 * puis en financier, avec les totaux en bas (budget additionné ; les
 * quantités ayant des unités différentes, le taux physique total est la
 * moyenne des taux, comme l'exécution physique du projet).
 */
function TableauActivites({
  activites,
}: {
  activites: RecapCadreStrategique["projets"][number]["activites"];
}) {
  if (activites.length === 0) return <Text size="sm" c="dimmed">Aucune activité.</Text>;

  const lignes = activites.map((a) => {
    const budgetAlloue = a.budget_alloue !== null ? Number(a.budget_alloue) : null;
    const budgetRealise = Number(a.budget_realise ?? 0);
    return { ...a, budgetAlloue, budgetRealise, tauxFinancier: tauxSur(budgetRealise, budgetAlloue) };
  });
  const totalAlloue = lignes.reduce((s, l) => s + (l.budgetAlloue ?? 0), 0);
  const totalRealise = lignes.reduce((s, l) => s + l.budgetRealise, 0);

  return (
    <Table.ScrollContainer minWidth={900}>
      <Table verticalSpacing={6} fz="sm" withTableBorder withColumnBorders striped>
        <Table.Thead>
          <Table.Tr>
            <Table.Th rowSpan={2} {...ENTETE}>Activité</Table.Th>
            <Table.Th colSpan={3} {...ENTETE} ta="center">Physique</Table.Th>
            <Table.Th colSpan={3} {...ENTETE} ta="center">Financier (FCFA)</Table.Th>
          </Table.Tr>
          <Table.Tr>
            <Table.Th {...ENTETE} ta="right">Cible</Table.Th>
            <Table.Th {...ENTETE} ta="right">Réalisé</Table.Th>
            <Table.Th {...ENTETE} ta="right">Taux</Table.Th>
            <Table.Th {...ENTETE} ta="right">Budget alloué</Table.Th>
            <Table.Th {...ENTETE} ta="right">Dépensé</Table.Th>
            <Table.Th {...ENTETE} ta="right">Taux</Table.Th>
          </Table.Tr>
        </Table.Thead>
        <Table.Tbody>
          {lignes.map((a) => (
            <Table.Tr key={a.id}>
              <Table.Td>
                {a.code && <Text span c="dimmed">{a.code} — </Text>}
                {a.libelle}
              </Table.Td>
              <Table.Td {...CHIFFRE}>
                {a.quantite_prevue !== null ? `${formatNombre(a.quantite_prevue)} ${a.unite_quantite}` : "—"}
              </Table.Td>
              <Table.Td {...CHIFFRE}>
                {a.quantite_prevue !== null ? `${formatNombre(a.quantite_realisee ?? 0)} ${a.unite_quantite}` : "—"}
              </Table.Td>
              <Table.Td><TauxCell taux={a.taux_realisation} /></Table.Td>
              <Table.Td {...CHIFFRE}>{a.budgetAlloue !== null ? formatNombre(a.budgetAlloue) : "—"}</Table.Td>
              <Table.Td {...CHIFFRE}>{formatNombre(a.budgetRealise)}</Table.Td>
              <Table.Td><TauxCell taux={a.tauxFinancier} /></Table.Td>
            </Table.Tr>
          ))}
        </Table.Tbody>
        <Table.Tfoot bg="gray.1">
          <Table.Tr>
            <Table.Th>Total ({lignes.length} activité{lignes.length > 1 ? "s" : ""})</Table.Th>
            <Table.Th {...CHIFFRE} c="dimmed" fw={400}>—</Table.Th>
            <Table.Th {...CHIFFRE} c="dimmed" fw={400}>—</Table.Th>
            <Table.Th><TauxCell taux={moyenne(lignes.map((l) => l.taux_realisation))} /></Table.Th>
            <Table.Th {...CHIFFRE}>{formatNombre(totalAlloue)}</Table.Th>
            <Table.Th {...CHIFFRE}>{formatNombre(totalRealise)}</Table.Th>
            <Table.Th><TauxCell taux={tauxSur(totalRealise, totalAlloue)} /></Table.Th>
          </Table.Tr>
        </Table.Tfoot>
      </Table>
      <Text size="xs" c="dimmed" mt={4}>
        Taux physique total : moyenne des taux des activités (les quantités ont des unités différentes et ne
        s'additionnent pas).
      </Text>
    </Table.ScrollContainer>
  );
}

function TableauIndicateurs({ indicateurs }: { indicateurs: RecapCadreStrategique["projets"][number]["indicateurs"] }) {
  if (indicateurs.length === 0) return <Text size="sm" c="dimmed">{voc("Aucun indicateur.")}</Text>;

  const lignes = indicateurs.map((i) => ({
    ...i,
    taux: tauxSur(Number(i.valeur_realisee), Number(i.valeur_cible)),
  }));

  return (
    <Table.ScrollContainer minWidth={700}>
      <Table verticalSpacing={6} fz="sm" withTableBorder withColumnBorders striped>
        <Table.Thead>
          <Table.Tr>
            <Table.Th {...ENTETE}>{voc("Indicateur")}</Table.Th>
            <Table.Th {...ENTETE} ta="right">Cible</Table.Th>
            <Table.Th {...ENTETE} ta="right">Réalisé</Table.Th>
            <Table.Th {...ENTETE} ta="right">Taux</Table.Th>
          </Table.Tr>
        </Table.Thead>
        <Table.Tbody>
          {lignes.map((i) => (
            <Table.Tr key={i.id}>
              <Table.Td>{i.libelle}</Table.Td>
              <Table.Td {...CHIFFRE}>{formatNombre(i.valeur_cible)} {i.unite}</Table.Td>
              <Table.Td {...CHIFFRE}>{formatNombre(i.valeur_realisee)} {i.unite}</Table.Td>
              <Table.Td><TauxCell taux={i.taux} /></Table.Td>
            </Table.Tr>
          ))}
        </Table.Tbody>
        <Table.Tfoot bg="gray.1">
          <Table.Tr>
            <Table.Th>Total ({lignes.length} {voc(" indicateur")}{lignes.length > 1 ? "s" : ""}) — taux moyen</Table.Th>
            <Table.Th {...CHIFFRE} c="dimmed" fw={400}>—</Table.Th>
            <Table.Th {...CHIFFRE} c="dimmed" fw={400}>—</Table.Th>
            <Table.Th><TauxCell taux={moyenne(lignes.map((l) => l.taux))} /></Table.Th>
          </Table.Tr>
        </Table.Tfoot>
      </Table>
    </Table.ScrollContainer>
  );
}

function CarteProjetRecap({ p }: { p: RecapCadreStrategique["projets"][number] }) {
  return (
    <Card withBorder padding="md" radius="md">
      <Group justify="space-between" align="flex-start" mb="xs" wrap="wrap">
        <div>
          <Group gap={8}>
            <Text size="sm" c="dimmed" fw={500}>{p.code}</Text>
            <Text component={Link} to={`/projets/${p.id}`} fw={700} c="teal.8">{p.nom}</Text>
            <Badge variant="light" size="sm">{p.statut}</Badge>
          </Group>
          <Text size="xs" c="dimmed" mt={2}>
            {p.chef_de_projet_nom || voc("Chef de projet non renseigné")} · {p.bailleur_nom || "Bailleur non renseigné"} ·{" "}
            {p.date_debut} → {p.date_fin}
          </Text>
        </div>
        <Group gap="lg">
          <div>
            <Text size="xs" c="dimmed" ta="right">Taux physique</Text>
            <TauxCell taux={p.taux_execution_physique} />
          </div>
          <div>
            <Text size="xs" c="dimmed" ta="right">Taux financier</Text>
            <TauxCell taux={p.taux_execution_financiere} />
          </div>
          <div>
            <Text size="xs" c="dimmed" ta="right">Budget total</Text>
            <Text fw={700} ta="right">{Number(p.budget_total).toLocaleString("fr-FR")} FCFA</Text>
          </div>
        </Group>
      </Group>

      <Stack gap="md" mt="sm">
        <Box>
          <Text size="xs" fw={700} c="dimmed" tt="uppercase" mb={4}>Activités ({p.nombre_activites})</Text>
          <TableauActivites activites={p.activites} />
        </Box>
        <Box>
          <Text size="xs" fw={700} c="dimmed" tt="uppercase" mb={4}>{voc("Indicateurs (")}{p.nombre_indicateurs})</Text>
          <TableauIndicateurs indicateurs={p.indicateurs} />
        </Box>
      </Stack>
    </Card>
  );
}

function RecapProjetsBudgets({ cadreId }: { cadreId: number }) {
  const { data: recap, isLoading } = useRecapCadreStrategique(cadreId);

  if (isLoading || !recap) return <Text c="dimmed">Chargement…</Text>;

  return (
    <Stack gap="md">
      <SimpleGrid cols={{ base: 1, xs: 3, md: 5 }} spacing="md">
        <StatCard
          label="Budget total contribuant"
          value={`${recap.budget_total.toLocaleString("fr-FR")} FCFA`}
          icon={<Wallet size={20} />}
          color="indigo"
        />
        <StatCard label="Activités" value={recap.nombre_activites_total} icon={<ListTree size={20} />} color="teal" />
        <StatCard
          label={voc("Indicateurs")}
          value={recap.nombre_indicateurs_total}
          icon={<Settings2 size={20} />}
          color="orange"
        />
        <StatCard
          label="Taux physique moyen"
          value={recap.taux_execution_physique_moyen !== null ? `${recap.taux_execution_physique_moyen}%` : "—"}
          icon={<Gauge size={20} />}
          color="grape"
        />
        <StatCard
          label="Taux financier moyen"
          value={recap.taux_execution_financiere_moyen !== null ? `${recap.taux_execution_financiere_moyen}%` : "—"}
          icon={<Gauge size={20} />}
          color="cyan"
        />
      </SimpleGrid>

      <div>
        <Title order={4} mb="xs">{voc("Projets contribuant à ce cadre stratégique")}</Title>
        {recap.projets.length === 0 ? (
          <Card withBorder padding="md" radius="md">
            <EmptyState icon={<Wallet size={32} strokeWidth={1.5} />} message={voc("Aucun projet rattaché à ce cadre stratégique.")} />
          </Card>
        ) : (
          <Stack gap="md">
            {recap.projets.map((p) => (
              <CarteProjetRecap key={p.id} p={p} />
            ))}
          </Stack>
        )}
      </div>
    </Stack>
  );
}

// ================== Page ==================

export function CadreStrategiqueDetailPage() {
  const { id } = useParams();
  const cadreId = Number(id);
  const { data: cadre } = useCadreStrategique(cadreId);
  const { data: niveaux, isLoading: chargementNiveaux } = useTypesNiveaux(cadreId);
  const { data: elements, isLoading: chargementElements } = useElementsStrategiques({ cadre_strategique: cadreId });
  const [modalImportOuvert, setModalImportOuvert] = useState(false);
  const [editionActive, setEditionActive] = useState(false);

  return (
    <Stack gap="md">
      <Group justify="space-between">
        <Group gap="xs">
          <ActionIcon component={Link} to="/strategie" variant="subtle" color="gray">
            <ArrowLeft size={18} />
          </ActionIcon>
          <Title order={2}>{cadre?.nom ?? voc("Cadre stratégique")}</Title>
        </Group>
        <Group gap="xs">
          <BoutonModeEdition actif={editionActive} onToggle={() => setEditionActive((v) => !v)} />
          <Button
            variant="light"
            leftSection={<Download size={16} />}
            onClick={() => telechargerExportStructuration(cadreId, cadre?.nom ?? String(cadreId))}
          >
            Exporter en Excel
          </Button>
          <Button variant="light" leftSection={<FileSpreadsheet size={16} />} onClick={() => setModalImportOuvert(true)}>
            Importer depuis Excel
          </Button>
        </Group>
      </Group>

      {chargementNiveaux || chargementElements ? (
        <Text c="dimmed">Chargement…</Text>
      ) : (
        <Tabs defaultValue="arborescence" keepMounted={false}>
          <Tabs.List>
            <Tabs.Tab value="configuration" leftSection={<Settings2 size={15} />}>
              Configuration des niveaux
            </Tabs.Tab>
            <Tabs.Tab value="arborescence" leftSection={<ListTree size={15} />}>
              Arborescence &amp; saisie
            </Tabs.Tab>
            <Tabs.Tab value="axes" leftSection={<Layers size={15} />}>
              Axes &amp; budgets
            </Tabs.Tab>
            <Tabs.Tab value="recap" leftSection={<Wallet size={15} />}>
              {voc("Projets & budgets")}</Tabs.Tab>
          </Tabs.List>

          <Tabs.Panel value="configuration" pt="md">
            <ConfigurationNiveaux cadreStrategiqueId={cadreId} niveaux={niveaux ?? []} editionActive={editionActive} />
          </Tabs.Panel>

          <Tabs.Panel value="arborescence" pt="md">
            <Arborescence niveaux={niveaux ?? []} elements={elements ?? []} editionActive={editionActive} />
          </Tabs.Panel>

          <Tabs.Panel value="axes" pt="md">
            <AxesBudgetsTab cadreId={cadreId} niveaux={niveaux ?? []} />
          </Tabs.Panel>

          <Tabs.Panel value="recap" pt="md">
            <RecapProjetsBudgets cadreId={cadreId} />
          </Tabs.Panel>
        </Tabs>
      )}

      <ImportStructurationModal
        opened={modalImportOuvert}
        onClose={() => setModalImportOuvert(false)}
        cadreStrategiqueId={cadreId}
      />
    </Stack>
  );
}
