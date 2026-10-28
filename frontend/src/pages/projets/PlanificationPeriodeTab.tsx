import { useEffect, useMemo, useState } from "react";
import {
  CalendarPlus,
  CalendarRange,
  Download,
  ListPlus,
  ListChecks,
  Pencil,
  Plus,
  Search,
  Target,
  Trash2,
  TrendingUp,
  Wallet,
} from "lucide-react";
import {
  ActionIcon,
  Alert,
  Badge,
  Button,
  Card,
  Group,
  Menu,
  Modal,
  NumberInput,
  Progress,
  Select,
  SimpleGrid,
  Stack,
  Switch,
  Table,
  Text,
  TextInput,
  Textarea,
  Tooltip,
} from "@mantine/core";
import { DatePickerInput } from "@mantine/dates";
import { notifications } from "@mantine/notifications";
import {
  useCreatePeriodePlanification,
  useCreateTranchePlanifiee,
  useDeletePeriodePlanification,
  useDeleteTranchePlanifiee,
  usePeriodesPlanification,
  useSuiviDashboard,
  telechargerExportPeriode,
  useTranchesPeriode,
  useValeursPeriode,
  useTranchesPlanifiees,
  useUpdatePeriodePlanification,
  useUpdateTranchePlanifiee,
} from "../../api/suivi";
import { useAccesModules } from "../../utils/modules";
import { EmptyState } from "../../components/common/EmptyState";
import { StatCard } from "../../components/common/StatCard";
import { EnTetePeriode } from "../../components/suivi/EnTetePeriode";
import { confirmerSuppression } from "../../components/common/confirmerSuppression";
import { messageErreurApi } from "../../utils/erreurs";
import { fmt, fmtDate, nombre } from "../../utils/periode";
import { correspond } from "../../utils/recherche";
import type {
  Activite,
  PeriodePlanification,
  Projet,
  SousActivite,
  SuiviDashboardIndicateur,
  TranchePlanifiee,
  ValeurElementPeriode,
} from "../../types";
import { ActiviteForm } from "./ActiviteForm";
import { SousActiviteForm } from "./SousActiviteForm";
import { voc } from "../../utils/vocabulaire";
import { libelleMethodeEffective } from "../../utils/methodesCalcul";

// ---------------------------------------------------------------- utilitaires

/**
 * Libellé proposé d'après les dates choisies sur le calendrier (« T1 2026 »,
 * « Mars 2026 », « Année 2026 »...) — vide pour une période quelconque :
 * les dates sont affichées à part, jamais dans le nom.
 */
function libelleSuggere(debut: string, fin: string): string {
  const [a1, m1, j1] = debut.split("-").map(Number);
  const [a2, m2, j2] = fin.split("-").map(Number);
  const dernierJour = new Date(a2, m2, 0).getDate();
  if (j1 !== 1 || j2 !== dernierJour) return "";
  const nbMois = (a2 - a1) * 12 + (m2 - m1) + 1;
  const mois = new Date(a1, m1 - 1, 1).toLocaleString("fr-FR", { month: "long" });
  if (nbMois === 1) return `${mois.charAt(0).toUpperCase()}${mois.slice(1)} ${a1}`;
  if (nbMois === 3 && (m1 - 1) % 3 === 0) return `T${(m1 + 2) / 3} ${a1}`;
  if (nbMois === 6 && (m1 === 1 || m1 === 7)) return `S${m1 === 1 ? 1 : 2} ${a1}`;
  if (nbMois === 12 && m1 === 1) return `Année ${a1}`;
  return "";
}

type Element =
  | { type: "activite"; objet: Activite }
  | { type: "sous_activite"; objet: SousActivite; unite: string };

/**
 * Élément suivi en avancement (%) plutôt qu'en quantité : toute méthode autre que « Par
 * quantité », et les niveaux agrégés. Objectif de la période = avancement visé à sa fin.
 */
function suiviEnAvancement(element: Element): boolean {
  return element.type === "activite" && element.objet.methode_calcul_effective !== "QUANTITE";
}

function uniteElement(element: Element): string {
  if (suiviEnAvancement(element)) return "%";
  return element.type === "activite" ? element.objet.unite_quantite : element.unite;
}

function cleElement(e: Element) {
  return `${e.type}-${e.objet.id}`;
}

// ------------------------------------------------- modal : période (calendrier)

function PeriodeModal({
  opened,
  onClose,
  projet,
  periode,
  onCreee,
}: {
  opened: boolean;
  onClose: () => void;
  projet: Projet;
  periode: PeriodePlanification | null;
  onCreee: (p: PeriodePlanification) => void;
}) {
  const createPeriode = useCreatePeriodePlanification();
  const updatePeriode = useUpdatePeriodePlanification();
  const [dates, setDates] = useState<[string | null, string | null]>([null, null]);
  const [libelle, setLibelle] = useState("");
  const [libelleModifie, setLibelleModifie] = useState(false);

  useEffect(() => {
    if (!opened) return;
    setDates(periode ? [periode.date_debut, periode.date_fin] : [null, null]);
    setLibelle(periode?.libelle ?? "");
    setLibelleModifie(!!periode);
  }, [opened, periode]);

  function changerDates(valeur: [string | null, string | null]) {
    setDates(valeur);
    if (!libelleModifie && valeur[0] && valeur[1]) setLibelle(libelleSuggere(valeur[0], valeur[1]));
  }

  async function enregistrer() {
    const [debut, fin] = dates;
    if (!debut || !fin || !libelle.trim()) {
      notifications.show({ message: "Choisis la période sur le calendrier et donne-lui un nom.", color: "orange" });
      return;
    }
    try {
      if (periode) {
        await updatePeriode.mutateAsync({ id: periode.id, payload: { libelle: libelle.trim(), date_debut: debut, date_fin: fin } });
        notifications.show({ message: "Période modifiée", color: "green" });
      } else {
        const creee = await createPeriode.mutateAsync({ projet: projet.id, libelle: libelle.trim(), date_debut: debut, date_fin: fin });
        notifications.show({ message: "Période créée", color: "green" });
        onCreee(creee);
      }
      onClose();
    } catch (error) {
      notifications.show({ message: messageErreurApi(error, "Erreur lors de l'enregistrement de la période"), color: "red" });
    }
  }

  return (
    <Modal opened={opened} onClose={onClose} title={periode ? "Modifier la période" : voc("Nouvelle période de planification")}>
      <Stack gap="sm">
        <DatePickerInput
          type="range"
          label="Période"
          description="Clique sur la date de début puis sur la date de fin."
          placeholder="Choisir sur le calendrier…"
          value={dates}
          onChange={(v) => changerDates(v as [string | null, string | null])}
          defaultDate={projet.date_debut}
          valueFormat="DD/MM/YYYY"
          allowSingleDateInRange
          numberOfColumns={2}
          required
        />
        <TextInput
          label="Nom de la période"
          description="Proposé automatiquement d'après les dates — modifiable."
          placeholder="Ex : T1 2026, Année 2027…"
          value={libelle}
          onChange={(e) => {
            setLibelle(e.currentTarget.value);
            setLibelleModifie(true);
          }}
          required
        />
        {periode && (
          <Alert color="blue" variant="light" py={6}>
            Changer les dates met à jour toutes les valeurs de cette période ; une date prévue qui sortirait de la
            nouvelle période est effacée.
          </Alert>
        )}
        <Group justify="flex-end">
          <Button onClick={enregistrer} loading={createPeriode.isPending || updatePeriode.isPending}>
            {periode ? "Enregistrer" : "Créer la période"}
          </Button>
        </Group>
      </Stack>
    </Modal>
  );
}

// ------------------------------------- modal : valeurs d'un élément sur la période

function ValeursPeriodeModal({
  element,
  periode,
  tranche,
  valeur,
  onClose,
}: {
  element: Element | null;
  periode: PeriodePlanification;
  tranche: TranchePlanifiee | undefined;
  /** Valeurs affichées (calculées au prorata tant que rien n'est saisi) : pré-remplissent le formulaire. */
  valeur: ValeurElementPeriode | undefined;
  onClose: () => void;
}) {
  const createTranche = useCreateTranchePlanifiee();
  const updateTranche = useUpdateTranchePlanifiee();
  const estActivite = element?.type === "activite";
  // Toutes les tranches de cet élément (toutes périodes) : pour afficher ce
  // qui est déjà réparti ailleurs, à comparer au global.
  const { data: toutesTranches } = useTranchesPlanifiees(
    element ? (estActivite ? { activite: element.objet.id } : { sous_activite: element.objet.id }) : {},
  );

  const [cible, setCible] = useState<number | string>("");
  const [budget, setBudget] = useState<number | string>("");
  const [dates, setDates] = useState<[string | null, string | null]>([null, null]);
  const [commentaire, setCommentaire] = useState("");

  useEffect(() => {
    if (!element) return;
    if (tranche) {
      setCible(nombre(tranche.cible) ?? "");
      setBudget(nombre(tranche.budget) ?? "");
      setDates([tranche.date_debut_prevue, tranche.date_fin_prevue]);
      setCommentaire(tranche.commentaire);
    } else {
      setCible(nombre(valeur?.prevu_quantite) ?? "");
      setBudget(nombre(valeur?.prevu_budget) ?? "");
      setDates([valeur?.debut_prevu ?? null, valeur?.fin_prevue ?? null]);
      setCommentaire("");
    }
  }, [element, tranche, valeur]);

  if (!element) return <Modal opened={false} onClose={onClose}>{null}</Modal>;

  const objet = element.objet;
  const avancement = suiviEnAvancement(element);
  const unite = uniteElement(element);
  const quantiteGlobale = avancement ? 100 : nombre(objet.quantite_prevue);
  const budgetGlobal = element.type === "activite" ? nombre(element.objet.budget_alloue) : null;
  const autres = (toutesTranches ?? []).filter((t) => t.periode !== null && t.id !== tranche?.id);
  const quantiteAilleurs = autres.reduce((s, t) => s + (nombre(t.cible) ?? 0), 0);
  const budgetAilleurs = autres.reduce((s, t) => s + (nombre(t.budget) ?? 0), 0);

  async function enregistrer() {
    const payload = {
      cible: nombre(cible),
      budget: estActivite ? nombre(budget) : null,
      date_debut_prevue: dates[0],
      date_fin_prevue: dates[1],
      commentaire,
    };
    try {
      if (tranche) {
        await updateTranche.mutateAsync({ id: tranche.id, payload });
      } else {
        await createTranche.mutateAsync({
          periode: periode.id,
          ...(estActivite ? { activite: objet.id } : { sous_activite: objet.id }),
          ...payload,
        });
      }
      notifications.show({ message: `Valeurs ${periode.libelle} enregistrées`, color: "green" });
      onClose();
    } catch (error) {
      notifications.show({ message: messageErreurApi(error, "Erreur lors de l'enregistrement"), color: "red" });
    }
  }

  return (
    <Modal opened onClose={onClose} title={`${periode.libelle} — ${objet.libelle}`} size="lg">
      <Stack gap="sm">
        <Card withBorder padding="xs" bg="gray.0">
          <Text size="xs" fw={600} c="dimmed" tt="uppercase">{voc("Planification globale")}</Text>
          <Text size="sm">
            {fmt(quantiteGlobale)} {unite}
            {estActivite && ` · ${fmt(budgetGlobal)} FCFA`} · {fmtDate(objet.date_debut)} → {fmtDate(objet.date_fin)}
          </Text>
          {avancement && element.type === "activite" && (
            <Text size="xs" c="dimmed" mt={2}>
              Méthode : {libelleMethodeEffective(element.objet.methode_calcul_effective)} — l'objectif de la période est
              l'avancement visé à sa fin (en %), le réalisé est l'avancement atteint à cette date.
            </Text>
          )}
          {autres.length > 0 && !avancement && (
            <Text size="xs" c="dimmed" mt={2}>
              Déjà réparti sur les autres périodes : {fmt(quantiteAilleurs)} {unite}
              {estActivite && ` · ${fmt(budgetAilleurs)} FCFA`}
            </Text>
          )}
        </Card>

        <Group grow align="flex-start">
          <NumberInput
            label={avancement ? "Avancement visé à la fin de la période (%)" : `Quantité prévue sur la période${unite ? ` (${unite})` : ""}`}
            value={cible}
            onChange={setCible}
            min={0}
            max={avancement ? 100 : undefined}
            thousandSeparator=" "
            description={
              !avancement && quantiteGlobale !== null && nombre(cible) !== null && quantiteAilleurs + (nombre(cible) ?? 0) > quantiteGlobale
                ? `Attention : dépasse le global (${fmt(quantiteAilleurs + (nombre(cible) ?? 0))} > ${fmt(quantiteGlobale)})`
                : undefined
            }
          />
          {estActivite && (
            <NumberInput
              label="Budget prévu sur la période (FCFA)"
              value={budget}
              onChange={setBudget}
              min={0}
              thousandSeparator=" "
              description={
                budgetGlobal !== null && nombre(budget) !== null && budgetAilleurs + (nombre(budget) ?? 0) > budgetGlobal
                  ? `Attention : dépasse le global (${fmt(budgetAilleurs + (nombre(budget) ?? 0))} > ${fmt(budgetGlobal)})`
                  : undefined
              }
            />
          )}
        </Group>

        <DatePickerInput
          type="range"
          label="Dates prévues dans la période"
          placeholder="Facultatif"
          value={dates}
          onChange={(v) => setDates(v as [string | null, string | null])}
          minDate={periode.date_debut}
          maxDate={periode.date_fin}
          defaultDate={periode.date_debut}
          valueFormat="DD/MM/YYYY"
          allowSingleDateInRange
          clearable
        />
        <Textarea label="Commentaire" autosize minRows={2} value={commentaire} onChange={(e) => setCommentaire(e.currentTarget.value)} />

        <Group justify="flex-end">
          <Button onClick={enregistrer} loading={createTranche.isPending || updateTranche.isPending}>Enregistrer</Button>
        </Group>
      </Stack>
    </Modal>
  );
}

// ------------------------------------- modal : cible d'un indicateur sur la période

function IndicateurPeriodeModal({
  indicateur,
  periode,
  tranche,
  valeur,
  onClose,
}: {
  indicateur: SuiviDashboardIndicateur;
  periode: PeriodePlanification;
  tranche: TranchePlanifiee | undefined;
  valeur: ValeurElementPeriode | undefined;
  onClose: () => void;
}) {
  const createTranche = useCreateTranchePlanifiee();
  const updateTranche = useUpdateTranchePlanifiee();
  const { data: toutesTranches } = useTranchesPlanifiees({ indicateur: indicateur.id });
  const [cible, setCible] = useState<number | string>(nombre(tranche ? tranche.cible : valeur?.prevu_quantite) ?? "");
  const [commentaire, setCommentaire] = useState(tranche?.commentaire ?? "");
  const autres = (toutesTranches ?? []).filter((t) => t.periode !== null && t.id !== tranche?.id);

  async function enregistrer() {
    const payload = { cible: nombre(cible), commentaire };
    try {
      if (tranche) await updateTranche.mutateAsync({ id: tranche.id, payload });
      else await createTranche.mutateAsync({ periode: periode.id, indicateur: indicateur.id, ...payload });
      notifications.show({ message: `Cible ${periode.libelle} enregistrée`, color: "green" });
      onClose();
    } catch (error) {
      notifications.show({ message: messageErreurApi(error, "Erreur lors de l'enregistrement"), color: "red" });
    }
  }

  return (
    <Modal opened onClose={onClose} title={`${periode.libelle} — ${indicateur.libelle}`} size="lg">
      <Stack gap="sm">
        <Card withBorder padding="xs" bg="gray.0">
          <Text size="xs" fw={600} c="dimmed" tt="uppercase">Cible globale</Text>
          <Text size="sm">
            {fmt(indicateur.valeur_cible)} {indicateur.unite}
            {indicateur.valeur_reference !== null && ` (valeur de référence : ${fmt(indicateur.valeur_reference)})`}
          </Text>
          {autres.length > 0 && (
            <Text size="xs" c="dimmed" mt={2}>
              Autres périodes : {autres.map((t) => `${t.libelle} ${fmt(t.cible)}`).join(" · ")}
            </Text>
          )}
        </Card>
        <NumberInput
          label={`Cible sur la période${indicateur.unite ? ` (${indicateur.unite})` : ""}`}
          description="Le réalisé de la période est calculé à partir des valeurs saisies dont les dates tombent dans la période."
          value={cible}
          onChange={setCible}
          min={0}
          thousandSeparator=" "
        />
        <Textarea label="Commentaire" autosize minRows={2} value={commentaire} onChange={(e) => setCommentaire(e.currentTarget.value)} />
        <Group justify="flex-end">
          <Button onClick={enregistrer} loading={createTranche.isPending || updateTranche.isPending}>Enregistrer</Button>
        </Group>
      </Stack>
    </Modal>
  );
}

// ------------------------------------------------------------ ligne de l'arbre

/**
 * Objectifs de l'élément sur la période, saisis directement sur la ligne
 * (enregistrés en quittant le champ) — c'est l'utilisateur qui les fixe,
 * rien n'est calculé automatiquement. Le réalisé, lui, est toujours calculé
 * à partir des saisies de suivi faites dans la période.
 */
function ObjectifsPeriode({
  v,
  cible,
  unite,
  avancement = false,
  avecBudget,
  periode,
  modifiable,
}: {
  v: ValeurElementPeriode | undefined;
  cible: { activite?: number; sous_activite?: number; indicateur?: number };
  unite: string;
  /** Objectif = avancement visé en fin de période (%), réalisé = avancement atteint (voir suiviEnAvancement). */
  avancement?: boolean;
  avecBudget: boolean;
  periode: PeriodePlanification;
  /** Mode « Éditer » actif et droit d'écriture : champs de saisie, sinon simple affichage. */
  modifiable: boolean;
}) {
  const createTranche = useCreateTranchePlanifiee();
  const updateTranche = useUpdateTranchePlanifiee();
  const [quantite, setQuantite] = useState<number | string>("");
  const [budget, setBudget] = useState<number | string>("");

  useEffect(() => {
    setQuantite(nombre(v?.prevu_quantite) ?? "");
    setBudget(nombre(v?.prevu_budget) ?? "");
  }, [v?.prevu_quantite, v?.prevu_budget]);

  if (!v) return null;
  const valeursCourantes = v;

  async function enregistrer() {
    const nouvelleQuantite = nombre(quantite);
    const nouveauBudget = avecBudget ? nombre(budget) : null;
    if (nouvelleQuantite === nombre(valeursCourantes.prevu_quantite) && nouveauBudget === nombre(valeursCourantes.prevu_budget)) return;
    const payload = { cible: nouvelleQuantite, budget: nouveauBudget };
    try {
      if (valeursCourantes.tranche_id) await updateTranche.mutateAsync({ id: valeursCourantes.tranche_id, payload });
      else await createTranche.mutateAsync({ periode: periode.id, ...cible, ...payload });
    } catch (error) {
      notifications.show({ message: messageErreurApi(error, "Erreur lors de l'enregistrement de l'objectif"), color: "red" });
    }
  }

  const enregistrement = createTranche.isPending || updateTranche.isPending;
  const couleur = v.statut === "Atteinte" ? "green" : v.statut === "En retard" ? "red" : "blue";
  const surEntree = (e: React.KeyboardEvent<HTMLInputElement>) => e.key === "Enter" && e.currentTarget.blur();

  return (
    <Stack gap={4}>
      <Group gap="sm" align="flex-end" wrap="wrap">
        {modifiable ? (
          <>
            <NumberInput
              size="xs"
              label={avancement ? "Avancement visé fin de période (%)" : `Objectif${unite ? ` (${unite})` : ""}`}
              placeholder="À définir"
              value={quantite}
              onChange={setQuantite}
              onBlur={enregistrer}
              onKeyDown={surEntree}
              min={0}
              max={avancement ? 100 : undefined}
              thousandSeparator=" "
              disabled={enregistrement}
              w={170}
            />
            {avecBudget && (
              <NumberInput
                size="xs"
                label="Budget (FCFA)"
                placeholder="À définir"
                value={budget}
                onChange={setBudget}
                onBlur={enregistrer}
                onKeyDown={surEntree}
                min={0}
                thousandSeparator=" "
                disabled={enregistrement}
                w={170}
              />
            )}
          </>
        ) : (
          v.source === "saisi" && (
            <Text size="xs">
              <Text span fw={600}>{avancement ? "Avancement visé : " : "Objectif : "}</Text>
              {fmt(v.prevu_quantite)} {unite}
              {avecBudget && ` · ${fmt(v.prevu_budget)} FCFA`}
            </Text>
          )
        )}
        <Stack gap={2} style={{ minWidth: 200 }}>
          <Text size="xs">
            <Text span fw={600}>{avancement ? "Avancement atteint : " : "Réalisé : "}</Text>
            {fmt(v.realise_quantite)} {unite}
            {v.taux !== null && (avancement ? ` (${v.taux} % de l'objectif)` : ` (${v.taux} %)`)}
            {avecBudget && ` · ${fmt(v.budget_realise)} FCFA`}
            {avecBudget && v.taux_financier !== null && ` (${v.taux_financier} %)`}
          </Text>
          {v.prevu_quantite !== null && <Progress value={Math.min(v.taux ?? 0, 100)} color={couleur} size="xs" />}
        </Stack>
      </Group>
      <Group gap={6} wrap="wrap">
        {v.source === "a_definir" && (
          <Badge size="xs" variant="light" color="orange">Objectif à définir</Badge>
        )}
        {v.dans_dates_globales === false && (
          <Text size="xs" c="dimmed">{voc("Hors de ses dates dans la planification globale")}</Text>
        )}
      </Group>
      {v.commentaire && <Text size="xs" c="dimmed" fs="italic">{v.commentaire}</Text>}
    </Stack>
  );
}

function LigneElement({
  element,
  nomNiveau,
  valeur,
  periode,
  editionActive,
  peutModifier,
  onEditer,
  onEffacer,
  ajouts,
}: {
  element: Element;
  nomNiveau: string;
  valeur: ValeurElementPeriode | undefined;
  periode: PeriodePlanification;
  editionActive: boolean;
  peutModifier: boolean;
  onEditer: (e: Element) => void;
  onEffacer: (trancheId: number, libelle: string) => void;
  /** Éléments de planification uniquement : ajouter un niveau en dessous, ou une sous-activité. */
  ajouts?: { libelle: string; sousActivite: boolean; onClick: () => void }[];
}) {
  const objet = element.objet;
  const estActivite = element.type === "activite";
  const avancement = suiviEnAvancement(element);
  const unite = uniteElement(element);
  const trancheId = valeur?.source === "saisi" ? valeur.tranche_id : null;

  return (
    <Card
      withBorder
      radius="sm"
      padding="xs"
      bg={estActivite ? "gray.0" : "white"}
      style={{
        borderLeft: `3px solid var(--mantine-color-${estActivite ? "grape" : "gray"}-5)`,
      }}
    >
      <Group justify="space-between" align="flex-start" wrap="nowrap">
        <Stack gap={4} style={{ flex: 1 }}>
          <Group gap={6} wrap="wrap">
            <Badge color={estActivite ? "grape" : "gray"} variant="light" size="xs">{nomNiveau}</Badge>
            {element.type === "activite" && element.objet.code_activite && (
              <Text size="xs" c="dimmed">{element.objet.code_activite}</Text>
            )}
            <Text size="sm" fw={estActivite ? 500 : 400}>{objet.libelle}</Text>
          </Group>
          <Text size="xs" c="dimmed">
            {element.type === "activite" && avancement
              ? `Méthode : ${libelleMethodeEffective(element.objet.methode_calcul_effective)} · objectif en avancement (%)`
              : `Global : ${fmt(objet.quantite_prevue)} ${unite}`}
            {element.type === "activite" && ` · ${fmt(element.objet.budget_alloue)} FCFA`}
          </Text>
          <ObjectifsPeriode
            v={valeur}
            cible={estActivite ? { activite: objet.id } : { sous_activite: objet.id }}
            unite={unite}
            avancement={avancement}
            avecBudget={estActivite}
            periode={periode}
            modifiable={editionActive && peutModifier}
          />
        </Stack>
        {editionActive && peutModifier && (
          <Group gap={4} wrap="nowrap">
            <Tooltip label={`Dates prévues et commentaire — ${periode.libelle}`}>
              <ActionIcon size="sm" variant="subtle" onClick={() => onEditer(element)}>
                <Pencil size={12} />
              </ActionIcon>
            </Tooltip>
            {ajouts?.map((ajout) => (
              <Tooltip key={ajout.libelle} label={ajout.libelle}>
                <ActionIcon size="sm" variant="subtle" onClick={ajout.onClick}>
                  {ajout.sousActivite ? <ListPlus size={13} /> : <Plus size={13} />}
                </ActionIcon>
              </Tooltip>
            ))}
            {trancheId !== null && (
              <Tooltip label="Effacer les objectifs de la période">
                <ActionIcon size="sm" variant="subtle" color="red" onClick={() => onEffacer(trancheId, objet.libelle)}>
                  <Trash2 size={12} />
                </ActionIcon>
              </Tooltip>
            )}
          </Group>
        )}
      </Group>
    </Card>
  );
}

// ------------------------------------------------------------------- onglet

/**
 * Onglet « Planification par période » : la même arborescence que l'onglet
 * Planification, mais avec pour chaque activité/sous-activité ses propres
 * valeurs sur une période choisie au calendrier (quantité, budget, dates) —
 * sans toucher à la planification globale — et le réalisé de cette période,
 * calculé à partir des saisies de suivi déjà faites.
 */
export function PlanificationPeriodeTab({
  projet,
  niveauxNoms,
  editionActive,
}: {
  projet: Projet;
  niveauxNoms: Record<number, string>;
  editionActive: boolean;
}) {
  const { data: periodes, isLoading } = usePeriodesPlanification(projet.id);
  const [periodeId, setPeriodeId] = useState<number | null>(null);
  const periode = periodes?.find((p) => p.id === periodeId) ?? null;
  const { data: tranches } = useTranchesPeriode(periodeId);
  const { data: valeurs, refetch: recalculerValeurs } = useValeursPeriode(periodeId);
  const deletePeriode = useDeletePeriodePlanification();
  const deleteTranche = useDeleteTranchePlanifiee();

  const [modalPeriode, setModalPeriode] = useState<"creation" | "edition" | null>(null);
  const [elementEnEdition, setElementEnEdition] = useState<Element | null>(null);
  const [indicateurEnEdition, setIndicateurEnEdition] = useState<SuiviDashboardIndicateur | null>(null);
  const [ajout, setAjout] = useState<
    | { type: "racine" }
    | { type: "enfant"; parent: Activite; profondeur: number }
    | { type: "sous_activite"; activite: Activite }
    | null
  >(null);
  const [recherche, setRecherche] = useState("");
  const [seulementDansLesDates, setSeulementDansLesDates] = useState(false);
  const peutModifier = useAccesModules().peutEcrire("/projets");
  const { data: suivi } = useSuiviDashboard(projet.id);
  const indicateurs = suivi?.indicateurs ?? [];

  // Période affichée par défaut : celle qui contient aujourd'hui, sinon la première.
  useEffect(() => {
    if (!periodes || periodes.length === 0) {
      setPeriodeId(null);
      return;
    }
    if (periodeId && periodes.some((p) => p.id === periodeId)) return;
    const aujourdhui = new Date().toISOString().slice(0, 10);
    const enCours = periodes.find((p) => p.date_debut <= aujourdhui && aujourdhui <= p.date_fin);
    setPeriodeId((enCours ?? periodes[0]).id);
  }, [periodes, periodeId]);

  const tranchesParElement = useMemo(() => {
    const map = new Map<string, TranchePlanifiee>();
    (tranches ?? []).forEach((t) => {
      if (t.activite) map.set(`activite-${t.activite}`, t);
      if (t.sous_activite) map.set(`sous_activite-${t.sous_activite}`, t);
      if (t.indicateur) map.set(`indicateur-${t.indicateur}`, t);
    });
    return map;
  }, [tranches]);

  const valeursParElement = useMemo(() => {
    const map = new Map<string, ValeurElementPeriode>();
    [...(valeurs?.lignes ?? []), ...(valeurs?.indicateurs ?? [])].forEach((v) => {
      map.set(`${v.type}-${v.id}`, v);
    });
    return map;
  }, [valeurs]);


  // Une activité ajoutée/modifiée (ici ou dans l'onglet Planification) change
  // les valeurs calculées : on les recalcule dès que le projet est rechargé.
  useEffect(() => {
    if (periodeId) recalculerValeurs();
  }, [projet, periodeId, recalculerValeurs]);

  // Même calcul que l'onglet Planification (contrôle du budget restant à la création d'une activité).
  const tousLesElements = (elements: Activite[]): Activite[] =>
    elements.flatMap((e) => [e, ...tousLesElements(e.enfants)]);
  const budgetDejaAlloue = tousLesElements(projet.activites).reduce(
    (somme, act) => somme + (nombre(act.budget_alloue) ?? 0),
    0,
  );
  const totaux = valeurs?.totaux;

  function visible(libelle: string, cle: string) {
    if (seulementDansLesDates && valeursParElement.get(cle)?.dans_dates_globales === false) return false;
    return !recherche.trim() || correspond(libelle, recherche);
  }

  /** Une activité est affichée si elle-même ou un de ses descendants correspond aux filtres. */
  function activiteVisible(act: Activite): boolean {
    return (
      visible(`${act.code_activite ?? ""} ${act.libelle}`, `activite-${act.id}`) ||
      act.enfants.some(activiteVisible) ||
      act.sous_activites.some((sa) => visible(sa.libelle, `sous_activite-${sa.id}`))
    );
  }

  function effacer(trancheId: number, libelle: string) {
    confirmerSuppression({
      message: voc`Effacer les objectifs de « ${libelle} » sur ${periode?.libelle ?? "cette période"} (quantité, budget, dates, commentaire) ? La planification globale et les saisies de suivi ne changent pas.`,
      onConfirm: async () => {
        try {
          await deleteTranche.mutateAsync(trancheId);
          notifications.show({ message: "Objectifs de la période effacés", color: "green" });
        } catch (error) {
          notifications.show({ message: messageErreurApi(error, "Erreur lors de la suppression"), color: "red" });
        }
      },
    });
  }

  function supprimerPeriode() {
    if (!periode) return;
    confirmerSuppression({
      message: voc`Supprimer la période « ${periode.libelle} » et toutes ses valeurs ? La planification globale et les saisies de suivi ne changent pas.`,
      onConfirm: async () => {
        try {
          await deletePeriode.mutateAsync(periode.id);
          setPeriodeId(null);
          notifications.show({ message: "Période supprimée", color: "green" });
        } catch (error) {
          notifications.show({ message: messageErreurApi(error, "Erreur lors de la suppression"), color: "red" });
        }
      },
    });
  }

  function renduActivite(act: Activite, profondeur: number) {
    if (!activiteVisible(act)) return null;
    return (
      <Stack key={act.id} gap={6}>
        <LigneElement
          element={{ type: "activite", objet: act }}
          nomNiveau={niveauxNoms[profondeur] ?? "Activité"}
          valeur={valeursParElement.get(`activite-${act.id}`)}
          periode={periode!}
          editionActive={editionActive}
          peutModifier={peutModifier}
          onEditer={setElementEnEdition}
          onEffacer={effacer}
          ajouts={[
            {
              libelle: voc`Nouveau « ${niveauxNoms[profondeur + 1] ?? "niveau"} » en dessous (ajouté aussi à la planification globale)`,
              sousActivite: false,
              onClick: () => setAjout({ type: "enfant", parent: act, profondeur: profondeur + 1 }),
            },
            {
              libelle: voc("Nouvelle sous-activité (ajoutée aussi à la planification globale)"),
              sousActivite: true,
              onClick: () => setAjout({ type: "sous_activite", activite: act }),
            },
          ]}
        />
        {(act.enfants.length > 0 || act.sous_activites.length > 0) && (
          <Stack gap={6} pl="md">
            {act.enfants.map((enfant) => renduActivite(enfant, profondeur + 1))}
            {act.sous_activites
              .filter((sa) => visible(sa.libelle, `sous_activite-${sa.id}`))
              .map((sa) => (
                <LigneElement
                  key={`sa-${sa.id}`}
                  element={{ type: "sous_activite", objet: sa, unite: sa.unite_quantite }}
                  nomNiveau="Sous-activité"
                  valeur={valeursParElement.get(`sous_activite-${sa.id}`)}
                  periode={periode!}
                  editionActive={editionActive}
                  peutModifier={peutModifier}
                  onEditer={setElementEnEdition}
                  onEffacer={effacer}
                />
              ))}
          </Stack>
        )}
      </Stack>
    );
  }

  const trancheEnEdition = elementEnEdition ? tranchesParElement.get(cleElement(elementEnEdition)) : undefined;

  return (
    <Stack gap="md">
      <Card withBorder padding="md">
        <Group justify="space-between" align="flex-end" wrap="wrap">
          <Select
            label="Période"
            placeholder={periodes && periodes.length === 0 ? "Aucune période — crée-en une" : "Choisir une période…"}
            leftSection={<CalendarRange size={16} />}
            data={(periodes ?? []).map((p) => ({
              value: String(p.id),
              label: p.libelle || "Période sans nom",
            }))}
            value={periodeId ? String(periodeId) : null}
            onChange={(v) => setPeriodeId(v ? Number(v) : null)}
            w={380}
            allowDeselect={false}
          />
          <Group gap="xs">
            {periode && editionActive && (
              <>
                <Button variant="subtle" size="sm" leftSection={<Pencil size={14} />} onClick={() => setModalPeriode("edition")}>
                  Modifier la période
                </Button>
                <Button
                  variant="subtle"
                  color="red"
                  size="sm"
                  leftSection={<Trash2 size={14} />}
                  onClick={supprimerPeriode}
                  loading={deletePeriode.isPending}
                >
                  Supprimer
                </Button>
              </>
            )}
            {periode && (
              <Menu shadow="md" width={200}>
                <Menu.Target>
                  <Button variant="light" leftSection={<Download size={16} />}>Exporter</Button>
                </Menu.Target>
                <Menu.Dropdown>
                  <Menu.Label>{periode.libelle}</Menu.Label>
                  <Menu.Item onClick={() => telechargerExportPeriode(periode, projet.code, "excel")}>Excel</Menu.Item>
                  <Menu.Item onClick={() => telechargerExportPeriode(periode, projet.code, "pdf")}>PDF</Menu.Item>
                </Menu.Dropdown>
              </Menu>
            )}
            <Button leftSection={<CalendarPlus size={16} />} onClick={() => setModalPeriode("creation")}>
              Nouvelle période
            </Button>
          </Group>
        </Group>
      </Card>

      {isLoading ? (
        <Text c="dimmed">Chargement…</Text>
      ) : !periode ? (
        <EmptyState message={voc("Crée une période (mois, trimestre, année…) sur le calendrier pour planifier le projet sur cette période précise.")} />
      ) : projet.activites.length === 0 ? (
        <EmptyState message={voc("Ce projet n'a pas encore de planification : commence par l'onglet « Planification ».")} />
      ) : (
        <>
          <EnTetePeriode periode={periode} />

          <SimpleGrid cols={{ base: 1, sm: 3 }}>
            <StatCard
              label={`Budget prévu — ${periode.libelle}`}
              value={`${fmt(totaux?.budget_prevu)} FCFA`}
              icon={<Wallet size={20} />}
              color="teal"
            />
            <StatCard
              label={`Budget réalisé — ${periode.libelle}`}
              value={`${fmt(totaux?.budget_realise)} FCFA`}
              icon={<TrendingUp size={20} />}
              color="blue"
            />
            <StatCard
              label="Éléments avec objectifs définis"
              value={`${totaux?.nb_definis ?? 0} / ${totaux?.nb_elements ?? 0}`}
              icon={<ListChecks size={20} />}
              color="grape"
            />
          </SimpleGrid>

          {peutModifier && (
            <Alert color="blue" variant="light" py={6}>
              {editionActive
                ? "Saisis les objectifs de chaque élément sur cette période directement dans les champs (quantité, et budget pour une activité) — l'enregistrement est automatique. Le crayon permet d'ajouter des dates prévues et un commentaire."
                : "Clique sur « Éditer » en haut de la page pour définir les objectifs de chaque élément sur cette période."}
            </Alert>
          )}

          <Card withBorder padding="md">
            <Group justify="space-between" mb="sm" wrap="wrap">
              <TextInput
                leftSection={<Search size={14} />}
                placeholder="Rechercher une activité…"
                value={recherche}
                onChange={(e) => setRecherche(e.currentTarget.value)}
                w={320}
              />
              <Switch
                label={voc("Seulement les éléments prévus à ces dates dans la planification globale")}
                checked={seulementDansLesDates}
                onChange={(e) => setSeulementDansLesDates(e.currentTarget.checked)}
              />
            </Group>

            {editionActive && (
              <Group justify="flex-end" mb="xs">
                <Tooltip label={voc("Ajouté aussi à la planification globale")}>
                  <Button
                    size="compact-xs"
                    variant="light"
                    leftSection={<Plus size={12} />}
                    onClick={() => setAjout({ type: "racine" })}
                  >
                    {niveauxNoms[0] ?? "Activité"}
                  </Button>
                </Tooltip>
              </Group>
            )}
            <Stack gap={6}>{projet.activites.map((act) => renduActivite(act, 0))}</Stack>
          </Card>

          <Card withBorder padding="md">
            <Group gap={6} mb="sm">
              <Target size={16} />
              <Text fw={600}>{voc("Indicateurs — ")}{periode.libelle}</Text>
            </Group>
            {indicateurs.length === 0 ? (
              <Text size="sm" c="dimmed">{voc("Aucun indicateur rattaché à ce projet.")}</Text>
            ) : (
              <Table.ScrollContainer minWidth={700}>
                <Table verticalSpacing="xs" striped>
                  <Table.Thead>
                    <Table.Tr>
                      <Table.Th>{voc("Indicateur")}</Table.Th>
                      <Table.Th>Cible globale</Table.Th>
                      <Table.Th>Objectif et réalisé sur la période</Table.Th>
                      <Table.Th w={70} />
                    </Table.Tr>
                  </Table.Thead>
                  <Table.Tbody>
                    {indicateurs
                      .filter((i) => !seulementDansLesDates || valeursParElement.get(`indicateur-${i.id}`)?.dans_dates_globales !== false)
                      .filter((i) => !recherche.trim() || correspond(i.libelle, recherche))
                      .map((i) => {
                        const v = valeursParElement.get(`indicateur-${i.id}`);
                        const trancheId = v?.source === "saisi" ? v.tranche_id : null;
                        return (
                          <Table.Tr key={i.id}>
                            <Table.Td>
                              <Text size="sm">{i.libelle}</Text>
                              {v?.commentaire && <Text size="xs" c="dimmed" fs="italic">{v.commentaire}</Text>}
                            </Table.Td>
                            <Table.Td><Text size="sm">{fmt(i.valeur_cible)} {i.unite}</Text></Table.Td>
                            <Table.Td>
                              <ObjectifsPeriode
                                v={v}
                                cible={{ indicateur: i.id }}
                                unite={i.unite}
                                avecBudget={false}
                                periode={periode}
                                modifiable={editionActive && peutModifier}
                              />
                            </Table.Td>
                            <Table.Td>
                              {editionActive && peutModifier && (
                                <Group gap={4} wrap="nowrap">
                                  <Tooltip label={`Commentaire — ${periode.libelle}`}>
                                    <ActionIcon size="sm" variant="subtle" onClick={() => setIndicateurEnEdition(i)}>
                                      <Pencil size={12} />
                                    </ActionIcon>
                                  </Tooltip>
                                  {trancheId !== null && (
                                    <Tooltip label="Effacer l'objectif de la période">
                                      <ActionIcon size="sm" variant="subtle" color="red" onClick={() => effacer(trancheId, i.libelle)}>
                                        <Trash2 size={12} />
                                      </ActionIcon>
                                    </Tooltip>
                                  )}
                                </Group>
                              )}
                            </Table.Td>
                          </Table.Tr>
                        );
                      })}
                  </Table.Tbody>
                </Table>
              </Table.ScrollContainer>
            )}
          </Card>
        </>
      )}

      <PeriodeModal
        opened={modalPeriode !== null}
        onClose={() => setModalPeriode(null)}
        projet={projet}
        periode={modalPeriode === "edition" ? periode : null}
        onCreee={(p) => setPeriodeId(p.id)}
      />
      {periode && indicateurEnEdition && (
        <IndicateurPeriodeModal
          key={indicateurEnEdition.id}
          indicateur={indicateurEnEdition}
          periode={periode}
          tranche={tranchesParElement.get(`indicateur-${indicateurEnEdition.id}`)}
          valeur={valeursParElement.get(`indicateur-${indicateurEnEdition.id}`)}
          onClose={() => setIndicateurEnEdition(null)}
        />
      )}

      <Modal
        opened={ajout !== null}
        onClose={() => setAjout(null)}
        title={
          ajout?.type === "sous_activite"
            ? `Nouvelle sous-activité sous « ${ajout.activite.libelle} »`
            : ajout?.type === "enfant"
              ? `Nouveau « ${niveauxNoms[ajout.profondeur] ?? "niveau"} » sous « ${ajout.parent.libelle} »`
              : `Nouvelle ${(niveauxNoms[0] ?? "activité").toLowerCase()}`
        }
        size="lg"
      >
        {ajout?.type === "sous_activite" ? (
          <SousActiviteForm
            activiteId={ajout.activite.id}
            cadreStrategiqueId={projet.cadre_strategique}
            onDone={() => setAjout(null)}
          />
        ) : ajout ? (
          <ActiviteForm
            activiteParentId={ajout.type === "enfant" ? ajout.parent.id : undefined}
            profondeur={ajout.type === "enfant" ? ajout.profondeur : 0}
            nomNiveau={niveauxNoms[ajout.type === "enfant" ? ajout.profondeur : 0] ?? null}
            cadreStrategiqueId={projet.cadre_strategique}
            projetId={projet.id}
            budgetProjetTotal={Number(projet.budget_total)}
            budgetDejaAlloue={budgetDejaAlloue}
            onDone={() => setAjout(null)}
          />
        ) : null}
      </Modal>

      {periode && elementEnEdition && (
        <ValeursPeriodeModal
          element={elementEnEdition}
          periode={periode}
          tranche={trancheEnEdition}
          valeur={valeursParElement.get(cleElement(elementEnEdition))}
          onClose={() => setElementEnEdition(null)}
        />
      )}
    </Stack>
  );
}
