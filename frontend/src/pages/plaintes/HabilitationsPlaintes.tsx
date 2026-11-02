import { useState } from "react";
import { Alert, Badge, Button, Group, Modal, Select, Stack, Table, Text, Textarea, TextInput } from "@mantine/core";
import { notifications } from "@mantine/notifications";
import { ShieldCheck } from "lucide-react";
import { useUtilisateurs } from "../../api/accounts";
import {
  type Habilitation,
  type StatutHabilitation,
  libelleStatutHabilitation,
  useHabilitations,
  useOperationHabilitation,
} from "../../api/plaintes";
import { useAuth } from "../../auth/useAuth";
import { messageErreurApi } from "../../utils/erreurs";
import { locale } from "../../utils/i18n";
import { voc } from "../../utils/vocabulaire";
import { erreursParChamp } from "./saisieRetour";

const COULEUR: Record<StatutHabilitation, string> = {
  EN_ATTENTE: "orange", EN_DELAI: "yellow", ACTIVE: "teal", REFUSEE: "gray", RETIREE: "gray",
};

const date = (d: string | null) => (d ? new Date(d).toLocaleString(locale(), { dateStyle: "short", timeStyle: "short" }) : "—");

type Fenetre = { type: "demander" } | { type: "valider" | "confirmer" | "retirer"; habilitation: Habilitation } | null;

/** Fenêtre commune : demande, validation, confirmation par code, retrait. */
function FenetreHabilitation({ fenetre, onClose }: { fenetre: NonNullable<Fenetre>; onClose: () => void }) {
  const { user } = useAuth();
  const { data: utilisateurs = [] } = useUtilisateurs();
  const operer = useOperationHabilitation();
  const [valeurs, setValeurs] = useState<Record<string, unknown>>({});
  const [erreurs, setErreurs] = useState<Record<string, string>>({});
  const h = fenetre.type === "demander" ? null : fenetre.habilitation;
  const changer = (v: Record<string, unknown>) => setValeurs((a) => ({ ...a, ...v }));
  const texte = (c: string) => String(valeurs[c] ?? "");

  const envoyer = async (donnees: Record<string, unknown>) => {
    setErreurs({});
    try {
      const resultat = await operer.mutateAsync(h ? { id: h.id, operation: fenetre.type as "valider", donnees } : { donnees });
      notifications.show({ color: "teal", message: resultat.premiere && resultat.statut === "EN_ATTENTE"
        ? voc("Un code de confirmation vous a été envoyé par courriel.")
        : libelleStatutHabilitation(resultat.statut) });
      onClose();
    } catch (error) {
      const parChamp = erreursParChamp(error);
      setErreurs(Object.keys(parChamp).length ? parChamp : { detail: messageErreurApi(error, voc("Erreur lors de l'enregistrement")) });
    }
  };

  const titres = {
    demander: voc("Demander une habilitation confidentielle"),
    valider: voc("Valider la demande"),
    confirmer: voc("Confirmer la première habilitation"),
    retirer: voc("Retirer l'habilitation"),
  };
  return (
    <Modal opened onClose={onClose} title={titres[fenetre.type]} size="lg">
      <Stack>
        {h && <Text size="sm"><b>{h.utilisateur_nom}</b> — {h.motif}</Text>}
        {fenetre.type === "demander" && (
          <>
            <Text size="sm" c="dimmed">
              {voc("La demande devra être validée par une deuxième personne (Administrateur ou personne déjà habilitée). Personne ne peut demander sa propre habilitation.")}
            </Text>
            <Select
              label={voc("Personne")}
              withAsterisk
              searchable
              data={utilisateurs.filter((u) => u.is_active && u.role !== "ADMIN" && u.id !== user?.id)
                .map((u) => ({ value: String(u.id), label: `${u.first_name} ${u.last_name}`.trim() || u.username }))}
              value={valeurs.utilisateur ? String(valeurs.utilisateur) : null}
              onChange={(v) => changer({ utilisateur: v ? Number(v) : null })}
              error={erreurs.utilisateur}
            />
            <Textarea label={voc("Motif")} withAsterisk autosize minRows={2} value={texte("motif")}
              description={voc("Pourquoi cette personne doit accéder aux dossiers confidentiels (fonction, protocole).")}
              onChange={(e) => changer({ motif: e.currentTarget.value })} error={erreurs.motif} />
          </>
        )}
        {fenetre.type === "valider" && (
          <Textarea label={voc("Commentaire")} description={voc("Obligatoire pour un refus.")} autosize minRows={2}
            value={texte("commentaire")} onChange={(e) => changer({ commentaire: e.currentTarget.value })} error={erreurs.commentaire} />
        )}
        {fenetre.type === "confirmer" && (
          <>
            <Text size="sm" c="dimmed">
              {voc("Aucune deuxième personne ne peut encore valider : saisissez le code reçu par courriel. L'habilitation prendra effet 24 heures après la confirmation.")}
            </Text>
            <TextInput label={voc("Code reçu par courriel")} withAsterisk value={texte("code")} dir="ltr"
              onChange={(e) => changer({ code: e.currentTarget.value })} error={erreurs.code} />
          </>
        )}
        {fenetre.type === "retirer" && (
          <>
            <Text size="sm" c="dimmed">
              {voc("Le retrait prend effet immédiatement. Les dossiers confidentiels ouverts confiés à cette personne devront être réaffectés.")}
            </Text>
            <Textarea label={voc("Motif")} withAsterisk autosize minRows={2} value={texte("motif")}
              onChange={(e) => changer({ motif: e.currentTarget.value })} error={erreurs.motif} />
          </>
        )}
        {erreurs.detail && <Alert color="red">{erreurs.detail}</Alert>}
        <Group justify="flex-end">
          <Button variant="default" onClick={onClose}>{voc("Annuler")}</Button>
          {fenetre.type === "valider" ? (
            <>
              <Button color="red" variant="light" loading={operer.isPending} onClick={() => envoyer({ accepter: false, commentaire: texte("commentaire") })}>{voc("Refuser")}</Button>
              <Button loading={operer.isPending} onClick={() => envoyer({ accepter: true, commentaire: texte("commentaire") })}>{voc("Valider")}</Button>
            </>
          ) : (
            <Button color={fenetre.type === "retirer" ? "red" : undefined} loading={operer.isPending} onClick={() => envoyer(valeurs)}>
              {fenetre.type === "demander" ? voc("Envoyer la demande") : fenetre.type === "confirmer" ? voc("Confirmer") : voc("Retirer")}
            </Button>
          )}
        </Group>
      </Stack>
    </Modal>
  );
}

/**
 * Habilitations aux dossiers confidentiels : seules les personnes habilitées (et l'Administrateur)
 * peuvent être responsables d'une étape confidentielle et voir ces dossiers. Double validation.
 */
export function HabilitationsPlaintes({ modifiable }: { modifiable: boolean }) {
  const { data: habilitations, isError } = useHabilitations();
  const [fenetre, setFenetre] = useState<Fenetre>(null);
  const [historique, setHistorique] = useState(false);

  if (isError) {
    return <Alert color="gray">{voc("Seuls l'Administrateur et les personnes habilitées gèrent les habilitations confidentielles.")}</Alert>;
  }
  const enCours = (habilitations ?? []).filter((h) => ["EN_ATTENTE", "EN_DELAI", "ACTIVE"].includes(h.statut));
  const terminees = (habilitations ?? []).filter((h) => !enCours.includes(h));
  const lignes = historique ? habilitations ?? [] : enCours;

  return (
    <Stack gap="sm">
      <Group justify="space-between" align="flex-start">
        <Text size="sm" c="dimmed" maw={760}>
          {voc("L'accès aux dossiers confidentiels est une habilitation distincte des rôles. Seules les personnes habilitées peuvent être responsables d'une étape d'un circuit confidentiel. Chaque habilitation est demandée par une personne et validée par une deuxième ; tout est inscrit au journal d'audit. L'Administrateur y accède d'office.")}
        </Text>
        {modifiable && (
          <Button size="xs" leftSection={<ShieldCheck size={14} />} onClick={() => setFenetre({ type: "demander" })}>
            {voc("Demander une habilitation")}
          </Button>
        )}
      </Group>
      <Table withTableBorder verticalSpacing={6}>
        <Table.Thead>
          <Table.Tr>
            <Table.Th>{voc("Personne")}</Table.Th>
            <Table.Th>{voc("Motif")}</Table.Th>
            <Table.Th>{voc("Demandée par")}</Table.Th>
            <Table.Th>{voc("Validée par")}</Table.Th>
            <Table.Th>{voc("État")}</Table.Th>
            {modifiable && <Table.Th w={190} />}
          </Table.Tr>
        </Table.Thead>
        <Table.Tbody>
          {lignes.map((h) => (
            <Table.Tr key={h.id}>
              <Table.Td>{h.utilisateur_nom}</Table.Td>
              <Table.Td><Text size="sm" lineClamp={2}>{h.statut === "RETIREE" ? `${h.motif} — ${voc("retrait")} : ${h.motif_retrait}` : h.motif}</Text></Table.Td>
              <Table.Td><Text size="xs">{h.demandee_par_nom ?? voc("Reprise de l'existant")}<br />{date(h.date_demande)}</Text></Table.Td>
              <Table.Td><Text size="xs">{h.validee_par_nom ?? "—"}{h.date_validation && <><br />{date(h.date_validation)}</>}</Text></Table.Td>
              <Table.Td>
                <Badge variant="light" tt="none" color={COULEUR[h.statut]}>{libelleStatutHabilitation(h.statut)}</Badge>
                {h.statut === "EN_DELAI" && h.active_le && <Text size="xs" c="dimmed">{voc`Active le ${date(h.active_le)}`}</Text>}
              </Table.Td>
              {modifiable && (
                <Table.Td>
                  <Group gap={4}>
                    {h.peut_valider && <Button size="compact-xs" onClick={() => setFenetre({ type: "valider", habilitation: h })}>{voc("Valider ou refuser")}</Button>}
                    {h.peut_confirmer && <Button size="compact-xs" onClick={() => setFenetre({ type: "confirmer", habilitation: h })}>{voc("Saisir le code")}</Button>}
                    {["EN_ATTENTE", "EN_DELAI", "ACTIVE"].includes(h.statut) && (
                      <Button size="compact-xs" variant="subtle" color="red" onClick={() => setFenetre({ type: "retirer", habilitation: h })}>
                        {h.statut === "ACTIVE" ? voc("Retirer") : voc("Annuler")}
                      </Button>
                    )}
                  </Group>
                </Table.Td>
              )}
            </Table.Tr>
          ))}
          {lignes.length === 0 && (
            <Table.Tr><Table.Td colSpan={6}><Text size="sm" c="dimmed">{voc("Aucune habilitation en cours.")}</Text></Table.Td></Table.Tr>
          )}
        </Table.Tbody>
      </Table>
      {terminees.length > 0 && (
        <Button variant="subtle" size="xs" onClick={() => setHistorique((x) => !x)} style={{ alignSelf: "flex-start" }}>
          {historique ? voc("Masquer l'historique") : voc`Afficher l'historique (${terminees.length})`}
        </Button>
      )}
      {fenetre && <FenetreHabilitation fenetre={fenetre} onClose={() => setFenetre(null)} />}
    </Stack>
  );
}
