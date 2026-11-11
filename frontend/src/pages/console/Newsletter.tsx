import { useState } from "react";
import {
  Alert, Badge, Button, Group, Loader, Modal, Progress, Select, SimpleGrid, Stack, Table, Tabs, Text, Textarea, TextInput,
} from "@mantine/core";
import { notifications } from "@mantine/notifications";
import { Download, Mail, Pencil, Plus, Send, Trash2 } from "lucide-react";
import {
  type EnvoiNewsletter, LANGUES_SITE, type LangueSite, exporterAbonnesNewsletter, useAbonnesNewsletter, useEnvoisNewsletter,
  useNewsletter, useResumeNewsletter,
} from "../../api/siteVitrine";
import { confirmerSuppression } from "../../components/common/confirmerSuppression";
import { messageErreurApi } from "../../utils/erreurs";
import { locale } from "../../utils/i18n";
import { voc } from "../../utils/vocabulaire";

const NOM_LANGUE: Record<string, string> = { fr: "Français", en: "English", ar: "العربية", es: "Español", de: "Deutsch", it: "Italiano" };
const jour = (d: string | null) => (d ? new Date(d).toLocaleString(locale(), { dateStyle: "short", timeStyle: "short" }) : "—");
const STATUTS_ABONNE = { ACTIF: ["teal", "Actif"], EN_ATTENTE: ["yellow", "En attente de confirmation"], DESINSCRIT: ["gray", "Désinscrit"] } as const;
const STATUTS_ENVOI = { BROUILLON: ["gray", "Brouillon"], EN_COURS: ["blue", "Envoi en cours"], ENVOYE: ["teal", "Envoyée"] } as const;

/** Rédaction d'une newsletter : français, traductions facultatives (l'abonné reçoit sa langue, sinon le français). */
function EnvoiModal({ envoi, onClose }: { envoi: EnvoiNewsletter | null; onClose: () => void }) {
  const { enregistrer } = useNewsletter();
  const [sujet, setSujet] = useState(envoi?.sujet ?? "");
  const [contenu, setContenu] = useState(envoi?.contenu ?? "");
  const [traductions, setTraductions] = useState<EnvoiNewsletter["traductions"]>(envoi?.traductions ?? {});
  const [envoiEnCours, setEnvoiEnCours] = useState(false);
  const traduire = (l: LangueSite, champ: "sujet" | "contenu", valeur: string) =>
    setTraductions((t) => ({ ...t, [l]: { ...(t[l] ?? {}), [champ]: valeur } }));

  const valider = async () => {
    setEnvoiEnCours(true);
    try {
      await enregistrer(envoi?.id, { sujet, contenu, traductions });
      notifications.show({ color: "teal", message: voc("Brouillon enregistré") });
      onClose();
    } catch (erreur) {
      notifications.show({ color: "red", message: messageErreurApi(erreur, voc("L'enregistrement n'a pas abouti.")) });
    } finally {
      setEnvoiEnCours(false);
    }
  };

  return (
    <Modal opened onClose={onClose} size="xl" title={envoi ? voc("Modifier la newsletter") : voc("Nouvelle newsletter")}>
      <Tabs defaultValue="fr">
        <Tabs.List mb="sm">
          <Tabs.Tab value="fr">Français</Tabs.Tab>
          {LANGUES_SITE.map((l) => <Tabs.Tab key={l} value={l}>{NOM_LANGUE[l]}</Tabs.Tab>)}
        </Tabs.List>
        <Tabs.Panel value="fr">
          <Stack gap="sm">
            <TextInput label={voc("Objet du courriel")} required value={sujet} onChange={(e) => setSujet(e.currentTarget.value)} maxLength={200} />
            <Textarea label={voc("Texte")} required autosize minRows={10} value={contenu} onChange={(e) => setContenu(e.currentTarget.value)}
              description={voc("Paragraphes séparés par une ligne vide. Un lien de désinscription est ajouté automatiquement en bas.")} />
          </Stack>
        </Tabs.Panel>
        {LANGUES_SITE.map((l) => (
          <Tabs.Panel key={l} value={l}>
            <Stack gap="sm" dir={l === "ar" ? "rtl" : undefined}>
              <Text size="sm" c="dimmed">{voc("Facultatif : sans traduction, les abonnés de cette langue reçoivent le français.")}</Text>
              <TextInput label={voc("Objet du courriel")} value={traductions[l]?.sujet ?? ""} onChange={(e) => traduire(l, "sujet", e.currentTarget.value)} />
              <Textarea label={voc("Texte")} autosize minRows={8} value={traductions[l]?.contenu ?? ""} onChange={(e) => traduire(l, "contenu", e.currentTarget.value)} />
            </Stack>
          </Tabs.Panel>
        ))}
      </Tabs>
      <Group justify="flex-end" mt="md">
        <Button variant="default" onClick={onClose}>{voc("Annuler")}</Button>
        <Button onClick={valider} loading={envoiEnCours} disabled={!sujet.trim() || !contenu.trim()}>{voc("Enregistrer le brouillon")}</Button>
      </Group>
    </Modal>
  );
}

/** Envoi définitif : confirmation dans la page (nombre d'abonnés), puis envoi en arrière-plan. */
function ConfirmerEnvoi({ envoi, actifs, onClose }: { envoi: EnvoiNewsletter; actifs: number; onClose: () => void }) {
  const { envoyer } = useNewsletter();
  const [enCours, setEnCours] = useState(false);
  const lancer = async () => {
    setEnCours(true);
    try {
      await envoyer(envoi.id);
      notifications.show({ color: "teal", message: voc("Envoi lancé : la progression s'affiche dans la liste.") });
      onClose();
    } catch (erreur) {
      notifications.show({ color: "red", message: messageErreurApi(erreur, voc("L'envoi n'a pas pu être lancé.")) });
      setEnCours(false);
    }
  };
  return (
    <Modal opened onClose={onClose} title={voc("Envoyer la newsletter")}>
      <Stack gap="sm">
        <Text>{voc`« ${envoi.sujet} » sera envoyée à ${actifs} abonné(s) confirmé(s), chacun dans sa langue. L'envoi ne peut pas être annulé ni refait.`}</Text>
        <Text size="sm" c="dimmed">{voc("Conseil : envoyez-vous d'abord un essai pour vérifier le texte.")}</Text>
        <Group justify="flex-end">
          <Button variant="default" onClick={onClose}>{voc("Annuler")}</Button>
          <Button color="teal" leftSection={<Send size={16} />} loading={enCours} onClick={lancer}>{voc`Envoyer à ${actifs} abonné(s)`}</Button>
        </Group>
      </Stack>
    </Modal>
  );
}

function Envois({ actifs }: { actifs: number }) {
  const { data: envois, isLoading } = useEnvoisNewsletter();
  const { essai, supprimerEnvoi } = useNewsletter();
  const [edition, setEdition] = useState<EnvoiNewsletter | null | undefined>(undefined);
  const [aEnvoyer, setAEnvoyer] = useState<EnvoiNewsletter | null>(null);
  const [langueEssai, setLangueEssai] = useState("fr");

  const envoyerEssai = async (e: EnvoiNewsletter) => {
    try {
      notifications.show({ color: "teal", message: voc((await essai(e.id, langueEssai)).detail) });
    } catch (erreur) {
      notifications.show({ color: "red", message: messageErreurApi(erreur, voc("L'essai n'a pas pu être envoyé.")) });
    }
  };

  return (
    <Stack gap="sm">
      <Group justify="space-between">
        <Group gap="xs">
          <Text size="sm" c="dimmed">{voc("Langue des essais :")}</Text>
          <Select size="xs" w={140} value={langueEssai} onChange={(v) => setLangueEssai(v ?? "fr")} allowDeselect={false}
            data={Object.entries(NOM_LANGUE).map(([value, label]) => ({ value, label }))} />
        </Group>
        <Button leftSection={<Plus size={16} />} onClick={() => setEdition(null)}>{voc("Nouvelle newsletter")}</Button>
      </Group>
      {isLoading ? <Loader size="sm" /> : !envois?.length ? (
        <Text c="dimmed" size="sm">{voc("Aucune newsletter pour l'instant.")}</Text>
      ) : (
        <Table.ScrollContainer minWidth={720}>
          <Table striped verticalSpacing="sm">
            <Table.Thead>
              <Table.Tr><Table.Th>{voc("Objet")}</Table.Th><Table.Th>{voc("État")}</Table.Th><Table.Th>{voc("Envoi")}</Table.Th><Table.Th /></Table.Tr>
            </Table.Thead>
            <Table.Tbody>
              {envois.map((e) => {
                const [couleur, libelle] = STATUTS_ENVOI[e.statut];
                return (
                  <Table.Tr key={e.id}>
                    <Table.Td><Text fw={600}>{e.sujet}</Text><Text size="xs" c="dimmed">{voc`Créée le ${jour(e.cree_le)}`}</Text></Table.Td>
                    <Table.Td><Badge color={couleur} variant="light">{voc(libelle)}</Badge></Table.Td>
                    <Table.Td>
                      {e.statut === "BROUILLON" ? "—" : (
                        <Stack gap={4}>
                          <Text size="sm">{voc`${e.envoyes} envoyé(s) sur ${e.destinataires}`}{e.echecs ? ` · ${voc`${e.echecs} échec(s)`}` : ""}</Text>
                          {e.statut === "EN_COURS" && <Progress value={e.destinataires ? (100 * (e.envoyes + e.echecs)) / e.destinataires : 0} size="sm" />}
                          {e.envoye_le && <Text size="xs" c="dimmed">{voc`Envoyée le ${jour(e.envoye_le)} par ${e.envoye_par}`}</Text>}
                        </Stack>
                      )}
                    </Table.Td>
                    <Table.Td>
                      <Group gap={6} justify="flex-end" wrap="nowrap">
                        <Button size="xs" variant="light" leftSection={<Mail size={14} />} onClick={() => envoyerEssai(e)}>{voc("M'envoyer un essai")}</Button>
                        {e.statut === "BROUILLON" && (
                          <>
                            <Button size="xs" variant="default" leftSection={<Pencil size={14} />} onClick={() => setEdition(e)}>{voc("Modifier")}</Button>
                            <Button size="xs" color="teal" leftSection={<Send size={14} />} disabled={!actifs} onClick={() => setAEnvoyer(e)}>{voc("Envoyer")}</Button>
                          </>
                        )}
                        {e.statut !== "EN_COURS" && (
                          <Button size="xs" variant="subtle" color="red" aria-label={voc("Supprimer")} onClick={() => confirmerSuppression({
                            message: voc`Supprimer la newsletter « ${e.sujet} » ?`,
                            onConfirm: () => supprimerEnvoi(e.id).catch((erreur) => notifications.show({ color: "red", message: messageErreurApi(erreur, voc("La suppression n'a pas abouti.")) })),
                          })}><Trash2 size={14} /></Button>
                        )}
                      </Group>
                    </Table.Td>
                  </Table.Tr>
                );
              })}
            </Table.Tbody>
          </Table>
        </Table.ScrollContainer>
      )}
      {edition !== undefined && <EnvoiModal envoi={edition} onClose={() => setEdition(undefined)} />}
      {aEnvoyer && <ConfirmerEnvoi envoi={aEnvoyer} actifs={actifs} onClose={() => setAEnvoyer(null)} />}
    </Stack>
  );
}

function Abonnes() {
  const { data: abonnes, isLoading } = useAbonnesNewsletter();
  const { supprimerAbonne } = useNewsletter();
  const [filtre, setFiltre] = useState<string | null>(null);
  const liste = (abonnes ?? []).filter((a) => !filtre || a.statut === filtre);
  return (
    <Stack gap="sm">
      <Group justify="space-between">
        <Select placeholder={voc("Tous les statuts")} clearable w={260} value={filtre} onChange={setFiltre}
          data={Object.entries(STATUTS_ABONNE).map(([value, [, label]]) => ({ value, label: voc(label) }))} />
        <Button variant="light" leftSection={<Download size={16} />} onClick={() => exporterAbonnesNewsletter().catch(() =>
          notifications.show({ color: "red", message: voc("L'export n'a pas abouti.") }))}>{voc("Exporter (Excel)")}</Button>
      </Group>
      {isLoading ? <Loader size="sm" /> : !liste.length ? <Text c="dimmed" size="sm">{voc("Aucun abonné pour l'instant.")}</Text> : (
        <Table.ScrollContainer minWidth={640}>
          <Table striped>
            <Table.Thead>
              <Table.Tr><Table.Th>{voc("Adresse courriel")}</Table.Th><Table.Th>{voc("Langue")}</Table.Th><Table.Th>{voc("État")}</Table.Th><Table.Th>{voc("Inscrit le")}</Table.Th><Table.Th /></Table.Tr>
            </Table.Thead>
            <Table.Tbody>
              {liste.map((a) => {
                const [couleur, libelle] = STATUTS_ABONNE[a.statut];
                return (
                  <Table.Tr key={a.id}>
                    <Table.Td dir="ltr">{a.courriel}</Table.Td>
                    <Table.Td>{NOM_LANGUE[a.langue] ?? a.langue}</Table.Td>
                    <Table.Td><Badge color={couleur} variant="light">{voc(libelle)}</Badge></Table.Td>
                    <Table.Td>{jour(a.cree_le)}</Table.Td>
                    <Table.Td>
                      <Button size="xs" variant="subtle" color="red" aria-label={voc("Supprimer")} onClick={() => confirmerSuppression({
                        message: voc`Supprimer l'abonné ${a.courriel} ? Il ne recevra plus la newsletter.`,
                        onConfirm: () => supprimerAbonne(a.id),
                      })}><Trash2 size={14} /></Button>
                    </Table.Td>
                  </Table.Tr>
                );
              })}
            </Table.Tbody>
          </Table>
        </Table.ScrollContainer>
      )}
    </Stack>
  );
}

/** Console : newsletter du site (abonnés et envois). */
export function NewsletterConsole() {
  const { data: resume } = useResumeNewsletter();
  const actifs = resume?.actifs ?? 0;
  return (
    <Stack gap="md">
      <SimpleGrid cols={{ base: 1, sm: 3 }}>
        {[["Abonnés confirmés", resume?.actifs, "teal"], ["En attente de confirmation", resume?.en_attente, "yellow"], ["Désinscrits", resume?.desinscrits, "gray"]].map(([libelle, nombre, couleur]) => (
          <Alert key={libelle as string} color={couleur as string} variant="light" title={voc(libelle as string)}>
            <Text fz={26} fw={700}>{nombre ?? "—"}</Text>
          </Alert>
        ))}
      </SimpleGrid>
      <Tabs defaultValue="envois">
        <Tabs.List mb="md">
          <Tabs.Tab value="envois" leftSection={<Send size={15} />}>{voc("Newsletters")}</Tabs.Tab>
          <Tabs.Tab value="abonnes" leftSection={<Mail size={15} />}>{voc("Abonnés")}</Tabs.Tab>
        </Tabs.List>
        <Tabs.Panel value="envois"><Envois actifs={actifs} /></Tabs.Panel>
        <Tabs.Panel value="abonnes"><Abonnes /></Tabs.Panel>
      </Tabs>
    </Stack>
  );
}
