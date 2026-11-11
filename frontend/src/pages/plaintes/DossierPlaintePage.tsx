import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import {
  ArrowLeft,
  ArrowRightLeft,
  CalendarPlus,
  CheckCheck,
  Eraser,
  FileDown,
  HandHeart,
  Send,
  ShieldAlert,
  ShieldCheck,
  ShieldX,
  UserRoundX,
  FolderCheck,
  Gavel,
  Landmark,
  Link2,
  Lock,
  MessageSquareText,
  Pencil,
  RotateCcw,
  Scale,
  Siren,
  StickyNote,
  Tags,
  Trash2,
  UserCheck,
  UserX,
  Wrench,
} from "lucide-react";
import { Alert, Anchor, Badge, Button, Card, Grid, Group, Loader, SimpleGrid, Stack, Text, Timeline, Title, Tooltip } from "@mantine/core";
import {
  type ActionDossier,
  type DossierDetail,
  type IssueDossier,
  type ModeReponse,
  type ObjetEchange,
  couleurStatutDossier,
  dateLisible,
  libelleCanal,
  libelleIssue,
  libelleModeReponse,
  libelleObjetEchange,
  libelleStatutDossier,
  libelleTypeAction,
  libelleTypePrestataire,
  useActionsCorrectives,
  useDossierPlainte,
} from "../../api/plaintes";
import { useAuth } from "../../auth/useAuth";
import { locale } from "../../utils/i18n";
import { useAccesModules } from "../../utils/modules";
import { voc } from "../../utils/vocabulaire";
import {
  AffecterDossier,
  ClasserDossier,
  CloturerDossier,
  CommuniquerDossier,
  DeciderDossier,
  EtapeDossier,
  LierDossier,
  MotifDossier,
  NoterDossier,
  ProlongerDossier,
  AnonymiserDossier,
  EffacerDossier,
  AssistanceDossier,
  ExporterDossier,
  EnvoyerMessage,
  MettreEnCauseDossier,
  ModifierPlaignant,
  SignalerDossier,
  SuspendreDossier,
} from "./OperationsDossier";
import { ActionCorrectiveModal, BadgeStatutAction } from "./ActionsCorrectivesPage";
import { BadgeDelai } from "./DelaiDossier";
import { PiecesJointesDossier } from "./PiecesJointesDossier";

const COULEUR_ACTION: Partial<Record<ActionDossier["type"], string>> = {
  RETARD: "red",
  PROLONGATION: "orange",
  MISE_EN_CAUSE: "grape",
  ASSISTANCE: "pink",
  EXPORT: "gray",
  SUSPENSION: "orange",
  ANONYMISATION: "dark",
  PLAIGNANT: "indigo",
  RECEPTION: "blue",
  AFFECTATION: "cyan",
  DECISION: "violet",
  COMMUNICATION: "teal",
  CLOTURE: "gray",
  REOUVERTURE: "orange",
  RECOURS: "red",
  SENSIBILITE: "grape",
  ACTION_CORRECTIVE: "lime",
  PIECE_JOINTE: "blue",
  TELECHARGEMENT: "gray",
  COMPLEMENT: "teal",
};

function Ligne({ libelle, children }: { libelle: string; children: React.ReactNode }) {
  return (
    <Stack gap={0}>
      <Text size="xs" c="dimmed">{libelle}</Text>
      <Text size="sm" component="div">{children || "—"}</Text>
    </Stack>
  );
}

const NOMS_CHAMPS: Record<string, string> = {
  type_retour: "Type de retour",
  categorie: "Catégorie",
  priorite: "Priorité",
  projet: "Projet",
};

/** Ce qu'une action a changé, en clair. */
function DetailsAction({ action }: { action: ActionDossier }) {
  const d = action.details as Record<string, unknown>;
  if (action.type === "RECEPTION") {
    return <Text size="xs" c="dimmed">{libelleCanal(d.canal as never)}{d.circuit ? ` · ${d.circuit}` : ""}</Text>;
  }
  if (action.type === "CLASSIFICATION") {
    return (
      <Stack gap={0}>
        {Object.entries(d).map(([champ, valeurs]) => {
          const [de, a] = valeurs as [string, string];
          return <Text key={champ} size="xs">{voc(NOMS_CHAMPS[champ] ?? champ)} : {de || "—"} → {a || "—"}</Text>;
        })}
      </Stack>
    );
  }
  if (action.type === "ASSISTANCE") {
    return <Text size="xs">{String(d.prestataire)} · {libelleTypePrestataire(d.type as never)} · {d.date ? dateLisible(String(d.date)) : ""}</Text>;
  }
  if (action.type === "MISE_EN_CAUSE") {
    return <Text size="xs">{voc`${Number(d.comptes ?? 0)} utilisateur(s)`}{d.noms_libres ? ` · ${voc("autres personnes")}` : ""}</Text>;
  }
  if (action.type === "SENSIBILITE" && d.leve) {
    return <Text size="xs" c="teal.8">{voc("Sensibilité levée")}{d.circuit ? ` · ${String(d.circuit)}` : ""}</Text>;
  }
  if (action.type === "PROLONGATION") {
    return <Text size="xs">+{String(d.jours)} j · {d.de ? dateLisible(String(d.de)) : "—"} → {dateLisible(String(d.a))}</Text>;
  }
  if (action.type === "RETARD") {
    return <Text size="xs" c="red.8">{voc("Échéance")} : {d.echeance ? dateLisible(String(d.echeance)) : "—"}</Text>;
  }
  if ("de" in d || "a" in d) {
    return <Text size="xs">{String(d.de || "—")} → {String(d.a || "—")}</Text>;
  }
  if (action.type === "CLOTURE") {
    return (
      <Text size="xs">
        {libelleIssue(d.issue as IssueDossier)} · {d.retour_donne ? voc("plaignant informé") : voc("plaignant non informé")}
        {d.oriente_vers ? ` · ${voc("orienté vers")} ${String(d.oriente_vers)}` : ""}
      </Text>
    );
  }
  if (action.type === "PIECE_JOINTE") {
    return <Text size="xs" c="dimmed">{d.retrait ? voc("Pièce retirée") : voc`${Number(d.ajout ?? 0)} fichier(s) ajouté(s)`}</Text>;
  }
  if (action.type === "COMPLEMENT" && Number(d.pieces)) {
    return <Text size="xs" c="dimmed">{voc`${Number(d.pieces)} fichier(s) joint(s)`}</Text>;
  }
  if (action.type === "COMMUNICATION") {
    const statut = d.statut_envoi as string | undefined;
    return (
      <Group gap={6}>
        <Text size="xs" c="dimmed">
          {action.sens === "ENTRANT" ? voc("Reçu du plaignant") : voc("Envoyé au plaignant")} · {libelleObjetEchange(action.objet as ObjetEchange)} ·{" "}
          {action.canal === "SMS" ? voc("SMS") : action.canal === "COURRIEL" ? voc("Courriel") : libelleModeReponse(action.canal as ModeReponse)}
        </Text>
        {statut && (
          <Badge size="xs" variant="light" tt="none" color={statut === "ENVOYE" ? "teal" : statut === "SIMULE" ? "yellow" : "red"}>
            {statut === "ENVOYE" ? voc("Envoyé") : statut === "SIMULE" ? voc("Envoi simulé") : voc("Échec de l'envoi")}
          </Badge>
        )}
        {d.satisfait !== undefined && <Badge size="xs" variant="light" tt="none" color={d.satisfait ? "teal" : "orange"}>{d.satisfait ? voc("Satisfait") : voc("Non satisfait")}</Badge>}
      </Group>
    );
  }
  return null;
}

function Journal({ actions }: { actions: ActionDossier[] }) {
  return (
    <Timeline bulletSize={14} lineWidth={2} active={actions.length}>
      {actions.map((a) => (
        <Timeline.Item key={a.id} color={COULEUR_ACTION[a.type] ?? "gray"} title={<Text size="sm" fw={600}>{libelleTypeAction(a.type)}</Text>}>
          <Text size="xs" c="dimmed">
            {new Date(a.date).toLocaleString(locale(), { dateStyle: "short", timeStyle: "short" })}
            {a.auteur_nom ? ` · ${a.auteur_nom}` : ""}
          </Text>
          <DetailsAction action={a} />
          {a.texte && <Text size="sm" mt={2} style={{ whiteSpace: "pre-line" }}>{a.texte}</Text>}
        </Timeline.Item>
      ))}
    </Timeline>
  );
}

type Fenetre =
  | "classer" | "affecter" | "etape" | "noter" | "communiquer" | "decider" | "cloturer" | "rouvrir" | "recours" | "recuser" | "lier"
  | "prolonger" | "signaler" | "lever" | "mettre_en_cause" | "assistance" | "suspendre" | "anonymiser" | "exporter" | "message" | "plaignant"
  | "effacer" | null;

/** Barre d'actions : seules les opérations possibles dans l'état du dossier sont proposées. */
function Actions({ dossier, ouvrir }: { dossier: DossierDetail; ouvrir: (f: Fenetre) => void }) {
  const { user } = useAuth();
  const clos = dossier.statut === "CLOTURE";
  const peutRouvrir = user?.role === "ADMIN" || user?.role === "COORDO_GENERAL";
  const bouton = (f: Fenetre, libelle: string, icone: React.ReactNode, props: Record<string, unknown> = {}) => (
    <Button size="xs" variant="light" leftSection={icone} onClick={() => ouvrir(f)} {...props}>{libelle}</Button>
  );
  return (
    <Group gap={6}>
      {!clos && bouton("affecter", dossier.responsable ? voc("Réaffecter") : voc("Affecter"), <UserCheck size={14} />, dossier.responsable ? {} : { variant: "filled" })}
      {!clos && bouton("classer", voc("Classer"), <Tags size={14} />)}
      {!clos && bouton("etape", voc("Changer d'étape"), <ArrowRightLeft size={14} />)}
      {bouton("noter", voc("Note"), <StickyNote size={14} />)}
      {!dossier.anonyme && (dossier.telephone || dossier.courriel) && bouton("message", voc("Envoyer un message"), <Send size={14} />)}
      {bouton("communiquer", voc("Échange avec le plaignant"), <MessageSquareText size={14} />)}
      {!clos && bouton("decider", voc("Décision"), <Gavel size={14} />)}
      {!clos && bouton("cloturer", voc("Clôturer"), <FolderCheck size={14} />, { color: "gray", variant: "filled" })}
      {(dossier.statut === "REPONDU" || clos) && bouton("recours", voc("Recours"), <Scale size={14} />, { color: "red" })}
      {clos && peutRouvrir && bouton("rouvrir", voc("Rouvrir"), <RotateCcw size={14} />, { color: "orange" })}
      {!clos && peutRouvrir && bouton("prolonger", voc("Prolonger le délai"), <CalendarPlus size={14} />, { variant: "subtle" })}
      {bouton("lier", voc("Lier"), <Link2 size={14} />, { variant: "subtle" })}
      {!clos && dossier.responsable === user?.id && bouton("recuser", voc("Me récuser"), <UserX size={14} />, { variant: "subtle", color: "red" })}
      {!clos && bouton("mettre_en_cause", voc("Personnes mises en cause"), <UserRoundX size={14} />, { color: "grape", variant: "subtle" })}
      {dossier.sensible && bouton("assistance", voc("Orienter vers une assistance"), <HandHeart size={14} />, { color: "pink", variant: "subtle" })}
      {dossier.sensible && dossier.habilite && bouton("lever", voc("Lever la sensibilité"), <ShieldCheck size={14} />, { color: "grape", variant: "subtle" })}
      {user?.role === "ADMIN" && bouton("suspendre", dossier.suspension_legale ? voc("Lever la suspension légale") : voc("Suspension légale"), <Landmark size={14} />, { color: "orange", variant: "subtle" })}
      {user?.role === "ADMIN" && clos && !dossier.suspension_legale && !dossier.anonymise && bouton("anonymiser", voc("Anonymiser"), <Eraser size={14} />, { color: "red", variant: "subtle" })}
      {user?.role === "ADMIN" && !dossier.suspension_legale && bouton("effacer", voc("Effacer définitivement"), <Trash2 size={14} />, { color: "red", variant: "subtle" })}
    </Group>
  );
}

/** Actions correctives reliées au dossier (suivies dans « Actions correctives »). */
function ActionsCorrectivesDossier({ dossierId, modifiable }: { dossierId: number; modifiable: boolean }) {
  const { data: actions = [] } = useActionsCorrectives({ dossiers: dossierId });
  const [nouvelle, setNouvelle] = useState(false);
  if (!actions.length && !modifiable) return null;
  return (
    <Card withBorder>
      <Stack gap="xs">
        <Group justify="space-between">
          <Group gap="xs"><Wrench size={16} /><Text fw={600} size="sm">{voc("Actions correctives")}</Text></Group>
          {modifiable && <Button size="xs" variant="subtle" onClick={() => setNouvelle(true)}>{voc("Nouvelle action corrective")}</Button>}
        </Group>
        {actions.map((a) => (
          <Group key={a.id} justify="space-between" wrap="nowrap">
            <Anchor component={Link} to="/plaintes/actions-correctives" size="sm">{a.titre}</Anchor>
            <Group gap="xs" wrap="nowrap">
              {a.echeance && <Text size="xs" c="dimmed">{dateLisible(a.echeance)}</Text>}
              <BadgeStatutAction statut={a.statut} />
            </Group>
          </Group>
        ))}
        {actions.length === 0 && <Text size="sm" c="dimmed">{voc("Aucune action corrective liée.")}</Text>}
      </Stack>
      {nouvelle && <ActionCorrectiveModal dossierInitial={dossierId} onClose={() => setNouvelle(false)} />}
    </Card>
  );
}

/** Fiche d'un dossier et son traitement. */
export function DossierPlaintePage() {
  const id = Number(useParams().id);
  const { data: dossier, isLoading, isError } = useDossierPlainte(id);
  const modifiable = useAccesModules().peutEcrire("/plaintes");
  const [fenetre, setFenetre] = useState<Fenetre>(null);
  const fermer = () => setFenetre(null);

  const retour = (
    <Anchor component={Link} to="/plaintes" size="sm">
      <Group gap={4}><ArrowLeft size={14} />{voc("Plaintes et retours")}</Group>
    </Anchor>
  );
  if (isLoading) return <Loader />;
  if (isError || !dossier) {
    return (
      <Stack>
        {retour}
        <Alert color="gray">{voc("Dossier introuvable, ou réservé aux personnes désignées (circuit confidentiel).")}</Alert>
      </Stack>
    );
  }

  return (
    <Stack>
      <Stack gap={4}>
        {retour}
        <Group justify="space-between" align="flex-start">
          <Group gap="xs">
            <Title order={2}>{dossier.numero}</Title>
            <Badge color={couleurStatutDossier(dossier.statut)} variant="light" tt="none" size="lg">{libelleStatutDossier(dossier.statut)}</Badge>
            {dossier.sensible && <Badge color="grape" leftSection={<Lock size={11} />} tt="none" size="lg">{voc("Confidentiel")}</Badge>}
            {dossier.priorite_urgente && <Badge color="red" leftSection={<Siren size={11} />} tt="none" size="lg">{dossier.priorite_nom}</Badge>}
            {dossier.en_recours && <Badge color="red" variant="outline" tt="none" size="lg">{voc("Recours en cours")}</Badge>}
          </Group>
        </Group>
        <Group gap={6}>
          {modifiable && !dossier.anonymise && <Actions dossier={dossier} ouvrir={setFenetre} />}
          {!dossier.sensible && !dossier.anonymise && (
            <Button size="xs" variant="subtle" color="grape" leftSection={<ShieldAlert size={14} />} onClick={() => setFenetre("signaler")}>
              {voc("Signaler comme sensible")}
            </Button>
          )}
          <Button size="xs" variant="subtle" color="gray" leftSection={<FileDown size={14} />} onClick={() => setFenetre("exporter")}>
            {voc("Exporter (PDF)")}
          </Button>
        </Group>
      </Stack>

      <Grid gap="md">
        <Grid.Col span={{ base: 12, md: 7 }}>
          <Stack>
            <Card withBorder>
              <Stack gap="sm">
                <SimpleGrid cols={{ base: 1, sm: 3 }} spacing="sm">
                  <Ligne libelle={voc("Gestionnaire")}>{dossier.responsable_nom ?? <Text size="sm" c="orange.8">{voc("Sans responsable")}</Text>}</Ligne>
                  <Ligne libelle={voc("Circuit et étape")}>{[dossier.circuit_nom, dossier.etape_nom].filter(Boolean).join(" › ")}</Ligne>
                  <Ligne libelle={voc("Priorité")}>{dossier.priorite_nom ?? voc("À évaluer")}</Ligne>
                  <Ligne libelle={voc("Échéance du dossier")}>
                    <BadgeDelai dossier={dossier} />
                    {dossier.jours_prolongation > 0 && <Text size="xs" c="dimmed">{voc`dont ${dossier.jours_prolongation} j de prolongation`}</Text>}
                  </Ligne>
                  <Ligne libelle={voc("Échéance de l'étape")}>
                    {dossier.statut !== "CLOTURE" && dossier.echeance_etape && (
                      <Text size="sm" c={new Date(`${dossier.echeance_etape}T23:59:59`) < new Date() ? "red.8" : undefined}>
                        {dateLisible(dossier.echeance_etape)}
                      </Text>
                    )}
                  </Ligne>
                  <Ligne libelle={voc("Dans l'étape depuis le")}>{dossier.statut !== "CLOTURE" && dossier.date_entree_etape && dateLisible(dossier.date_entree_etape)}</Ligne>
                  <Ligne libelle={voc("Reçu le")}>{dateLisible(dossier.date_reception)}</Ligne>
                  <Ligne libelle={voc("Canal de réception")}>{libelleCanal(dossier.canal)}</Ligne>
                  <Ligne libelle={voc("Type de retour")}>{dossier.type_retour_nom}</Ligne>
                  <Ligne libelle={voc("Catégorie")}>
                    {dossier.categorie_nom ? [dossier.categorie_parent_nom, dossier.categorie_nom].filter(Boolean).join(" › ") : voc("À classer")}
                  </Ligne>
                  <Ligne libelle={voc("Projet")}>{dossier.projet_code ? `${dossier.projet_code} — ${dossier.projet_nom}` : dossier.projet_nom}</Ligne>
                  <Ligne libelle={voc("Lieu")}>{dossier.lieu}</Ligne>
                </SimpleGrid>
                <Ligne libelle={voc("Description")}><Text size="sm" style={{ whiteSpace: "pre-line" }}>{dossier.description}</Text></Ligne>
                <Ligne libelle={voc("Concerne le personnel ou un partenaire")}>
                  {dossier.concerne_personnel === null ? voc("Ne sait pas") : dossier.concerne_personnel ? voc("Oui") : voc("Non")}
                </Ligne>
              </Stack>
            </Card>

            <Card withBorder>
              <Stack gap="sm">
                <Group justify="space-between">
                  <Text fw={600} size="sm">{voc("Plaignant")}</Text>
                  {modifiable && !dossier.anonymise && (
                    <Button size="compact-xs" variant="subtle" leftSection={<Pencil size={12} />} onClick={() => setFenetre("plaignant")}>
                      {voc("Modifier")}
                    </Button>
                  )}
                </Group>
                {dossier.anonyme ? (
                  <Text size="sm">
                    {dossier.saisi_par_nom
                      ? voc("Anonyme vis-à-vis de l'organisation : l'agent qui a saisi le retour n'a enregistré aucune information d'identité.")
                      : voc("Anonyme : aucune information d'identité enregistrée.")}
                  </Text>
                ) : (
                  <SimpleGrid cols={{ base: 1, sm: 2 }} spacing="sm">
                    <Ligne libelle={voc("Nom")}>{dossier.nom}</Ligne>
                    <Ligne libelle={voc("Téléphone")}>{dossier.telephone}</Ligne>
                    <Ligne libelle={voc("Courriel")}>{dossier.courriel}</Ligne>
                    <Ligne libelle={voc("Réponse souhaitée")}>{libelleModeReponse(dossier.mode_reponse)}</Ligne>
                  </SimpleGrid>
                )}
                <SimpleGrid cols={{ base: 1, sm: 2 }} spacing="sm">
                  <Ligne libelle={voc("Consentement")}>
                    {dossier.consentement ? voc("Oui") : voc("Non")}
                    {dossier.consentement_le && (
                      <Tooltip label={dossier.consentement_texte} multiline w={360} disabled={!dossier.consentement_texte}>
                        <Text span size="xs" c="dimmed"> · {voc("le")} {dateLisible(dossier.consentement_le.slice(0, 10))}</Text>
                      </Tooltip>
                    )}
                  </Ligne>
                  <Ligne libelle={voc("Saisi par")}>
                    {dossier.saisi_par_nom ?? voc("Le plaignant (formulaire public)")}
                    {dossier.recueilli_directement === false && ` — ${voc("non recueilli directement")}`}
                  </Ligne>
                </SimpleGrid>
              </Stack>
            </Card>

            <Card withBorder>
              <Stack gap="sm">
                <Group gap="xs"><CheckCheck size={16} /><Text fw={600} size="sm">{voc("Décision et clôture")}</Text></Group>
                <Ligne libelle={voc("Décision")}>
                  {dossier.decision ? (
                    <Text size="sm" style={{ whiteSpace: "pre-line" }}>
                      {dossier.decision}
                      {dossier.date_decision && <Text span size="xs" c="dimmed"> — {dateLisible(dossier.date_decision)}</Text>}
                    </Text>
                  ) : (
                    <Text size="sm" c="dimmed">{voc("Pas encore de décision.")}</Text>
                  )}
                </Ligne>
                <SimpleGrid cols={{ base: 1, sm: 2 }} spacing="sm">
                  <Ligne libelle={voc("Réponse communiquée le")}>{dossier.date_reponse && dateLisible(dossier.date_reponse)}</Ligne>
                  {dossier.gestionnaire_initial_nom && <Ligne libelle={voc("Premier gestionnaire")}>{dossier.gestionnaire_initial_nom}</Ligne>}
                </SimpleGrid>
                {dossier.statut === "CLOTURE" && (
                  <SimpleGrid cols={{ base: 1, sm: 2 }} spacing="sm">
                    <Ligne libelle={voc("Issue")}>{dossier.issue && libelleIssue(dossier.issue)}</Ligne>
                    <Ligne libelle={voc("Clôturé le")}>{dossier.date_cloture && dateLisible(dossier.date_cloture)}</Ligne>
                    <Ligne libelle={voc("Motif de la clôture")}>{dossier.motif_cloture}</Ligne>
                    <Ligne libelle={voc("Plaignant informé")}>
                      {dossier.retour_donne ? voc("Oui") : `${voc("Non")} — ${dossier.raison_sans_retour}`}
                    </Ligne>
                    {dossier.oriente_vers && <Ligne libelle={voc("Orienté vers")}>{dossier.oriente_vers}</Ligne>}
                  </SimpleGrid>
                )}
              </Stack>
            </Card>

            {(dossier.sensible || dossier.mis_en_cause_noms.length > 0 || dossier.mis_en_cause_libre || dossier.suspension_legale ||
              dossier.anonymise || dossier.fin_conservation) && (
              <Card withBorder>
                <Stack gap="sm">
                  <Group gap="xs"><ShieldX size={16} /><Text fw={600} size="sm">{voc("Confidentialité et conservation")}</Text></Group>
                  {dossier.anonymise && <Alert color="gray">{voc`Dossier anonymisé le ${dossier.date_anonymisation ? dateLisible(dossier.date_anonymisation) : ""} : seules les données statistiques sont conservées.`}</Alert>}
                  {dossier.suspension_legale && <Alert color="orange" title={voc("Suspension légale")}>{dossier.motif_suspension}</Alert>}
                  <SimpleGrid cols={{ base: 1, sm: 2 }} spacing="sm">
                    {(dossier.mis_en_cause_noms.length > 0 || dossier.mis_en_cause_libre) && (
                      <Ligne libelle={voc("Personnes mises en cause")}>{[...dossier.mis_en_cause_noms, dossier.mis_en_cause_libre].filter(Boolean).join(", ")}</Ligne>
                    )}
                    {dossier.fin_conservation && !dossier.anonymise && (
                      <Ligne libelle={voc("Fin de la durée de conservation")}>{dateLisible(dossier.fin_conservation)}</Ligne>
                    )}
                  </SimpleGrid>
                  {dossier.referencements.length > 0 && (
                    <Ligne libelle={voc("Assistance et référencement")}>
                      {dossier.referencements.map((r) => (
                        <Text key={r.id} size="sm">{dateLisible(r.date)} · {r.prestataire} ({libelleTypePrestataire(r.type)}) · {voc("avec consentement")}</Text>
                      ))}
                    </Ligne>
                  )}
                </Stack>
              </Card>
            )}

            <PiecesJointesDossier dossier={dossier} modifiable={modifiable} />

            <ActionsCorrectivesDossier dossierId={dossier.id} modifiable={modifiable} />

            {dossier.dossiers_lies.length > 0 && (
              <Card withBorder>
                <Stack gap={6}>
                  <Group gap="xs"><Link2 size={16} /><Text fw={600} size="sm">{voc("Dossiers liés")}</Text></Group>
                  <Group gap="xs">
                    {dossier.dossiers_lies.map((l) => (
                      <Badge key={l.id} component={Link} to={`/plaintes/dossiers/${l.id}`} variant="light" color={couleurStatutDossier(l.statut)}
                        tt="none" style={{ cursor: "pointer" }}>
                        {l.numero} · {libelleStatutDossier(l.statut)}
                      </Badge>
                    ))}
                  </Group>
                </Stack>
              </Card>
            )}
          </Stack>
        </Grid.Col>
        <Grid.Col span={{ base: 12, md: 5 }}>
          <Card withBorder>
            <Stack gap="sm">
              <Text fw={600} size="sm">{voc("Journal du dossier")}</Text>
              <Journal actions={dossier.actions} />
            </Stack>
          </Card>
        </Grid.Col>
      </Grid>

      {fenetre === "classer" && <ClasserDossier dossier={dossier} onClose={fermer} />}
      {fenetre === "affecter" && <AffecterDossier dossier={dossier} onClose={fermer} />}
      {fenetre === "etape" && <EtapeDossier dossier={dossier} onClose={fermer} />}
      {fenetre === "noter" && <NoterDossier dossier={dossier} onClose={fermer} />}
      {fenetre === "communiquer" && <CommuniquerDossier dossier={dossier} onClose={fermer} />}
      {fenetre === "decider" && <DeciderDossier dossier={dossier} onClose={fermer} />}
      {fenetre === "cloturer" && <CloturerDossier dossier={dossier} onClose={fermer} />}
      {fenetre === "lier" && <LierDossier dossier={dossier} onClose={fermer} />}
      {fenetre === "prolonger" && <ProlongerDossier dossier={dossier} onClose={fermer} />}
      {fenetre === "signaler" && <SignalerDossier dossier={dossier} onClose={fermer} />}
      {fenetre === "message" && <EnvoyerMessage dossier={dossier} onClose={fermer} />}
      {fenetre === "exporter" && <ExporterDossier dossier={dossier} onClose={fermer} />}
      {fenetre === "mettre_en_cause" && <MettreEnCauseDossier dossier={dossier} onClose={fermer} />}
      {fenetre === "assistance" && <AssistanceDossier dossier={dossier} onClose={fermer} />}
      {fenetre === "suspendre" && <SuspendreDossier dossier={dossier} onClose={fermer} />}
      {fenetre === "anonymiser" && <AnonymiserDossier dossier={dossier} onClose={fermer} />}
      {fenetre === "effacer" && <EffacerDossier dossier={dossier} onClose={fermer} />}
      {fenetre === "plaignant" && <ModifierPlaignant dossier={dossier} onClose={fermer} />}
      {fenetre === "lever" && (
        <MotifDossier dossier={dossier} operation="lever-sensibilite" titre={voc("Lever la sensibilité")} onClose={fermer} libelleBouton={voc("Lever la sensibilité")} couleur="grape"
          aide={voc("Le dossier repassera au circuit ordinaire. À réserver aux signalements sans objet ; le motif est inscrit au journal.")} />
      )}
      {fenetre === "recuser" && (
        <MotifDossier dossier={dossier} operation="recuser" titre={voc("Me récuser")} onClose={fermer} libelleBouton={voc("Me récuser")} couleur="red"
          aide={voc("Vous vous retirez de ce dossier (conflit d'intérêts, lien avec le plaignant…). Il devra être réaffecté.")} />
      )}
      {fenetre === "rouvrir" && (
        <MotifDossier dossier={dossier} operation="rouvrir" titre={voc("Rouvrir le dossier")} onClose={fermer} libelleBouton={voc("Rouvrir")} couleur="orange" avecEtape
          aide={voc("La réouverture est exceptionnelle : indiquez ce qui la justifie.")} />
      )}
      {fenetre === "recours" && (
        <MotifDossier dossier={dossier} operation="recours" titre={voc("Enregistrer un recours")} onClose={fermer} libelleBouton={voc("Enregistrer le recours")} couleur="red" avecEtape
          aide={voc("Le plaignant conteste la réponse. Le dossier sera réexaminé par une autre personne que le premier gestionnaire.")} />
      )}
    </Stack>
  );
}
