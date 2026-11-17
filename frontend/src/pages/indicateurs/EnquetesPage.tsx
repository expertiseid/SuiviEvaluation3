import { useEffect, useState } from "react";
import { AlertTriangle, Trash2, Upload } from "lucide-react";
import {
  ActionIcon, Alert, Badge, Button, Card, FileInput, Group, Loader, Modal, MultiSelect, SegmentedControl, Select, SimpleGrid,
  Stack, Table, Text, TextInput, Title, Tooltip,
} from "@mantine/core";
import { notifications } from "@mantine/notifications";
import {
  useCalculEnquete, useEnquetes, useImporterEnquete, useModalitesEnquete, useModifierEnquete, useSupprimerEnquete,
} from "../../api/enquetes";
import { useProjets } from "../../api/projects";
import { EmptyState } from "../../components/common/EmptyState";
import { confirmerSuppression } from "../../components/common/confirmerSuppression";
import type { CalculEnquete, Enquete } from "../../types";
import { messageErreurApi } from "../../utils/erreurs";
import { locale } from "../../utils/i18n";
import { voc } from "../../utils/vocabulaire";

const nombre = (x: number, chiffres = 1) => x.toLocaleString(locale(), { maximumFractionDigits: chiffres });

function ImportEnquete({ opened, onClose, onImportee }: { opened: boolean; onClose: () => void; onImportee: (e: Enquete) => void }) {
  const importer = useImporterEnquete();
  const { data: projets = [] } = useProjets();
  const [fichier, setFichier] = useState<File | null>(null);
  const [titre, setTitre] = useState("");
  const [projet, setProjet] = useState<string | null>(null);
  async function valider() {
    if (!fichier) return;
    try {
      const enquete = await importer.mutateAsync({ fichier, titre: titre.trim(), projet: projet ? Number(projet) : null });
      notifications.show({ message: voc`${enquete.nombre_reponses} réponse(s) importée(s).`, color: "green" });
      onImportee(enquete);
      setFichier(null);
      setTitre("");
      onClose();
    } catch (e) {
      notifications.show({ message: messageErreurApi(e, voc("L'import a échoué.")), color: "red" });
    }
  }
  return (
    <Modal opened={opened} onClose={onClose} title={voc("Importer une enquête")} size="lg">
      <Stack gap="sm">
        <FileInput label={voc("Fichier")} description={voc("Excel (.xlsx) ou CSV : une ligne par répondant, les noms de colonnes en première ligne (export KoboToolbox, ODK…).")}
          accept=".xlsx,.xlsm,.csv,.txt" value={fichier} onChange={setFichier} clearable required />
        <TextInput label={voc("Titre")} placeholder={voc("Ex : Enquête ménages de référence 2026")} value={titre} onChange={(e) => setTitre(e.currentTarget.value)} />
        <Select label={voc("Projet")} description={voc("Vide : enquête de toute l'organisation.")} searchable clearable
          data={projets.map((p) => ({ value: String(p.id), label: `${p.code} · ${p.nom}` }))} value={projet} onChange={setProjet} />
        <Alert color="blue" variant="light">
          {voc("Les colonnes d'identification personnelle (noms, téléphones, pièces d'identité, positions GPS) et les colonnes techniques de l'outil de collecte ne sont pas conservées.")}
        </Alert>
        <Group justify="flex-end">
          <Button variant="default" onClick={onClose}>{voc("Annuler")}</Button>
          <Button leftSection={<Upload size={15} />} onClick={valider} loading={importer.isPending} disabled={!fichier}>{voc("Importer")}</Button>
        </Group>
      </Stack>
    </Modal>
  );
}

/** Poids, strate et grappe : décrivent comment l'échantillon a été tiré. */
function PlanSondage({ enquete }: { enquete: Enquete }) {
  const modifier = useModifierEnquete();
  const nombres = enquete.colonnes.filter((c) => c.type === "NOMBRE").map((c) => c.nom);
  const toutes = enquete.colonnes.map((c) => c.nom);
  const changer = (champ: "colonne_poids" | "colonne_strate" | "colonne_grappe", valeur: string | null) =>
    modifier.mutate({ id: enquete.id, [champ]: valeur ?? "" }, {
      onError: (e) => notifications.show({ message: messageErreurApi(e, voc("Erreur lors de l'enregistrement")), color: "red" }),
    });
  return (
    <SimpleGrid cols={{ base: 1, sm: 3 }}>
      <Select label={voc("Poids")} description={voc("Combien de personnes chaque répondant représente. Vide : tous comptent pareil.")}
        data={nombres} value={enquete.colonne_poids || null} onChange={(v) => changer("colonne_poids", v)} clearable searchable />
      <Select label={voc("Strate")} description={voc("Sous-populations tirées séparément (région, milieu…).")}
        data={toutes} value={enquete.colonne_strate || null} onChange={(v) => changer("colonne_strate", v)} clearable searchable />
      <Select label={voc("Grappe")} description={voc("Unité tirée au premier degré (village, zone de dénombrement…).")}
        data={toutes} value={enquete.colonne_grappe || null} onChange={(v) => changer("colonne_grappe", v)} clearable searchable />
    </SimpleGrid>
  );
}

function Calculateur({ enquete }: { enquete: Enquete }) {
  const [calcul, setCalcul] = useState<CalculEnquete>("proportion");
  const [colonne, setColonne] = useState<string | null>(null);
  const [valeurs, setValeurs] = useState<string[]>([]);
  const [par, setPar] = useState<string | null>(null);
  useEffect(() => { setColonne(null); setValeurs([]); setPar(null); }, [enquete.id]);
  const type = enquete.colonnes.find((c) => c.nom === colonne)?.type;
  const { data: modalites = [] } = useModalitesEnquete(enquete.id, type === "TEXTE" || calcul === "proportion" ? colonne : null);
  const { data: resultat, isFetching, error } = useCalculEnquete(enquete.id, { calcul, colonne, valeurs, par });
  const colonnesPossibles = enquete.colonnes.filter((c) => calcul !== "moyenne" || c.type === "NOMBRE");
  const pourcent = calcul === "proportion";
  return (
    <Stack gap="sm">
      <SegmentedControl value={calcul} onChange={(v) => { setCalcul(v as CalculEnquete); setValeurs([]); }}
        data={[{ value: "proportion", label: voc("Proportion (%)") }, { value: "moyenne", label: voc("Moyenne") }, { value: "total", label: voc("Total estimé") }]} />
      <SimpleGrid cols={{ base: 1, sm: 3 }}>
        <Select label={voc("Question (colonne)")} searchable data={colonnesPossibles.map((c) => ({ value: c.nom, label: c.nom }))} value={colonne}
          onChange={(v) => { setColonne(v); setValeurs([]); }} />
        {(pourcent || type === "TEXTE") && (
          <MultiSelect label={pourcent ? voc("Réponses comptées") : voc("Réponses à compter")} searchable
            data={modalites.map((m) => ({ value: m.valeur, label: `${m.valeur} (${m.nombre})` }))} value={valeurs} onChange={setValeurs} />
        )}
        <Select label={voc("Ventiler par")} placeholder={voc("Ensemble des répondants")} clearable searchable
          data={enquete.colonnes.filter((c) => c.type === "TEXTE" && c.nom !== colonne).map((c) => c.nom)} value={par} onChange={setPar} />
      </SimpleGrid>
      {error ? (
        <Alert color="orange" variant="light">{messageErreurApi(error, voc("Calcul impossible."))}</Alert>
      ) : resultat && (
        <Stack gap={6}>
          <Group gap="xs">
            <Text size="sm" c="dimmed">{voc`Plan de sondage : ${resultat.plan}. Intervalle de confiance à 95 %.`}</Text>
            {isFetching && <Loader size="xs" />}
          </Group>
          {resultat.avertissements.map((a) => <Text key={a} size="sm" c="orange.8">{a}</Text>)}
          <Table.ScrollContainer minWidth={640}>
            <Table striped withTableBorder verticalSpacing={6} fz="sm">
              <Table.Thead>
                <Table.Tr>
                  {par && <Table.Th>{par}</Table.Th>}
                  <Table.Th ta="right">{voc("Estimation")}</Table.Th>
                  <Table.Th ta="right">{voc("Intervalle à 95 %")}</Table.Th>
                  <Table.Th ta="right">{voc("Marge d'erreur")}</Table.Th>
                  <Table.Th ta="right">{voc("Répondants")}</Table.Th>
                  <Table.Th ta="right">
                    <Tooltip label={voc("Combien de fois la variance dépasse celle d'un tirage au hasard de même taille (poids, grappes).")} multiline w={260}>
                      <span>{voc("Effet de plan")}</span>
                    </Tooltip>
                  </Table.Th>
                </Table.Tr>
              </Table.Thead>
              <Table.Tbody>
                {resultat.resultats.map((r) => (
                  <Table.Tr key={r.groupe ?? "tous"}>
                    {par && <Table.Td fw={600}>{r.groupe}</Table.Td>}
                    <Table.Td ta="right" fw={700}>{nombre(r.estimation)}{pourcent ? " %" : ""}</Table.Td>
                    <Table.Td ta="right" style={{ whiteSpace: "nowrap" }}>{nombre(r.ic_bas)} – {nombre(r.ic_haut)}{pourcent ? " %" : ""}</Table.Td>
                    <Table.Td ta="right">± {nombre(r.marge)}{pourcent ? voc(" pts") : ""}</Table.Td>
                    <Table.Td ta="right">
                      {r.n.toLocaleString(locale())}
                      {r.effectif_faible && (
                        <Tooltip label={voc("Moins de 30 répondants : résultat fragile, à interpréter avec prudence.")}>
                          <AlertTriangle size={13} color="var(--mantine-color-orange-7)" style={{ marginLeft: 4, verticalAlign: -2 }} />
                        </Tooltip>
                      )}
                    </Table.Td>
                    <Table.Td ta="right">{r.deff === null ? "—" : nombre(r.deff, 2)}</Table.Td>
                  </Table.Tr>
                ))}
              </Table.Tbody>
            </Table>
          </Table.ScrollContainer>
          <Text size="xs" c="dimmed">
            {voc("Pour suivre ce résultat comme un indicateur, créez un indicateur « Calculé par une formule » avec la mesure « Résultat d'une enquête ».")}
          </Text>
        </Stack>
      )}
    </Stack>
  );
}

/** Données d'enquête : import, plan de sondage et estimations pondérées avec leur marge d'erreur. */
export function EnquetesPage() {
  const { data: enquetes = [], isLoading } = useEnquetes();
  const supprimer = useSupprimerEnquete();
  const [importOuvert, setImportOuvert] = useState(false);
  const [choisie, setChoisie] = useState<number | null>(null);
  const enquete = enquetes.find((e) => e.id === choisie) ?? enquetes[0];
  return (
    <Stack gap="md">
      <Group justify="space-between">
        <div>
          <Title order={2}>{voc("Données d'enquête")}</Title>
          <Text c="dimmed" size="sm">{voc("Proportions, moyennes et totaux pondérés, avec leur marge d'erreur, selon le plan de sondage.")}</Text>
        </div>
        <Button leftSection={<Upload size={16} />} onClick={() => setImportOuvert(true)}>{voc("Importer une enquête")}</Button>
      </Group>
      {isLoading ? <Loader /> : !enquete ? (
        <EmptyState message={voc("Aucune enquête pour l'instant. Importez un fichier de réponses (Excel ou CSV) pour calculer vos résultats.")} />
      ) : (
        <>
          <Card withBorder padding="md" radius="md">
            <Group justify="space-between" align="flex-end">
              <Select label={voc("Enquête")} w={420} allowDeselect={false} data={enquetes.map((e) => ({ value: String(e.id), label: e.titre }))}
                value={String(enquete.id)} onChange={(v) => setChoisie(Number(v))} />
              <Tooltip label={voc("Supprimer l'enquête")}>
                <ActionIcon variant="subtle" color="red" aria-label={voc("Supprimer l'enquête")} onClick={() => confirmerSuppression({
                  message: voc`Supprimer l'enquête « ${enquete.titre} » et toutes ses réponses ?`,
                  onConfirm: async () => { await supprimer.mutateAsync(enquete.id); setChoisie(null); },
                })}><Trash2 size={16} /></ActionIcon>
              </Tooltip>
            </Group>
            <Group gap="xs" mt="sm">
              <Badge variant="light">{voc`${enquete.nombre_reponses.toLocaleString(locale())} réponses`}</Badge>
              <Badge variant="light" color="gray">{voc`${enquete.colonnes.length} colonnes`}</Badge>
              <Badge variant="light" color="gray">{enquete.projet_code || voc("Toute l'organisation")}</Badge>
              <Text size="xs" c="dimmed">{enquete.fichier_source} · {new Date(enquete.created_at).toLocaleDateString(locale())} · {enquete.cree_par_nom}</Text>
            </Group>
            {enquete.colonnes_ecartees.length > 0 && (
              <Text size="xs" c="dimmed" mt={6}>{voc`Colonnes non conservées (données personnelles ou techniques) : ${enquete.colonnes_ecartees.join(", ")}.`}</Text>
            )}
          </Card>
          <Card withBorder padding="md" radius="md">
            <Text fw={600} mb="xs">{voc("Plan de sondage")}</Text>
            <PlanSondage enquete={enquete} />
          </Card>
          <Card withBorder padding="md" radius="md">
            <Text fw={600} mb="xs">{voc("Calculer un résultat")}</Text>
            <Calculateur enquete={enquete} />
          </Card>
        </>
      )}
      <ImportEnquete opened={importOuvert} onClose={() => setImportOuvert(false)} onImportee={(e) => setChoisie(e.id)} />
    </Stack>
  );
}
