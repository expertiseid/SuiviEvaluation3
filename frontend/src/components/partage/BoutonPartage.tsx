import { useState } from "react";
import { Check, Copy, KeyRound, Link2, Lock, Share2, Trash2 } from "lucide-react";
import {
  ActionIcon,
  Badge,
  Button,
  CopyButton,
  Group,
  Modal,
  Paper,
  PasswordInput,
  Popover,
  SegmentedControl,
  Stack,
  Switch,
  Text,
  TextInput,
  Tooltip,
} from "@mantine/core";
import { DateInput } from "@mantine/dates";
import { notifications } from "@mantine/notifications";
import { adresseLien, useEnregistrerLienPartage, useLiensPartage, useSupprimerLienPartage, type LienPartage } from "../../api/partage";
import { confirmerSuppression } from "../common/confirmerSuppression";
import { messageErreurApi } from "../../utils/erreurs";

import { locale } from "../../utils/i18n";
import { voc } from "../../utils/vocabulaire";
const CONTENUS: { value: LienPartage["contenu"]; label: string }[] = [
  { value: "TOUT", label: voc("Activités et indicateurs") },
  { value: "ACTIVITES", label: voc("Activités") },
  { value: "INDICATEURS", label: voc("Indicateurs") },
];
const dateFr = (d: string) => new Date(d).toLocaleDateString(locale());

function Adresse({ jeton }: { jeton: string }) {
  const adresse = adresseLien(jeton);
  return (
    <Group gap={4} wrap="nowrap">
      <TextInput value={adresse} readOnly size="xs" style={{ flex: 1 }} onFocus={(e) => e.currentTarget.select()} />
      <CopyButton value={adresse}>
        {({ copied, copy }) => (
          <Tooltip label={copied ? voc("Copié") : voc("Copier le lien")}>
            <ActionIcon variant="light" color={copied ? "teal" : "gray"} onClick={copy} aria-label={voc("Copier le lien")}>
              {copied ? <Check size={14} /> : <Copy size={14} />}
            </ActionIcon>
          </Tooltip>
        )}
      </CopyButton>
    </Group>
  );
}

/** Mot de passe d'un lien existant : le changer, l'ajouter ou le retirer. */
function MotDePasseLien({ lien }: { lien: LienPartage }) {
  const enregistrer = useEnregistrerLienPartage();
  const [ouvert, setOuvert] = useState(false);
  const [motDePasse, setMotDePasse] = useState("");

  async function appliquer(valeur: string) {
    try {
      await enregistrer.mutateAsync({ id: lien.id, mot_de_passe: valeur });
      notifications.show({ message: valeur ? voc("Mot de passe enregistré.") : voc("Mot de passe retiré : le lien s'ouvre sans."), color: "green" });
      setOuvert(false);
      setMotDePasse("");
    } catch (e) {
      notifications.show({ message: messageErreurApi(e, voc("Erreur lors de l'enregistrement")), color: "red" });
    }
  }

  return (
    <Popover opened={ouvert} onChange={setOuvert} width={280} position="bottom-end" withArrow>
      <Popover.Target>
        <Tooltip label={lien.protege ? voc("Changer ou retirer le mot de passe") : voc("Protéger par un mot de passe")}>
          <ActionIcon size="sm" variant="subtle" color={lien.protege ? "grape" : "gray"} onClick={() => setOuvert((o) => !o)}
            aria-label={voc("Mot de passe du lien")}>
            <KeyRound size={13} />
          </ActionIcon>
        </Tooltip>
      </Popover.Target>
      <Popover.Dropdown>
        <Stack gap="xs">
          <PasswordInput size="xs" label={lien.protege ? voc("Nouveau mot de passe") : voc("Mot de passe")}
            description={voc("4 caractères au moins. Les accès déjà ouverts devront le saisir.")}
            value={motDePasse} onChange={(e) => setMotDePasse(e.currentTarget.value)} />
          <Group justify="space-between">
            {lien.protege ? (
              <Button size="xs" variant="subtle" color="red" onClick={() => appliquer("")} loading={enregistrer.isPending}>{voc("Retirer")}</Button>
            ) : <span />}
            <Button size="xs" onClick={() => appliquer(motDePasse)} disabled={motDePasse.length < 4} loading={enregistrer.isPending}>
              {voc("Enregistrer")}
            </Button>
          </Group>
        </Stack>
      </Popover.Dropdown>
    </Popover>
  );
}

/**
 * Partage d'une page en lecture seule par un lien secret, sans compte : création (contenu,
 * expiration, mot de passe facultatif), copie, désactivation et suppression des liens existants.
 */
function PartageModal({ type, projetId, filtres, onClose }: { type: LienPartage["type"]; projetId: number | null; filtres?: Record<string, unknown>; onClose: () => void }) {
  const { data: liens = [] } = useLiensPartage(type, projetId);
  const enregistrer = useEnregistrerLienPartage();
  const supprimer = useSupprimerLienPartage();
  const [libelle, setLibelle] = useState("");
  const [contenu, setContenu] = useState<LienPartage["contenu"]>("TOUT");
  const [expireLe, setExpireLe] = useState<string | null>(null);
  const [motDePasse, setMotDePasse] = useState("");

  async function creer() {
    try {
      await enregistrer.mutateAsync({
        type, projet: projetId, contenu, libelle: libelle.trim(), expire_le: expireLe, filtres: filtres ?? {},
        ...(motDePasse ? { mot_de_passe: motDePasse } : {}),
      });
      notifications.show({
        message: motDePasse ? voc("Lien créé : envoyez le lien et, séparément, son mot de passe.") : voc("Lien créé : copiez-le pour l'envoyer."),
        color: "green",
      });
      setLibelle("");
      setMotDePasse("");
    } catch (e) {
      notifications.show({ message: messageErreurApi(e, voc("Erreur lors de la création du lien")), color: "red" });
    }
  }

  return (
    <Modal opened onClose={onClose} title={type === "TABLEAU_DE_BORD" ? voc("Partager le tableau de bord") : voc("Partager le suivi du projet")} size="lg">
      <Stack gap="md">
        <Text size="sm" c="dimmed">
          {voc("Toute personne qui a le lien voit la page en lecture seule, sans compte et sans pouvoir rien modifier. Avec un mot de passe, elle doit aussi le saisir.")}
          {type === "TABLEAU_DE_BORD" && voc(" Les chiffres portent sur les projets que vous voyez, avec les filtres actuels.")}
        </Text>
        <Paper withBorder p="sm" radius="md">
          <Stack gap="sm">
            <TextInput label={voc("Destinataire ou objet (facultatif)")} placeholder={voc("Ex : Comité de pilotage, bailleur")} value={libelle} onChange={(e) => setLibelle(e.currentTarget.value)} />
            {type === "SUIVI_PROJET" && (
              <div>
                <Text size="sm" fw={500} mb={4}>{voc("Contenu partagé")}</Text>
                <SegmentedControl fullWidth value={contenu} onChange={(v) => setContenu(v as LienPartage["contenu"])} data={CONTENUS} />
              </div>
            )}
            <PasswordInput label={voc("Mot de passe (facultatif)")}
              description={voc("4 caractères au moins. Communiquez-le séparément du lien (par téléphone, par exemple).")}
              value={motDePasse} onChange={(e) => setMotDePasse(e.currentTarget.value)} autoComplete="new-password" />
            <DateInput label={voc("Expire le (facultatif)")} description={voc("Sans date, le lien reste valable jusqu'à ce que vous le désactiviez.")} valueFormat="DD/MM/YYYY" clearable value={expireLe} onChange={setExpireLe} minDate={new Date()} />
            <Group justify="flex-end">
              <Button leftSection={<Link2 size={15} />} onClick={creer} loading={enregistrer.isPending}
                disabled={motDePasse.length > 0 && motDePasse.length < 4}>{voc("Créer le lien")}</Button>
            </Group>
          </Stack>
        </Paper>

        {liens.length > 0 && (
          <Stack gap="xs">
            <Text size="sm" fw={600}>{voc("Liens existants")}</Text>
            {liens.map((l) => (
              <Paper key={l.id} withBorder p="xs" radius="md" style={{ opacity: l.valide ? 1 : 0.6 }}>
                <Group justify="space-between" wrap="nowrap" mb={6}>
                  <Group gap={6}>
                    <Text size="sm" fw={500}>{l.libelle || voc("Sans nom")}</Text>
                    {type === "SUIVI_PROJET" && <Badge size="xs" variant="light">{CONTENUS.find((c) => c.value === l.contenu)?.label}</Badge>}
                    {!l.valide && <Badge size="xs" color="gray">{l.actif ? voc("Expiré") : voc("Désactivé")}</Badge>}
                    {l.protege && <Badge size="xs" color="grape" variant="light" leftSection={<Lock size={10} />}>{voc("Mot de passe")}</Badge>}
                  </Group>
                  <Group gap={6} wrap="nowrap">
                    <Switch size="xs" checked={l.actif} label={voc("Actif")} onChange={(e) => enregistrer.mutate({ id: l.id, actif: e.currentTarget.checked })} />
                    <MotDePasseLien lien={l} />
                    <ActionIcon size="sm" variant="subtle" color="red" aria-label={voc("Supprimer le lien")}
                      onClick={() => confirmerSuppression({ message: voc("Supprimer ce lien ? Il ne fonctionnera plus."), onConfirm: () => supprimer.mutate(l.id) })}>
                      <Trash2 size={13} />
                    </ActionIcon>
                  </Group>
                </Group>
                <Adresse jeton={l.jeton} />
                <Text size="xs" c="dimmed" mt={4}>
                  {voc("Créé le")} {dateFr(l.created_at)} {voc("par")} {l.cree_par_nom}
                  {l.expire_le && voc` · expire le ${dateFr(l.expire_le)}`} · {l.nombre_consultations} {voc("consultation(s)")}
                  {l.derniere_consultation && voc`, la dernière le ${dateFr(l.derniere_consultation)}`}
                </Text>
              </Paper>
            ))}
          </Stack>
        )}
      </Stack>
    </Modal>
  );
}

export function BoutonPartage({ type, projetId = null, filtres }: { type: LienPartage["type"]; projetId?: number | null; filtres?: Record<string, unknown> }) {
  const [ouvert, setOuvert] = useState(false);
  return (
    <>
      <Button variant="light" color="grape" leftSection={<Share2 size={16} />} onClick={() => setOuvert(true)}>{voc("Partager")}</Button>
      {ouvert && <PartageModal type={type} projetId={projetId} filtres={filtres} onClose={() => setOuvert(false)} />}
    </>
  );
}
