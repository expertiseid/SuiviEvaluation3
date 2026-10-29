import { Stack, Text } from "@mantine/core";
import { DocumentsTab } from "../../components/documents/DocumentsTab";
import { TitreRubrique } from "../../components/common/TitreRubrique";
import { voc } from "../../utils/vocabulaire";

/**
 * Bibliothèque de documents libres, sans rattachement à un projet, une
 * activité ou une sous-activité précise — pour tout ce qui n'a pas sa place
 * ailleurs (ex : modèles, documents administratifs généraux...).
 */
export function DocumentsGlobauxPage() {
  return (
    <Stack gap="lg">
      <div>
        <TitreRubrique route="/documents" defaut={voc("Documents")} />
        <Text c="dimmed">{voc("Documents libres, sans rattachement à un projet en particulier.")}</Text>
      </div>
      <DocumentsTab />
    </Stack>
  );
}
