import { type ReactNode, useEffect, useMemo, useState } from "react";
import { CalendarRange, Download, FileText, Plus, Search, Target } from "lucide-react";
import { Alert, Badge, Button, Card, Group, Menu, Modal, Select, SimpleGrid, Stack, Text, TextInput, Title } from "@mantine/core";
import { notifications } from "@mantine/notifications";
import { Link } from "react-router-dom";
import { useDeleteValeurIndicateur } from "../../api/indicators";
import { useAuth } from "../../auth/useAuth";
import {
  telechargerExportSuiviPeriode,
  useDeletePointSuivi,
  usePeriodesPlanification,
  useValeursPeriode,
} from "../../api/suivi";
import { EmptyState } from "../../components/common/EmptyState";
import { confirmerSuppression } from "../../components/common/confirmerSuppression";
import { EvolutionChart } from "../../components/charts/EvolutionChart";
import { SaisieValeurIndicateurForm } from "../../components/indicators/SaisieValeurIndicateurForm";
import { BarreProgression, toneDeTaux } from "../../components/suivi/BarreProgression";
import { EnTetePeriode } from "../../components/suivi/EnTetePeriode";
import { HistoriqueSuiviTable } from "../../components/suivi/HistoriqueSuiviTable";
import { SaisiePointSuiviForm } from "../../components/suivi/SaisiePointSuiviForm";
import { SaisieSuiviMethode } from "../../components/suivi/SaisieSuiviMethode";
import { libelleMethodeEffective } from "../../utils/methodesCalcul";
import { ACTIVITE_STATUT_LABEL } from "../../utils/statusTones";
import { messageErreurApi } from "../../utils/erreurs";
import { fmt, fmtDate, nombre } from "../../utils/periode";
import { correspond } from "../../utils/recherche";
import { ecartTexte, tauxDe, valeurAttendueA, type FenetreAttendue } from "../../utils/suivi";
import type {
  PeriodePlanification,
  SuiviDashboard,
  SuiviHistoriquePoint,
  SuiviHistoriqueValeurIndicateur,
  ValeurElementPeriode,
} from "../../types";
import { voc } from "../../utils/vocabulaire";

type Statuts = { value: string; label: string }[];

type Saisie =
  | { type: "activite"; id: number; point?: SuiviHistoriquePoint }
  | { type: "sous_activite"; id: number; point?: SuiviHistoriquePoint }
  | { type: "indicateur"; id: number; valeur?: SuiviHistoriqueValeurIndicateur };

const COULEUR_STATUT: Record<string, string> = { Atteinte: "green", "En retard": "red", "En cours": "blue" };

function aujourdHui() {
  return new Date().toISOString().slice(0, 10);
}

/** Carte d'exécution de la période — même présentation que les cartes « globales » du suivi. */
function CarteExecution({ titre, valeur, detail }: { titre: string; valeur: string; detail?: string }) {
  return (
    <Card withBorder padding="md" radius="md">
      <Text size="sm" c="dimmed" fw={600} tt="uppercase" style={{ letterSpacing: 0.4 }}>
        {titre}
      </Text>
      <Text fz={28} fw={700}>{valeur}</Text>
      {detail && <Text size="sm" c="dimmed">{detail}</Text>}
    </Card>
  );
}

/**
 * Carte de suivi d'un élément sur la période, avec les mêmes visuels que le
 * suivi global (barres empilées par saisie, repère « attendu aujourd'hui »,
 * courbe du cumul, historique des saisies) — mais rapportée à l'objectif
 * fixé pour la période et limitée aux saisies faites dans ses dates.
 */
function CarteSuiviPeriode({
  v,
  periode,
  entete,
  globale,
  unite,
  avecBudget,
  editionActive,
  libelleBouton,
  onSaisir,
  onModifier,
  onSupprimer,
  retrait = 0,
  secondaire = false,
  avancement = false,
}: {
  v: ValeurElementPeriode;
  periode: PeriodePlanification;
  entete: ReactNode;
  globale: string;
  unite: string;
  avecBudget: boolean;
  editionActive: boolean;
  libelleBouton: string;
  /** Absent : projet en lecture seule (clôturé), pas de bouton de saisie. */
  onSaisir?: () => void;
  onModifier: (id: number) => void;
  onSupprimer: (id: number) => void;
  retrait?: number;
  secondaire?: boolean;
  /**
   * Élément dont le taux ne vient pas des quantités : objectif = avancement visé à la fin de la
   * période (%), réalisé = avancement atteint ; pas de cumul ni de courbe de quantités.
   */
  avancement?: boolean;
}) {
  const cible = nombre(v.prevu_quantite);
  const budgetPrevu = avecBudget ? nombre(v.prevu_budget) : null;
  const debut = v.debut_prevu ?? periode.date_debut;
  const fin = v.fin_prevue ?? periode.date_fin;
  const fenetre: FenetreAttendue | null = cible !== null ? { debut, fin, depart: 0, arrivee: cible } : null;
  const fenetreBudget: FenetreAttendue | null =
    budgetPrevu !== null ? { debut, fin, depart: 0, arrivee: budgetPrevu } : null;
  const defini = v.source === "saisi";

  let cumul = 0;
  let cumulBudget = 0;
  const historique = v.saisies.map((s) => {
    cumul += nombre(s.quantite) ?? 0;
    cumulBudget += nombre(s.budget) ?? 0;
    return { ...s, cumul, cumulBudget };
  });

  return (
    <Card
      withBorder
      padding={secondaire ? "sm" : "md"}
      radius="md"
      ml={retrait}
      bg={secondaire ? "gray.0" : undefined}
    >
      <Group justify="space-between" align="flex-start" wrap="nowrap" mb="xs">
        <div>
          <Group gap={8} wrap="wrap">
            {entete}
            {defini ? (
              <Badge size="md" variant="light" color={COULEUR_STATUT[v.statut] ?? "gray"}>{v.statut}</Badge>
            ) : (
              <Badge size="md" variant="light" color="orange">Objectif non défini</Badge>
            )}
          </Group>
          <Text size="sm" c="dimmed" mt={2}>{globale}</Text>
          {defini && (
            <Text size="sm" c="dimmed">
              Prévu sur la période : {fmtDate(debut)} → {fmtDate(fin)}
            </Text>
          )}
        </div>
        {onSaisir && (
          <Button size="sm" variant="light" leftSection={<Plus size={15} />} onClick={onSaisir}>
            {libelleBouton}
          </Button>
        )}
      </Group>

      {avancement ? (
        cible !== null ? (
          <BarreProgression
            label={`Avancement atteint à la fin de la période (visé : ${fmt(cible)} %)`}
            segments={[{ key: 0, valeur: nombre(v.realise_quantite) ?? 0, titre: `Atteint : ${fmt(v.realise_quantite)} %` }]}
            cible={cible}
            attendu={null}
            unite="%"
            tone={toneDeTaux(v.taux)}
          />
        ) : (
          <Text size="md">
            Avancement atteint à la fin de la période : <Text span fw={700}>{fmt(v.realise_quantite)} %</Text>
            {avecBudget && ` · ${fmt(v.budget_realise)} FCFA`}
          </Text>
        )
      ) : cible !== null ? (
        <BarreProgression
          label="Avancement physique sur la période"
          segments={historique.map((h) => ({
            key: h.id,
            valeur: nombre(h.quantite) ?? 0,
            titre: `${fmtDate(h.periode_debut)} → ${fmtDate(h.periode_fin)} : ${fmt(h.quantite)} ${unite}`,
          }))}
          cible={cible}
          attendu={fenetre ? valeurAttendueA(aujourdHui(), fenetre) : null}
          unite={unite}
          tone={toneDeTaux(v.taux)}
        />
      ) : (
        <Text size="md">
          Réalisé sur la période : <Text span fw={700}>{fmt(v.realise_quantite)} {unite}</Text>
          {avecBudget && ` · ${fmt(v.budget_realise)} FCFA`}
        </Text>
      )}
      {budgetPrevu !== null && (
        <BarreProgression
          label="Avancement financier sur la période"
          segments={historique.map((h) => ({
            key: h.id,
            valeur: nombre(h.budget) ?? 0,
            titre: `${fmtDate(h.periode_debut)} → ${fmtDate(h.periode_fin)} : ${fmt(h.budget)} FCFA`,
          }))}
          cible={budgetPrevu}
          attendu={fenetreBudget ? valeurAttendueA(aujourdHui(), fenetreBudget) : null}
          unite="FCFA"
          tone={toneDeTaux(v.taux_financier)}
        />
      )}
      {!avancement && (
        <EvolutionChart
          data={historique.map((h) => ({ date: h.periode_fin, valeur: h.cumul }))}
          cible={cible}
          unite={unite}
          height={secondaire ? 120 : 160}
        />
      )}
      <HistoriqueSuiviTable
        editable={editionActive}
        lignes={historique
          .map((h) => {
            const attendu = fenetre && !avancement ? valeurAttendueA(h.periode_fin, fenetre) : null;
            const tauxCumul = tauxDe(h.cumul, cible);
            const ecart = ecartTexte(h.cumul, attendu, unite);
            return {
              id: h.id,
              periode: `${fmtDate(h.periode_debut)} → ${fmtDate(h.periode_fin)}`,
              valeur: avancement ? undefined : `${fmt(h.quantite)} ${unite}`,
              cumule: avancement ? undefined : `${fmt(h.cumul)} ${unite}${tauxCumul !== null ? ` (${tauxCumul}%)` : ""}`,
              detail:
                avecBudget && h.budget
                  ? `${fmt(h.budget)} FCFA — cumul ${fmt(h.cumulBudget)}` +
                    (budgetPrevu ? ` (${tauxDe(h.cumulBudget, budgetPrevu)}%)` : "")
                  : undefined,
              attendu:
                attendu !== null
                  ? `${Math.round(attendu)} ${unite} (${tauxDe(attendu, cible)}%)${ecart ? " · " + ecart : ""}`
                  : undefined,
              statut: avancement
                ? [ACTIVITE_STATUT_LABEL[h.statut as keyof typeof ACTIVITE_STATUT_LABEL] ?? h.statut, h.commentaire]
                    .filter(Boolean)
                    .join(" — ") || undefined
                : h.commentaire || undefined,
            };
          })
          .reverse()}
        libelleStatut={avancement ? "Statut / commentaire" : "Commentaire"}
        messageVide="Aucune saisie sur cette période."
        onEdit={onModifier}
        onDelete={onSupprimer}
      />
    </Card>
  );
}

/**
 * Onglet « Suivi par période » du suivi d'un projet : pour une période de
 * planification, l'objectif fixé et le réalisé de chaque élément sur cette
 * période, et la saisie du réalisé dans ses dates. Une saisie faite ici est
 * un point de suivi comme un autre : le suivi global (quantités, budget,
 * statut, dates réelles) s'actualise automatiquement.
 */
export function SuiviPeriodeTab({
  projetId,
  data,
  editionActive,
  statutsActivite,
  statutsSousActivite,
}: {
  projetId: number;
  data: SuiviDashboard;
  editionActive: boolean;
  statutsActivite: Statuts;
  statutsSousActivite: Statuts;
}) {
  const { data: periodes, isLoading } = usePeriodesPlanification(projetId);
  const [periodeId, setPeriodeId] = useState<number | null>(null);
  const periode = periodes?.find((p) => p.id === periodeId) ?? null;
  const { data: valeurs } = useValeursPeriode(periodeId);
  const deletePoint = useDeletePointSuivi();
  const deleteValeur = useDeleteValeurIndicateur();
  const [saisie, setSaisie] = useState<Saisie | null>(null);
  const [recherche, setRecherche] = useState("");
  const { user } = useAuth();
  const cloture = data.projet.statut === "CLOTURE";
  const peutSaisir = !!user && (user.role === "ADMIN" || user.niveau_acces === "LECTURE_ECRITURE") && !cloture;

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

  // Historique des saisies par élément, tiré du suivi global (source unique).
  const historiques = useMemo(() => {
    const map = new Map<string, SuiviHistoriquePoint[]>();
    data.activites.forEach((a) => {
      map.set(`activite-${a.id}`, a.historique);
      a.sous_activites.forEach((sa) => map.set(`sous_activite-${sa.id}`, sa.historique));
    });
    return map;
  }, [data]);

  function supprimerPoint(id: number) {
    confirmerSuppression({
      message: voc("Supprimer cette saisie ? Le suivi global du projet sera recalculé en conséquence."),
      onConfirm: async () => {
        try {
          await deletePoint.mutateAsync(id);
          notifications.show({ message: "Saisie supprimée", color: "green" });
        } catch (error) {
          notifications.show({ message: messageErreurApi(error, "Erreur lors de la suppression"), color: "red" });
        }
      },
    });
  }

  function supprimerValeur(id: number) {
    confirmerSuppression({
      message: voc("Supprimer cette valeur d'indicateur ? Le suivi global de l'indicateur sera recalculé en conséquence."),
      onConfirm: async () => {
        try {
          await deleteValeur.mutateAsync(id);
          notifications.show({ message: "Valeur supprimée", color: "green" });
        } catch (error) {
          notifications.show({ message: messageErreurApi(error, "Erreur lors de la suppression"), color: "red" });
        }
      },
    });
  }

  if (isLoading) return <Text c="dimmed">Chargement…</Text>;

  if (!periodes || periodes.length === 0) {
    return (
      <EmptyState
        icon={<CalendarRange size={32} strokeWidth={1.5} />}
        message={voc("Aucune période de planification pour ce projet. Crée-en une dans la fiche projet, onglet « Planification par période ».")}
      />
    );
  }

  const lignes = valeurs?.lignes ?? [];
  const lignesFiltrees = recherche.trim()
    ? lignes.filter((l) => correspond(`${l.code} ${l.libelle}`, recherche))
    : lignes;
  const indicateurs = (valeurs?.indicateurs ?? []).filter((i) => !recherche.trim() || correspond(i.libelle, recherche));

  const bornes = periode ? { debut: periode.date_debut, fin: periode.date_fin } : undefined;

  return (
    <Stack gap="lg">
      <Group justify="space-between" align="flex-end" wrap="wrap">
        <Select
          label={voc("Période de planification")}
          size="md"
          leftSection={<CalendarRange size={18} />}
          data={periodes.map((p) => ({ value: String(p.id), label: p.libelle || "Période sans nom" }))}
          value={periodeId ? String(periodeId) : null}
          onChange={(v) => setPeriodeId(v ? Number(v) : null)}
          allowDeselect={false}
          w={340}
        />
        <Group gap="xs">
          {periode && (
            <Menu position="bottom-end">
              <Menu.Target>
                <Button variant="light" leftSection={<Download size={16} />}>
                  {voc("Exporter le suivi de la période")}</Button>
              </Menu.Target>
              <Menu.Dropdown>
                <Menu.Item
                  leftSection={<Download size={14} />}
                  onClick={() => telechargerExportSuiviPeriode(periode, data.projet.code, "excel")}
                >
                  Excel (.xlsx)
                </Menu.Item>
                <Menu.Item
                  leftSection={<FileText size={14} />}
                  onClick={() => telechargerExportSuiviPeriode(periode, data.projet.code, "pdf")}
                >
                  PDF
                </Menu.Item>
              </Menu.Dropdown>
            </Menu>
          )}
          <Button component={Link} to={`/projets/${projetId}`} variant="subtle">
            Gérer les périodes et leurs objectifs
          </Button>
        </Group>
      </Group>

      {periode && valeurs && (
        <>
          <EnTetePeriode periode={periode} />

          <SimpleGrid cols={{ base: 1, sm: 3 }}>
            <CarteExecution
              titre="Exécution physique de la période"
              valeur={valeurs.totaux.taux_physique !== null ? `${valeurs.totaux.taux_physique}%` : "—"}
              detail="Moyenne des activités dont l'objectif est défini"
            />
            <CarteExecution
              titre="Exécution financière de la période"
              valeur={valeurs.totaux.taux_financier !== null ? `${valeurs.totaux.taux_financier}%` : "—"}
              detail={`${fmt(valeurs.totaux.budget_realise)} FCFA dépensés sur ${fmt(valeurs.totaux.budget_prevu)} FCFA prévus`}
            />
            <CarteExecution
              titre="Objectifs définis"
              valeur={`${valeurs.totaux.nb_definis} / ${valeurs.totaux.nb_elements}`}
              detail="Éléments ayant un objectif fixé pour la période"
            />
          </SimpleGrid>

          <Alert color="blue" variant="light">
            <Text size="sm">
              {voc("Les saisies faites ici (dates comprises dans la période) sont aussi comptées dans le suivi global du projet : quantités, budget, statut et dates réelles s'actualisent automatiquement.")}</Text>
          </Alert>

          <TextInput
            placeholder={voc("Rechercher une activité ou un indicateur…")}
            size="md"
            leftSection={<Search size={16} />}
            value={recherche}
            onChange={(e) => setRecherche(e.currentTarget.value)}
            maw={420}
          />

          <Title order={3}>Activités</Title>
          <Text size="sm" c="dimmed">
            Chaque segment coloré de la barre = une saisie faite pendant la période · trait gris = où on devrait être
            aujourd'hui · trait teal = objectif de la période. La courbe trace le cumul sur la période.
          </Text>
          <Stack gap="md">
            {lignesFiltrees.map((l) => {
              const ligne = l;
              const estActivite = ligne.type === "activite";
              const type = ligne.type as "activite" | "sous_activite";
              return (
                <CarteSuiviPeriode
                  key={`${ligne.type}-${ligne.id}`}
                  v={ligne}
                  periode={periode}
                  retrait={ligne.profondeur * 24}
                  secondaire={!estActivite}
                  entete={
                    <>
                      <Badge color={estActivite ? "grape" : "gray"} variant="light" size="md">{ligne.niveau}</Badge>
                      {ligne.code && <Text size="sm" c="dimmed">{ligne.code}</Text>}
                      <Text size={estActivite ? "lg" : "md"} fw={estActivite ? 700 : 600}>{ligne.libelle}</Text>
                    </>
                  }
                  globale={
                    (ligne.mode === "avancement"
                      ? `Méthode : ${libelleMethodeEffective(ligne.methode)} · objectif en avancement (%)`
                      : `Global : ${fmt(ligne.global_quantite)} ${ligne.unite}`) +
                    (estActivite ? ` · ${fmt(ligne.global_budget)} FCFA` : "")
                  }
                  unite={ligne.unite}
                  avancement={ligne.mode === "avancement"}
                  avecBudget={estActivite}
                  editionActive={editionActive}
                  libelleBouton={voc("Saisir un suivi")}
                  onSaisir={cloture ? undefined : () => setSaisie({ type, id: ligne.id })}
                  onModifier={(id) =>
                    setSaisie({ type, id: ligne.id, point: historiques.get(`${type}-${ligne.id}`)?.find((p) => p.id === id) })
                  }
                  onSupprimer={supprimerPoint}
                />
              );
            })}
          </Stack>

          <Group gap={8} mt="md">
            <Target size={20} />
            <Title order={3}>{voc("Indicateurs")}</Title>
          </Group>
          {indicateurs.length === 0 ? (
            <Text c="dimmed">{voc("Aucun indicateur rattaché à ce projet.")}</Text>
          ) : (
            <Stack gap="md">
              {indicateurs.map((i) => (
                <CarteSuiviPeriode
                  key={i.id}
                  v={i}
                  periode={periode}
                  entete={<Text size="lg" fw={700}>{i.libelle}</Text>}
                  globale={`Cible globale : ${fmt(i.valeur_cible)} ${i.unite}`}
                  unite={i.unite}
                  avecBudget={false}
                  editionActive={editionActive}
                  libelleBouton="Saisir une valeur"
                  onSaisir={cloture ? undefined : () => setSaisie({ type: "indicateur", id: i.id })}
                  onModifier={(id) =>
                    setSaisie({
                      type: "indicateur",
                      id: i.id,
                      valeur: data.indicateurs.find((x) => x.id === i.id)?.historique.find((h) => h.id === id),
                    })
                  }
                  onSupprimer={supprimerValeur}
                />
              ))}
            </Stack>
          )}
        </>
      )}

      <Modal
        opened={saisie !== null}
        onClose={() => setSaisie(null)}
        title={`${periode?.libelle ?? "Période"} — ${saisie?.type === "indicateur" ? voc("valeur d'indicateur") : voc("saisir un suivi")}`}
        size="lg"
      >
        {saisie?.type === "indicateur" ? (
          <SaisieValeurIndicateurForm
            indicateurId={saisie.id}
            valeurExistante={saisie.valeur}
            historiqueExistant={data.indicateurs.find((x) => x.id === saisie.id)?.historique}
            bornes={bornes}
            onDone={() => setSaisie(null)}
          />
        ) : saisie?.type === "activite" && !saisie.point && lignes.find((l) => l.type === "activite" && l.id === saisie.id)?.mode === "avancement" ? (
          <SaisieSuiviMethode activiteId={saisie.id} modifiable={peutSaisir} bornes={bornes} onDone={() => setSaisie(null)} />
        ) : saisie ? (
          <SaisiePointSuiviForm
            activiteId={saisie.type === "activite" ? saisie.id : undefined}
            sousActiviteId={saisie.type === "sous_activite" ? saisie.id : undefined}
            statutsDisponibles={saisie.type === "activite" ? statutsActivite : statutsSousActivite}
            avecBudget={saisie.type === "activite"}
            historiqueExistant={historiques.get(`${saisie.type}-${saisie.id}`)}
            pointExistant={saisie.point}
            avecQuantite={
              saisie.type !== "activite" ||
              lignes.find((l) => l.type === "activite" && l.id === saisie.id)?.mode !== "avancement"
            }
            bornes={bornes}
            onDone={() => setSaisie(null)}
          />
        ) : null}
      </Modal>
    </Stack>
  );
}
