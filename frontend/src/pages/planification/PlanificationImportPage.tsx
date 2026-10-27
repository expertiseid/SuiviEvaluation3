import { useState } from "react";
import { Link } from "react-router-dom";
import { Download, FileSpreadsheet, Upload } from "lucide-react";
import {
  Alert,
  Badge,
  Button,
  Card,
  FileInput,
  Group,
  List,
  SimpleGrid,
  Stack,
  Text,
  Title,
} from "@mantine/core";
import { notifications } from "@mantine/notifications";
import { useImporterComplet, telechargerModeleImportComplet } from "../../api/planification";
import type { ImportPlanificationCompleteResultat } from "../../types";
import { TitreRubrique } from "../../components/common/TitreRubrique";
import { voc } from "../../utils/vocabulaire";

function CarteImportSepare({
  titre,
  description,
  lien,
}: {
  titre: string;
  description: string;
  lien: string;
}) {
  return (
    <Card withBorder padding="md" radius="md">
      <Text fw={600} size="sm">{titre}</Text>
      <Text size="xs" c="dimmed" mt={4} mb="sm">{description}</Text>
      <Button component={Link} to={lien} variant="light" size="xs" fullWidth>
        Ouvrir cet écran
      </Button>
    </Card>
  );
}

export function PlanificationImportPage() {
  const importer = useImporterComplet();
  const [fichier, setFichier] = useState<File | null>(null);
  const [resultat, setResultat] = useState<ImportPlanificationCompleteResultat | null>(null);

  async function handleImporter() {
    if (!fichier) {
      notifications.show({ message: "Choisis d'abord un fichier Excel.", color: "orange" });
      return;
    }
    const formData = new FormData();
    formData.append("fichier", fichier);
    try {
      const res = await importer.mutateAsync(formData);
      setResultat(res);
      if (res.projet_id) {
        notifications.show({ message: voc`Planification importée — projet « ${res.projet_code} » créé`, color: "green" });
      }
    } catch {
      notifications.show({ message: "Erreur lors de l'import — vérifie le format du fichier.", color: "red" });
    }
  }

  return (
    <Stack gap="lg">
      <div>
        <TitreRubrique route="/planification" defaut="Planification complète" />
        <Text c="dimmed" size="sm">
          {voc("Nous chargeons ici, en un seul classeur Excel, un cadre stratégique complet (objectifs, axes...), un projet (modalités, budget, planification), ses indicateurs et ses bénéficiaires. Pour importer chaque élément séparément, utilise plutôt les écrans listés plus bas.")}</Text>
      </div>

      <Card withBorder padding="lg" radius="md">
        <Group gap="xs" mb="sm">
          <FileSpreadsheet size={18} />
          <Text fw={600}>Import combiné — un seul fichier Excel</Text>
        </Group>

        <Alert color="blue" variant="light" mb="md">
          {voc("Le fichier est un classeur à plusieurs feuilles (Cadre stratégique, Structuration, Projet, Planification, Indicateurs, Bénéficiaires), avec une colonne par niveau pour les hiérarchies. Seule la feuille « Projet » est obligatoire — les autres sections sont ignorées si elles sont laissées vides. Les bénéficiaires importés sont automatiquement inscrits au projet créé.")}</Alert>

        <Button
          variant="light"
          leftSection={<Download size={16} />}
          onClick={() => telechargerModeleImportComplet()}
          mb="md"
        >
          Télécharger le modèle Excel complet
        </Button>

        <Group align="flex-end">
          <FileInput
            label="Fichier à importer"
            placeholder="Choisir un fichier .xlsx"
            accept=".xlsx"
            value={fichier}
            onChange={setFichier}
            style={{ flex: 1 }}
          />
          <Button leftSection={<Upload size={16} />} onClick={handleImporter} loading={importer.isPending}>
            Importer
          </Button>
        </Group>

        {resultat && (
          <Stack gap="xs" mt="md">
            <Alert color={resultat.projet_id ? "green" : "orange"} title="Résultat de l'import">
              <Group gap="xs" mb={6}>
                {resultat.cadre_strategique_id && <Badge variant="light">Cadre : {resultat.cadre_strategique_nom}</Badge>}
                {resultat.projet_id && <Badge variant="light" color="teal">{voc("Projet : ")}{resultat.projet_code}</Badge>}
              </Group>
              <Text size="sm">
                {resultat.elements_strategiques_crees > 0 && (
                  <>· <strong>{resultat.elements_strategiques_crees}</strong> élément(s) stratégique(s) créé(s)<br /></>
                )}
                · <strong>{resultat.elements_crees}</strong> {voc(" élément(s) de planification")}{resultat.niveaux.length > 0 && <> (niveaux : {resultat.niveaux.join(" › ")})</>},{" "}
                <strong>{resultat.sous_activites_creees}</strong> sous-activité(s)
                <br />
                · <strong>{resultat.indicateurs_crees}</strong> {voc(" indicateur(s) créé(s)")}<br />
                · <strong>{resultat.beneficiaires_crees}</strong> {voc(" bénéficiaire(s) créé(s) et inscrit(s) au projet")}{resultat.doublons_detectes > 0 && (
                  <> (dont <strong>{resultat.doublons_detectes}</strong> {voc(" doublon(s) potentiel(s) — à traiter dans \"Doublons signalés\")")}</>
                )}
              </Text>
            </Alert>

            {resultat.erreurs.length > 0 && (
              <Alert color="red" title={`${resultat.erreurs.length} erreur(s)`}>
                <List size="sm">
                  {resultat.erreurs.map((e, i) => (
                    <List.Item key={i}>Ligne {e.ligne} : {e.message}</List.Item>
                  ))}
                </List>
              </Alert>
            )}

            {resultat.avertissements.length > 0 && (
              <Alert color="yellow" title={`${resultat.avertissements.length} avertissement(s)`}>
                <List size="sm">
                  {resultat.avertissements.map((a, i) => (
                    <List.Item key={i}>Ligne {a.ligne} : {a.message}</List.Item>
                  ))}
                </List>
              </Alert>
            )}
          </Stack>
        )}
      </Card>

      <div>
        <Title order={4} mb="sm">Ou importer séparément</Title>
        <SimpleGrid cols={{ base: 1, sm: 2, lg: 4 }}>
          <CarteImportSepare
            titre={voc("Cadre stratégique")}
            description={voc("Ouvre ou crée un cadre stratégique, puis importe sa structuration depuis son propre écran.")}
            lien="/strategie"
          />
          <CarteImportSepare
            titre={voc("Projet")}
            description={voc("Fiche projet + planification (niveaux libres → Sous-activité), sans cadre stratégique ni indicateurs.")}
            lien="/projets"
          />
          <CarteImportSepare
            titre={voc("Indicateurs")}
            description={voc("Indicateurs seuls, rattachés à un projet déjà existant (par son code) ou stratégiques.")}
            lien="/indicateurs"
          />
          <CarteImportSepare
            titre={voc("Bénéficiaires")}
            description={voc("Bénéficiaires seuls, sans inscription automatique à un projet.")}
            lien="/beneficiaires"
          />
        </SimpleGrid>
      </div>
    </Stack>
  );
}
