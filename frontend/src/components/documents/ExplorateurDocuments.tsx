import { useState } from "react";
import {
  ActionIcon,
  Anchor,
  Badge,
  Breadcrumbs,
  Button,
  Card,
  Checkbox,
  Group,
  Menu,
  Modal,
  SegmentedControl,
  Select,
  SimpleGrid,
  Stack,
  Table,
  Text,
  TextInput,
} from "@mantine/core";
import { notifications } from "@mantine/notifications";
import {
  ArrowLeft,
  Download,
  Ellipsis,
  File,
  FileImage,
  FileSpreadsheet,
  FileText,
  FileVideo,
  Folder,
  FolderInput,
  FolderPlus,
  History,
  LayoutGrid,
  List,
  Pencil,
  Trash2,
  Upload,
  X,
  Link2,
} from "lucide-react";
import { Link } from "react-router-dom";
import {
  useDeleteDocument,
  useDeleteDossier,
  useDocuments,
  useDossiers,
  useModifierDocument,
  useModifierDossier,
  useSupprimerSelection,
  telechargerSelection,
} from "../../api/documents";
import type { Dossier, GedDocument } from "../../types";
import { usePreference } from "../../utils/affichage";
import { messageErreurApi } from "../../utils/erreurs";
import { locale } from "../../utils/i18n";
import { voc } from "../../utils/vocabulaire";
import { confirmerSuppression } from "../common/confirmerSuppression";
import { PartageDocumentModal } from "./PartageDocumentModal";
import { NouveauDocumentModal, NouveauDossierModal, VersionsModal } from "./DocumentsTab";

const extension = (doc: GedDocument) => (doc.derniere_version?.fichier.split("?")[0].split(".").pop() ?? "").toLowerCase();
const IMAGES = ["jpg", "jpeg", "png", "gif", "webp", "svg"];
const VIDEOS = ["mp4", "mov", "webm", "avi", "mkv", "m4v"];
const TABLEURS = ["xls", "xlsx", "csv", "ods"];
const TEXTES = ["pdf", "doc", "docx", "odt", "txt", "ppt", "pptx"];

function IconeDocument({ doc, taille }: { doc: GedDocument; taille: number }) {
  const ext = extension(doc);
  if (IMAGES.includes(ext)) return <FileImage size={taille} color="var(--mantine-color-grape-6)" />;
  if (VIDEOS.includes(ext)) return <FileVideo size={taille} color="var(--mantine-color-red-6)" />;
  if (TABLEURS.includes(ext)) return <FileSpreadsheet size={taille} color="var(--mantine-color-green-7)" />;
  if (TEXTES.includes(ext)) return <FileText size={taille} color="var(--mantine-color-blue-6)" />;
  return <File size={taille} color="var(--mantine-color-gray-6)" />;
}

const ouvrir = (doc: GedDocument) => doc.derniere_version && window.open(doc.derniere_version.fichier, "_blank", "noopener");

/** Renommer un dossier ou un document. */
function RenommerModal({ cible, onClose }: { cible: { type: "dossier" | "document"; id: number; nom: string } | null; onClose: () => void }) {
  const modifierDossier = useModifierDossier();
  const modifierDocument = useModifierDocument();
  const [nom, setNom] = useState(cible?.nom ?? "");
  const valider = async () => {
    if (!cible || !nom.trim()) return;
    try {
      if (cible.type === "dossier") await modifierDossier.mutateAsync({ id: cible.id, nom: nom.trim() });
      else await modifierDocument.mutateAsync({ id: cible.id, nom: nom.trim() });
      onClose();
    } catch (error) {
      notifications.show({ color: "red", message: messageErreurApi(error, voc("Erreur lors de l'enregistrement")) });
    }
  };
  return (
    <Modal opened={!!cible} onClose={onClose} title={voc("Renommer")} size="sm">
      <Stack>
        <TextInput label={voc("Nouveau nom")} value={nom} onChange={(e) => setNom(e.currentTarget.value)} data-autofocus
          onKeyDown={(e) => e.key === "Enter" && valider()} />
        <Group justify="flex-end">
          <Button onClick={valider} loading={modifierDossier.isPending || modifierDocument.isPending}>{voc("Enregistrer")}</Button>
        </Group>
      </Stack>
    </Modal>
  );
}

/** Déplacer un document vers un autre dossier (ou à la racine). */
function DeplacerModal({ doc, dossiers, onClose }: { doc: GedDocument | null; dossiers: Dossier[]; onClose: () => void }) {
  const modifier = useModifierDocument();
  const [cible, setCible] = useState<string>(doc?.dossier ? String(doc.dossier) : "racine");
  const chemin = (d: Dossier): string => {
    const parent = dossiers.find((x) => x.id === d.parent);
    return parent ? `${chemin(parent)} › ${d.nom}` : d.nom;
  };
  const valider = async () => {
    if (!doc) return;
    try {
      await modifier.mutateAsync({ id: doc.id, dossier: cible === "racine" ? null : Number(cible) });
      notifications.show({ color: "teal", message: voc("Document déplacé") });
      onClose();
    } catch (error) {
      notifications.show({ color: "red", message: messageErreurApi(error, voc("Erreur lors de l'enregistrement")) });
    }
  };
  return (
    <Modal opened={!!doc} onClose={onClose} title={voc("Déplacer le document")} size="md">
      <Stack>
        <Text size="sm">{doc?.nom}</Text>
        <Select label={voc("Vers le dossier")} searchable allowDeselect={false} value={cible} onChange={(v) => v && setCible(v)}
          data={[{ value: "racine", label: voc("Documents (racine)") }, ...dossiers.map((d) => ({ value: String(d.id), label: chemin(d) })).sort((a, b) => a.label.localeCompare(b.label))]} />
        <Group justify="flex-end">
          <Button onClick={valider} loading={modifier.isPending}>{voc("Déplacer")}</Button>
        </Group>
      </Stack>
    </Modal>
  );
}

/**
 * Explorateur de documents, comme sur un ordinateur : dossiers et sous-dossiers en icônes, un clic
 * pour entrer, fil d'Ariane pour remonter ; documents du dossier courant en grille (aperçu des photos)
 * ou en liste. Projet (projetId) ou bibliothèque libre (sans projetId).
 */
export function ExplorateurDocuments({ projetId }: { projetId?: number }) {
  const { data: dossiers = [] } = useDossiers(projetId);
  const [courant, setCourantBrut] = useState<number | null>(null);
  // Sélection multiple (cases à cocher) : clés « d<id> » (dossiers) et « f<id> » (documents).
  const [selection, setSelection] = useState<Set<string>>(new Set());
  const setCourant = (id: number | null) => {
    setCourantBrut(id);
    setSelection(new Set());
  };
  const [affichage, setAffichage] = usePreference("documents-affichage", ["grille", "liste"] as const);
  const { data: documents = [], isLoading } = useDocuments(
    courant !== null ? { dossier: courant } : projetId ? { projet: projetId, sans_dossier: true } : { libres: true, sans_dossier: true },
  );
  const supprimerDocument = useDeleteDocument();
  const supprimerDossier = useDeleteDossier();
  const supprimerSelection = useSupprimerSelection();
  const [telechargement, setTelechargement] = useState(false);
  const [nouveauDossier, setNouveauDossier] = useState(false);
  const [nouveauDocument, setNouveauDocument] = useState(false);
  const [versions, setVersions] = useState<number | null>(null);
  const [renommer, setRenommer] = useState<{ type: "dossier" | "document"; id: number; nom: string } | null>(null);
  const [deplacer, setDeplacer] = useState<GedDocument | null>(null);
  const [partager, setPartager] = useState<GedDocument | null>(null);

  const sousDossiers = dossiers.filter((d) => d.parent === courant);
  const chemin: Dossier[] = [];
  for (let d = dossiers.find((x) => x.id === courant); d; d = dossiers.find((x) => x.id === d!.parent)) chemin.unshift(d);
  const dossierCourant = chemin[chemin.length - 1];

  const supprimerLeDossier = (d: Dossier) => confirmerSuppression({
    message: voc`Mettre le dossier "${d.nom}" et son contenu à la corbeille ? Vous pourrez le restaurer depuis la Corbeille.`,
    onConfirm: async () => {
      try {
        await supprimerDossier.mutateAsync(d.id);
        notifications.show({ message: voc("Dossier mis à la corbeille"), color: "green" });
      } catch (error) {
        notifications.show({ message: messageErreurApi(error, voc("Erreur lors de la suppression du dossier")), color: "red" });
      }
    },
  });
  const supprimerLeDocument = (doc: GedDocument) => confirmerSuppression({
    message: voc`Mettre le document "${doc.nom}" à la corbeille ? Vous pourrez le restaurer depuis la Corbeille.`,
    onConfirm: async () => {
      try {
        await supprimerDocument.mutateAsync(doc.id);
        notifications.show({ message: voc("Document mis à la corbeille"), color: "green" });
      } catch (error) {
        notifications.show({ message: messageErreurApi(error, voc("Erreur lors de la suppression du document")), color: "red" });
      }
    },
  });

  const menuDossier = (d: Dossier) => (
    <Menu position="bottom-end" withinPortal>
      <Menu.Target>
        <ActionIcon size="sm" variant="subtle" color="gray" aria-label={voc("Actions")} onClick={(e) => e.stopPropagation()}><Ellipsis size={16} /></ActionIcon>
      </Menu.Target>
      <Menu.Dropdown onClick={(e) => e.stopPropagation()}>
        <Menu.Item leftSection={<Pencil size={14} />} onClick={() => setRenommer({ type: "dossier", id: d.id, nom: d.nom })}>{voc("Renommer")}</Menu.Item>
        <Menu.Item leftSection={<Trash2 size={14} />} color="red" onClick={() => supprimerLeDossier(d)}>{voc("Supprimer")}</Menu.Item>
      </Menu.Dropdown>
    </Menu>
  );
  const menuDocument = (doc: GedDocument) => (
    <Menu position="bottom-end" withinPortal>
      <Menu.Target>
        <ActionIcon size="sm" variant="subtle" color="gray" aria-label={voc("Actions")} onClick={(e) => e.stopPropagation()}><Ellipsis size={16} /></ActionIcon>
      </Menu.Target>
      <Menu.Dropdown onClick={(e) => e.stopPropagation()}>
        <Menu.Item leftSection={<Link2 size={14} />} onClick={() => setPartager(doc)}>{voc("Partager par lien")}</Menu.Item>
        <Menu.Item leftSection={<History size={14} />} onClick={() => setVersions(doc.id)}>{voc("Versions")}</Menu.Item>
        <Menu.Item leftSection={<Pencil size={14} />} onClick={() => setRenommer({ type: "document", id: doc.id, nom: doc.nom })}>{voc("Renommer")}</Menu.Item>
        <Menu.Item leftSection={<FolderInput size={14} />} onClick={() => setDeplacer(doc)}>{voc("Déplacer")}</Menu.Item>
        <Menu.Divider />
        <Menu.Item leftSection={<Trash2 size={14} />} color="red" onClick={() => supprimerLeDocument(doc)}>{voc("Supprimer")}</Menu.Item>
      </Menu.Dropdown>
    </Menu>
  );
  const cles = [...sousDossiers.map((d) => `d${d.id}`), ...documents.map((doc) => `f${doc.id}`)];
  const toutCoche = cles.length > 0 && cles.every((c) => selection.has(c));
  const basculer = (cle: string) => setSelection((avant) => {
    const apres = new Set(avant);
    if (apres.has(cle)) apres.delete(cle);
    else apres.add(cle);
    return apres;
  });
  const choisis = () => ({
    dossiers: [...selection].filter((c) => c.startsWith("d")).map((c) => Number(c.slice(1))),
    documents: [...selection].filter((c) => c.startsWith("f")).map((c) => Number(c.slice(1))),
  });
  const caseACocher = (cle: string, nom: string) => (
    <Checkbox size="sm" checked={selection.has(cle)} aria-label={voc`Sélectionner ${nom}`}
      onClick={(e) => e.stopPropagation()} onChange={() => basculer(cle)} />
  );
  const supprimerLaSelection = () => confirmerSuppression({
    message: voc`Mettre les ${selection.size} élément(s) sélectionné(s) à la corbeille (dossiers avec leur contenu) ? Vous pourrez les restaurer depuis la Corbeille.`,
    onConfirm: async () => {
      try {
        const { nombre } = await supprimerSelection.mutateAsync(choisis());
        setSelection(new Set());
        notifications.show({ color: "green", message: voc`${nombre} élément(s) mis à la corbeille` });
      } catch (error) {
        notifications.show({ color: "red", message: messageErreurApi(error, voc("Erreur lors de la suppression")) });
      }
    },
  });
  const telechargerLaSelection = async () => {
    setTelechargement(true);
    try {
      await telechargerSelection(choisis());
    } catch (error) {
      notifications.show({ color: "red", message: messageErreurApi(error, voc("Le téléchargement n'a pas abouti.")) });
    } finally {
      setTelechargement(false);
    }
  };
  const nbElements = (d: Dossier) => d.nombre_documents + d.nombre_sous_dossiers;
  const vide = !isLoading && sousDossiers.length === 0 && documents.length === 0;

  return (
    <Stack gap="md">
      <Group justify="space-between" gap="sm">
        <Group gap="xs" wrap="nowrap" style={{ minWidth: 0 }}>
          {courant !== null && (
            <ActionIcon variant="default" aria-label={voc("Dossier parent")} onClick={() => setCourant(dossierCourant?.parent ?? null)}>
              <ArrowLeft size={16} />
            </ActionIcon>
          )}
          <Breadcrumbs separator="›" separatorMargin={6}>
            <Anchor component="button" type="button" size="sm" fw={courant === null ? 700 : 500} c={courant === null ? "dark" : undefined} onClick={() => setCourant(null)}>
              {voc("Documents")}
            </Anchor>
            {chemin.map((d, i) => (
              <Anchor key={d.id} component="button" type="button" size="sm" fw={i === chemin.length - 1 ? 700 : 500}
                c={i === chemin.length - 1 ? "dark" : undefined} onClick={() => setCourant(d.id)}>
                {d.nom}
              </Anchor>
            ))}
          </Breadcrumbs>
        </Group>
        <Group gap="xs">
          <SegmentedControl size="xs" value={affichage} onChange={(v) => setAffichage(v as typeof affichage)}
            data={[
              { value: "grille", label: <LayoutGrid size={14} aria-label={voc("Grille")} /> },
              { value: "liste", label: <List size={14} aria-label={voc("Liste")} /> },
            ]} />
          <Button variant="light" leftSection={<FolderPlus size={16} />} onClick={() => setNouveauDossier(true)}>{voc("Nouveau dossier")}</Button>
          <Button leftSection={<Upload size={16} />} onClick={() => setNouveauDocument(true)}>{voc("Ajouter un document")}</Button>
        </Group>
      </Group>

      {cles.length > 0 && (
        <Group justify="space-between" gap="xs" px="xs" py={6} bg={selection.size ? "teal.0" : undefined} style={{ borderRadius: 8 }}>
          <Checkbox size="sm" label={selection.size ? voc`${selection.size} sélectionné(s)` : voc("Tout sélectionner")}
            checked={toutCoche} indeterminate={selection.size > 0 && !toutCoche}
            onChange={() => setSelection(toutCoche ? new Set() : new Set(cles))} />
          <Group gap="xs">
            {selection.size > 0 && (
              <>
                <Button size="xs" variant="default" leftSection={<Download size={14} />} loading={telechargement} onClick={telechargerLaSelection}>
                  {voc("Télécharger")}
                </Button>
                <Button size="xs" color="red" variant="light" leftSection={<Trash2 size={14} />} onClick={supprimerLaSelection}>
                  {voc("Supprimer")}
                </Button>
                <ActionIcon variant="subtle" color="gray" aria-label={voc("Annuler la sélection")} onClick={() => setSelection(new Set())}>
                  <X size={16} />
                </ActionIcon>
              </>
            )}
            <Button size="xs" variant="subtle" color="gray" component={Link} to="/corbeille" leftSection={<Trash2 size={14} />}>
              {voc("Corbeille")}
            </Button>
          </Group>
        </Group>
      )}

      <Card withBorder padding="md" radius="md" mih={220}>
        {isLoading ? (
          <Text c="dimmed">{voc("Chargement…")}</Text>
        ) : vide ? (
          <Stack align="center" gap={6} py="xl">
            <Folder size={44} strokeWidth={1.3} color="var(--mantine-color-gray-5)" />
            <Text c="dimmed" size="sm">{courant === null ? voc("Aucun dossier ni document pour l'instant.") : voc("Ce dossier est vide.")}</Text>
            <Text c="dimmed" size="xs">{voc("Créez un dossier ou ajoutez un document avec les boutons ci-dessus.")}</Text>
          </Stack>
        ) : affichage === "grille" ? (
          <SimpleGrid cols={{ base: 2, xs: 3, sm: 4, md: 5, lg: 6 }} spacing="sm">
            {sousDossiers.map((d) => (
              <Card key={`d${d.id}`} withBorder padding="sm" radius="md" style={{ cursor: "pointer" }} onClick={() => setCourant(d.id)}
                bd={selection.has(`d${d.id}`) ? "2px solid var(--mantine-color-teal-6)" : undefined}>
                <Group justify="space-between" mt={-6} mx={-6} h={20}>{caseACocher(`d${d.id}`, d.nom)}{menuDossier(d)}</Group>
                <Stack align="center" gap={4}>
                  <Folder size={52} strokeWidth={1.4} fill="white" color="var(--mantine-color-teal-7)" />
                  <Text size="sm" fw={600} ta="center" lineClamp={2} lh={1.25}>{d.nom}</Text>
                  <Text size="xs" c="dimmed">{voc`${nbElements(d)} élément(s)`}</Text>
                </Stack>
              </Card>
            ))}
            {documents.map((doc) => {
              const image = IMAGES.includes(extension(doc)) && doc.derniere_version;
              return (
                <Card key={`f${doc.id}`} withBorder padding="sm" radius="md" style={{ cursor: "pointer" }} onClick={() => ouvrir(doc)}
                  bd={selection.has(`f${doc.id}`) ? "2px solid var(--mantine-color-teal-6)" : undefined}>
                  <Group justify="space-between" mt={-6} mx={-6} h={20}>{caseACocher(`f${doc.id}`, doc.nom)}{menuDocument(doc)}</Group>
                  <Stack align="center" gap={4}>
                    {image ? (
                      <img src={doc.derniere_version!.fichier} alt={doc.nom} loading="lazy"
                        style={{ width: "100%", height: 64, objectFit: "cover", borderRadius: 6 }} />
                    ) : (
                      <IconeDocument doc={doc} taille={52} />
                    )}
                    <Text size="sm" fw={500} ta="center" lineClamp={2} lh={1.25}>{doc.nom}</Text>
                    <Text size="xs" c="dimmed">{extension(doc).toUpperCase() || "—"}{doc.nombre_versions > 1 ? ` · v${doc.derniere_version?.version}` : ""}</Text>
                  </Stack>
                </Card>
              );
            })}
          </SimpleGrid>
        ) : (
          <Table.ScrollContainer minWidth={640}>
            <Table verticalSpacing="xs" highlightOnHover>
              <Table.Thead>
                <Table.Tr>
                  <Table.Th w={36} />
                  <Table.Th>{voc("Nom")}</Table.Th>
                  <Table.Th>{voc("Type")}</Table.Th>
                  <Table.Th>{voc("Version")}</Table.Th>
                  <Table.Th>{voc("Ajouté par")}</Table.Th>
                  <Table.Th>{voc("Date")}</Table.Th>
                  <Table.Th w={40} />
                </Table.Tr>
              </Table.Thead>
              <Table.Tbody>
                {sousDossiers.map((d) => (
                  <Table.Tr key={`d${d.id}`} style={{ cursor: "pointer" }} onClick={() => setCourant(d.id)} bg={selection.has(`d${d.id}`) ? "teal.0" : undefined}>
                    <Table.Td>{caseACocher(`d${d.id}`, d.nom)}</Table.Td>
                    <Table.Td>
                      <Group gap="xs" wrap="nowrap">
                        <Folder size={20} fill="white" color="var(--mantine-color-teal-7)" />
                        <Text size="sm" fw={600}>{d.nom}</Text>
                      </Group>
                    </Table.Td>
                    <Table.Td><Text size="sm" c="dimmed">{voc("Dossier")}</Text></Table.Td>
                    <Table.Td><Text size="sm" c="dimmed">{voc`${nbElements(d)} élément(s)`}</Text></Table.Td>
                    <Table.Td><Text size="sm">{d.cree_par_nom}</Text></Table.Td>
                    <Table.Td />
                    <Table.Td>{menuDossier(d)}</Table.Td>
                  </Table.Tr>
                ))}
                {documents.map((doc) => (
                  <Table.Tr key={`f${doc.id}`} style={{ cursor: "pointer" }} onClick={() => ouvrir(doc)} bg={selection.has(`f${doc.id}`) ? "teal.0" : undefined}>
                    <Table.Td>{caseACocher(`f${doc.id}`, doc.nom)}</Table.Td>
                    <Table.Td>
                      <Group gap="xs" wrap="nowrap">
                        <IconeDocument doc={doc} taille={20} />
                        <Text size="sm" fw={500}>{doc.nom}</Text>
                      </Group>
                    </Table.Td>
                    <Table.Td><Text size="sm">{doc.type_document || extension(doc).toUpperCase() || "—"}</Text></Table.Td>
                    <Table.Td><Badge variant="light" size="sm">v{doc.derniere_version?.version ?? 1}</Badge></Table.Td>
                    <Table.Td><Text size="sm">{doc.cree_par_nom}</Text></Table.Td>
                    <Table.Td><Text size="sm">{new Date(doc.created_at).toLocaleDateString(locale())}</Text></Table.Td>
                    <Table.Td>{menuDocument(doc)}</Table.Td>
                  </Table.Tr>
                ))}
              </Table.Tbody>
            </Table>
          </Table.ScrollContainer>
        )}
      </Card>

      <NouveauDossierModal projetId={projetId} parentId={courant} opened={nouveauDossier} onClose={() => setNouveauDossier(false)} />
      <NouveauDocumentModal projetId={projetId} dossierId={courant} opened={nouveauDocument} onClose={() => setNouveauDocument(false)} />
      <VersionsModal documentId={versions} opened={versions !== null} onClose={() => setVersions(null)} />
      {renommer && <RenommerModal key={`${renommer.type}${renommer.id}`} cible={renommer} onClose={() => setRenommer(null)} />}
      {deplacer && <DeplacerModal key={deplacer.id} doc={deplacer} dossiers={dossiers} onClose={() => setDeplacer(null)} />}
      {partager && <PartageDocumentModal key={partager.id} doc={partager} onClose={() => setPartager(null)} />}
    </Stack>
  );
}
