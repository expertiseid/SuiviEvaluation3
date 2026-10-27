import { useMemo, useState } from "react";
import { Download, FileSpreadsheet, Search } from "lucide-react";
import {
  Alert,
  Badge,
  Button,
  FileInput,
  Group,
  Modal,
  SegmentedControl,
  Stack,
  Table,
  Text,
} from "@mantine/core";
import { notifications } from "@mantine/notifications";
import {
  analyserCanevasSuivi,
  telechargerCanevasSuivi,
  telechargerRapportErreursCanevas,
  useImporterCanevasSuivi,
  type LigneCanevas,
  type ModeCanevas,
  type ResultatCanevas,
} from "../../api/suivi";
import { messageErreurApi } from "../../utils/erreurs";
import { voc } from "../../utils/vocabulaire";

const STATUTS: Record<LigneCanevas["statut"], { libelle: string; couleur: string }> = {
  ajout: { libelle: "Ajout", couleur: "teal" },
  modification: { libelle: "Modification", couleur: "blue" },
  ignoree: { libelle: "Ignorée", couleur: "gray" },
  erreur: { libelle: "Erreur", couleur: "red" },
};

/**
 * Saisie du suivi en masse par Excel : télécharger le canevas prérempli, le compléter hors
 * ligne, puis le réimporter — aperçu détaillé (ajouts, modifications, erreurs par cellule)
 * avant tout enregistrement.
 */
export function ImportCanevasSuiviModal({
  projetId,
  codeProjet,
  opened,
  onClose,
}: {
  projetId: number;
  codeProjet: string;
  opened: boolean;
  onClose: () => void;
}) {
  const [fichier, setFichier] = useState<File | null>(null);
  const [mode, setMode] = useState<ModeCanevas>("ajout");
  const [apercu, setApercu] = useState<ResultatCanevas | null>(null);
  const [resultat, setResultat] = useState<ResultatCanevas | null>(null);
  const [analyseEnCours, setAnalyseEnCours] = useState(false);
  const [filtre, setFiltre] = useState<"toutes" | LigneCanevas["statut"]>("toutes");
  const importer = useImporterCanevasSuivi();

  const fermer = () => {
    setFichier(null);
    setApercu(null);
    setResultat(null);
    setFiltre("toutes");
    onClose();
  };

  async function analyser(f: File | null = fichier, m: ModeCanevas = mode) {
    if (!f) return;
    setAnalyseEnCours(true);
    setResultat(null);
    try {
      setApercu(await analyserCanevasSuivi(projetId, f, m));
    } catch (error) {
      notifications.show({ message: messageErreurApi(error, "Impossible d'analyser ce fichier"), color: "red" });
    } finally {
      setAnalyseEnCours(false);
    }
  }

  const lignesFiltrees = useMemo(
    () => (apercu?.lignes ?? []).filter((l) => filtre === "toutes" || l.statut === filtre),
    [apercu, filtre],
  );
  const aEnregistrer = apercu ? apercu.totaux.ajout + apercu.totaux.modification : 0;

  return (
    <Modal opened={opened} onClose={fermer} title={voc("Saisie du suivi par Excel")} size="xl">
      <Stack gap="sm">
        <Text size="sm" c="dimmed">
          {voc("1. Télécharge le canevas prérempli avec la planification du projet et ses indicateurs. 2. Complète les colonnes bleues hors ligne. 3. Réimporte-le : un aperçu montre ce qui sera ajouté ou modifié, et les cellules en erreur, avant tout enregistrement.")}
        </Text>
        <Group>
          <Button variant="light" leftSection={<Download size={16} />} onClick={() => telechargerCanevasSuivi(projetId, codeProjet)}>
            {voc("Télécharger le canevas de suivi")}
          </Button>
        </Group>

        <Group align="flex-end" gap="sm">
          <FileInput
            label="Canevas complété"
            placeholder="Choisir un fichier .xlsx"
            accept=".xlsx"
            leftSection={<FileSpreadsheet size={16} />}
            value={fichier}
            onChange={(f) => {
              setFichier(f);
              setApercu(null);
              setResultat(null);
            }}
            style={{ flex: 1 }}
          />
          <Stack gap={2}>
            <Text size="sm" fw={500}>Saisies déjà existantes</Text>
            <SegmentedControl
              value={mode}
              onChange={(v) => {
                setMode(v as ModeCanevas);
                if (fichier && apercu) analyser(fichier, v as ModeCanevas);
              }}
              data={[
                { value: "ajout", label: "Conserver (ajouter seulement)" },
                { value: "mise_a_jour", label: "Mettre à jour" },
              ]}
            />
          </Stack>
          <Button leftSection={<Search size={16} />} disabled={!fichier} loading={analyseEnCours} onClick={() => analyser()}>
            Analyser
          </Button>
        </Group>

        {apercu && !resultat && (
          <>
            {apercu.erreurs_generales.map((m) => (
              <Alert key={m} color="red" variant="light">
                {m}
              </Alert>
            ))}
            <Group gap="xs">
              {(["toutes", "ajout", "modification", "ignoree", "erreur"] as const).map((cle) => (
                <Badge
                  key={cle}
                  size="lg"
                  variant={filtre === cle ? "filled" : "light"}
                  color={cle === "toutes" ? "dark" : STATUTS[cle].couleur}
                  style={{ cursor: "pointer" }}
                  onClick={() => setFiltre(cle)}
                >
                  {cle === "toutes"
                    ? `Toutes : ${apercu.lignes.length}`
                    : `${STATUTS[cle].libelle} : ${apercu.totaux[cle]}`}
                </Badge>
              ))}
            </Group>
            {apercu.lignes.length === 0 ? (
              <Text size="sm" c="dimmed">Aucune saisie trouvée dans le fichier.</Text>
            ) : (
              <Table.ScrollContainer minWidth={700} mah={360}>
                <Table striped withTableBorder verticalSpacing={4} fz="sm">
                  <Table.Thead>
                    <Table.Tr>
                      <Table.Th w={150}>Feuille / ligne</Table.Th>
                      <Table.Th>Élément</Table.Th>
                      <Table.Th w={110}>Résultat</Table.Th>
                      <Table.Th>Détail</Table.Th>
                    </Table.Tr>
                  </Table.Thead>
                  <Table.Tbody>
                    {lignesFiltrees.map((l) => (
                      <Table.Tr key={`${l.feuille}-${l.ligne}`}>
                        <Table.Td>
                          {l.feuille} · {l.ligne}
                        </Table.Td>
                        <Table.Td>
                          <Text size="sm">{l.libelle || l.identifiant || "—"}</Text>
                          {l.identifiant && <Text size="xs" c="dimmed">{l.identifiant}</Text>}
                        </Table.Td>
                        <Table.Td>
                          <Badge color={STATUTS[l.statut].couleur} variant="light">
                            {STATUTS[l.statut].libelle}
                          </Badge>
                        </Table.Td>
                        <Table.Td>
                          {l.erreurs.map((e) => (
                            <Text key={e.colonne + e.message} size="xs" c="red">
                              « {e.colonne} » : {e.message}
                            </Text>
                          ))}
                          {l.actions.map((a) => (
                            <Text key={a} size="xs">
                              {a}
                            </Text>
                          ))}
                        </Table.Td>
                      </Table.Tr>
                    ))}
                  </Table.Tbody>
                </Table>
              </Table.ScrollContainer>
            )}
            <Group justify="space-between">
              {apercu.totaux.erreur > 0 ? (
                <Button
                  variant="subtle"
                  color="red"
                  leftSection={<Download size={16} />}
                  onClick={() => fichier && telechargerRapportErreursCanevas(projetId, fichier, mode)}
                >
                  Télécharger le rapport d'erreurs
                </Button>
              ) : (
                <span />
              )}
              <Button
                disabled={aEnregistrer === 0}
                loading={importer.isPending}
                onClick={() =>
                  fichier &&
                  importer.mutate(
                    { projetId, fichier, mode },
                    {
                      onSuccess: (r) => {
                        setResultat(r);
                        notifications.show({ message: "Suivi importé", color: "green" });
                      },
                      onError: (error) =>
                        notifications.show({ message: messageErreurApi(error, "Erreur lors de l'import"), color: "red" }),
                    },
                  )
                }
              >
                {aEnregistrer === 0
                  ? "Rien à enregistrer"
                  : `Valider l'import (${aEnregistrer} ligne${aEnregistrer > 1 ? "s" : ""})`}
              </Button>
            </Group>
            {apercu.totaux.erreur > 0 && aEnregistrer > 0 && (
              <Text size="xs" c="dimmed">Les lignes en erreur ne seront pas enregistrées.</Text>
            )}
          </>
        )}

        {resultat && (
          <Alert color="green" title="Import terminé">
            {resultat.totaux.ajout} ajout(s), {resultat.totaux.modification} modification(s) enregistré(s)
            {resultat.totaux.erreur > 0 ? `, ${resultat.totaux.erreur} ligne(s) en erreur ignorée(s)` : ""}
            {voc(". Les taux d'exécution sont recalculés.")}
          </Alert>
        )}
      </Stack>
    </Modal>
  );
}
