import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Download, Pencil } from "lucide-react";
import { ActionIcon, Badge, Box, Button, Group, Menu, Paper, Progress, Stack, Text, Textarea, Tooltip } from "@mantine/core";
import { notifications } from "@mantine/notifications";
import { apiClient } from "../../api/client";
import { useUpdateActivite } from "../../api/projects";
import { telecharger } from "../../api/suivi";
import { messageErreurApi } from "../../utils/erreurs";
import { voc } from "../../utils/vocabulaire";

import { locale, traduireDonnee } from "../../utils/i18n";
interface IndicateurCadre {
  id: number;
  libelle: string;
  unite: string;
  reference: number | null;
  cible: number | null;
  realise: number;
  taux: number | null;
}

interface LigneCadre {
  id: number | null;
  profondeur: number;
  niveau: string;
  code: string;
  libelle: string;
  description: string;
  indicateurs: IndicateurCadre[];
  sources_verification: string;
  hypotheses: string;
  avancement: number | null;
}

// Même code couleur par profondeur que l'export PDF.
const COULEURS = ["teal", "blue", "violet", "orange", "pink", "gray"];
const nombre = (v: number | null) => (v === null ? "—" : v.toLocaleString(locale(), { maximumFractionDigits: 2 }));

function useCadreLogique(projetId: number) {
  return useQuery({
    queryKey: ["cadre-logique", projetId],
    queryFn: async () => (await apiClient.get<{ lignes: LigneCadre[] }>(`/rapports/cadre-logique/${projetId}/`)).data,
  });
}

/** Cellule « sources » ou « hypothèses » : texte, modifiable sur place. */
function CelluleTexte({ ligne, champ, modifiable, onSaved }: { ligne: LigneCadre; champ: "sources_verification" | "hypotheses"; modifiable: boolean; onSaved: () => void }) {
  const modifier = useUpdateActivite();
  const [edition, setEdition] = useState<string | null>(null);
  const valeur = ligne[champ];

  if (edition !== null) {
    return (
      <Stack gap={4}>
        <Textarea value={edition} onChange={(e) => setEdition(e.currentTarget.value)} autosize minRows={2} size="xs" autoFocus />
        <Group gap={4} justify="flex-end">
          <Button size="compact-xs" variant="subtle" onClick={() => setEdition(null)}>{voc("Annuler")}</Button>
          <Button
            size="compact-xs"
            loading={modifier.isPending}
            onClick={async () => {
              try {
                await modifier.mutateAsync({ id: ligne.id!, payload: { [champ]: edition.trim() } });
                setEdition(null);
                onSaved();
              } catch (e) {
                notifications.show({ message: messageErreurApi(e, voc("Erreur lors de l'enregistrement")), color: "red" });
              }
            }}
          >
            {voc("Enregistrer")}
          </Button>
        </Group>
      </Stack>
    );
  }
  return (
    <Group gap={4} wrap="nowrap" align="flex-start" justify="space-between">
      <Text size="xs" c={valeur ? undefined : "dimmed"} style={{ whiteSpace: "pre-wrap" }}>{valeur || "—"}</Text>
      {modifiable && ligne.id !== null && (
        <Tooltip label={voc("Modifier")}>
          <ActionIcon size="xs" variant="subtle" onClick={() => setEdition(valeur)}>
            <Pencil size={11} />
          </ActionIcon>
        </Tooltip>
      )}
    </Group>
  );
}

function Indicateurs({ indicateurs }: { indicateurs: IndicateurCadre[] }) {
  if (indicateurs.length === 0) return <Text size="xs" c="dimmed">—</Text>;
  return (
    <Stack gap={8}>
      {indicateurs.map((i) => (
        <div key={i.id}>
          <Text size="xs" fw={500}>{i.libelle}</Text>
          <Text size="xs" c="dimmed">
            {voc("Réf.")} {nombre(i.reference)} {voc("· Cible")} {nombre(i.cible)} {i.unite} · <b style={{ color: "var(--mantine-color-text)" }}>{voc("Réalisé")} {nombre(i.realise)}</b>
          </Text>
          {i.taux !== null && (
            <Group gap={6} wrap="nowrap">
              <Progress value={Math.min(i.taux, 100)} size="sm" color={i.taux >= 80 ? "teal" : i.taux >= 40 ? "yellow" : "red"} style={{ flex: 1 }} />
              <Text size="xs" w={44} ta="right">{i.taux.toLocaleString(locale())} %</Text>
            </Group>
          )}
        </div>
      ))}
    </Stack>
  );
}

const GRILLE = { display: "grid", gridTemplateColumns: "minmax(220px, 30%) minmax(240px, 34%) 1fr 1fr", gap: 12 } as const;

/** Cadre logique : logique d'intervention, indicateurs, sources de vérification, hypothèses. */
export function CadreLogiqueTab({ projetId, codeProjet, modifiable }: { projetId: number; codeProjet: string; modifiable: boolean }) {
  const { data, isLoading, refetch } = useCadreLogique(projetId);
  if (isLoading || !data) return <Text c="dimmed">{voc("Chargement…")}</Text>;

  return (
    <Stack gap="sm">
      <Group justify="space-between">
        <Text size="sm" c="dimmed" maw={760}>
          {voc("Construit à partir de la planification et des indicateurs rattachés à chaque élément. Les sources de vérification et les hypothèses se saisissent ici, sur chaque ligne.")}
        </Text>
        <Menu position="bottom-end">
          <Menu.Target>
            <Button variant="light" leftSection={<Download size={16} />}>{voc("Exporter")}</Button>
          </Menu.Target>
          <Menu.Dropdown>
            <Menu.Item onClick={() => telecharger(`/rapports/cadre-logique/${projetId}/?fichier=pdf`, `cadre_logique_${codeProjet}.pdf`)}>{voc("PDF")}</Menu.Item>
            <Menu.Item onClick={() => telecharger(`/rapports/cadre-logique/${projetId}/?fichier=docx`, `cadre_logique_${codeProjet}.docx`)}>{voc("Word")}</Menu.Item>
          </Menu.Dropdown>
        </Menu>
      </Group>

      <Box style={{ overflowX: "auto" }}>
        <Box miw={900}>
          <Box style={{ ...GRILLE, padding: "8px 12px", background: "var(--mantine-color-teal-9)", color: "white", borderRadius: "8px 8px 0 0" }}>
            {["Logique d'intervention", voc("Indicateurs (référence, cible, réalisé)"), voc("Sources de vérification"), voc("Hypothèses / risques")].map((t) => (
              <Text key={t} size="xs" fw={700} tt="uppercase">{t}</Text>
            ))}
          </Box>
          {data.lignes.length === 0 && <Text p="md" c="dimmed">{voc("Aucune activité planifiée pour ce projet.")}</Text>}
          {data.lignes.map((l) => {
            const couleur = l.id === null ? "dark" : COULEURS[Math.min(l.profondeur, COULEURS.length - 1)];
            return (
              <Paper
                key={l.id ?? "projet"}
                withBorder
                radius={0}
                p="sm"
                style={{ ...GRILLE, borderTop: 0, borderLeft: `4px solid var(--mantine-color-${couleur}-6)`, background: l.profondeur === 0 ? "var(--mantine-color-gray-0)" : undefined }}
              >
                <div style={{ paddingLeft: l.profondeur * 14 }}>
                  <Badge size="xs" variant="light" color={couleur} mb={4}>{traduireDonnee(l.niveau)}</Badge>
                  <Text size="sm" fw={l.profondeur === 0 ? 700 : 500}>
                    {l.code && <Text span c="dimmed" size="xs" mr={4}>{l.code}</Text>}
                    {l.libelle}
                  </Text>
                  {l.avancement !== null && (
                    <Text size="xs" c="dimmed" mt={2}>{voc("Avancement :")} {l.avancement.toLocaleString(locale())} %</Text>
                  )}
                </div>
                <Indicateurs indicateurs={l.indicateurs} />
                <CelluleTexte ligne={l} champ="sources_verification" modifiable={modifiable} onSaved={() => refetch()} />
                <CelluleTexte ligne={l} champ="hypotheses" modifiable={modifiable} onSaved={() => refetch()} />
              </Paper>
            );
          })}
        </Box>
      </Box>
    </Stack>
  );
}
