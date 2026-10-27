import { useState } from "react";
import { FileText, FolderPlus, History, Trash2, Upload } from "lucide-react";
import {
  ActionIcon,
  Badge,
  Button,
  Card,
  FileInput,
  Group,
  Modal,
  Select,
  Stack,
  Table,
  Text,
  TextInput,
  Timeline,
  Tooltip,
} from "@mantine/core";
import { notifications } from "@mantine/notifications";
import {
  useCreateDocument,
  useCreateDossier,
  useDeleteDocument,
  useDeleteDossier,
  useDocumentVersions,
  useDocuments,
  useDossiers,
  useNouvelleVersion,
} from "../../api/documents";
import { confirmerSuppression } from "../common/confirmerSuppression";
import { messageErreurApi } from "../../utils/erreurs";
import { EmptyState } from "../common/EmptyState";
import type { GedDocument } from "../../types";
import { voc } from "../../utils/vocabulaire";

function NouveauDossierModal({
  projetId,
  opened,
  onClose,
  onCree,
}: {
  /** Absent = dossier libre, sans rattachement à un projet (bibliothèque "Documents"). */
  projetId?: number;
  opened: boolean;
  onClose: () => void;
  /** Permet au parent de sélectionner immédiatement le dossier créé, pour qu'il soit visible sans avoir à rouvrir la liste déroulante. */
  onCree?: (dossierId: number) => void;
}) {
  const createDossier = useCreateDossier();
  const [nom, setNom] = useState("");

  async function handleCreate() {
    if (!nom.trim()) return;
    try {
      const dossier = await createDossier.mutateAsync({ nom: nom.trim(), projet: projetId ?? null });
      notifications.show({ message: "Dossier créé", color: "green" });
      setNom("");
      onCree?.(dossier.id);
      onClose();
    } catch (error) {
      notifications.show({ message: messageErreurApi(error, "Erreur lors de la création du dossier"), color: "red" });
    }
  }

  return (
    <Modal opened={opened} onClose={onClose} title="Nouveau dossier">
      <Stack gap="sm">
        <TextInput label="Nom du dossier" value={nom} onChange={(e) => setNom(e.currentTarget.value)} />
        <Group justify="flex-end">
          <Button onClick={handleCreate} loading={createDossier.isPending}>Créer</Button>
        </Group>
      </Stack>
    </Modal>
  );
}

function NouveauDocumentModal({
  projetId,
  activiteId,
  sousActiviteId,
  dossierId,
  opened,
  onClose,
}: {
  projetId?: number;
  activiteId?: number;
  sousActiviteId?: number;
  dossierId: number | null;
  opened: boolean;
  onClose: () => void;
}) {
  const createDocument = useCreateDocument();
  const [nom, setNom] = useState("");
  const [typeDocument, setTypeDocument] = useState("");
  const [fichier, setFichier] = useState<File | null>(null);

  async function handleCreate() {
    if (!nom.trim() || !fichier) {
      notifications.show({ message: "Nom et fichier requis.", color: "orange" });
      return;
    }
    const formData = new FormData();
    formData.append("nom", nom.trim());
    formData.append("type_document", typeDocument);
    if (projetId) formData.append("projet", String(projetId));
    if (activiteId) formData.append("activite", String(activiteId));
    if (sousActiviteId) formData.append("sous_activite", String(sousActiviteId));
    if (dossierId) formData.append("dossier", String(dossierId));
    formData.append("fichier", fichier);

    try {
      await createDocument.mutateAsync(formData);
      notifications.show({ message: voc("Document ajouté"), color: "green" });
      setNom("");
      setTypeDocument("");
      setFichier(null);
      onClose();
    } catch {
      notifications.show({ message: voc("Erreur lors de l'ajout du document"), color: "red" });
    }
  }

  return (
    <Modal opened={opened} onClose={onClose} title={voc("Nouveau document")}>
      <Stack gap="sm">
        <TextInput label={voc("Nom du document")} value={nom} onChange={(e) => setNom(e.currentTarget.value)} />
        <TextInput label="Type" placeholder="Ex : Note, Contrat, Rapport bailleur…" value={typeDocument} onChange={(e) => setTypeDocument(e.currentTarget.value)} />
        <FileInput label="Fichier" value={fichier} onChange={setFichier} required />
        <Group justify="flex-end">
          <Button onClick={handleCreate} loading={createDocument.isPending}>Ajouter</Button>
        </Group>
      </Stack>
    </Modal>
  );
}

function VersionsModal({ documentId, opened, onClose }: { documentId: number | null; opened: boolean; onClose: () => void }) {
  const { data: versions, isLoading } = useDocumentVersions(documentId ?? undefined);
  const nouvelleVersion = useNouvelleVersion();
  const [fichier, setFichier] = useState<File | null>(null);
  const [commentaire, setCommentaire] = useState("");

  async function handleUpload() {
    if (!documentId || !fichier) return;
    const formData = new FormData();
    formData.append("fichier", fichier);
    formData.append("commentaire", commentaire);
    try {
      await nouvelleVersion.mutateAsync({ documentId, formData });
      notifications.show({ message: "Nouvelle version ajoutée", color: "green" });
      setFichier(null);
      setCommentaire("");
    } catch {
      notifications.show({ message: "Erreur lors de l'ajout de la version", color: "red" });
    }
  }

  return (
    <Modal opened={opened} onClose={onClose} title="Historique des versions" size="lg">
      <Stack gap="md">
        <Card withBorder padding="sm">
          <Text size="sm" fw={600} mb="xs">Ajouter une nouvelle version</Text>
          <Group align="flex-end">
            <FileInput placeholder="Choisir un fichier" value={fichier} onChange={setFichier} style={{ flex: 1 }} />
            <TextInput placeholder="Commentaire (optionnel)" value={commentaire} onChange={(e) => setCommentaire(e.currentTarget.value)} style={{ flex: 1 }} />
            <Button leftSection={<Upload size={14} />} onClick={handleUpload} loading={nouvelleVersion.isPending}>
              Envoyer
            </Button>
          </Group>
        </Card>

        {isLoading ? (
          <Text c="dimmed">Chargement…</Text>
        ) : (
          <Timeline active={versions?.length ?? 0}>
            {versions?.map((v) => (
              <Timeline.Item key={v.id} title={`Version ${v.version}`}>
                <Text size="xs" c="dimmed">{new Date(v.created_at).toLocaleString("fr-FR")} · {v.uploaded_by_nom}</Text>
                {v.commentaire && <Text size="sm">{v.commentaire}</Text>}
                <Text component="a" href={v.fichier} target="_blank" size="sm" c="teal.8">
                  Télécharger cette version
                </Text>
              </Timeline.Item>
            ))}
          </Timeline>
        )}
      </Stack>
    </Modal>
  );
}

/**
 * Documents liés à un projet (avec navigation par dossiers) ou directement à
 * une activité ou une sous-activité (liste simple, sans dossiers —
 * Document.activite/sous_activite sont des rattachements indépendants de
 * Document.projet/dossier). Passer un seul des trois identifiants.
 */
export function DocumentsTab({
  projetId,
  activiteId,
  sousActiviteId,
}: {
  projetId?: number;
  activiteId?: number;
  sousActiviteId?: number;
}) {
  const { data: dossiers } = useDossiers(projetId);
  const [dossierActif, setDossierActif] = useState<string | null>(null);
  const { data: documents, isLoading } = useDocuments({
    projet: projetId,
    activite: activiteId,
    sous_activite: sousActiviteId,
    dossier: dossierActif ? Number(dossierActif) : undefined,
  });
  const deleteDocument = useDeleteDocument();
  const deleteDossier = useDeleteDossier();

  const [modalDossier, setModalDossier] = useState(false);
  const [modalDocument, setModalDocument] = useState(false);
  const [documentVersionsId, setDocumentVersionsId] = useState<number | null>(null);

  // Dans l'onglet "Documents" d'un projet, le filtre `projet` élargi
  // remonte aussi les documents rattachés à une activité/sous-activité — la
  // colonne "Rattaché à" permet de distinguer d'où vient chaque ligne dans
  // cette vue unifiée (inutile quand on est déjà dans le contexte d'une
  // seule activité/sous-activité précise).
  const afficherRattachement = projetId !== undefined;
  // Les dossiers n'existent que pour un projet précis ou en libre (aucun
  // rattachement) — pas de sens pour une vue déjà scopée à une
  // activité/sous-activité précise.
  const afficherDossiers = projetId !== undefined || (activiteId === undefined && sousActiviteId === undefined);

  function rattachementDe(doc: GedDocument) {
    if (doc.activite_nom) return `Activité — ${doc.activite_nom}`;
    if (doc.sous_activite_nom) return `Sous-activité — ${doc.sous_activite_nom}`;
    return voc("Projet");
  }

  function handleSupprimer(doc: { id: number; nom: string }) {
    confirmerSuppression({
      message: voc`Supprimer le document "${doc.nom}" ainsi que toutes ses versions ? Cette action est irréversible.`,
      onConfirm: async () => {
        try {
          await deleteDocument.mutateAsync(doc.id);
          notifications.show({ message: voc("Document supprimé"), color: "green" });
        } catch (error) {
          notifications.show({
            message: messageErreurApi(error, voc("Erreur lors de la suppression du document")),
            color: "red",
          });
        }
      },
    });
  }

  function handleSupprimerDossier() {
    if (!dossierActif) return;
    const dossier = dossiers?.find((d) => String(d.id) === dossierActif);
    confirmerSuppression({
      message: voc`Supprimer le dossier "${dossier?.nom ?? ""}" ainsi que tous les documents qu'il contient ? Cette action est irréversible.`,
      onConfirm: async () => {
        try {
          await deleteDossier.mutateAsync(Number(dossierActif));
          setDossierActif(null);
          notifications.show({ message: "Dossier supprimé", color: "green" });
        } catch (error) {
          notifications.show({
            message: messageErreurApi(error, "Erreur lors de la suppression du dossier"),
            color: "red",
          });
        }
      },
    });
  }

  return (
    <Stack gap="md">
      <Group justify="space-between">
        {afficherDossiers ? (
          <Group gap={6}>
            <Select
              placeholder="Tous les dossiers"
              data={dossiers?.map((d) => ({ value: String(d.id), label: d.nom })) ?? []}
              value={dossierActif}
              onChange={setDossierActif}
              clearable
              w={260}
            />
            {dossierActif && (
              <Tooltip label="Supprimer ce dossier">
                <ActionIcon variant="subtle" color="red" loading={deleteDossier.isPending} onClick={handleSupprimerDossier}>
                  <Trash2 size={16} />
                </ActionIcon>
              </Tooltip>
            )}
          </Group>
        ) : (
          <div />
        )}
        <Group gap="xs">
          {afficherDossiers && (
            <Button variant="light" leftSection={<FolderPlus size={16} />} onClick={() => setModalDossier(true)}>
              Nouveau dossier
            </Button>
          )}
          <Button leftSection={<Upload size={16} />} onClick={() => setModalDocument(true)}>
            {voc("Ajouter un document")}</Button>
        </Group>
      </Group>

      <Card withBorder padding="md" radius="md">
        {isLoading ? (
          <Text c="dimmed">Chargement…</Text>
        ) : !documents || documents.length === 0 ? (
          <EmptyState
            icon={<FileText size={32} strokeWidth={1.5} />}
            message={
              projetId
                ? voc("Aucun document dans ce dossier.")
                : sousActiviteId
                  ? voc("Aucun document lié à cette sous-activité.")
                  : activiteId
                    ? voc("Aucun document lié à cette activité.")
                    : voc("Aucun document pour l'instant.")
            }
          />
        ) : (
          <Table.ScrollContainer minWidth={600}>
            <Table verticalSpacing="sm" striped highlightOnHover>
              <Table.Thead>
                <Table.Tr>
                  <Table.Th tt="uppercase" fz="xs" c="dimmed">Nom</Table.Th>
                  {afficherRattachement && <Table.Th tt="uppercase" fz="xs" c="dimmed">Rattaché à</Table.Th>}
                  <Table.Th tt="uppercase" fz="xs" c="dimmed">Type</Table.Th>
                  <Table.Th tt="uppercase" fz="xs" c="dimmed">Version</Table.Th>
                  <Table.Th tt="uppercase" fz="xs" c="dimmed">Ajouté par</Table.Th>
                  <Table.Th />
                </Table.Tr>
              </Table.Thead>
              <Table.Tbody>
                {documents.map((doc) => (
                  <Table.Tr key={doc.id}>
                    <Table.Td>
                      {doc.derniere_version ? (
                        <Text component="a" href={doc.derniere_version.fichier} target="_blank" size="sm" fw={500} c="teal.8">
                          {doc.nom}
                        </Text>
                      ) : (
                        <Text size="sm" fw={500}>{doc.nom}</Text>
                      )}
                    </Table.Td>
                    {afficherRattachement && <Table.Td>{rattachementDe(doc)}</Table.Td>}
                    <Table.Td>{doc.type_document || "—"}</Table.Td>
                    <Table.Td>
                      <Badge variant="light" size="sm">v{doc.derniere_version?.version ?? 1} · {doc.nombre_versions} version(s)</Badge>
                    </Table.Td>
                    <Table.Td>{doc.cree_par_nom}</Table.Td>
                    <Table.Td>
                      <Group gap={4} wrap="nowrap">
                        <Tooltip label="Historique des versions">
                          <ActionIcon variant="subtle" onClick={() => setDocumentVersionsId(doc.id)}>
                            <History size={16} />
                          </ActionIcon>
                        </Tooltip>
                        <Tooltip label="Supprimer">
                          <ActionIcon variant="subtle" color="red" onClick={() => handleSupprimer(doc)}>
                            <Trash2 size={16} />
                          </ActionIcon>
                        </Tooltip>
                      </Group>
                    </Table.Td>
                  </Table.Tr>
                ))}
              </Table.Tbody>
            </Table>
          </Table.ScrollContainer>
        )}
      </Card>

      {afficherDossiers && (
        <NouveauDossierModal
          projetId={projetId}
          opened={modalDossier}
          onClose={() => setModalDossier(false)}
          onCree={(dossierId) => setDossierActif(String(dossierId))}
        />
      )}
      <NouveauDocumentModal
        projetId={projetId}
        activiteId={activiteId}
        sousActiviteId={sousActiviteId}
        dossierId={dossierActif ? Number(dossierActif) : null}
        opened={modalDocument}
        onClose={() => setModalDocument(false)}
      />
      <VersionsModal
        documentId={documentVersionsId}
        opened={documentVersionsId !== null}
        onClose={() => setDocumentVersionsId(null)}
      />
    </Stack>
  );
}
