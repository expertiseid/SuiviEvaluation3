import { useState } from "react";
import { Pencil, Plus, Trash2 } from "lucide-react";
import {
  ActionIcon, Autocomplete, Badge, Button, Card, Checkbox, Group, Modal, Select, SimpleGrid, Stack, Table, Text, Textarea, TextInput, Tooltip,
} from "@mantine/core";
import { DateInput } from "@mantine/dates";
import { notifications } from "@mantine/notifications";
import { useDocuments } from "../../api/documents";
import { useIntervenants } from "../../api/intervenants";
import { apprentissagesApi, documentsObligatoiresApi, rapportsApi, recommandationsApi } from "../../api/pilotage";
import { useActivitesPourProjet } from "../../api/projects";
import { EmptyState } from "../../components/common/EmptyState";
import { confirmerSuppression } from "../../components/common/confirmerSuppression";
import type { Apprentissage, DocumentObligatoire, RapportProjet, Recommandation } from "../../types";
import { messageErreurApi } from "../../utils/erreurs";
import { locale } from "../../utils/i18n";
import { voc } from "../../utils/vocabulaire";

export type SectionPilotage = "rapports" | "documents-obligatoires" | "recommandations" | "apprentissage";

const dateFr = (d: string | null) => (d ? new Date(d).toLocaleDateString(locale()) : "—");
const aujourdhui = () => new Date().toISOString().slice(0, 10);

const statutsRapport = (): Record<RapportProjet["statut"], { label: string; couleur: string }> => ({
  ATTENDU: { label: voc("Attendu"), couleur: "gray" },
  RECU: { label: voc("Reçu"), couleur: "blue" },
  A_REVOIR: { label: voc("À revoir"), couleur: "orange" },
  VALIDE: { label: voc("Validé"), couleur: "teal" },
});
const statutsRecommandation = (): Record<Recommandation["statut"], { label: string; couleur: string }> => ({
  A_FAIRE: { label: voc("À mettre en œuvre"), couleur: "gray" },
  EN_COURS: { label: voc("En cours"), couleur: "blue" },
  REALISEE: { label: voc("Mise en œuvre"), couleur: "teal" },
  ABANDONNEE: { label: voc("Abandonnée"), couleur: "dark" },
});
const priorites = (): Record<Recommandation["priorite"], { label: string; couleur: string }> => ({
  HAUTE: { label: voc("Haute"), couleur: "red" },
  MOYENNE: { label: voc("Moyenne"), couleur: "yellow" },
  BASSE: { label: voc("Basse"), couleur: "gray" },
});
const origines = (): Record<Exclude<Recommandation["origine"], "">, string> => ({
  EVALUATION: voc("Évaluation"),
  AUDIT: voc("Audit"),
  MISSION: voc("Mission de suivi ou de supervision"),
  REVUE: voc("Revue de projet, comité de pilotage"),
  ANALYSE: voc("Analyse des données"),
  AUTRE: voc("Autre"),
});
const typesApprentissage = (): Record<Apprentissage["type"], { label: string; couleur: string }> => ({
  LECON: { label: voc("Leçon apprise"), couleur: "grape" },
  BONNE_PRATIQUE: { label: voc("Bonne pratique"), couleur: "teal" },
  DECISION: { label: voc("Décision"), couleur: "indigo" },
});
const typesRapport = () => [
  voc("Mensuel"), voc("Trimestriel"), voc("Semestriel"), voc("Annuel"), voc("À mi-parcours"), voc("Final"), voc("Pour un bailleur"), voc("Autre"),
];
const sources = () => [
  voc("Revue à mi-parcours"), voc("Évaluation finale"), voc("Mission de supervision"), voc("Analyse des données"), voc("Comité de pilotage"), voc("Audit"),
];

const choix = <K extends string>(dico: Record<K, { label: string }>) =>
  (Object.entries(dico) as [K, { label: string }][]).map(([value, { label }]) => ({ value, label }));

function versDate(v: string | Date | null): string | null {
  if (!v) return null;
  return typeof v === "string" ? v.slice(0, 10) : v.toISOString().slice(0, 10);
}

/** Enregistre et ferme, ou affiche l'erreur. */
async function enregistrer<T>(action: () => Promise<T>, onClose: () => void) {
  try {
    await action();
    notifications.show({ message: voc("Enregistré"), color: "green" });
    onClose();
  } catch (e) {
    notifications.show({ message: messageErreurApi(e, voc("Erreur lors de l'enregistrement")), color: "red" });
  }
}

function Actions({ modifiable, onModifier, onSupprimer }: { modifiable: boolean; onModifier: () => void; onSupprimer: () => void }) {
  if (!modifiable) return null;
  return (
    <Group gap={4} wrap="nowrap">
      <Tooltip label={voc("Modifier")}><ActionIcon variant="subtle" onClick={onModifier} aria-label={voc("Modifier")}><Pencil size={15} /></ActionIcon></Tooltip>
      <Tooltip label={voc("Supprimer")}><ActionIcon variant="subtle" color="red" onClick={onSupprimer} aria-label={voc("Supprimer")}><Trash2 size={15} /></ActionIcon></Tooltip>
    </Group>
  );
}

function supprimer(nom: string, action: () => Promise<unknown>) {
  confirmerSuppression({
    message: voc`Supprimer « ${nom} » ? Cette action est irréversible.`,
    onConfirm: async () => {
      try {
        await action();
        notifications.show({ message: voc("Supprimé"), color: "green" });
      } catch (e) {
        notifications.show({ message: messageErreurApi(e, voc("Erreur lors de la suppression")), color: "red" });
      }
    },
  });
}

// --- Rapports attendus -----------------------------------------------------------------------------

function RapportForm({ projetId, rapport, onClose }: { projetId: number; rapport: Partial<RapportProjet>; onClose: () => void }) {
  const sauver = rapportsApi.useEnregistrer();
  const { data: documents = [] } = useDocuments({ projet: projetId });
  const [r, setR] = useState<Partial<RapportProjet>>({ statut: "ATTENDU", ...rapport });
  const set = (champs: Partial<RapportProjet>) => setR((x) => ({ ...x, ...champs }));
  const valider = () => {
    if (!r.libelle?.trim() || !r.echeance) {
      notifications.show({ message: voc("Indiquez le rapport et son échéance."), color: "orange" });
      return;
    }
    enregistrer(() => sauver.mutateAsync({ ...r, projet: projetId, libelle: r.libelle?.trim() }), onClose);
  };
  return (
    <Modal opened onClose={onClose} title={rapport.id ? voc("Modifier le rapport") : voc("Nouveau rapport attendu")} size="lg">
      <Stack gap="sm">
        <TextInput label={voc("Rapport")} placeholder={voc("Ex : Rapport du 1er trimestre 2026")} required data-autofocus
          value={r.libelle ?? ""} onChange={(e) => set({ libelle: e.currentTarget.value })} />
        <SimpleGrid cols={{ base: 1, sm: 2 }}>
          <Autocomplete label={voc("Type")} data={typesRapport()} value={r.type ?? ""} onChange={(v) => set({ type: v })} />
          <TextInput label={voc("Destinataire")} placeholder={voc("Bailleur, comité de pilotage…")} value={r.destinataire ?? ""}
            onChange={(e) => set({ destinataire: e.currentTarget.value })} />
        </SimpleGrid>
        <SimpleGrid cols={{ base: 1, sm: 3 }}>
          <DateInput label={voc("Échéance")} required value={r.echeance ?? null} onChange={(v) => set({ echeance: versDate(v) ?? undefined })} />
          <DateInput label={voc("Remis le")} clearable value={r.date_remise ?? null} onChange={(v) => set({ date_remise: versDate(v) })} />
          <DateInput label={voc("Validé le")} clearable value={r.date_validation ?? null} onChange={(v) => set({ date_validation: versDate(v) })} />
        </SimpleGrid>
        <Select label={voc("Statut")} allowDeselect={false} data={choix(statutsRapport())} value={r.statut}
          onChange={(v) => v && set({ statut: v as RapportProjet["statut"] })} />
        <Select label={voc("Document remis")} description={voc("Parmi les documents du projet (onglet « Documents »).")} searchable clearable
          data={documents.map((d) => ({ value: String(d.id), label: d.nom }))} value={r.document ? String(r.document) : null}
          onChange={(v) => set({ document: v ? Number(v) : null })} />
        <Textarea label={voc("Commentaire")} autosize minRows={2} value={r.commentaire ?? ""} onChange={(e) => set({ commentaire: e.currentTarget.value })} />
        <Group justify="flex-end">
          <Button variant="default" onClick={onClose}>{voc("Annuler")}</Button>
          <Button onClick={valider} loading={sauver.isPending}>{voc("Enregistrer")}</Button>
        </Group>
      </Stack>
    </Modal>
  );
}

function Rapports({ projetId, modifiable }: { projetId: number; modifiable: boolean }) {
  const { data: rapports = [], isLoading } = rapportsApi.useListe(projetId);
  const supprimerRapport = rapportsApi.useSupprimer();
  const [edition, setEdition] = useState<Partial<RapportProjet> | null>(null);
  const statuts = statutsRapport();
  const echus = rapports.filter((r) => r.echeance <= aujourdhui());
  const recus = echus.filter((r) => r.statut !== "ATTENDU").length;
  return (
    <Stack gap="sm">
      <Group justify="space-between">
        <Text size="sm" c="dimmed">
          {voc`${recus} rapport(s) reçu(s) sur ${echus.length} attendu(s) à ce jour ; ${rapports.filter((r) => r.statut === "VALIDE").length} validé(s).`}
        </Text>
        {modifiable && <Button size="xs" leftSection={<Plus size={14} />} onClick={() => setEdition({})}>{voc("Ajouter un rapport attendu")}</Button>}
      </Group>
      {!isLoading && rapports.length === 0 ? (
        <EmptyState message={voc("Aucun rapport attendu. Ajoutez les rapports à remettre (trimestriels, annuels, au bailleur…) avec leur échéance.")} />
      ) : (
        <Table.ScrollContainer minWidth={760}>
          <Table striped highlightOnHover verticalSpacing="xs" fz="sm">
            <Table.Thead>
              <Table.Tr>
                <Table.Th>{voc("Rapport")}</Table.Th><Table.Th>{voc("Échéance")}</Table.Th><Table.Th>{voc("Remis le")}</Table.Th>
                <Table.Th>{voc("Statut")}</Table.Th><Table.Th>{voc("Document")}</Table.Th><Table.Th />
              </Table.Tr>
            </Table.Thead>
            <Table.Tbody>
              {rapports.map((r) => (
                <Table.Tr key={r.id}>
                  <Table.Td>
                    <Text size="sm" fw={500}>{r.libelle}</Text>
                    <Text size="xs" c="dimmed">{[r.type, r.destinataire].filter(Boolean).join(" · ")}</Text>
                  </Table.Td>
                  <Table.Td c={r.en_retard ? "red.7" : undefined}>{dateFr(r.echeance)}</Table.Td>
                  <Table.Td>{dateFr(r.date_remise)}</Table.Td>
                  <Table.Td>
                    <Badge variant="light" color={statuts[r.statut].couleur}>{statuts[r.statut].label}</Badge>
                    {r.en_retard && <Badge ml={4} variant="light" color="red">{r.statut === "ATTENDU" ? voc("En retard") : voc("Remis en retard")}</Badge>}
                  </Table.Td>
                  <Table.Td>{r.document_titre || "—"}</Table.Td>
                  <Table.Td>
                    <Actions modifiable={modifiable} onModifier={() => setEdition(r)} onSupprimer={() => supprimer(r.libelle, () => supprimerRapport.mutateAsync(r.id))} />
                  </Table.Td>
                </Table.Tr>
              ))}
            </Table.Tbody>
          </Table>
        </Table.ScrollContainer>
      )}
      {edition && <RapportForm projetId={projetId} rapport={edition} onClose={() => setEdition(null)} />}
    </Stack>
  );
}

// --- Documents obligatoires -------------------------------------------------------------------------

const modelesDocuments = () => [
  voc("Convention de financement"), voc("Accord de partenariat"), voc("Rapport de démarrage"), voc("Plan de travail annuel"),
  voc("Plan de passation des marchés"), voc("Cadre de résultats"), voc("Plan de suivi-évaluation"), voc("Étude de référence"),
  voc("Plan de gestion environnementale et sociale"), voc("Rapport d'audit"),
];

function DocumentObligatoireForm({ projetId, element, onClose }: { projetId: number; element: Partial<DocumentObligatoire>; onClose: () => void }) {
  const sauver = documentsObligatoiresApi.useEnregistrer();
  const { data: documents = [] } = useDocuments({ projet: projetId });
  const [d, setD] = useState<Partial<DocumentObligatoire>>(element);
  const set = (champs: Partial<DocumentObligatoire>) => setD((x) => ({ ...x, ...champs }));
  const valider = () => {
    if (!d.libelle?.trim()) {
      notifications.show({ message: voc("Indiquez le document attendu."), color: "orange" });
      return;
    }
    enregistrer(() => sauver.mutateAsync({ ...d, projet: projetId, libelle: d.libelle?.trim() }), onClose);
  };
  return (
    <Modal opened onClose={onClose} title={element.id ? voc("Modifier le document obligatoire") : voc("Nouveau document obligatoire")} size="lg">
      <Stack gap="sm">
        <Autocomplete label={voc("Document attendu")} required data-autofocus data={modelesDocuments()} value={d.libelle ?? ""}
          onChange={(v) => set({ libelle: v })} />
        <DateInput label={voc("Doit être disponible le")} clearable value={d.echeance ?? null} onChange={(v) => set({ echeance: versDate(v) })} />
        <Select label={voc("Document fourni")} description={voc("Parmi les documents du projet (onglet « Documents ») : vide tant qu'il manque.")}
          searchable clearable data={documents.map((x) => ({ value: String(x.id), label: x.nom }))} value={d.document ? String(d.document) : null}
          onChange={(v) => set({ document: v ? Number(v) : null })} />
        <Textarea label={voc("Commentaire")} autosize minRows={2} value={d.commentaire ?? ""} onChange={(e) => set({ commentaire: e.currentTarget.value })} />
        <Group justify="flex-end">
          <Button variant="default" onClick={onClose}>{voc("Annuler")}</Button>
          <Button onClick={valider} loading={sauver.isPending}>{voc("Enregistrer")}</Button>
        </Group>
      </Stack>
    </Modal>
  );
}

function DocumentsObligatoires({ projetId, modifiable }: { projetId: number; modifiable: boolean }) {
  const { data: elements = [], isLoading } = documentsObligatoiresApi.useListe(projetId);
  const supprimerElement = documentsObligatoiresApi.useSupprimer();
  const [edition, setEdition] = useState<Partial<DocumentObligatoire> | null>(null);
  const disponibles = elements.filter((d) => d.disponible).length;
  return (
    <Stack gap="sm">
      <Group justify="space-between">
        <Text size="sm" c="dimmed">
          {voc`${disponibles} document(s) disponible(s) sur ${elements.length} obligatoire(s) ; ${elements.filter((d) => d.en_retard).length} manquant(s) après leur échéance.`}
        </Text>
        {modifiable && <Button size="xs" leftSection={<Plus size={14} />} onClick={() => setEdition({})}>{voc("Ajouter un document obligatoire")}</Button>}
      </Group>
      {!isLoading && elements.length === 0 ? (
        <EmptyState message={voc("Aucun document obligatoire. Listez ceux que le projet doit avoir (convention, rapport de démarrage, plan de passation…), puis associez chaque document dès qu'il est déposé.")} />
      ) : (
        <Table.ScrollContainer minWidth={680}>
          <Table striped highlightOnHover verticalSpacing="xs" fz="sm">
            <Table.Thead>
              <Table.Tr>
                <Table.Th>{voc("Document attendu")}</Table.Th><Table.Th>{voc("Échéance")}</Table.Th><Table.Th>{voc("État")}</Table.Th>
                <Table.Th>{voc("Document fourni")}</Table.Th><Table.Th />
              </Table.Tr>
            </Table.Thead>
            <Table.Tbody>
              {elements.map((d) => (
                <Table.Tr key={d.id}>
                  <Table.Td>
                    <Text size="sm" fw={500}>{d.libelle}</Text>
                    {d.commentaire && <Text size="xs" c="dimmed">{d.commentaire}</Text>}
                  </Table.Td>
                  <Table.Td c={d.en_retard ? "red.7" : undefined}>{dateFr(d.echeance)}</Table.Td>
                  <Table.Td>
                    <Badge variant="light" color={d.disponible ? "teal" : d.en_retard ? "red" : "gray"}>
                      {d.disponible ? voc("Disponible") : d.en_retard ? voc("Manquant, en retard") : voc("Manquant")}
                    </Badge>
                  </Table.Td>
                  <Table.Td>{d.document_titre || "—"}</Table.Td>
                  <Table.Td>
                    <Actions modifiable={modifiable} onModifier={() => setEdition(d)} onSupprimer={() => supprimer(d.libelle, () => supprimerElement.mutateAsync(d.id))} />
                  </Table.Td>
                </Table.Tr>
              ))}
            </Table.Tbody>
          </Table>
        </Table.ScrollContainer>
      )}
      {edition && <DocumentObligatoireForm projetId={projetId} element={edition} onClose={() => setEdition(null)} />}
    </Stack>
  );
}

// --- Recommandations ---------------------------------------------------------------------------------

function RecommandationForm({ projetId, recommandation, onClose }: { projetId: number; recommandation: Partial<Recommandation>; onClose: () => void }) {
  const sauver = recommandationsApi.useEnregistrer();
  const { data: rapports = [] } = rapportsApi.useListe(projetId);
  const { data: intervenants = [] } = useIntervenants();
  const [r, setR] = useState<Partial<Recommandation>>({ statut: "A_FAIRE", priorite: "MOYENNE", date: aujourdhui(), ...recommandation });
  const set = (champs: Partial<Recommandation>) => setR((x) => ({ ...x, ...champs }));
  const valider = () => {
    if (!r.libelle?.trim()) {
      notifications.show({ message: voc("Indiquez la recommandation."), color: "orange" });
      return;
    }
    enregistrer(() => sauver.mutateAsync({ ...r, projet: projetId, libelle: r.libelle?.trim() }), onClose);
  };
  return (
    <Modal opened onClose={onClose} title={recommandation.id ? voc`Modifier la recommandation ${recommandation.code}` : voc("Nouvelle recommandation")} size="lg">
      <Stack gap="sm">
        <Textarea label={voc("Recommandation")} required autosize minRows={2} data-autofocus value={r.libelle ?? ""}
          onChange={(e) => set({ libelle: e.currentTarget.value })} />
        <SimpleGrid cols={{ base: 1, sm: 3 }}>
          <Select label={voc("Origine")} description={voc("Évaluation, audit, supervision…")} clearable
            data={Object.entries(origines()).map(([value, label]) => ({ value, label }))}
            value={r.origine || null} onChange={(v) => set({ origine: (v ?? "") as Recommandation["origine"] })} />
          <Autocomplete label={voc("Source")} description={voc("Laquelle précisément ?")} data={sources()} value={r.source ?? ""}
            onChange={(v) => set({ source: v })} />
          <Select label={voc("Rapport d'origine")} description={voc("Facultatif")} clearable data={rapports.map((x) => ({ value: String(x.id), label: x.libelle }))}
            value={r.rapport ? String(r.rapport) : null} onChange={(v) => set({ rapport: v ? Number(v) : null })} />
        </SimpleGrid>
        <SimpleGrid cols={{ base: 1, sm: 3 }}>
          <DateInput label={voc("Formulée le")} value={r.date ?? null} onChange={(v) => set({ date: versDate(v) ?? aujourdhui() })} />
          <Select label={voc("Priorité")} allowDeselect={false} data={choix(priorites())} value={r.priorite}
            onChange={(v) => v && set({ priorite: v as Recommandation["priorite"] })} />
          <DateInput label={voc("Échéance")} clearable value={r.echeance ?? null} onChange={(v) => set({ echeance: versDate(v) })} />
        </SimpleGrid>
        <SimpleGrid cols={{ base: 1, sm: 2 }}>
          <Select label={voc("Responsable")} searchable clearable data={intervenants.map((i) => ({ value: String(i.id), label: `${i.prenom ?? ""} ${i.nom}`.trim() }))}
            value={r.responsable ? String(r.responsable) : null} onChange={(v) => set({ responsable: v ? Number(v) : null })} />
          <Select label={voc("Mise en œuvre")} allowDeselect={false} data={choix(statutsRecommandation())} value={r.statut}
            onChange={(v) => v && set({ statut: v as Recommandation["statut"] })} />
        </SimpleGrid>
        <Textarea label={voc("Suivi")} description={voc("Ce qui a été fait.")} autosize minRows={2} value={r.suivi ?? ""}
          onChange={(e) => set({ suivi: e.currentTarget.value })} />
        <Group justify="flex-end">
          <Button variant="default" onClick={onClose}>{voc("Annuler")}</Button>
          <Button onClick={valider} loading={sauver.isPending}>{voc("Enregistrer")}</Button>
        </Group>
      </Stack>
    </Modal>
  );
}

function Recommandations({ projetId, modifiable }: { projetId: number; modifiable: boolean }) {
  const { data: recommandations = [], isLoading } = recommandationsApi.useListe(projetId);
  const supprimerRecommandation = recommandationsApi.useSupprimer();
  const [edition, setEdition] = useState<Partial<Recommandation> | null>(null);
  const statuts = statutsRecommandation();
  const prio = priorites();
  const retenues = recommandations.filter((r) => r.statut !== "ABANDONNEE");
  const realisees = retenues.filter((r) => r.statut === "REALISEE").length;
  return (
    <Stack gap="sm">
      <Group justify="space-between">
        <Text size="sm" c="dimmed">
          {voc`${realisees} recommandation(s) mise(s) en œuvre sur ${retenues.length}${retenues.length ? ` (${Math.round((realisees / retenues.length) * 100)} %)` : ""}.`}
        </Text>
        {modifiable && <Button size="xs" leftSection={<Plus size={14} />} onClick={() => setEdition({})}>{voc("Ajouter une recommandation")}</Button>}
      </Group>
      {!isLoading && recommandations.length === 0 ? (
        <EmptyState message={voc("Aucune recommandation. Notez celles issues des revues, supervisions, analyses ou évaluations, puis suivez leur mise en œuvre.")} />
      ) : (
        <Table.ScrollContainer minWidth={820}>
          <Table striped highlightOnHover verticalSpacing="xs" fz="sm">
            <Table.Thead>
              <Table.Tr>
                <Table.Th>{voc("Recommandation")}</Table.Th><Table.Th>{voc("Priorité")}</Table.Th><Table.Th>{voc("Responsable")}</Table.Th>
                <Table.Th>{voc("Échéance")}</Table.Th><Table.Th>{voc("Mise en œuvre")}</Table.Th><Table.Th />
              </Table.Tr>
            </Table.Thead>
            <Table.Tbody>
              {recommandations.map((r) => {
                const enRetard = r.echeance && r.echeance < aujourdhui() && r.statut !== "REALISEE" && r.statut !== "ABANDONNEE";
                return (
                  <Table.Tr key={r.id}>
                    <Table.Td>
                      <Text size="sm"><Text span fw={600}>{r.code}</Text> {r.libelle}</Text>
                      <Text size="xs" c="dimmed">{[r.origine ? origines()[r.origine] : "", r.source, r.rapport_libelle, dateFr(r.date)].filter((x) => x && x !== "—").join(" · ")}</Text>
                      {r.suivi && <Text size="xs" mt={2}>{r.suivi}</Text>}
                    </Table.Td>
                    <Table.Td><Badge variant="light" color={prio[r.priorite].couleur}>{prio[r.priorite].label}</Badge></Table.Td>
                    <Table.Td>{r.responsable_nom || "—"}</Table.Td>
                    <Table.Td c={enRetard ? "red.7" : undefined}>{dateFr(r.echeance)}</Table.Td>
                    <Table.Td>
                      <Badge variant="light" color={statuts[r.statut].couleur}>{statuts[r.statut].label}</Badge>
                      {r.date_mise_en_oeuvre && <Text size="xs" c="dimmed">{dateFr(r.date_mise_en_oeuvre)}</Text>}
                    </Table.Td>
                    <Table.Td>
                      <Actions modifiable={modifiable} onModifier={() => setEdition(r)}
                        onSupprimer={() => supprimer(`${r.code} ${r.libelle}`, () => supprimerRecommandation.mutateAsync(r.id))} />
                    </Table.Td>
                  </Table.Tr>
                );
              })}
            </Table.Tbody>
          </Table>
        </Table.ScrollContainer>
      )}
      {edition && <RecommandationForm projetId={projetId} recommandation={edition} onClose={() => setEdition(null)} />}
    </Stack>
  );
}

// --- Leçons apprises, bonnes pratiques et décisions ---------------------------------------------

function ApprentissageForm({ projetId, element, onClose }: { projetId: number; element: Partial<Apprentissage>; onClose: () => void }) {
  const sauver = apprentissagesApi.useEnregistrer();
  const { data: recommandations = [] } = recommandationsApi.useListe(projetId);
  const { data: elements = [] } = useActivitesPourProjet(projetId);
  const [a, setA] = useState<Partial<Apprentissage>>({ type: "LECON", date: aujourdhui(), ...element });
  const set = (champs: Partial<Apprentissage>) => setA((x) => ({ ...x, ...champs }));
  const valider = () => {
    if (!a.titre?.trim()) {
      notifications.show({ message: voc("Indiquez un titre."), color: "orange" });
      return;
    }
    enregistrer(() => sauver.mutateAsync({ ...a, projet: projetId, titre: a.titre?.trim() }), onClose);
  };
  return (
    <Modal opened onClose={onClose} title={element.id ? voc("Modifier") : voc("Nouvelle leçon, bonne pratique ou décision")} size="lg">
      <Stack gap="sm">
        <Select label={voc("Type")} allowDeselect={false} data={choix(typesApprentissage())} value={a.type}
          onChange={(v) => v && set({ type: v as Apprentissage["type"] })} />
        <TextInput label={voc("Titre")} required data-autofocus value={a.titre ?? ""} onChange={(e) => set({ titre: e.currentTarget.value })} />
        <Textarea label={a.type === "DECISION" ? voc("Décision et justification") : voc("Ce qui s'est passé et ce qu'on en retient")}
          autosize minRows={3} value={a.description ?? ""} onChange={(e) => set({ description: e.currentTarget.value })} />
        <SimpleGrid cols={{ base: 1, sm: 2 }}>
          <DateInput label={voc("Date")} value={a.date ?? null} onChange={(v) => set({ date: versDate(v) ?? aujourdhui() })} />
          {a.type === "DECISION" && (
            <TextInput label={voc("Prise par")} placeholder={voc("Comité de pilotage, équipe de projet…")} value={a.decideur ?? ""}
              onChange={(e) => set({ decideur: e.currentTarget.value })} />
          )}
        </SimpleGrid>
        {a.type !== "DECISION" && (
          <>
            <Checkbox label={voc("Cette leçon a entraîné un changement dans le projet")} checked={a.adaptation ?? false}
              onChange={(e) => set({ adaptation: e.currentTarget.checked })} />
            {a.adaptation && (
              <Textarea label={voc("Changement apporté")} autosize minRows={2} value={a.changement ?? ""}
                onChange={(e) => set({ changement: e.currentTarget.value })} />
            )}
          </>
        )}
        <SimpleGrid cols={{ base: 1, sm: 2 }}>
          <Select label={voc("Recommandation liée")} clearable searchable data={recommandations.map((r) => ({ value: String(r.id), label: `${r.code} ${r.libelle}` }))}
            value={a.recommandation ? String(a.recommandation) : null} onChange={(v) => set({ recommandation: v ? Number(v) : null })} />
          <Select label={voc("Élément de la planification")} clearable searchable data={elements.map((e) => ({ value: String(e.id), label: e.libelle }))}
            value={a.element ? String(a.element) : null} onChange={(v) => set({ element: v ? Number(v) : null })} />
        </SimpleGrid>
        <Group justify="flex-end">
          <Button variant="default" onClick={onClose}>{voc("Annuler")}</Button>
          <Button onClick={valider} loading={sauver.isPending}>{voc("Enregistrer")}</Button>
        </Group>
      </Stack>
    </Modal>
  );
}

function Apprentissages({ projetId, modifiable }: { projetId: number; modifiable: boolean }) {
  const { data: elements = [], isLoading } = apprentissagesApi.useListe(projetId);
  const supprimerElement = apprentissagesApi.useSupprimer();
  const [edition, setEdition] = useState<Partial<Apprentissage> | null>(null);
  const types = typesApprentissage();
  return (
    <Stack gap="sm">
      <Group justify="space-between">
        <Text size="sm" c="dimmed">
          {voc`${elements.filter((e) => e.type === "LECON").length} leçon(s) apprise(s), ${elements.filter((e) => e.type === "BONNE_PRATIQUE").length} bonne(s) pratique(s), ${elements.filter((e) => e.type === "DECISION").length} décision(s).`}
        </Text>
        {modifiable && <Button size="xs" leftSection={<Plus size={14} />} onClick={() => setEdition({})}>{voc("Ajouter")}</Button>}
      </Group>
      {!isLoading && elements.length === 0 ? (
        <EmptyState message={voc("Rien de documenté pour l'instant : notez les leçons apprises, les bonnes pratiques et les décisions importantes du projet.")} />
      ) : (
        <Stack gap="xs">
          {elements.map((e) => (
            <Card key={e.id} withBorder padding="sm" radius="md">
              <Group justify="space-between" align="flex-start" wrap="nowrap">
                <div style={{ flex: 1 }}>
                  <Group gap="xs" mb={4}>
                    <Badge variant="light" color={types[e.type].couleur}>{types[e.type].label}</Badge>
                    {e.adaptation && <Badge variant="light" color="green">{voc("A entraîné un changement")}</Badge>}
                    <Text size="xs" c="dimmed">{[dateFr(e.date), e.decideur, e.element_libelle, e.recommandation_libelle].filter(Boolean).join(" · ")}</Text>
                  </Group>
                  <Text fw={600} size="sm">{e.titre}</Text>
                  {e.description && <Text size="sm" style={{ whiteSpace: "pre-line" }}>{e.description}</Text>}
                  {e.adaptation && e.changement && <Text size="sm" c="green.8" mt={2}>{voc("Changement :")} {e.changement}</Text>}
                </div>
                <Actions modifiable={modifiable} onModifier={() => setEdition(e)} onSupprimer={() => supprimer(e.titre, () => supprimerElement.mutateAsync(e.id))} />
              </Group>
            </Card>
          ))}
        </Stack>
      )}
      {edition && <ApprentissageForm projetId={projetId} element={edition} onClose={() => setEdition(null)} />}
    </Stack>
  );
}

/** Onglets « Rapports », « Documents obligatoires », « Recommandations » et « Leçons et décisions » d'un projet. */
export function PilotageTab({ projetId, section, modifiable }: { projetId: number; section: SectionPilotage; modifiable: boolean }) {
  if (section === "rapports") return <Rapports projetId={projetId} modifiable={modifiable} />;
  if (section === "documents-obligatoires") return <DocumentsObligatoires projetId={projetId} modifiable={modifiable} />;
  if (section === "recommandations") return <Recommandations projetId={projetId} modifiable={modifiable} />;
  return <Apprentissages projetId={projetId} modifiable={modifiable} />;
}
