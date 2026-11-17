import { useEffect, useState, type ReactNode } from "react";
import {
  ActionIcon, Button, ColorInput, Divider, Drawer, Grid, Group, NumberInput, Paper, ScrollArea, SegmentedControl, Select,
  Stack, Switch, Text, TextInput, Title, Tooltip,
} from "@mantine/core";
import { Redo2, RotateCcw, Undo2 } from "lucide-react";
import { ApparenceContext, PALETTES, type ApparenceBloc, type NomPalette } from "../../utils/apparence";
import { voc } from "../../utils/vocabulaire";

/** Supprime les réglages vides : seul ce qui diffère de l'affichage par défaut est enregistré. */
function nettoyer(a: ApparenceBloc): ApparenceBloc {
  const resultat: Record<string, unknown> = {};
  for (const [cle, valeur] of Object.entries(a)) {
    if (valeur === undefined || valeur === "" || valeur === null) continue;
    if (cle === "couleurs" && Object.keys(valeur as object).length === 0) continue;
    resultat[cle] = valeur;
  }
  return resultat as ApparenceBloc;
}

/**
 * Personnaliser un bloc du tableau de bord, avec un aperçu immédiat : titres, mode d'affichage, légende,
 * valeurs, palette et couleur de chaque série ou catégorie, axes, inclinaison des libellés, hauteur,
 * taille du texte, format des nombres, tri. Annuler, rétablir, revenir à l'affichage par défaut.
 */
export function ApparenceBlocDrawer({ opened, onClose, titreDefaut, initiale, noms, apercu, onEnregistrer, enregistrement }: {
  opened: boolean;
  onClose: () => void;
  titreDefaut: string;
  initiale: ApparenceBloc;
  /** Séries et catégories du bloc, pour choisir leur couleur. */
  noms: string[];
  apercu: () => ReactNode;
  onEnregistrer: (apparence: ApparenceBloc) => void;
  enregistrement: boolean;
}) {
  const [historique, setHistorique] = useState<ApparenceBloc[]>([initiale]);
  const [position, setPosition] = useState(0);
  useEffect(() => {
    if (opened) {
      setHistorique([initiale]);
      setPosition(0);
    }
  }, [opened, initiale]);
  const a = historique[position];
  const changer = (modif: Partial<ApparenceBloc>) => {
    const suivant = nettoyer({ ...a, ...modif });
    setHistorique((h) => [...h.slice(0, position + 1), suivant]);
    setPosition((p) => p + 1);
  };
  const couleur = (nom: string, valeur: string) => {
    const couleurs = { ...(a.couleurs ?? {}) };
    if (/^#[0-9a-fA-F]{6}$/.test(valeur)) couleurs[nom] = valeur;
    else delete couleurs[nom];
    changer({ couleurs });
  };

  return (
    <Drawer opened={opened} onClose={onClose} position="right" size="min(1200px, 95vw)" title={<Title order={4}>{voc("Personnaliser le bloc")}</Title>}>
      <Grid gap="lg">
        <Grid.Col span={{ base: 12, md: 5 }}>
          <ScrollArea.Autosize mah="calc(100vh - 170px)" offsetScrollbars>
            <Stack gap="sm">
              <Group justify="space-between">
                <Group gap={4}>
                  <Tooltip label={voc("Annuler")}><ActionIcon variant="default" disabled={position === 0} onClick={() => setPosition((p) => p - 1)}
                    aria-label={voc("Annuler")}><Undo2 size={15} /></ActionIcon></Tooltip>
                  <Tooltip label={voc("Rétablir")}><ActionIcon variant="default" disabled={position === historique.length - 1}
                    onClick={() => setPosition((p) => p + 1)} aria-label={voc("Rétablir")}><Redo2 size={15} /></ActionIcon></Tooltip>
                </Group>
                <Button size="xs" variant="subtle" leftSection={<RotateCcw size={14} />} onClick={() => changer({
                  titre: undefined, sous_titre: undefined, mode: undefined, legende: undefined, valeurs: undefined, quadrillage: undefined,
                  palette: undefined, couleurs: undefined, axe_x: undefined, axe_y: undefined, rotation: undefined, hauteur: undefined,
                  taille_texte: undefined, format: undefined, tri: undefined,
                })}>{voc("Affichage par défaut")}</Button>
              </Group>

              <Divider label={voc("Textes")} labelPosition="left" />
              <TextInput label={voc("Titre")} placeholder={titreDefaut} value={a.titre ?? ""} onChange={(e) => changer({ titre: e.currentTarget.value })} />
              <TextInput label={voc("Sous-titre")} value={a.sous_titre ?? ""} onChange={(e) => changer({ sous_titre: e.currentTarget.value })} />
              <Group grow>
                <TextInput label={voc("Titre de l'axe des catégories")} value={a.axe_x ?? ""} onChange={(e) => changer({ axe_x: e.currentTarget.value })} />
                <TextInput label={voc("Titre de l'axe des valeurs")} value={a.axe_y ?? ""} onChange={(e) => changer({ axe_y: e.currentTarget.value })} />
              </Group>

              <Divider label={voc("Présentation")} labelPosition="left" />
              <div>
                <Text size="sm" fw={500} mb={4}>{voc("Afficher")}</Text>
                <SegmentedControl fullWidth value={a.mode ?? "graphique"} onChange={(v) => changer({ mode: v === "graphique" ? undefined : v as ApparenceBloc["mode"] })}
                  data={[{ value: "graphique", label: voc("Graphique") }, { value: "tableau", label: voc("Tableau") }, { value: "les_deux", label: voc("Les deux") }]} />
              </div>
              <Select label={voc("Légende")} value={a.legende ?? "auto"} allowDeselect={false}
                onChange={(v) => changer({ legende: v === "auto" ? undefined : v as ApparenceBloc["legende"] })}
                data={[{ value: "auto", label: voc("Automatique") }, { value: "masquee", label: voc("Masquée") }, { value: "haut", label: voc("En haut") },
                  { value: "bas", label: voc("En bas") }, { value: "droite", label: voc("À droite") }]} />
              <Group grow>
                <Switch label={voc("Valeurs sur le graphique")} checked={a.valeurs ?? true} onChange={(e) => changer({ valeurs: e.currentTarget.checked ? undefined : false })} />
                <Switch label={voc("Quadrillage")} checked={a.quadrillage ?? true} onChange={(e) => changer({ quadrillage: e.currentTarget.checked ? undefined : false })} />
              </Group>
              <Group grow>
                <Select label={voc("Libellés des catégories")} value={String(a.rotation ?? 0)} allowDeselect={false}
                  onChange={(v) => changer({ rotation: Number(v) ? Number(v) as ApparenceBloc["rotation"] : undefined })}
                  data={[{ value: "0", label: voc("Droits") }, { value: "30", label: "30°" }, { value: "45", label: "45°" }, { value: "90", label: voc("Verticaux") }]} />
                <Select label={voc("Trier")} value={a.tri ?? "aucun"} allowDeselect={false}
                  onChange={(v) => changer({ tri: v === "aucun" ? undefined : v as ApparenceBloc["tri"] })}
                  data={[{ value: "aucun", label: voc("Ordre d'origine") }, { value: "decroissant", label: voc("Du plus grand au plus petit") },
                    { value: "croissant", label: voc("Du plus petit au plus grand") }]} />
              </Group>
              <Select label={voc("Format des nombres")} value={a.format ?? "auto"} allowDeselect={false}
                  onChange={(v) => changer({ format: v === "auto" ? undefined : v as ApparenceBloc["format"] })}
                  data={[{ value: "auto", label: voc("Automatique") }, { value: "entier", label: "1 234 567" }, { value: "court", label: "1,2 M" },
                    { value: "pourcent", label: "45 %" }]} />
              <Group grow>
                <NumberInput label={voc("Hauteur (pixels)")} placeholder={voc("Automatique")} min={160} max={900} step={20} value={a.hauteur ?? ""}
                  onChange={(v) => changer({ hauteur: typeof v === "number" && v >= 160 && v <= 900 ? v : undefined })} />
                <NumberInput label={voc("Taille du texte")} placeholder="13" min={9} max={18} value={a.taille_texte ?? ""}
                  onChange={(v) => changer({ taille_texte: typeof v === "number" && v >= 9 && v <= 18 ? v : undefined })} />
              </Group>

              <Divider label={voc("Couleurs")} labelPosition="left" />
              <Select label={voc("Palette")} value={a.palette ?? "defaut"} allowDeselect={false}
                onChange={(v) => changer({ palette: v === "defaut" ? undefined : v as NomPalette })}
                data={[{ value: "defaut", label: voc("Couleurs d'origine") }, { value: "vive", label: voc("Vive") }, { value: "douce", label: voc("Douce") },
                  { value: "bleus", label: voc("Nuances de bleu") }, { value: "verts", label: voc("Nuances de vert") },
                  { value: "contraste", label: voc("Contrastée (lisible par tous)") }]} />
              {a.palette && a.palette !== "defaut" && (
                <Group gap={4}>{PALETTES[a.palette].map((c) => <div key={c} style={{ width: 18, height: 18, borderRadius: 4, background: c }} />)}</Group>
              )}
              {noms.length > 0 && (
                <Stack gap={6}>
                  <Text size="xs" c="dimmed">{voc("Couleur imposée (laisser vide pour garder la palette) :")}</Text>
                  {noms.slice(0, 40).map((nom) => (
                    <ColorInput key={nom} size="xs" label={nom} value={a.couleurs?.[nom] ?? ""} format="hex" placeholder={voc("Palette")}
                      onChangeEnd={(v) => couleur(nom, v)} />
                  ))}
                </Stack>
              )}
            </Stack>
          </ScrollArea.Autosize>
        </Grid.Col>
        <Grid.Col span={{ base: 12, md: 7 }}>
          <Text size="sm" fw={600} mb="xs">{voc("Aperçu")}</Text>
          <Paper withBorder p="md" radius="md">
            <Title order={4} c="dark.8" style={{ borderLeft: "4px solid var(--mantine-color-teal-6)", paddingLeft: 10 }}>{a.titre || titreDefaut}</Title>
            {a.sous_titre && <Text size="sm" c="dimmed" mt={2}>{a.sous_titre}</Text>}
            <div style={{ marginTop: 12 }}>
              <ApparenceContext.Provider value={a}>{apercu()}</ApparenceContext.Provider>
            </div>
          </Paper>
          <Group justify="flex-end" mt="md">
            <Button variant="default" onClick={onClose}>{voc("Fermer sans enregistrer")}</Button>
            <Button loading={enregistrement} onClick={() => onEnregistrer(a)}>{voc("Enregistrer pour tous")}</Button>
          </Group>
        </Grid.Col>
      </Grid>
    </Drawer>
  );
}
