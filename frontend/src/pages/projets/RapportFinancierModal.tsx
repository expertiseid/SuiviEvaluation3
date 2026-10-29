import { useState } from "react";
import { FileSpreadsheet, FileText, FileType } from "lucide-react";
import { Button, Checkbox, Group, Modal, SimpleGrid, Stack, Text } from "@mantine/core";
import { DateInput } from "@mantine/dates";
import { notifications } from "@mantine/notifications";
import { telechargerRapportFinancier, type SectionRapportFinancier } from "../../api/suivi";
import { voc } from "../../utils/vocabulaire";

const SECTIONS: { value: SectionRapportFinancier; label: string; description: string }[] = [
  { value: "sources", label: voc("Sources de financement"), description: voc("Fonds propres et bailleurs : montant initial, rallonges, part.") },
  { value: "rallonges", label: voc("Rallonges de fonds"), description: voc("Date, bailleur, montant et motif de chaque rallonge.") },
  { value: "execution", label: voc("Exécution par composante"), description: voc("Prévu, dépensé, taux et solde des grandes composantes.") },
  { value: "detail", label: voc("Détail par élément"), description: voc("Les mêmes chiffres pour chaque niveau de la planification.") },
  { value: "trimestres", label: voc("Dépenses par trimestre"), description: voc("Dépenses et cumul, trimestre par trimestre.") },
];

/** Rapport financier seul : sections et période au choix, en PDF, Word ou Excel. */
export function RapportFinancierModal({ projetId, codeProjet, onClose }: { projetId: number; codeProjet: string; onClose: () => void }) {
  const [sections, setSections] = useState<SectionRapportFinancier[]>(SECTIONS.map((s) => s.value));
  const [debut, setDebut] = useState<string | null>(null);
  const [fin, setFin] = useState<string | null>(null);
  const [enCours, setEnCours] = useState<string | null>(null);

  async function telecharger(fichier: "pdf" | "docx" | "xlsx") {
    if (sections.length === 0) {
      notifications.show({ message: voc("Choisissez au moins une section."), color: "orange" });
      return;
    }
    setEnCours(fichier);
    try {
      await telechargerRapportFinancier(projetId, codeProjet, { fichier, sections, debut, fin });
    } catch {
      notifications.show({ message: voc("Erreur lors de la génération du rapport."), color: "red" });
    } finally {
      setEnCours(null);
    }
  }

  return (
    <Modal opened onClose={onClose} title={voc("Rapport financier")} size="lg">
      <Stack gap="md">
        <div>
          <Text size="sm" fw={600} mb={6}>{voc("Sections")}</Text>
          <Checkbox.Group value={sections} onChange={(v) => setSections(v as SectionRapportFinancier[])}>
            <Stack gap={8}>
              {SECTIONS.map((s) => (
                <Checkbox key={s.value} value={s.value} label={s.label} description={s.description} />
              ))}
            </Stack>
          </Checkbox.Group>
        </div>
        <div>
          <Text size="sm" fw={600}>{voc("Période des dépenses (facultatif)")}</Text>
          <Text size="xs" c="dimmed" mb={6}>{voc("Sans dates, toutes les dépenses saisies sont prises en compte.")}</Text>
          <SimpleGrid cols={{ base: 1, xs: 2 }}>
            <DateInput label={voc("Du")} value={debut} onChange={setDebut} valueFormat="DD/MM/YYYY" clearable />
            <DateInput label={voc("Au")} value={fin} onChange={setFin} valueFormat="DD/MM/YYYY" clearable minDate={debut ?? undefined} />
          </SimpleGrid>
        </div>
        <Group justify="flex-end" gap="xs">
          <Button variant="light" leftSection={<FileText size={15} />} loading={enCours === "pdf"} onClick={() => telecharger("pdf")}>{voc("PDF")}</Button>
          <Button variant="light" leftSection={<FileType size={15} />} loading={enCours === "docx"} onClick={() => telecharger("docx")}>{voc("Word")}</Button>
          <Button variant="light" leftSection={<FileSpreadsheet size={15} />} loading={enCours === "xlsx"} onClick={() => telecharger("xlsx")}>{voc("Excel")}</Button>
        </Group>
      </Stack>
    </Modal>
  );
}
