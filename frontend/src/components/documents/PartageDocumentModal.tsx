import { useState } from "react";
import {
  ActionIcon, Alert, Badge, Button, CopyButton, Divider, Group, Modal, NumberInput, PasswordInput, SegmentedControl, Stack,
  Table, Text, TextInput, Tooltip,
} from "@mantine/core";
import { DateTimePicker } from "@mantine/dates";
import { notifications } from "@mantine/notifications";
import { Ban, Check, Copy, Link2 } from "lucide-react";
import {
  type CiblePartage, type LienDocument, adresseLienDocument, useCreerLienDocument, useLiensDocument, useRevoquerLienDocument,
} from "../../api/documents";
import { messageErreurApi } from "../../utils/erreurs";
import { locale } from "../../utils/i18n";
import { voc } from "../../utils/vocabulaire";
import { confirmerSuppression } from "../common/confirmerSuppression";

const DUREES = () => [
  { value: "1", label: voc("1 jour") }, { value: "7", label: voc("7 jours") }, { value: "30", label: voc("30 jours") },
  { value: "date", label: voc("Date précise") },
];
const COULEUR_ETAT: Record<LienDocument["etat"], string> = { ACTIF: "teal", EXPIRE: "gray", EPUISE: "orange", REVOQUE: "red" };
const LIBELLE_ETAT = (): Record<LienDocument["etat"], string> => ({
  ACTIF: voc("Actif"), EXPIRE: voc("Expiré"), EPUISE: voc("Ouvertures épuisées"), REVOQUE: voc("Désactivé"),
});
const dateHeure = (d: string) => new Date(d).toLocaleString(locale(), { dateStyle: "short", timeStyle: "short" });

/**
 * Partager un document — ou un dossier entier — avec une personne qui n'a pas de compte : lien secret,
 * droit (consulter, ou consulter et télécharger ; un dossier se télécharge toujours), expiration, mot de
 * passe et nombre d'ouvertures facultatifs. Liste des liens, avec leur état et leurs ouvertures ;
 * révocation immédiate.
 */
export function PartageDocumentModal({ cible, onClose }: { cible: CiblePartage; onClose: () => void }) {
  const dossier = cible.type === "dossier";
  const { data: liens = [] } = useLiensDocument(cible);
  const creer = useCreerLienDocument(cible);
  const revoquer = useRevoquerLienDocument(cible);
  const [droit, setDroit] = useState<"CONSULTER" | "TELECHARGER">("CONSULTER");
  const [duree, setDuree] = useState("7");
  const [date, setDate] = useState<string | null>(null);
  const [libelle, setLibelle] = useState("");
  const [motDePasse, setMotDePasse] = useState("");
  const [ouvertures, setOuvertures] = useState<number | string>("");
  const [erreur, setErreur] = useState<string | null>(null);
  const [nouveau, setNouveau] = useState<LienDocument | null>(null);

  const expiration = () => {
    if (duree === "date") return date ? new Date(date) : null;
    const d = new Date();
    d.setDate(d.getDate() + Number(duree));
    return d;
  };

  const valider = async () => {
    setErreur(null);
    const expire = expiration();
    if (!expire) {
      setErreur(voc("Choisissez la date d'expiration."));
      return;
    }
    try {
      setNouveau(await creer.mutateAsync({
        droit: dossier ? "TELECHARGER" : droit, expire_le: expire.toISOString(), libelle: libelle.trim(), mot_de_passe: motDePasse,
        ouvertures_max: ouvertures === "" ? null : Number(ouvertures),
      }));
      setLibelle("");
      setMotDePasse("");
      setOuvertures("");
    } catch (error) {
      setErreur(messageErreurApi(error, voc("Le lien n'a pas pu être créé.")));
    }
  };

  const retirer = (lien: LienDocument) => confirmerSuppression({
    message: dossier
      ? voc("Désactiver ce lien ? La personne ne pourra plus ouvrir le dossier, même si elle a déjà le lien.")
      : voc("Désactiver ce lien ? La personne ne pourra plus ouvrir le document, même si elle a déjà le lien."),
    labelConfirmer: voc("Désactiver"),
    onConfirm: async () => {
      try {
        await revoquer.mutateAsync(lien.id);
        if (nouveau?.id === lien.id) setNouveau(null);
        notifications.show({ message: voc("Lien désactivé"), color: "green" });
      } catch (error) {
        notifications.show({ message: messageErreurApi(error, voc("Erreur")), color: "red" });
      }
    },
  });

  const boutonCopier = (jeton: string) => (
    <CopyButton value={adresseLienDocument(jeton)}>
      {({ copied, copy }) => (
        <Tooltip label={copied ? voc("Copié") : voc("Copier le lien")}>
          <ActionIcon variant="subtle" color={copied ? "teal" : "gray"} onClick={copy} aria-label={voc("Copier le lien")}>
            {copied ? <Check size={16} /> : <Copy size={16} />}
          </ActionIcon>
        </Tooltip>
      )}
    </CopyButton>
  );

  return (
    <Modal opened onClose={onClose} title={dossier ? voc`Partager le dossier « ${cible.nom} » par lien` : voc`Partager « ${cible.nom} » par lien`} size="xl">
      <Stack gap="md">
        <Text size="sm" c="dimmed">
          {dossier
            ? voc("La personne qui reçoit le lien n'a pas besoin de compte. Elle voit les fichiers de ce dossier et de ses sous-dossiers (dernières versions, y compris ceux ajoutés plus tard) et les télécharge pour les lire, un par un ou tous en zip, jusqu'à la date d'expiration ; vous pouvez désactiver le lien à tout moment.")
            : voc("La personne qui reçoit le lien n'a pas besoin de compte. Elle ne voit que ce document, jusqu'à la date d'expiration ; vous pouvez désactiver le lien à tout moment.")}
        </Text>
        {nouveau && (
          <Alert color="teal" icon={<Link2 size={18} />} title={voc("Lien créé : copiez-le et envoyez-le")}>
            <Group gap="xs" wrap="nowrap">
              <TextInput value={adresseLienDocument(nouveau.jeton)} readOnly style={{ flex: 1 }} dir="ltr" onFocus={(e) => e.currentTarget.select()} />
              {boutonCopier(nouveau.jeton)}
            </Group>
            {nouveau.a_mot_de_passe && (
              <Text size="xs" mt={6}>{voc("Communiquez le mot de passe séparément (par téléphone ou par message), jamais avec le lien.")}</Text>
            )}
          </Alert>
        )}
        <Stack gap="sm">
          <Text fw={600} size="sm">{voc("Nouveau lien")}</Text>
          {!dossier && (
            <SegmentedControl value={droit} onChange={(v) => setDroit(v as typeof droit)} data={[
              { value: "CONSULTER", label: voc("Consulter seulement") },
              { value: "TELECHARGER", label: voc("Consulter et télécharger") },
            ]} />
          )}
          <Group grow align="flex-start">
            <TextInput label={voc("Pour qui ? (facultatif)")} placeholder={voc("Ex : Bailleur — rapport annuel")} value={libelle}
              onChange={(e) => setLibelle(e.currentTarget.value)} />
            <Stack gap={4}>
              <Text size="sm" fw={500}>{voc("Expire dans")}</Text>
              <SegmentedControl size="xs" value={duree} onChange={setDuree} data={DUREES()} />
              {duree === "date" && (
                <DateTimePicker value={date} onChange={setDate} minDate={new Date()} placeholder={voc("Date et heure")} valueFormat="DD/MM/YYYY HH:mm" />
              )}
            </Stack>
          </Group>
          <Group grow align="flex-start">
            <PasswordInput label={voc("Mot de passe (facultatif)")} value={motDePasse} onChange={(e) => setMotDePasse(e.currentTarget.value)}
              description={voc("Demandé à l'ouverture.")} autoComplete="new-password" />
            <NumberInput label={voc("Nombre d'ouvertures (facultatif)")} min={1} value={ouvertures} onChange={setOuvertures}
              description={voc("Vide : sans limite.")} />
          </Group>
          {erreur && <Alert color="red" p="xs">{erreur}</Alert>}
          <Group justify="flex-end">
            <Button leftSection={<Link2 size={16} />} onClick={valider} loading={creer.isPending}>{voc("Créer le lien")}</Button>
          </Group>
        </Stack>
        <Divider label={dossier ? voc("Liens de ce dossier") : voc("Liens de ce document")} labelPosition="left" />
        {liens.length === 0 ? (
          <Text size="sm" c="dimmed">{voc("Aucun lien pour l'instant.")}</Text>
        ) : (
          <Table.ScrollContainer minWidth={640}>
            <Table verticalSpacing="xs" striped>
              <Table.Thead>
                <Table.Tr>
                  <Table.Th>{voc("Pour qui")}</Table.Th>
                  <Table.Th>{voc("Droit")}</Table.Th>
                  <Table.Th>{voc("Expire le")}</Table.Th>
                  <Table.Th>{voc("Ouvertures")}</Table.Th>
                  <Table.Th>{voc("État")}</Table.Th>
                  <Table.Th />
                </Table.Tr>
              </Table.Thead>
              <Table.Tbody>
                {liens.map((lien) => (
                  <Table.Tr key={lien.id}>
                    <Table.Td>
                      <Text size="sm">{lien.libelle || "—"}</Text>
                      <Text size="xs" c="dimmed">{voc`par ${lien.cree_par_nom}`}{lien.a_mot_de_passe ? ` · ${voc("mot de passe")}` : ""}</Text>
                    </Table.Td>
                    <Table.Td><Text size="sm">{voc(lien.droit_libelle)}</Text></Table.Td>
                    <Table.Td><Text size="sm">{dateHeure(lien.expire_le)}</Text></Table.Td>
                    <Table.Td><Text size="sm">{lien.nombre_ouvertures}{lien.ouvertures_max ? ` / ${lien.ouvertures_max}` : ""}</Text></Table.Td>
                    <Table.Td><Badge variant="light" color={COULEUR_ETAT[lien.etat]}>{LIBELLE_ETAT()[lien.etat]}</Badge></Table.Td>
                    <Table.Td>
                      {lien.etat === "ACTIF" && (
                        <Group gap={4} wrap="nowrap" justify="flex-end">
                          {boutonCopier(lien.jeton)}
                          <Tooltip label={voc("Désactiver")}>
                            <ActionIcon variant="subtle" color="red" onClick={() => retirer(lien)} aria-label={voc("Désactiver")}><Ban size={16} /></ActionIcon>
                          </Tooltip>
                        </Group>
                      )}
                    </Table.Td>
                  </Table.Tr>
                ))}
              </Table.Tbody>
            </Table>
          </Table.ScrollContainer>
        )}
      </Stack>
    </Modal>
  );
}
