import { useEffect, useState } from "react";
import { Download } from "lucide-react";
import { Badge, Button, Card, Code, Group, SegmentedControl, Stack, Switch, Text, TextInput, Textarea } from "@mantine/core";
import { notifications } from "@mantine/notifications";
import {
  LANGUES_MESSAGES,
  type ModeleMessage,
  OBJETS_MESSAGE,
  libelleObjetEchange,
  useEnregistrerModeleMessage,
  useInstallerModelesMessages,
  useModelesMessages,
} from "../../api/plaintes";
import { messageErreurApi } from "../../utils/erreurs";
import { voc } from "../../utils/vocabulaire";

const VARIABLES = ["{numero}", "{nom}", "{mecanisme}", "{date_reception}", "{lien_suivi}", "{decision}", "{signature}"];

/** Un modèle : objet du courriel, texte du courriel, texte du SMS (enregistrés en quittant le champ). */
function CarteModele({ modele, modifiable }: { modele: ModeleMessage; modifiable: boolean }) {
  const enregistrer = useEnregistrerModeleMessage();
  const [valeurs, setValeurs] = useState(modele);
  useEffect(() => setValeurs(modele), [modele]);
  const sauver = async (champ: keyof ModeleMessage, valeur: string | boolean) => {
    if (valeur === modele[champ]) return;
    try {
      await enregistrer.mutateAsync({ id: modele.id, [champ]: valeur });
    } catch (error) {
      notifications.show({ message: messageErreurApi(error, voc("Erreur lors de l'enregistrement")), color: "red" });
    }
  };
  const nombreSms = Math.max(1, Math.ceil(valeurs.texte_sms.length / 160));
  const sens = modele.langue === "ar" ? "rtl" : "ltr";
  return (
    <Card withBorder padding="sm">
      <Stack gap="xs">
        <Group justify="space-between">
          <Text fw={600} size="sm">{libelleObjetEchange(modele.objet)}</Text>
          <Switch size="xs" label={voc("Actif")} checked={valeurs.actif} disabled={!modifiable}
            onChange={(e) => { const actif = e.currentTarget.checked; setValeurs((v) => ({ ...v, actif })); sauver("actif", actif); }} />
        </Group>
        <TextInput label={voc("Objet du courriel")} dir={sens} value={valeurs.sujet} disabled={!modifiable}
          onChange={(e) => { const sujet = e.currentTarget.value; setValeurs((v) => ({ ...v, sujet })); }} onBlur={() => sauver("sujet", valeurs.sujet)} />
        <Textarea label={voc("Courriel")} dir={sens} autosize minRows={3} value={valeurs.texte_courriel} disabled={!modifiable}
          onChange={(e) => { const texte_courriel = e.currentTarget.value; setValeurs((v) => ({ ...v, texte_courriel })); }}
          onBlur={() => sauver("texte_courriel", valeurs.texte_courriel)} />
        <Textarea label={voc("SMS")} dir={sens} autosize minRows={1} maxLength={480} value={valeurs.texte_sms} disabled={!modifiable}
          description={voc`${valeurs.texte_sms.length} caractères — ${nombreSms} SMS (avant remplacement des variables)`}
          onChange={(e) => { const texte_sms = e.currentTarget.value; setValeurs((v) => ({ ...v, texte_sms })); }}
          onBlur={() => sauver("texte_sms", valeurs.texte_sms)} />
      </Stack>
    </Card>
  );
}

/** Modèles de messages au plaignant, par langue. */
export function MessagesPlaintes({ modifiable }: { modifiable: boolean }) {
  const { data: modeles = [] } = useModelesMessages();
  const installer = useInstallerModelesMessages();
  const [langue, setLangue] = useState("fr");
  const affiches = OBJETS_MESSAGE.map((o) => modeles.find((m) => m.objet === o && m.langue === langue)).filter(Boolean) as ModeleMessage[];
  return (
    <Stack gap="sm">
      <Text size="sm" c="dimmed">
        {voc("Messages envoyés au plaignant par courriel ou par SMS, dans sa langue (celle de son dépôt), sinon en français. Ils ne doivent jamais contenir de détail confidentiel : pour un dossier confidentiel, la décision n'est jamais insérée.")}
      </Text>
      <Group gap={6}>
        <Text size="sm">{voc("Variables :")}</Text>
        {VARIABLES.map((v) => <Code key={v}>{v}</Code>)}
      </Group>
      <Group justify="space-between">
        <SegmentedControl value={langue} onChange={setLangue} data={LANGUES_MESSAGES} />
        {modifiable && (
          <Button variant="light" leftSection={<Download size={14} />} loading={installer.isPending}
            onClick={async () => {
              const r = await installer.mutateAsync();
              notifications.show({ message: voc`${r.ajoutes} modèle(s) ajouté(s).`, color: "teal" });
            }}>
            {voc("Installer les modèles manquants")}
          </Button>
        )}
      </Group>
      {affiches.length === 0 && <Badge color="orange" variant="light" tt="none">{voc("Aucun modèle dans cette langue.")}</Badge>}
      {affiches.map((m) => <CarteModele key={m.id} modele={m} modifiable={modifiable} />)}
    </Stack>
  );
}
