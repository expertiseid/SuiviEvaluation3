import { useState } from "react";
import {
  Alert, Badge, Button, Checkbox, FileInput, Group, Image, Loader, Modal, NumberInput, Select, Stack, Table, Tabs, Text, Textarea,
  TextInput,
} from "@mantine/core";
import { DatePickerInput } from "@mantine/dates";
import { notifications } from "@mantine/notifications";
import { ExternalLink, ImagePlus, Pencil, Plus, Trash2 } from "lucide-react";
import {
  type ActualiteSite, LANGUES_SITE, type LangueSite, type PartenaireSite, useActualitesSite, useEnregistrerSite, usePartenairesSite,
  useSupprimerSite,
} from "../../api/siteVitrine";
import { confirmerSuppression } from "../../components/common/confirmerSuppression";
import { messageErreurApi } from "../../utils/erreurs";
import { locale } from "../../utils/i18n";
import { voc } from "../../utils/vocabulaire";
import { erreursParChamp } from "../plaintes/saisieRetour";

const NOM_LANGUE: Record<LangueSite, string> = { en: "English", ar: "العربية", es: "Español", de: "Deutsch", it: "Italiano" };
const ADRESSE_SITE = (import.meta.env.VITE_URL_SITE as string | undefined) || "http://localhost:5193";
const date = (d: string) => new Date(d + "T12:00:00").toLocaleDateString(locale());
const CATEGORIES = () => [
  { value: "FINANCIER", label: voc("Partenaire financier") }, { value: "TECHNIQUE", label: voc("Partenaire technique") },
  { value: "INSTITUTION", label: voc("Institution") }, { value: "CLIENT", label: voc("Organisation utilisatrice") },
];

/** Image (ou logo) : aperçu de l'actuelle, nouvelle à choisir, ou retrait. */
function ChampImage({ actuelle, fichier, setFichier, retirer, setRetirer, label }: {
  actuelle: string | null; fichier: File | null; setFichier: (f: File | null) => void; retirer: boolean; setRetirer: (v: boolean) => void; label: string;
}) {
  return (
    <Stack gap={6}>
      <Group align="flex-end" gap="sm">
        {actuelle && !retirer && !fichier && <Image src={actuelle} h={56} w="auto" maw={140} fit="contain" radius="sm" alt="" />}
        <FileInput label={label} accept="image/png,image/jpeg,image/webp" value={fichier} onChange={setFichier} clearable
          leftSection={<ImagePlus size={16} />} placeholder={voc("PNG, JPEG ou WEBP, 3 Mo au plus")} style={{ flex: 1 }} />
      </Group>
      {actuelle && !fichier && <Checkbox size="xs" checked={retirer} onChange={(e) => setRetirer(e.currentTarget.checked)} label={voc("Retirer l'image actuelle")} />}
    </Stack>
  );
}

function ActualiteModal({ actu, onClose }: { actu: ActualiteSite | null; onClose: () => void }) {
  const enregistrer = useEnregistrerSite("actualites");
  const [v, setV] = useState({
    titre: actu?.titre ?? "", resume: actu?.resume ?? "", contenu: actu?.contenu ?? "", lien: actu?.lien ?? "",
    date_publication: actu?.date_publication ?? new Date().toISOString().slice(0, 10), publiee: actu?.publiee ?? false,
  });
  const [traductions, setTraductions] = useState<ActualiteSite["traductions"]>(actu?.traductions ?? {});
  const [fichier, setFichier] = useState<File | null>(null);
  const [retirer, setRetirer] = useState(false);
  const [erreurs, setErreurs] = useState<Record<string, string>>({});
  const traduire = (l: LangueSite, champ: "titre" | "resume" | "contenu", valeur: string) =>
    setTraductions((t) => ({ ...t, [l]: { ...(t[l] ?? {}), [champ]: valeur } }));

  const valider = async () => {
    setErreurs({});
    try {
      await enregistrer.mutateAsync({
        id: actu?.id, champs: { ...v, traductions, supprimer_image: retirer || undefined },
        fichier: fichier ? { nom: "image", valeur: fichier } : undefined,
      });
      notifications.show({ color: "teal", message: v.publiee ? voc("Actualité publiée sur le site") : voc("Brouillon enregistré") });
      onClose();
    } catch (error) {
      const parChamp = erreursParChamp(error);
      setErreurs(Object.keys(parChamp).length ? parChamp : { detail: messageErreurApi(error, voc("L'enregistrement n'a pas abouti.")) });
    }
  };

  return (
    <Modal opened onClose={onClose} title={actu ? voc("Modifier l'actualité") : voc("Nouvelle actualité")} size="xl">
      <Stack gap="sm">
        {erreurs.detail && <Alert color="red">{erreurs.detail}</Alert>}
        <Tabs defaultValue="fr">
          <Tabs.List>
            <Tabs.Tab value="fr">Français</Tabs.Tab>
            {LANGUES_SITE.map((l) => <Tabs.Tab key={l} value={l}>{NOM_LANGUE[l]}</Tabs.Tab>)}
          </Tabs.List>
          <Tabs.Panel value="fr" pt="sm">
            <Stack gap="sm">
              <TextInput label={voc("Titre")} withAsterisk value={v.titre} error={erreurs.titre} onChange={(e) => setV({ ...v, titre: e.currentTarget.value })} />
              <Textarea label={voc("Résumé")} description={voc("Une ou deux phrases, affichées dans la liste.")} autosize minRows={2}
                value={v.resume} onChange={(e) => setV({ ...v, resume: e.currentTarget.value })} />
              <Textarea label={voc("Texte")} description={voc("Paragraphes séparés par une ligne vide.")} autosize minRows={6}
                value={v.contenu} onChange={(e) => setV({ ...v, contenu: e.currentTarget.value })} />
            </Stack>
          </Tabs.Panel>
          {LANGUES_SITE.map((l) => (
            <Tabs.Panel key={l} value={l} pt="sm" dir={l === "ar" ? "rtl" : undefined}>
              <Stack gap="sm">
                <Text size="xs" c="dimmed">{voc("Facultatif : sans traduction, le site affiche le français.")}</Text>
                <TextInput label={voc("Titre")} value={traductions[l]?.titre ?? ""} onChange={(e) => traduire(l, "titre", e.currentTarget.value)} />
                <Textarea label={voc("Résumé")} autosize minRows={2} value={traductions[l]?.resume ?? ""} onChange={(e) => traduire(l, "resume", e.currentTarget.value)} />
                <Textarea label={voc("Texte")} autosize minRows={6} value={traductions[l]?.contenu ?? ""} onChange={(e) => traduire(l, "contenu", e.currentTarget.value)} />
              </Stack>
            </Tabs.Panel>
          ))}
        </Tabs>
        <Group grow align="flex-start">
          <DatePickerInput label={voc("Date de publication")} value={v.date_publication} valueFormat="DD/MM/YYYY"
            onChange={(d) => setV({ ...v, date_publication: d ?? v.date_publication })} />
          <TextInput label={voc("Lien « En savoir plus » (facultatif)")} placeholder="https://…" value={v.lien} error={erreurs.lien}
            onChange={(e) => setV({ ...v, lien: e.currentTarget.value })} />
        </Group>
        <ChampImage actuelle={actu?.image ?? null} fichier={fichier} setFichier={setFichier} retirer={retirer} setRetirer={setRetirer} label={voc("Image")} />
        {erreurs.image && <Text size="xs" c="red">{erreurs.image}</Text>}
        <Checkbox checked={v.publiee} onChange={(e) => setV({ ...v, publiee: e.currentTarget.checked })}
          label={voc("Publiée sur le site (sinon : brouillon, invisible)")} />
        <Group justify="flex-end">
          <Button variant="default" onClick={onClose}>{voc("Annuler")}</Button>
          <Button onClick={valider} loading={enregistrer.isPending} disabled={!v.titre.trim()}>{voc("Enregistrer")}</Button>
        </Group>
      </Stack>
    </Modal>
  );
}

export function ActualitesSite() {
  const { data: actus = [], isLoading } = useActualitesSite();
  const supprimer = useSupprimerSite("actualites");
  const [edition, setEdition] = useState<ActualiteSite | "nouvelle" | null>(null);
  if (isLoading) return <Loader size="sm" />;
  const retirer = (a: ActualiteSite) => confirmerSuppression({
    message: voc`Supprimer l'actualité « ${a.titre} » ? Elle disparaît du site.`,
    onConfirm: async () => {
      try { await supprimer.mutateAsync(a.id); } catch (error) { notifications.show({ color: "red", message: messageErreurApi(error, voc("Erreur")) }); }
    },
  });
  return (
    <Stack gap="sm">
      <Group justify="space-between">
        <Text size="sm" c="dimmed">{voc("Page « Notre actualité » du site vitrine.")}{" "}
          <a href={`${ADRESSE_SITE}/actualites.html`} target="_blank" rel="noopener">{voc("Voir la page")} <ExternalLink size={12} /></a>
        </Text>
        <Button leftSection={<Plus size={16} />} onClick={() => setEdition("nouvelle")}>{voc("Nouvelle actualité")}</Button>
      </Group>
      <Table withTableBorder striped verticalSpacing="sm">
        <Table.Thead>
          <Table.Tr>
            <Table.Th>{voc("Date")}</Table.Th><Table.Th>{voc("Titre")}</Table.Th><Table.Th>{voc("Traductions")}</Table.Th>
            <Table.Th>{voc("État")}</Table.Th><Table.Th w={110} />
          </Table.Tr>
        </Table.Thead>
        <Table.Tbody>
          {actus.map((a) => (
            <Table.Tr key={a.id}>
              <Table.Td><Text size="sm">{date(a.date_publication)}</Text></Table.Td>
              <Table.Td><Text size="sm" fw={600}>{a.titre}</Text>{a.resume && <Text size="xs" c="dimmed" lineClamp={1}>{a.resume}</Text>}</Table.Td>
              <Table.Td><Text size="xs">{["FR", ...LANGUES_SITE.filter((l) => a.traductions[l]?.titre).map((l) => l.toUpperCase())].join(" · ")}</Text></Table.Td>
              <Table.Td><Badge variant="light" color={a.publiee ? "teal" : "gray"}>{a.publiee ? voc("Publiée") : voc("Brouillon")}</Badge></Table.Td>
              <Table.Td>
                <Group gap={4} justify="flex-end" wrap="nowrap">
                  <Button size="compact-xs" variant="subtle" onClick={() => setEdition(a)} aria-label={voc("Modifier")}><Pencil size={14} /></Button>
                  <Button size="compact-xs" variant="subtle" color="red" onClick={() => retirer(a)} aria-label={voc("Supprimer")}><Trash2 size={14} /></Button>
                </Group>
              </Table.Td>
            </Table.Tr>
          ))}
          {actus.length === 0 && <Table.Tr><Table.Td colSpan={5}><Text size="sm" c="dimmed">{voc("Aucune actualité pour l'instant.")}</Text></Table.Td></Table.Tr>}
        </Table.Tbody>
      </Table>
      {edition && <ActualiteModal key={edition === "nouvelle" ? 0 : edition.id} actu={edition === "nouvelle" ? null : edition} onClose={() => setEdition(null)} />}
    </Stack>
  );
}

function PartenaireModal({ partenaire, onClose }: { partenaire: PartenaireSite | null; onClose: () => void }) {
  const enregistrer = useEnregistrerSite("partenaires");
  const [v, setV] = useState({
    nom: partenaire?.nom ?? "", categorie: partenaire?.categorie ?? "TECHNIQUE", description: partenaire?.description ?? "",
    site_web: partenaire?.site_web ?? "", ordre: partenaire?.ordre ?? 0, visible: partenaire?.visible ?? true,
  });
  const [traductions, setTraductions] = useState<PartenaireSite["traductions"]>(partenaire?.traductions ?? {});
  const [fichier, setFichier] = useState<File | null>(null);
  const [retirer, setRetirer] = useState(false);
  const [erreurs, setErreurs] = useState<Record<string, string>>({});

  const valider = async () => {
    setErreurs({});
    try {
      await enregistrer.mutateAsync({
        id: partenaire?.id, champs: { ...v, traductions, supprimer_logo: retirer || undefined },
        fichier: fichier ? { nom: "logo", valeur: fichier } : undefined,
      });
      onClose();
    } catch (error) {
      const parChamp = erreursParChamp(error);
      setErreurs(Object.keys(parChamp).length ? parChamp : { detail: messageErreurApi(error, voc("L'enregistrement n'a pas abouti.")) });
    }
  };

  return (
    <Modal opened onClose={onClose} title={partenaire ? voc("Modifier le partenaire") : voc("Nouveau partenaire")} size="lg">
      <Stack gap="sm">
        {erreurs.detail && <Alert color="red">{erreurs.detail}</Alert>}
        <Group grow align="flex-start">
          <TextInput label={voc("Nom")} withAsterisk value={v.nom} error={erreurs.nom} onChange={(e) => setV({ ...v, nom: e.currentTarget.value })} />
          <Select label={voc("Catégorie")} data={CATEGORIES()} value={v.categorie} allowDeselect={false}
            onChange={(c) => setV({ ...v, categorie: (c ?? "TECHNIQUE") as PartenaireSite["categorie"] })} />
        </Group>
        <Tabs defaultValue="fr">
          <Tabs.List>
            <Tabs.Tab value="fr">Français</Tabs.Tab>
            {LANGUES_SITE.map((l) => <Tabs.Tab key={l} value={l}>{NOM_LANGUE[l]}</Tabs.Tab>)}
          </Tabs.List>
          <Tabs.Panel value="fr" pt="sm">
            <Textarea label={voc("Description (facultative)")} autosize minRows={2} value={v.description} onChange={(e) => setV({ ...v, description: e.currentTarget.value })} />
          </Tabs.Panel>
          {LANGUES_SITE.map((l) => (
            <Tabs.Panel key={l} value={l} pt="sm" dir={l === "ar" ? "rtl" : undefined}>
              <Textarea label={voc("Description")} autosize minRows={2} value={traductions[l]?.description ?? ""}
                onChange={(e) => { const valeur = e.currentTarget.value; setTraductions((t) => ({ ...t, [l]: { description: valeur } })); }} />
            </Tabs.Panel>
          ))}
        </Tabs>
        <Group grow align="flex-start">
          <TextInput label={voc("Site web (facultatif)")} placeholder="https://…" value={v.site_web} error={erreurs.site_web}
            onChange={(e) => setV({ ...v, site_web: e.currentTarget.value })} />
          <NumberInput label={voc("Ordre d'affichage")} min={0} value={v.ordre} onChange={(n) => setV({ ...v, ordre: Number(n) || 0 })} />
        </Group>
        <ChampImage actuelle={partenaire?.logo ?? null} fichier={fichier} setFichier={setFichier} retirer={retirer} setRetirer={setRetirer} label={voc("Logo")} />
        {erreurs.logo && <Text size="xs" c="red">{erreurs.logo}</Text>}
        <Checkbox checked={v.visible} onChange={(e) => setV({ ...v, visible: e.currentTarget.checked })} label={voc("Visible sur le site")} />
        <Group justify="flex-end">
          <Button variant="default" onClick={onClose}>{voc("Annuler")}</Button>
          <Button onClick={valider} loading={enregistrer.isPending} disabled={!v.nom.trim()}>{voc("Enregistrer")}</Button>
        </Group>
      </Stack>
    </Modal>
  );
}

export function PartenairesSite() {
  const { data: partenaires = [], isLoading } = usePartenairesSite();
  const supprimer = useSupprimerSite("partenaires");
  const [edition, setEdition] = useState<PartenaireSite | "nouveau" | null>(null);
  if (isLoading) return <Loader size="sm" />;
  const retirer = (p: PartenaireSite) => confirmerSuppression({
    message: voc`Supprimer le partenaire « ${p.nom} » ? Il disparaît du site.`,
    onConfirm: async () => {
      try { await supprimer.mutateAsync(p.id); } catch (error) { notifications.show({ color: "red", message: messageErreurApi(error, voc("Erreur")) }); }
    },
  });
  return (
    <Stack gap="sm">
      <Group justify="space-between">
        <Text size="sm" c="dimmed">{voc("Page « Nos partenaires » du site vitrine.")}{" "}
          <a href={`${ADRESSE_SITE}/partenaires.html`} target="_blank" rel="noopener">{voc("Voir la page")} <ExternalLink size={12} /></a>
        </Text>
        <Button leftSection={<Plus size={16} />} onClick={() => setEdition("nouveau")}>{voc("Nouveau partenaire")}</Button>
      </Group>
      <Table withTableBorder striped verticalSpacing="sm">
        <Table.Thead>
          <Table.Tr>
            <Table.Th w={90}>{voc("Logo")}</Table.Th><Table.Th>{voc("Nom")}</Table.Th><Table.Th>{voc("Catégorie")}</Table.Th>
            <Table.Th>{voc("Ordre")}</Table.Th><Table.Th>{voc("État")}</Table.Th><Table.Th w={110} />
          </Table.Tr>
        </Table.Thead>
        <Table.Tbody>
          {partenaires.map((p) => (
            <Table.Tr key={p.id}>
              <Table.Td>{p.logo ? <Image src={p.logo} h={34} w="auto" maw={80} fit="contain" alt="" /> : <Text size="xs" c="dimmed">—</Text>}</Table.Td>
              <Table.Td><Text size="sm" fw={600}>{p.nom}</Text>{p.site_web && <Text size="xs" c="dimmed">{p.site_web}</Text>}</Table.Td>
              <Table.Td><Text size="sm">{voc(p.categorie_libelle)}</Text></Table.Td>
              <Table.Td><Text size="sm">{p.ordre}</Text></Table.Td>
              <Table.Td><Badge variant="light" color={p.visible ? "teal" : "gray"}>{p.visible ? voc("Visible") : voc("Masqué")}</Badge></Table.Td>
              <Table.Td>
                <Group gap={4} justify="flex-end" wrap="nowrap">
                  <Button size="compact-xs" variant="subtle" onClick={() => setEdition(p)} aria-label={voc("Modifier")}><Pencil size={14} /></Button>
                  <Button size="compact-xs" variant="subtle" color="red" onClick={() => retirer(p)} aria-label={voc("Supprimer")}><Trash2 size={14} /></Button>
                </Group>
              </Table.Td>
            </Table.Tr>
          ))}
          {partenaires.length === 0 && <Table.Tr><Table.Td colSpan={6}><Text size="sm" c="dimmed">{voc("Aucun partenaire pour l'instant.")}</Text></Table.Td></Table.Tr>}
        </Table.Tbody>
      </Table>
      {edition && <PartenaireModal key={edition === "nouveau" ? 0 : edition.id} partenaire={edition === "nouveau" ? null : edition} onClose={() => setEdition(null)} />}
    </Stack>
  );
}
