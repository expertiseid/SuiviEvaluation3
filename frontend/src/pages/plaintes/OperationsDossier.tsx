import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Link2 } from "lucide-react";
import {
  Alert,
  Button,
  Checkbox,
  Group,
  Modal,
  MultiSelect,
  NumberInput,
  Radio,
  SegmentedControl,
  Select,
  SimpleGrid,
  Stack,
  Switch,
  Text,
  TextInput,
  Textarea,
} from "@mantine/core";
import { notifications } from "@mantine/notifications";
import {
  type DossierDetail,
  type IssueDossier,
  ISSUES,
  exporterFicheDossier,
  libelleTypePrestataire,
  usePrestataires,
  useSignalerSensible,
  MODES_REPONSE,
  OBJETS_ECHANGE,
  type OperationDossier,
  dateLisible,
  libelleIssue,
  libelleModeReponse,
  libelleObjetEchange,
  libelleStatutDossier,
  useCategoriesPlainte,
  useCircuitsPlainte,
  useMecanisme,
  useOperationDossier,
  usePossiblementLies,
  usePrioritesPlainte,
  useResponsablesPossibles,
  useTypesRetour,
} from "../../api/plaintes";
import { useUtilisateurs } from "../../api/accounts";
import { useProjets } from "../../api/projects";
import { messageErreurApi } from "../../utils/erreurs";
import { libelleRole } from "../../utils/roles";
import { voc } from "../../utils/vocabulaire";
import { erreursParChamp, optionsCategories } from "./saisieRetour";

type Valeurs = Record<string, unknown>;

/** Fenêtre d'une opération : champs, erreurs du serveur sous chaque champ, envoi. */
function Fenetre({
  dossier,
  operation,
  titre,
  onClose,
  initiales = {},
  libelleBouton,
  couleur,
  children,
}: {
  dossier: DossierDetail;
  operation: OperationDossier;
  titre: string;
  onClose: () => void;
  initiales?: Valeurs;
  libelleBouton?: string;
  couleur?: string;
  children: (valeurs: Valeurs, changer: (v: Valeurs) => void, erreurs: Record<string, string>) => React.ReactNode;
}) {
  const operer = useOperationDossier(dossier.id);
  const navigate = useNavigate();
  const [valeurs, setValeurs] = useState<Valeurs>(initiales);
  const [erreurs, setErreurs] = useState<Record<string, string>>({});
  const envoyer = async () => {
    setErreurs({});
    try {
      const resultat = await operer.mutateAsync({ operation, donnees: valeurs });
      onClose();
      if ("visible" in resultat && resultat.visible === false) {
        notifications.show({
          title: voc("Transmis au circuit confidentiel"),
          message: voc("Ce dossier est désormais réservé aux personnes désignées."),
          color: "grape",
        });
        navigate("/plaintes");
      } else {
        notifications.show({ message: voc("Dossier mis à jour"), color: "teal" });
      }
    } catch (error) {
      const parChamp = erreursParChamp(error);
      setErreurs(Object.keys(parChamp).length ? parChamp : { detail: messageErreurApi(error, voc("Erreur lors de l'enregistrement")) });
    }
  };
  return (
    <Modal opened onClose={onClose} title={titre} size="lg">
      <Stack>
        {children(valeurs, (v) => setValeurs((ancien) => ({ ...ancien, ...v })), erreurs)}
        {erreurs.detail && <Alert color="red">{erreurs.detail}</Alert>}
        <Group justify="flex-end">
          <Button variant="default" onClick={onClose}>{voc("Annuler")}</Button>
          <Button color={couleur} onClick={envoyer} loading={operer.isPending}>{libelleBouton ?? voc("Enregistrer")}</Button>
        </Group>
      </Stack>
    </Modal>
  );
}

const texte = (v: unknown) => (typeof v === "string" ? v : "");
const nombre = (v: unknown) => (v == null || v === "" ? null : String(v));

/** Type, catégorie, priorité et projet. */
export function ClasserDossier({ dossier, onClose }: { dossier: DossierDetail; onClose: () => void }) {
  const { data: types = [] } = useTypesRetour();
  const { data: categories = [] } = useCategoriesPlainte();
  const { data: priorites = [] } = usePrioritesPlainte();
  const { data: mecanisme } = useMecanisme();
  const { data: tousProjets = [] } = useProjets();
  const couverts = mecanisme?.projets ?? [];
  const projets = couverts.length ? tousProjets.filter((p) => couverts.includes(p.id)) : tousProjets;
  return (
    <Fenetre
      dossier={dossier}
      operation="classer"
      titre={voc("Classer le dossier")}
      onClose={onClose}
      initiales={{ type_retour: dossier.type_retour, categorie: dossier.categorie, priorite: dossier.priorite, projet: dossier.projet }}
    >
      {(v, changer, erreurs) => {
        const categorie = categories.find((c) => c.id === Number(v.categorie));
        return (
          <>
            <SimpleGrid cols={2}>
              <Select label={voc("Type de retour")} data={types.filter((t) => t.actif).map((t) => ({ value: String(t.id), label: t.nom }))}
                value={nombre(v.type_retour)} onChange={(x) => changer({ type_retour: x ? Number(x) : null })} error={erreurs.type_retour} allowDeselect={false} />
              <Select label={voc("Priorité")} placeholder={voc("À évaluer")} data={priorites.filter((p) => p.actif).map((p) => ({ value: String(p.id), label: p.nom }))}
                value={nombre(v.priorite)} onChange={(x) => changer({ priorite: x ? Number(x) : null })} error={erreurs.priorite} clearable />
            </SimpleGrid>
            <Select label={voc("Catégorie")} placeholder={voc("À classer")} data={optionsCategories(categories.filter((c) => c.actif))}
              value={nombre(v.categorie)} onChange={(x) => changer({ categorie: x ? Number(x) : null })} error={erreurs.categorie} searchable clearable />
            <Select label={voc("Projet")} data={projets.map((p) => ({ value: String(p.id), label: p.code ? `${p.code} — ${p.nom}` : p.nom }))}
              value={nombre(v.projet)} onChange={(x) => changer({ projet: x ? Number(x) : null })} error={erreurs.projet} searchable clearable />
            {!dossier.sensible && categorie?.sensible_effective && (
              <Alert color="grape" title={voc("Catégorie sensible")}>
                {voc("Le dossier passera au circuit confidentiel : seules les personnes désignées (et l'Administrateur) y auront accès.")}
              </Alert>
            )}
          </>
        );
      }}
    </Fenetre>
  );
}

export function AffecterDossier({ dossier, onClose }: { dossier: DossierDetail; onClose: () => void }) {
  const { data: personnes = [] } = useResponsablesPossibles(dossier.id, true);
  return (
    <Fenetre dossier={dossier} operation="affecter" titre={voc("Affecter le dossier")} onClose={onClose} initiales={{ responsable: dossier.responsable }}>
      {(v, changer, erreurs) => (
        <>
          {dossier.sensible && <Text size="sm" c="dimmed">{voc("Dossier confidentiel : seules les personnes désignées dans son circuit peuvent le recevoir.")}</Text>}
          {dossier.en_recours && dossier.gestionnaire_initial_nom && (
            <Text size="sm" c="dimmed">{voc`Recours : le dossier est réexaminé par une autre personne que ${dossier.gestionnaire_initial_nom}.`}</Text>
          )}
          <Select label={voc("Gestionnaire du dossier")} data={personnes.map((p) => ({ value: String(p.id), label: `${p.nom} — ${libelleRole(p.role)}` }))}
            value={nombre(v.responsable)} onChange={(x) => changer({ responsable: x ? Number(x) : null })} error={erreurs.responsable} searchable />
        </>
      )}
    </Fenetre>
  );
}

/** Saisie d'un motif seul (récusation, recours…). */
export function MotifDossier({ dossier, operation, titre, aide, libelleBouton, couleur, onClose, avecEtape = false }: {
  dossier: DossierDetail;
  operation: OperationDossier;
  titre: string;
  aide: string;
  libelleBouton: string;
  couleur?: string;
  onClose: () => void;
  avecEtape?: boolean;
}) {
  const { data: circuits = [] } = useCircuitsPlainte();
  const etapes = (circuits.find((c) => c.id === dossier.circuit)?.etapes ?? []).filter((e) => !e.est_cloture);
  return (
    <Fenetre dossier={dossier} operation={operation} titre={titre} onClose={onClose} libelleBouton={libelleBouton} couleur={couleur}>
      {(v, changer, erreurs) => (
        <>
          <Text size="sm" c="dimmed">{aide}</Text>
          <Textarea label={voc("Motif")} withAsterisk autosize minRows={3} value={texte(v.motif)} onChange={(e) => changer({ motif: e.currentTarget.value })} error={erreurs.motif} />
          {avecEtape && (
            <Select label={voc("Reprendre à l'étape")} placeholder={voc("Étape avant la clôture")} data={etapes.map((e) => ({ value: String(e.id), label: e.nom }))}
              value={nombre(v.etape)} onChange={(x) => changer({ etape: x ? Number(x) : null })} error={erreurs.etape} clearable />
          )}
        </>
      )}
    </Fenetre>
  );
}

export function EtapeDossier({ dossier, onClose }: { dossier: DossierDetail; onClose: () => void }) {
  const { data: circuits = [] } = useCircuitsPlainte();
  const etapes = circuits.find((c) => c.id === dossier.circuit)?.etapes ?? [];
  const suivante = etapes.find((e, i) => i > 0 && etapes[i - 1].id === dossier.etape && !e.est_cloture);
  return (
    <Fenetre dossier={dossier} operation="etape" titre={voc("Changer d'étape")} onClose={onClose} initiales={{ etape: suivante?.id ?? null }}>
      {(v, changer, erreurs) => (
        <>
          <Select label={voc("Étape")} data={etapes.filter((e) => !e.est_cloture).map((e) => ({ value: String(e.id), label: `${e.ordre}. ${e.nom}` }))}
            value={nombre(v.etape)} onChange={(x) => changer({ etape: x ? Number(x) : null })} error={erreurs.etape} allowDeselect={false} />
          <Text size="xs" c="dimmed">{voc("La dernière étape se franchit avec « Clôturer » (motif, décision et retour au plaignant).")}</Text>
          <Textarea label={voc("Commentaire")} autosize minRows={2} value={texte(v.commentaire)} onChange={(e) => changer({ commentaire: e.currentTarget.value })} />
        </>
      )}
    </Fenetre>
  );
}

export function NoterDossier({ dossier, onClose }: { dossier: DossierDetail; onClose: () => void }) {
  return (
    <Fenetre dossier={dossier} operation="noter" titre={voc("Ajouter une note")} onClose={onClose}>
      {(v, changer, erreurs) => (
        <>
          <Textarea label={voc("Note")} withAsterisk autosize minRows={3} value={texte(v.texte)} onChange={(e) => changer({ texte: e.currentTarget.value })} error={erreurs.texte} />
          <Switch label={voc("Action corrective (mesure prise pour corriger le problème)")} checked={!!v.corrective}
            onChange={(e) => changer({ corrective: e.currentTarget.checked })} />
          <Text size="xs" c="dimmed">{voc("Les notes sont internes : le plaignant ne les voit jamais.")}</Text>
        </>
      )}
    </Fenetre>
  );
}

export function CommuniquerDossier({ dossier, onClose }: { dossier: DossierDetail; onClose: () => void }) {
  const canalParDefaut = dossier.mode_reponse !== "AUCUN" ? dossier.mode_reponse : "EN_PERSONNE";
  return (
    <Fenetre dossier={dossier} operation="communiquer" titre={voc("Échange avec le plaignant")} onClose={onClose}
      initiales={{ sens: "SORTANT", canal: canalParDefaut, objet: dossier.decision ? "DECISION" : "PRISE_EN_CHARGE" }}>
      {(v, changer, erreurs) => (
        <>
          {dossier.anonyme && <Alert color="gray">{voc("Plaignant anonyme : aucune coordonnée. Il suit son dossier avec son code de suivi.")}</Alert>}
          <SegmentedControl value={texte(v.sens)} onChange={(x) => changer({ sens: x })}
            data={[{ value: "SORTANT", label: voc("Envoyé au plaignant") }, { value: "ENTRANT", label: voc("Reçu du plaignant") }]} />
          <SimpleGrid cols={2}>
            <Select label={voc("Objet")} data={OBJETS_ECHANGE.map((o) => ({ value: o, label: libelleObjetEchange(o) }))}
              value={texte(v.objet)} onChange={(x) => changer({ objet: x })} error={erreurs.objet} allowDeselect={false} />
            <Select label={voc("Moyen")} data={MODES_REPONSE.filter((m) => m !== "AUCUN").map((m) => ({ value: m, label: libelleModeReponse(m) }))}
              value={texte(v.canal)} onChange={(x) => changer({ canal: x })} error={erreurs.canal} allowDeselect={false} />
          </SimpleGrid>
          {(dossier.telephone || dossier.courriel) && (
            <Text size="xs" c="dimmed">{[dossier.nom, dossier.telephone, dossier.courriel].filter(Boolean).join(" · ")}</Text>
          )}
          <Textarea label={voc("Résumé de l'échange")} withAsterisk autosize minRows={3} value={texte(v.texte)}
            onChange={(e) => changer({ texte: e.currentTarget.value })} error={erreurs.texte} />
          <Text size="xs" c="dimmed">{voc("Ne jamais communiquer de détail confidentiel. La communication de la décision fait passer le dossier à « Réponse donnée ».")}</Text>
        </>
      )}
    </Fenetre>
  );
}

export function DeciderDossier({ dossier, onClose }: { dossier: DossierDetail; onClose: () => void }) {
  return (
    <Fenetre dossier={dossier} operation="decider" titre={voc("Enregistrer la décision")} onClose={onClose} initiales={{ decision: dossier.decision }}>
      {(v, changer, erreurs) => (
        <Textarea label={voc("Décision")} withAsterisk autosize minRows={4} value={texte(v.decision)}
          onChange={(e) => changer({ decision: e.currentTarget.value })} error={erreurs.decision} />
      )}
    </Fenetre>
  );
}

export function CloturerDossier({ dossier, onClose }: { dossier: DossierDetail; onClose: () => void }) {
  return (
    <Fenetre dossier={dossier} operation="cloturer" titre={voc("Clôturer le dossier")} onClose={onClose} libelleBouton={voc("Clôturer")}
      initiales={{ issue: "RESOLU", decision: dossier.decision, retour_donne: dossier.statut === "REPONDU" ? true : null }}>
      {(v, changer, erreurs) => (
        <>
          <Select label={voc("Issue")} data={ISSUES.map((i) => ({ value: i, label: libelleIssue(i) }))} value={texte(v.issue)}
            onChange={(x) => changer({ issue: x as IssueDossier })} error={erreurs.issue} allowDeselect={false} />
          {v.issue === "REFERE" && (
            <>
              <TextInput label={voc("Orienté vers")} placeholder={voc("Service, organisation ou prestataire")} withAsterisk
                value={texte(v.oriente_vers)} onChange={(e) => changer({ oriente_vers: e.currentTarget.value })} error={erreurs.oriente_vers} />
              <Checkbox label={voc("Le plaignant a donné son consentement à cette orientation")} checked={!!v.consentement_reference}
                onChange={(e) => changer({ consentement_reference: e.currentTarget.checked })} error={erreurs.consentement_reference} />
            </>
          )}
          <Textarea label={voc("Décision")} withAsterisk autosize minRows={2} value={texte(v.decision)}
            onChange={(e) => changer({ decision: e.currentTarget.value })} error={erreurs.decision} />
          <Textarea label={voc("Motif de la clôture")} withAsterisk autosize minRows={2} value={texte(v.motif)}
            onChange={(e) => changer({ motif: e.currentTarget.value })} error={erreurs.motif} />
          <Radio.Group label={voc("Le plaignant a-t-il été informé de la réponse ?")} withAsterisk error={erreurs.retour_donne}
            value={v.retour_donne === true ? "oui" : v.retour_donne === false ? "non" : ""} onChange={(x) => changer({ retour_donne: x === "oui" })}>
            <Group mt={6}><Radio value="oui" label={voc("Oui")} /><Radio value="non" label={voc("Non")} /></Group>
          </Radio.Group>
          {v.retour_donne === false && (
            <Textarea label={voc("Pourquoi ?")} withAsterisk autosize minRows={2} placeholder={voc("Plaignant anonyme, injoignable…")}
              value={texte(v.raison_sans_retour)} onChange={(e) => changer({ raison_sans_retour: e.currentTarget.value })} error={erreurs.raison_sans_retour} />
          )}
        </>
      )}
    </Fenetre>
  );
}

export function LierDossier({ dossier, onClose }: { dossier: DossierDetail; onClose: () => void }) {
  const { data: proches = [] } = usePossiblementLies(dossier.id);
  return (
    <Fenetre dossier={dossier} operation="lier" titre={voc("Lier à un autre dossier")} onClose={onClose} libelleBouton={voc("Lier")}>
      {(v, changer, erreurs) => (
        <>
          <Text size="sm" c="dimmed">{voc("Pour rapprocher des retours qui concernent le même problème. Rien n'est fusionné automatiquement.")}</Text>
          <TextInput label={voc("Numéro du dossier")} placeholder="MGP-2026-00012" value={texte(v.numero)}
            onChange={(e) => changer({ numero: e.currentTarget.value })} error={erreurs.numero} />
          {proches.length > 0 && (
            <Stack gap={4}>
              <Text size="sm" fw={500}>{voc("Dossiers possiblement liés (même projet, même catégorie, dates proches)")}</Text>
              {proches.map((p) => (
                <Button key={p.id} variant="subtle" size="xs" justify="flex-start" leftSection={<Link2 size={13} />} onClick={() => changer({ numero: p.numero })}>
                  {p.numero} — {dateLisible(p.date_reception)} — {libelleStatutDossier(p.statut)}
                </Button>
              ))}
            </Stack>
          )}
        </>
      )}
    </Fenetre>
  );
}

export function ProlongerDossier({ dossier, onClose }: { dossier: DossierDetail; onClose: () => void }) {
  return (
    <Fenetre dossier={dossier} operation="prolonger" titre={voc("Prolonger le délai")} onClose={onClose} libelleBouton={voc("Prolonger")} initiales={{ jours: 7 }}>
      {(v, changer, erreurs) => (
        <>
          <Text size="sm" c="dimmed">
            {dossier.echeance ? voc`Échéance actuelle : ${dateLisible(dossier.echeance)}.` : ""}{" "}
            {voc("La prolongation est exceptionnelle et tracée au journal du dossier.")}
          </Text>
          <NumberInput label={voc("Nombre de jours supplémentaires")} withAsterisk min={1} max={180} w={220}
            value={typeof v.jours === "number" ? v.jours : ""} onChange={(x) => changer({ jours: x === "" ? null : Number(x) })} error={erreurs.jours} />
          <Textarea label={voc("Motif")} withAsterisk autosize minRows={2} value={texte(v.motif)}
            onChange={(e) => changer({ motif: e.currentTarget.value })} error={erreurs.motif} />
        </>
      )}
    </Fenetre>
  );
}

/** Personnes mises en cause : exclues du dossier ; le dossier devient confidentiel (circuit alternatif si besoin). */
export function MettreEnCauseDossier({ dossier, onClose }: { dossier: DossierDetail; onClose: () => void }) {
  const { data: utilisateurs = [] } = useUtilisateurs();
  return (
    <Fenetre dossier={dossier} operation="mettre-en-cause" titre={voc("Personnes mises en cause")} onClose={onClose}
      initiales={{ utilisateurs: dossier.mis_en_cause_utilisateurs, libre: dossier.mis_en_cause_libre }}>
      {(v, changer, erreurs) => (
        <>
          <Alert color="grape">
            {voc("Une personne mise en cause n'a plus aucun accès au dossier, quel que soit son rôle, ni à ses notifications. Si elle fait partie du circuit confidentiel habituel, le dossier part au circuit alternatif.")}
          </Alert>
          <MultiSelect label={voc("Utilisateurs de la plateforme")} searchable clearable error={erreurs.utilisateurs}
            data={utilisateurs.map((u) => ({ value: String(u.id), label: `${u.first_name} ${u.last_name}`.trim() || u.username }))}
            value={((v.utilisateurs as number[]) ?? []).map(String)} onChange={(x) => changer({ utilisateurs: x.map(Number) })} />
          <TextInput label={voc("Autres personnes (noms ou fonctions)")} value={texte(v.libre)} onChange={(e) => changer({ libre: e.currentTarget.value })} />
        </>
      )}
    </Fenetre>
  );
}

/** Orientation vers une assistance : on enregistre consentement, date et prestataire, jamais le contenu des échanges. */
export function AssistanceDossier({ dossier, onClose }: { dossier: DossierDetail; onClose: () => void }) {
  const { data: prestataires = [] } = usePrestataires();
  return (
    <Fenetre dossier={dossier} operation="assistance" titre={voc("Orienter vers une assistance")} onClose={onClose}
      initiales={{ date: new Date().toISOString().slice(0, 10) }}>
      {(v, changer, erreurs) => (
        <>
          <Text size="sm" c="dimmed">{voc("Seuls le prestataire, la date et le consentement sont enregistrés — jamais le contenu des échanges avec le prestataire.")}</Text>
          <Select label={voc("Prestataire")} withAsterisk searchable error={erreurs.prestataire}
            data={prestataires.filter((p) => p.actif).map((p) => ({ value: String(p.id), label: `${p.nom} — ${libelleTypePrestataire(p.type)}${p.zone ? ` (${p.zone})` : ""}` }))}
            value={nombre(v.prestataire)} onChange={(x) => changer({ prestataire: x ? Number(x) : null })}
            nothingFoundMessage={voc("Annuaire vide : ajoutez des prestataires dans le paramétrage.")} />
          <TextInput type="date" label={voc("Date de l'orientation")} value={texte(v.date)} onChange={(e) => changer({ date: e.currentTarget.value })} error={erreurs.date} w={200} />
          <Checkbox label={voc("La personne a donné son consentement à cette orientation")} checked={v.consentement === true}
            onChange={(e) => changer({ consentement: e.currentTarget.checked })} error={erreurs.consentement} />
        </>
      )}
    </Fenetre>
  );
}

export function SuspendreDossier({ dossier, onClose }: { dossier: DossierDetail; onClose: () => void }) {
  const lever = dossier.suspension_legale;
  return (
    <Fenetre dossier={dossier} operation="suspendre" titre={lever ? voc("Lever la suspension légale") : voc("Suspension légale")} onClose={onClose}
      initiales={{ suspendre: !lever }} libelleBouton={lever ? voc("Lever la suspension") : voc("Suspendre")} couleur="orange">
      {(v, changer, erreurs) => (
        <>
          <Text size="sm" c="dimmed">
            {lever ? voc("Le dossier pourra de nouveau être anonymisé à l'échéance de conservation.")
              : voc("Dossier lié à une procédure (enquête, justice…) : il ne sera jamais anonymisé tant que la suspension dure.")}
          </Text>
          <Textarea label={voc("Motif")} withAsterisk autosize minRows={2} value={texte(v.motif)} onChange={(e) => changer({ motif: e.currentTarget.value })} error={erreurs.motif} />
        </>
      )}
    </Fenetre>
  );
}

export function AnonymiserDossier({ dossier, onClose }: { dossier: DossierDetail; onClose: () => void }) {
  return (
    <Fenetre dossier={dossier} operation="anonymiser" titre={voc("Anonymiser le dossier")} onClose={onClose} libelleBouton={voc("Anonymiser définitivement")} couleur="red">
      {(v, changer, erreurs) => (
        <>
          <Alert color="red">
            {voc("Le récit, l'identité et les coordonnées du plaignant, les personnes mises en cause, les notes, la décision et l'historique détaillé seront supprimés. Seules les informations utiles aux statistiques sont conservées (numéro, dates, type, catégorie, canal, statut, issue). Cette action est irréversible.")}
          </Alert>
          <Checkbox label={voc("Je confirme l'anonymisation définitive de ce dossier")} checked={v.confirmation === true}
            onChange={(e) => changer({ confirmation: e.currentTarget.checked })} error={erreurs.confirmation} />
        </>
      )}
    </Fenetre>
  );
}

/** Signalement manuel comme sensible (même en lecture seule) : on peut en perdre l'accès aussitôt. */
export function SignalerDossier({ dossier, onClose }: { dossier: DossierDetail; onClose: () => void }) {
  const signaler = useSignalerSensible(dossier.id);
  const navigate = useNavigate();
  const [motif, setMotif] = useState("");
  const envoyer = async () => {
    try {
      const r = await signaler.mutateAsync(motif);
      onClose();
      notifications.show({ title: voc("Transmis au circuit confidentiel"), message: voc("Le dossier est désormais traité de façon confidentielle."), color: "grape" });
      if (!r.visible) navigate("/plaintes");
    } catch (error) {
      notifications.show({ message: messageErreurApi(error, voc("Erreur lors de l'enregistrement")), color: "red" });
    }
  };
  return (
    <Modal opened onClose={onClose} title={voc("Signaler comme sensible")} size="lg">
      <Stack>
        <Alert color="grape">
          {voc("Le dossier passera aussitôt au circuit confidentiel. Si vous n'êtes pas une personne désignée de ce circuit, vous n'y aurez plus accès. Dans le doute, mieux vaut signaler : une erreur se corrige, une fuite ne se corrige pas.")}
        </Alert>
        <Textarea label={voc("Pourquoi ? (facultatif)")} autosize minRows={2} value={motif} onChange={(e) => setMotif(e.currentTarget.value)} />
        <Group justify="flex-end">
          <Button variant="default" onClick={onClose}>{voc("Annuler")}</Button>
          <Button color="grape" onClick={envoyer} loading={signaler.isPending}>{voc("Signaler comme sensible")}</Button>
        </Group>
      </Stack>
    </Modal>
  );
}

/** Export PDF en filigrane ; pour un dossier confidentiel : motif et confirmation, tracés au journal. */
export function ExporterDossier({ dossier, onClose }: { dossier: DossierDetail; onClose: () => void }) {
  const [motif, setMotif] = useState("");
  const [confirme, setConfirme] = useState(false);
  const [erreurs, setErreurs] = useState<Record<string, string>>({});
  const [enCours, setEnCours] = useState(false);
  const envoyer = async () => {
    setErreurs({});
    setEnCours(true);
    try {
      await exporterFicheDossier(dossier.id, dossier.numero, motif, confirme);
      onClose();
    } catch (error) {
      // Réponse d'erreur reçue comme fichier : on la relit.
      const donnees = (error as { response?: { data?: unknown } }).response?.data;
      const lu = donnees instanceof Blob ? JSON.parse(await donnees.text()) : {};
      setErreurs(Object.fromEntries(Object.entries(lu).map(([k, x]) => [k, voc(String(Array.isArray(x) ? x[0] : x))])));
    } finally {
      setEnCours(false);
    }
  };
  return (
    <Modal opened onClose={onClose} title={voc("Exporter la fiche (PDF)")} size="lg">
      <Stack>
        <Text size="sm" c="dimmed">
          {voc("Chaque page porte votre nom et la date en filigrane. L'export est inscrit au journal du dossier.")}
        </Text>
        <Textarea label={voc("Motif de l'export")} withAsterisk={dossier.sensible} autosize minRows={2} value={motif}
          onChange={(e) => setMotif(e.currentTarget.value)} error={erreurs.motif} />
        {dossier.sensible && (
          <Checkbox label={voc("Je confirme exporter un dossier confidentiel et le garder en sécurité")} checked={confirme}
            onChange={(e) => setConfirme(e.currentTarget.checked)} error={erreurs.confirmation} />
        )}
        <Group justify="flex-end">
          <Button variant="default" onClick={onClose}>{voc("Annuler")}</Button>
          <Button onClick={envoyer} loading={enCours}>{voc("Exporter")}</Button>
        </Group>
      </Stack>
    </Modal>
  );
}
