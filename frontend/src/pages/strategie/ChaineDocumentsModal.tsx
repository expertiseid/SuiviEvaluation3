import { useState } from "react";
import { ArrowDown, ArrowUp, Download, Plus, Trash2, Upload } from "lucide-react";
import { ActionIcon, Alert, Badge, Button, FileInput, Group, List, Modal, Select, Stack, Table, Tabs, Text, TextInput, Tooltip } from "@mantine/core";
import { notifications } from "@mantine/notifications";
import {
  telechargerChaine,
  useEnregistrerTypeDocument,
  useImporterChaine,
  useSupprimerTypeDocument,
  useTypesDocuments,
} from "../../api/strategy";
import type { ImportChaineResultat, TypeDocument } from "../../types";
import { ICONES_MENU } from "../../utils/iconesMenu";
import { messageErreurApi } from "../../utils/erreurs";
import { confirmerSuppression } from "../../components/common/confirmerSuppression";
import { voc } from "../../utils/vocabulaire";

/** Un maillon : nom, nom de la rubrique du menu et icône, enregistrés en quittant le champ. */
function LigneMaillon({ maillon, rang, total, onMonter, onDescendre }: {
  maillon: TypeDocument;
  rang: number;
  total: number;
  onMonter: () => void;
  onDescendre: () => void;
}) {
  const enregistrer = useEnregistrerTypeDocument();
  const supprimer = useSupprimerTypeDocument();
  const [nom, setNom] = useState(maillon.nom);
  const [pluriel, setPluriel] = useState(maillon.nom_pluriel);

  async function sauver(champs: Partial<TypeDocument>) {
    try {
      await enregistrer.mutateAsync({ id: maillon.id, ...champs });
    } catch (error) {
      notifications.show({ message: messageErreurApi(error, voc("Erreur lors de l'enregistrement")), color: "red" });
    }
  }

  return (
    <Table.Tr>
      <Table.Td w={36}><Badge variant="light" circle>{rang + 1}</Badge></Table.Td>
      <Table.Td>
        <TextInput size="xs" value={nom} onChange={(e) => setNom(e.currentTarget.value)} onBlur={() => nom.trim() && nom !== maillon.nom && sauver({ nom: nom.trim() })} />
      </Table.Td>
      <Table.Td>
        <TextInput size="xs" value={pluriel} onChange={(e) => setPluriel(e.currentTarget.value)} onBlur={() => pluriel.trim() && pluriel !== maillon.nom_pluriel && sauver({ nom_pluriel: pluriel.trim() })} />
      </Table.Td>
      <Table.Td w={150}>
        <Select
          size="xs"
          placeholder={voc("Icône")}
          data={Object.keys(ICONES_MENU)}
          value={maillon.icone || null}
          onChange={(v) => sauver({ icone: v ?? "" })}
          renderOption={({ option }) => {
            const Icone = ICONES_MENU[option.value];
            return <Group gap={6}><Icone size={14} /><Text size="xs">{option.value}</Text></Group>;
          }}
          searchable
          clearable
        />
      </Table.Td>
      <Table.Td w={60} ta="center"><Text size="sm" c="dimmed">{maillon.nombre_documents}</Text></Table.Td>
      <Table.Td w={100}>
        <Group gap={2} wrap="nowrap">
          <ActionIcon size="sm" variant="subtle" disabled={rang === 0} onClick={onMonter} aria-label={voc("Monter")}><ArrowUp size={13} /></ActionIcon>
          <ActionIcon size="sm" variant="subtle" disabled={rang === total - 1} onClick={onDescendre} aria-label={voc("Descendre")}><ArrowDown size={13} /></ActionIcon>
          <Tooltip label={maillon.nombre_documents ? voc("Contient des documents") : voc("Supprimer")}>
            <ActionIcon
              size="sm"
              variant="subtle"
              color="red"
              disabled={maillon.nombre_documents > 0 || total <= 1}
              aria-label={voc("Supprimer")}
              onClick={() =>
                confirmerSuppression({
                  message: voc`Supprimer le maillon « ${maillon.nom} » ?`,
                  onConfirm: async () => {
                    try {
                      await supprimer.mutateAsync(maillon.id);
                    } catch (error) {
                      notifications.show({ message: messageErreurApi(error, voc("Suppression impossible")), color: "red" });
                    }
                  },
                })
              }
            >
              <Trash2 size={13} />
            </ActionIcon>
          </Tooltip>
        </Group>
      </Table.Td>
    </Table.Tr>
  );
}

/** Liste des maillons : renommer, réordonner (flèches), choisir l'icône, ajouter en bas, supprimer s'il est vide. */
function Maillons() {
  const { data: maillons = [] } = useTypesDocuments();
  const enregistrer = useEnregistrerTypeDocument();
  const [nouveau, setNouveau] = useState("");

  async function echanger(i: number, j: number) {
    const [a, b] = [maillons[i], maillons[j]];
    await enregistrer.mutateAsync({ id: a.id, ordre: b.ordre });
    await enregistrer.mutateAsync({ id: b.id, ordre: a.ordre });
  }

  async function ajouter() {
    if (!nouveau.trim()) return;
    const ordre = Math.max(0, ...maillons.map((m) => m.ordre)) + 1;
    await enregistrer.mutateAsync({ nom: nouveau.trim(), nom_pluriel: nouveau.trim(), ordre, icone: "Layers" });
    setNouveau("");
  }

  return (
    <Stack gap="sm">
      <Text size="sm" c="dimmed">
        {voc("De haut en bas : chaque maillon est une rubrique du menu, avec ses propres documents. Un document se rattache à un document d'un maillon au-dessus ; les projets se rattachent au dernier maillon.")}
      </Text>
      <Table withTableBorder verticalSpacing={4}>
        <Table.Thead>
          <Table.Tr>
            <Table.Th />
            <Table.Th>{voc("Maillon")}</Table.Th>
            <Table.Th>{voc("Rubrique du menu")}</Table.Th>
            <Table.Th>{voc("Icône")}</Table.Th>
            <Table.Th ta="center">{voc("Documents")}</Table.Th>
            <Table.Th />
          </Table.Tr>
        </Table.Thead>
        <Table.Tbody>
          {maillons.map((m, i) => (
            <LigneMaillon
              key={`${m.id}-${m.ordre}`}
              maillon={m}
              rang={i}
              total={maillons.length}
              onMonter={() => echanger(i, i - 1)}
              onDescendre={() => echanger(i, i + 1)}
            />
          ))}
        </Table.Tbody>
      </Table>
      <Group gap="xs">
        <TextInput placeholder={voc("Ex : Pilier 3")} value={nouveau} onChange={(e) => setNouveau(e.currentTarget.value)} onKeyDown={(e) => e.key === "Enter" && ajouter()} />
        <Button leftSection={<Plus size={14} />} variant="light" onClick={ajouter} loading={enregistrer.isPending}>
          {voc("Ajouter un maillon en bas")}
        </Button>
      </Group>
    </Stack>
  );
}

/** Modèle, export et import de toute la chaîne en un fichier Excel, avec le compte rendu de l'import. */
function ImportChaine() {
  const importer = useImporterChaine();
  const [fichier, setFichier] = useState<File | null>(null);
  const [resultat, setResultat] = useState<ImportChaineResultat | null>(null);

  async function lancer() {
    if (!fichier) return;
    const donnees = new FormData();
    donnees.append("fichier", fichier);
    try {
      setResultat(await importer.mutateAsync(donnees));
    } catch (error) {
      notifications.show({ message: messageErreurApi(error, voc("Erreur lors de l'import — vérifie le format du fichier.")), color: "red" });
    }
  }

  return (
    <Stack gap="sm">
      <Alert color="blue" variant="light">
        {voc("Un seul fichier pour toute la chaîne : feuille « Maillons » (les rubriques), « Documents » (chaque document et son rattachement) et « Éléments » (la structuration de chaque document et l'élément au-dessus auquel chacun contribue). Réimporter met à jour sans dupliquer.")}
      </Alert>
      <Group gap="xs">
        <Button variant="light" leftSection={<Download size={16} />} onClick={() => telechargerChaine("modele")}>{voc("Télécharger le modèle")}</Button>
        <Button variant="light" leftSection={<Download size={16} />} onClick={() => telechargerChaine("export")}>{voc("Exporter la chaîne actuelle")}</Button>
      </Group>
      <FileInput label={voc("Fichier Excel (.xlsx)")} accept=".xlsx" value={fichier} onChange={setFichier} clearable />
      <Group justify="flex-end">
        <Button leftSection={<Upload size={16} />} onClick={lancer} loading={importer.isPending} disabled={!fichier}>{voc("Importer")}</Button>
      </Group>
      {resultat && (
        <Stack gap={6}>
          <Alert color={resultat.erreurs.length ? "orange" : "green"} variant="light">
            {voc`${resultat.maillons_crees} maillon(s) créé(s) · ${resultat.documents_crees} document(s) créé(s), ${resultat.documents_mis_a_jour} mis à jour · ${resultat.elements_crees} élément(s) créé(s), ${resultat.elements_mis_a_jour} mis à jour`}
          </Alert>
          {resultat.erreurs.length > 0 && (
            <>
              <Text size="sm" fw={600} c="red.7">{voc("Erreurs (lignes ignorées)")}</Text>
              <List size="sm">{resultat.erreurs.map((e, i) => <List.Item key={i}>{voc`Ligne ${e.ligne}`} : {e.message}</List.Item>)}</List>
            </>
          )}
          {resultat.avertissements.length > 0 && (
            <>
              <Text size="sm" fw={600} c="orange.8">{voc("Avertissements")}</Text>
              <List size="sm">{resultat.avertissements.map((e, i) => <List.Item key={i}>{voc`Ligne ${e.ligne}`} : {e.message}</List.Item>)}</List>
            </>
          )}
        </Stack>
      )}
    </Stack>
  );
}

/** Chaîne des documents stratégiques : les maillons (rubriques du menu) et l'import / export Excel. */
export function ChaineDocumentsModal({ opened, onClose }: { opened: boolean; onClose: () => void }) {
  return (
    <Modal opened={opened} onClose={onClose} title={voc("Chaîne des documents stratégiques")} size="xl">
      <Tabs defaultValue="maillons" keepMounted={false}>
        <Tabs.List mb="md">
          <Tabs.Tab value="maillons">{voc("Maillons")}</Tabs.Tab>
          <Tabs.Tab value="excel">{voc("Import / export Excel")}</Tabs.Tab>
        </Tabs.List>
        <Tabs.Panel value="maillons"><Maillons /></Tabs.Panel>
        <Tabs.Panel value="excel"><ImportChaine /></Tabs.Panel>
      </Tabs>
    </Modal>
  );
}
