import { useState } from "react";
import { Download, Search } from "lucide-react";
import { Button, Checkbox, Group, Modal, ScrollArea, SegmentedControl, Stack, Text, TextInput } from "@mantine/core";
import { notifications } from "@mantine/notifications";
import { telechargerExportBeneficiaires } from "../../api/beneficiaries";
import { messageErreurApi } from "../../utils/erreurs";
import { correspond } from "../../utils/recherche";
import { voc } from "../../utils/vocabulaire";

type ProjetExport = { id: number; code: string; nom: string };

/**
 * Export de la liste des bénéficiaires : tous, ou un/plusieurs projets
 * cochés (avec recherche dans la liste des projets), en Excel ou en PDF.
 */
export function ExportBeneficiairesModal({
  opened,
  onClose,
  projets,
}: {
  opened: boolean;
  onClose: () => void;
  projets: ProjetExport[];
}) {
  const [recherche, setRecherche] = useState("");
  const [coches, setCoches] = useState<number[]>([]);
  const [fichier, setFichier] = useState<"excel" | "pdf">("excel");
  const [enCours, setEnCours] = useState(false);

  const visibles = projets.filter((p) => correspond(`${p.code} ${p.nom}`, recherche));
  const tous = coches.length === 0;

  function basculer(id: number) {
    setCoches((c) => (c.includes(id) ? c.filter((x) => x !== id) : [...c, id]));
  }

  async function exporter() {
    setEnCours(true);
    try {
      await telechargerExportBeneficiaires(
        projets.filter((p) => coches.includes(p.id)),
        fichier,
      );
      onClose();
    } catch (error) {
      notifications.show({ message: messageErreurApi(error, voc("Erreur lors de l'export")), color: "red" });
    } finally {
      setEnCours(false);
    }
  }

  return (
    <Modal opened={opened} onClose={onClose} title={voc("Exporter les bénéficiaires")} size="lg">
      <Stack gap="sm">
        <SegmentedControl
          value={fichier}
          onChange={(v) => setFichier(v as "excel" | "pdf")}
          data={[
            { value: "excel", label: voc("Excel (.xlsx)") },
            { value: "pdf", label: voc("PDF") },
          ]}
        />

        <Checkbox
          label={voc("Tous les bénéficiaires (tous les projets, et ceux sans projet)")}
          checked={tous}
          onChange={() => setCoches([])}
          fw={600}
        />

        <Text size="sm" c="dimmed">{voc("Ou cocher un ou plusieurs projets :")}</Text>
        <TextInput
          placeholder={voc("Rechercher un projet par code ou nom…")}
          leftSection={<Search size={15} />}
          value={recherche}
          onChange={(e) => setRecherche(e.currentTarget.value)}
          data-autofocus
        />
        <ScrollArea.Autosize mah={300}>
          <Stack gap="xs">
            {visibles.length === 0 && <Text size="sm" c="dimmed">{voc("Aucun projet ne correspond à la recherche.")}</Text>}
            {visibles.map((p) => (
              <Checkbox
                key={p.id}
                checked={coches.includes(p.id)}
                onChange={() => basculer(p.id)}
                label={
                  <Text size="sm">
                    <Text span fw={600}>{p.code}</Text> — {p.nom}
                  </Text>
                }
              />
            ))}
          </Stack>
        </ScrollArea.Autosize>

        <Group justify="space-between" mt="sm">
          <Text size="sm" c="dimmed">
            {tous
              ? voc("Export de tous les bénéficiaires, une feuille par projet.")
              : coches.length > 1
                ? voc`${coches.length} projets sélectionnés`
                : voc`${coches.length} projet sélectionné`}
          </Text>
          <Button leftSection={<Download size={16} />} onClick={exporter} loading={enCours}>
            {voc("Exporter en")} {fichier === "pdf" ? voc("PDF") : voc("Excel")}
          </Button>
        </Group>
      </Stack>
    </Modal>
  );
}
