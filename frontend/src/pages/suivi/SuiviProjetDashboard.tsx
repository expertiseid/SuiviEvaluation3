import { useEffect, useMemo, useState } from "react";
import { useLocation, useParams } from "react-router-dom";
import { AlertTriangle, Download, FileSpreadsheet, FileText, RefreshCw, Search } from "lucide-react";
import { ActionIcon, Alert, Badge, Button, Card, Group, Menu, Modal, SimpleGrid, Stack, Tabs, Text, TextInput, Title, Tooltip } from "@mantine/core";
import { notifications } from "@mantine/notifications";
import { useSuiviDashboard, telechargerExportSuiviExcel, telechargerExportSuiviPdf } from "../../api/suivi";
import { useDeleteValeurIndicateur, useParametresAlerte } from "../../api/indicators";
import { useDeletePointSuivi } from "../../api/suivi";
import { AlerteBadge } from "../../components/indicators/AlerteBadge";
import { StatusBadge } from "../../components/common/StatusBadge";
import { BarreProgression, toneDeTaux } from "../../components/suivi/BarreProgression";
import { EvolutionChart } from "../../components/charts/EvolutionChart";
import { SaisieValeurIndicateurForm } from "../../components/indicators/SaisieValeurIndicateurForm";
import { SaisiePointSuiviForm } from "../../components/suivi/SaisiePointSuiviForm";
import { SuiviPeriodeTab } from "./SuiviPeriodeTab";
import { HistoriqueSuiviTable } from "../../components/suivi/HistoriqueSuiviTable";
import { confirmerSuppression } from "../../components/common/confirmerSuppression";
import { BoutonModeEdition } from "../../components/common/BoutonModeEdition";
import { correspond } from "../../utils/recherche";
import {
  ACTIVITE_STATUT_LABEL,
  ACTIVITE_STATUT_TONE,
  SOUS_ACTIVITE_STATUT_LABEL,
  SUIVI_STATUT_GLOBAL_LABEL,
  SUIVI_STATUT_GLOBAL_TONE,
} from "../../utils/statusTones";
import type { SuiviDashboardIndicateur, SuiviHistoriquePoint } from "../../types";
import { ecartTexte, tauxDe, valeurAttendueA, type FenetreAttendue } from "../../utils/suivi";
import { voc } from "../../utils/vocabulaire";
import { ImportCanevasSuiviModal } from "../../components/suivi/ImportCanevasSuiviModal";
import { useAuth } from "../../auth/useAuth";
import { MethodeCalculLigne } from "../../components/suivi/MethodeCalculLigne";
import { SaisieSuiviMethode } from "../../components/suivi/SaisieSuiviMethode";
import { libelleMethodeEffective } from "../../utils/methodesCalcul";

function libelleStatut(statut: string, labels: Record<string, string>): string | undefined {
  if (!statut) return undefined;
  return labels[statut] ?? statut;
}

function LegendeGraphique() {
  return (
    <Text size="sm" c="dimmed">
      Chaque segment coloré de la barre = ce qui a été réalisé pendant une période · trait gris = où on devrait
      être aujourd'hui · trait teal en bout de barre = cible. La courbe en dessous trace le cumul dans le temps.
    </Text>
  );
}

function aujourdHui() {
  return new Date().toISOString().slice(0, 10);
}

type StatutEcheance = "RETARD" | "PROCHE" | null;

function statutEcheance(dateFin: string | null | undefined, termine: boolean, seuilJours: number): StatutEcheance {
  if (!dateFin || termine) return null;
  const joursRestants = Math.floor(
    (new Date(dateFin).getTime() - new Date(aujourdHui()).getTime()) / 86400000,
  );
  if (joursRestants < 0) return "RETARD";
  if (joursRestants <= seuilJours) return "PROCHE";
  return null;
}

function EcheanceBadge({ statut, dateFin }: { statut: StatutEcheance; dateFin?: string | null }) {
  if (!statut) return null;
  return (
    <Tooltip
      label={
        statut === "RETARD"
          ? `Échéance dépassée le ${dateFin}`
          : `Échéance prévue le ${dateFin} — approche`
      }
    >
      <Badge
        color={statut === "RETARD" ? "red" : "orange"}
        variant="filled"
        size="sm"
        leftSection={<AlertTriangle size={12} />}
        styles={{ root: { textTransform: "none" } }}
      >
        {statut === "RETARD" ? "En retard" : "Échéance proche"}
      </Badge>
    </Tooltip>
  );
}

const STATUTS_ACTIVITE = [
  { value: "NON_REALISEE", label: "Non réalisée" },
  { value: "EN_COURS", label: "En cours" },
  { value: "REALISEE", label: "Réalisée" },
];

const STATUTS_SOUS_ACTIVITE = [
  { value: "PLANIFIEE", label: "Planifiée" },
  { value: "EN_COURS", label: "En cours" },
  { value: "TERMINEE", label: "Terminée" },
];

export function SuiviProjetDashboard() {
  const { id } = useParams();
  const location = useLocation();
  const projetId = Number(id);
  const { data, isLoading, isFetching, refetch } = useSuiviDashboard(projetId);
  const deleteValeur = useDeleteValeurIndicateur();
  const deletePoint = useDeletePointSuivi();

  const [modalIndicateur, setModalIndicateur] = useState<number | null>(null);
  const [modalActivite, setModalActivite] = useState<number | null>(null);
  const [modalSousActivite, setModalSousActivite] = useState<number | null>(null);

  const [editionValeur, setEditionValeur] = useState<{
    indicateurId: number;
    valeur: SuiviDashboardIndicateur["historique"][number];
  } | null>(null);
  const [editionPointActivite, setEditionPointActivite] = useState<{
    activiteId: number;
    point: SuiviHistoriquePoint;
  } | null>(null);
  const [editionPointSousActivite, setEditionPointSousActivite] = useState<{
    sousActiviteId: number;
    point: SuiviHistoriquePoint;
  } | null>(null);
  const [recherche, setRecherche] = useState("");
  const [canevasOuvert, setCanevasOuvert] = useState(false);
  const { user } = useAuth();
  const peutSaisir = !!user && (user.role === "ADMIN" || user.niveau_acces === "LECTURE_ECRITURE");
  const [editionActive, setEditionActive] = useState(false);
  const { data: parametresAlerte } = useParametresAlerte();
  const seuilEcheanceJours = parametresAlerte?.seuil_echeance_jours ?? 7;

  const indicateursFiltres = useMemo(
    () => (data?.indicateurs ?? []).filter((i) => correspond(i.libelle, recherche)),
    [data, recherche],
  );
  // Une activité reste visible si elle-même ou une de ses sous-activités
  // correspond à la recherche — pour ne jamais masquer le chemin vers une
  // sous-activité trouvée.
  const activitesFiltrees = useMemo(
    () =>
      (data?.activites ?? []).filter(
        (a) =>
          correspond(a.libelle, recherche) ||
          correspond(a.code_activite ?? "", recherche) ||
          a.sous_activites.some((sa) => correspond(sa.libelle, recherche)),
      ),
    [data, recherche],
  );

  const echeances = useMemo(() => {
    let retard = 0;
    let proche = 0;
    for (const activite of data?.activites ?? []) {
      const statutA = statutEcheance(activite.date_fin, activite.statut === "REALISEE", seuilEcheanceJours);
      if (statutA === "RETARD") retard += 1;
      else if (statutA === "PROCHE") proche += 1;
      for (const sa of activite.sous_activites) {
        const statutSA = statutEcheance(sa.date_fin, sa.statut === "TERMINEE", seuilEcheanceJours);
        if (statutSA === "RETARD") retard += 1;
        else if (statutSA === "PROCHE") proche += 1;
      }
    }
    return { retard, proche };
  }, [data, seuilEcheanceJours]);

  const [surligne, setSurligne] = useState<string | null>(null);

  // Arrivée depuis le bandeau des échéances (ex: /suivi/37#sous-activite-27) : on défile
  // jusqu'à la carte visée et on la met brièvement en évidence.
  useEffect(() => {
    if (!data || !location.hash) return;
    const cible = location.hash.slice(1);
    setSurligne(cible);
    const frame = requestAnimationFrame(() => {
      document.getElementById(cible)?.scrollIntoView({ behavior: "smooth", block: "center" });
    });
    const timer = setTimeout(() => setSurligne(null), 2500);
    return () => {
      cancelAnimationFrame(frame);
      clearTimeout(timer);
    };
  }, [data, location.hash]);

  if (isLoading || !data) return <Text>Chargement…</Text>;

  function handleSupprimerValeur(id: number) {
    confirmerSuppression({
      message: voc("Supprimer cette saisie d'indicateur ? Cette action est irréversible."),
      onConfirm: async () => {
        try {
          await deleteValeur.mutateAsync(id);
          notifications.show({ message: "Saisie supprimée", color: "green" });
        } catch {
          notifications.show({ message: "Erreur lors de la suppression", color: "red" });
        }
      },
    });
  }

  function handleSupprimerPoint(id: number) {
    confirmerSuppression({
      message: voc("Supprimer ce point de suivi ? Cette action est irréversible."),
      onConfirm: async () => {
        try {
          await deletePoint.mutateAsync(id);
          notifications.show({ message: voc("Point de suivi supprimé"), color: "green" });
        } catch {
          notifications.show({ message: "Erreur lors de la suppression", color: "red" });
        }
      },
    });
  }

  return (
    <Stack gap="lg" className="bareme-police-suivi">
      <Group justify="space-between">
        <div>
          <Title order={2}>{voc("Suivi — ")}{data.projet.nom}</Title>
          <Text c="dimmed">{data.projet.code}</Text>
        </div>
        <Group gap="xs">
          <StatusBadge tone={SUIVI_STATUT_GLOBAL_TONE[data.statut_global]}>
            {SUIVI_STATUT_GLOBAL_LABEL[data.statut_global]}
          </StatusBadge>
          <Tooltip label="Actualiser">
            <ActionIcon variant="light" size="lg" onClick={() => refetch()} loading={isFetching}>
              <RefreshCw size={18} />
            </ActionIcon>
          </Tooltip>
          <Menu position="bottom-end">
            <Menu.Target>
              <Button variant="light" leftSection={<Download size={16} />}>
                Exporter
              </Button>
            </Menu.Target>
            <Menu.Dropdown>
              <Menu.Item
                leftSection={<Download size={14} />}
                onClick={() => telechargerExportSuiviExcel(projetId, data.projet.code)}
              >
                Excel (.xlsx)
              </Menu.Item>
              <Menu.Item
                leftSection={<FileText size={14} />}
                onClick={() => telechargerExportSuiviPdf(projetId, data.projet.code)}
              >
                PDF
              </Menu.Item>
            </Menu.Dropdown>
          </Menu>
          {peutSaisir && (
            <Button variant="light" leftSection={<FileSpreadsheet size={16} />} onClick={() => setCanevasOuvert(true)}>
              Saisie par Excel
            </Button>
          )}
          <BoutonModeEdition actif={editionActive} onToggle={() => setEditionActive((v) => !v)} />
        </Group>
      </Group>
      <ImportCanevasSuiviModal
        projetId={projetId}
        codeProjet={data.projet.code}
        opened={canevasOuvert}
        onClose={() => setCanevasOuvert(false)}
      />

      <Tabs defaultValue="global" keepMounted={false} styles={{ tabLabel: { fontSize: "var(--mantine-font-size-md)", fontWeight: 600 } }}>
        <Tabs.List>
          <Tabs.Tab value="global">{voc("Suivi global")}</Tabs.Tab>
          <Tabs.Tab value="periode">{voc("Suivi par période")}</Tabs.Tab>
        </Tabs.List>

        <Tabs.Panel value="periode" pt="md">
          <SuiviPeriodeTab
            projetId={projetId}
            data={data}
            editionActive={editionActive}
            statutsActivite={STATUTS_ACTIVITE}
            statutsSousActivite={STATUTS_SOUS_ACTIVITE}
          />
        </Tabs.Panel>

        <Tabs.Panel value="global" pt="md">
          <Stack gap="lg">
              <SimpleGrid cols={{ base: 1, sm: 2 }}>
                <Card withBorder padding="md" radius="md">
                  <Text size="sm" c="dimmed" fw={600} tt="uppercase" style={{ letterSpacing: 0.4 }}>
                    Exécution physique globale
                  </Text>
                  <Text fz={28} fw={700}>
                    {data.taux_execution_physique_global !== null ? `${data.taux_execution_physique_global}%` : "—"}
                  </Text>
                </Card>
                <Card withBorder padding="md" radius="md">
                  <Text size="sm" c="dimmed" fw={600} tt="uppercase" style={{ letterSpacing: 0.4 }}>
                    Exécution financière globale
                  </Text>
                  <Text fz={28} fw={700}>
                    {data.taux_execution_financiere_global !== null ? `${data.taux_execution_financiere_global}%` : "—"}
                  </Text>
                </Card>
              </SimpleGrid>

              {(echeances.retard > 0 || echeances.proche > 0) && (
                <Alert color={echeances.retard > 0 ? "red" : "orange"} icon={<AlertTriangle size={18} />} variant="light">
                  {echeances.retard > 0 && (
                    <Text size="sm" fw={600}>
                      {echeances.retard} activité{echeances.retard > 1 ? "s" : ""}/sous-activité
                      {echeances.retard > 1 ? "s" : ""} en retard
                    </Text>
                  )}
                  {echeances.proche > 0 && (
                    <Text size="sm" c={echeances.retard > 0 ? "dimmed" : undefined} fw={echeances.retard > 0 ? 400 : 600}>
                      {echeances.proche} échéance{echeances.proche > 1 ? "s" : ""} proche
                      {echeances.proche > 1 ? "s" : ""} (dans les {seuilEcheanceJours} prochains jours)
                    </Text>
                  )}
                </Alert>
              )}

              {(data.indicateurs.length > 0 || data.activites.length > 0) && (
                <TextInput
                  placeholder={voc("Rechercher un indicateur ou une activité…")}
                  leftSection={<Search size={15} />}
                  value={recherche}
                  onChange={(e) => setRecherche(e.currentTarget.value)}
                  maw={400}
                />
              )}

              <Title order={3}>Activités</Title>
              {data.activites.length > 0 && <LegendeGraphique />}
              <Stack gap="sm">
                {data.activites.length === 0 && (
                  <Text c="dimmed">{voc("Aucune activité planifiée pour ce projet.")}</Text>
                )}
                {data.activites.length > 0 && activitesFiltrees.length === 0 && (
                  <Text c="dimmed">Aucune activité ne correspond à la recherche.</Text>
                )}
                {activitesFiltrees.map((activite) => {
                  const parQuantite = activite.methode_calcul_effective === "QUANTITE";
                  const cible = activite.quantite_prevue ? Number(activite.quantite_prevue) : null;
                  const fenetreAttendue: FenetreAttendue | null =
                    activite.date_debut && activite.date_fin && cible !== null
                      ? {
                          debut: activite.date_debut,
                          fin: activite.date_fin,
                          depart: Number(activite.valeur_reference ?? 0),
                          arrivee: cible,
                        }
                      : null;
                  const derniereQuantiteCumulee =
                    activite.historique.length > 0
                      ? Number(activite.historique[activite.historique.length - 1].quantite_cumulee ?? 0)
                      : 0;
                  const budgetAlloue = activite.budget_alloue ? Number(activite.budget_alloue) : null;
                  const derniereBudgetCumule =
                    activite.historique.length > 0
                      ? Number(activite.historique[activite.historique.length - 1].budget_cumule ?? 0)
                      : 0;
                  const fenetreAttendueBudget: FenetreAttendue | null =
                    activite.date_debut && activite.date_fin && budgetAlloue !== null
                      ? { debut: activite.date_debut, fin: activite.date_fin, depart: 0, arrivee: budgetAlloue }
                      : null;
                  return (
                  <Card
                    key={activite.id}
                    id={`activite-${activite.id}`}
                    withBorder
                    padding="md"
                    radius="md"
                    style={
                      surligne === `activite-${activite.id}`
                        ? { outline: "3px solid var(--mantine-color-orange-5)", outlineOffset: 2 }
                        : undefined
                    }
                  >
                    <Group justify="space-between" mb="xs" wrap="nowrap">
                      <Group gap={6} wrap="nowrap">
                        {activite.code_activite && <Text size="sm" c="dimmed">{activite.code_activite}</Text>}
                        <Text size="lg" fw={700}>{activite.libelle}</Text>
                        <StatusBadge tone={ACTIVITE_STATUT_TONE[activite.statut]}>
                          {ACTIVITE_STATUT_LABEL[activite.statut]}
                        </StatusBadge>
                        <AlerteBadge palier={activite.palier_actuel} taux={activite.taux_realisation ?? undefined} />
                        <EcheanceBadge
                          statut={statutEcheance(activite.date_fin, activite.statut === "REALISEE", seuilEcheanceJours)}
                          dateFin={activite.date_fin}
                        />
                      </Group>
                      <Button size="sm" variant="light" onClick={() => setModalActivite(activite.id)}>
                        {voc("Saisir un suivi")}</Button>
                    </Group>
                    {fenetreAttendue && (
                      <Text size="sm" c="dimmed" mb="xs">
                        Planifié : {fenetreAttendue.debut} → {fenetreAttendue.fin}
                      </Text>
                    )}
                    <MethodeCalculLigne
                      activite={{ ...activite, quantite_realisee: derniereQuantiteCumulee === null ? null : String(derniereQuantiteCumulee) }}
                      modifiable={peutSaisir}
                    />
                    {/* Avancement physique : par quantité, la barre détaille chaque saisie ; avec une autre
                        méthode, elle montre le taux calculé selon cette méthode (le même que le badge). */}
                    {activite.methode_calcul_effective !== "QUANTITE" ? (
                      <BarreProgression
                        label="Avancement physique"
                        segments={[
                          {
                            key: "taux",
                            valeur: activite.taux_realisation ?? 0,
                            titre: `${libelleMethodeEffective(activite.methode_calcul_effective)} : ${activite.taux_realisation ?? "—"} %`,
                          },
                        ]}
                        cible={100}
                        attendu={null}
                        unite="%"
                        tone={toneDeTaux(activite.taux_realisation)}
                      />
                    ) : cible !== null && (
                      <BarreProgression
                        label="Avancement physique"
                        segments={activite.historique.map((h) => ({
                          key: h.id,
                          valeur: Number(h.quantite_realisee ?? 0),
                          titre: `${h.periode_debut} → ${h.periode_fin} : ${h.quantite_realisee ?? 0} ${activite.unite_quantite}`,
                        }))}
                        cible={cible}
                        attendu={fenetreAttendue ? valeurAttendueA(aujourdHui(), fenetreAttendue) : null}
                        unite={activite.unite_quantite}
                        tone={toneDeTaux(tauxDe(derniereQuantiteCumulee, cible))}
                      />
                    )}
                    {budgetAlloue !== null && (
                      <BarreProgression
                        label="Avancement financier"
                        segments={activite.historique.map((h) => ({
                          key: h.id,
                          valeur: Number(h.budget_realise ?? 0),
                          titre: `${h.periode_debut} → ${h.periode_fin} : ${(h.budget_realise ? Number(h.budget_realise).toLocaleString("fr-FR") : 0)} FCFA`,
                        }))}
                        cible={budgetAlloue}
                        attendu={fenetreAttendueBudget ? valeurAttendueA(aujourdHui(), fenetreAttendueBudget) : null}
                        unite="FCFA"
                        tone={toneDeTaux(tauxDe(derniereBudgetCumule, budgetAlloue))}
                      />
                    )}
                    {activite.methode_calcul_effective === "QUANTITE" && (
                      <EvolutionChart
                        data={activite.historique.map((h) => ({ date: h.periode_fin, valeur: Number(h.quantite_cumulee ?? 0) }))}
                        cible={cible ?? undefined}
                        unite={activite.unite_quantite}
                      />
                    )}
                    <HistoriqueSuiviTable
                      editable={editionActive}
                      lignes={[...activite.historique]
                        .map((h) => {
                          const cumule = h.quantite_cumulee !== null ? Number(h.quantite_cumulee) : null;
                          const tauxCumule = tauxDe(cumule, cible);
                          const valeurAttendue = fenetreAttendue ? valeurAttendueA(h.periode_fin, fenetreAttendue) : null;
                          const tauxAttendu = valeurAttendue !== null ? tauxDe(valeurAttendue, cible) : null;
                          const ecart = ecartTexte(cumule, valeurAttendue, activite.unite_quantite);

                          const budgetCumule = h.budget_cumule !== null ? Number(h.budget_cumule) : null;
                          const tauxBudgetCumule = tauxDe(budgetCumule, budgetAlloue);
                          const budgetAttendu = fenetreAttendueBudget
                            ? valeurAttendueA(h.periode_fin, fenetreAttendueBudget)
                            : null;
                          const ecartBudget = ecartTexte(budgetCumule, budgetAttendu, "FCFA");

                          return {
                            id: h.id,
                            periode: `${h.periode_debut} → ${h.periode_fin}`,
                            valeur: parQuantite ? `${h.quantite_realisee ?? "—"} ${activite.unite_quantite}` : undefined,
                            cumule:
                              parQuantite && cumule !== null
                                ? `${cumule} ${activite.unite_quantite}${tauxCumule !== null ? ` (${tauxCumule}%)` : ""}`
                                : undefined,
                            detail: h.budget_realise
                              ? `${Number(h.budget_realise).toLocaleString("fr-FR")} FCFA` +
                                (budgetCumule !== null
                                  ? ` — cumul ${budgetCumule.toLocaleString("fr-FR")}${tauxBudgetCumule !== null ? ` (${tauxBudgetCumule}%)` : ""}${ecartBudget ? " · " + ecartBudget : ""}`
                                  : "")
                              : undefined,
                            attendu:
                              parQuantite && valeurAttendue !== null
                                ? `${Math.round(valeurAttendue)} ${activite.unite_quantite} (${tauxAttendu}%)${ecart ? " · " + ecart : ""}`
                                : undefined,
                            statut: libelleStatut(h.statut, ACTIVITE_STATUT_LABEL),
                          };
                        })
                        .reverse()}
                      onEdit={(pointId) => {
                        const point = activite.historique.find((h) => h.id === pointId);
                        if (point) setEditionPointActivite({ activiteId: activite.id, point });
                      }}
                      onDelete={handleSupprimerPoint}
                    />
                    {activite.sous_activites.length > 0 && (
                      <Stack gap="xs" mt="sm" pl="md">
                        {activite.sous_activites.map((sousActivite) => {
                          const cible = sousActivite.quantite_prevue ? Number(sousActivite.quantite_prevue) : null;
                          const derniereCumulee =
                            sousActivite.historique.length > 0
                              ? Number(sousActivite.historique[sousActivite.historique.length - 1].quantite_cumulee ?? 0)
                              : 0;
                          const taux = tauxDe(derniereCumulee, cible);
                          const fenetreAttendueSA: FenetreAttendue | null =
                            sousActivite.date_debut && sousActivite.date_fin && cible !== null
                              ? { debut: sousActivite.date_debut, fin: sousActivite.date_fin, depart: 0, arrivee: cible }
                              : null;
                          return (
                            <Card
                              key={sousActivite.id}
                              id={`sous-activite-${sousActivite.id}`}
                              withBorder
                              padding="xs"
                              radius="sm"
                              bg="gray.0"
                              style={
                                surligne === `sous-activite-${sousActivite.id}`
                                  ? { outline: "3px solid var(--mantine-color-orange-5)", outlineOffset: 2 }
                                  : undefined
                              }
                            >
                              <Group justify="space-between" mb={4} wrap="nowrap">
                                <Group gap={6} wrap="nowrap">
                                  <Text size="md" fw={600}>{sousActivite.libelle}</Text>
                                  <Badge size="md">{SOUS_ACTIVITE_STATUT_LABEL[sousActivite.statut]}</Badge>
                                  <EcheanceBadge
                                    statut={statutEcheance(
                                      sousActivite.date_fin,
                                      sousActivite.statut === "TERMINEE",
                                      seuilEcheanceJours,
                                    )}
                                    dateFin={sousActivite.date_fin}
                                  />
                                </Group>
                                <Button size="sm" variant="subtle" onClick={() => setModalSousActivite(sousActivite.id)}>
                                  {voc("Saisir un suivi")}</Button>
                              </Group>
                              {cible !== null && (
                                <BarreProgression
                                  label={
                                    sousActivite.date_debut && sousActivite.date_fin
                                      ? `Planifié : ${sousActivite.date_debut} → ${sousActivite.date_fin}`
                                      : undefined
                                  }
                                  segments={sousActivite.historique.map((h) => ({
                                    key: h.id,
                                    valeur: Number(h.quantite_realisee ?? 0),
                                    titre: `${h.periode_debut} → ${h.periode_fin} : ${h.quantite_realisee ?? 0} ${sousActivite.unite_quantite}`,
                                  }))}
                                  cible={cible}
                                  attendu={fenetreAttendueSA ? valeurAttendueA(aujourdHui(), fenetreAttendueSA) : null}
                                  unite={sousActivite.unite_quantite}
                                  tone={toneDeTaux(taux)}
                                />
                              )}
                              <EvolutionChart
                                data={sousActivite.historique.map((h) => ({
                                  date: h.periode_fin,
                                  valeur: Number(h.quantite_cumulee ?? 0),
                                }))}
                                cible={cible ?? undefined}
                                unite={sousActivite.unite_quantite}
                                height={130}
                              />
                              <HistoriqueSuiviTable
                                editable={editionActive}
                                lignes={[...sousActivite.historique]
                                  .map((h) => {
                                    const cumule = h.quantite_cumulee !== null ? Number(h.quantite_cumulee) : null;
                                    const tauxCumule = tauxDe(cumule, cible);
                                    const valeurAttendue = fenetreAttendueSA
                                      ? valeurAttendueA(h.periode_fin, fenetreAttendueSA)
                                      : null;
                                    const tauxAttendu = valeurAttendue !== null ? tauxDe(valeurAttendue, cible) : null;
                                    const ecart = ecartTexte(cumule, valeurAttendue, sousActivite.unite_quantite);
                                    return {
                                      id: h.id,
                                      periode: `${h.periode_debut} → ${h.periode_fin}`,
                                      valeur: `${h.quantite_realisee ?? "—"} ${sousActivite.unite_quantite}`,
                                      cumule:
                                        cumule !== null
                                          ? `${cumule} ${sousActivite.unite_quantite}${tauxCumule !== null ? ` (${tauxCumule}%)` : ""}`
                                          : undefined,
                                      attendu:
                                        valeurAttendue !== null
                                          ? `${Math.round(valeurAttendue)} ${sousActivite.unite_quantite} (${tauxAttendu}%)${ecart ? " · " + ecart : ""}`
                                          : undefined,
                                      statut: libelleStatut(h.statut, SOUS_ACTIVITE_STATUT_LABEL),
                                    };
                                  })
                                  .reverse()}
                                onEdit={(pointId) => {
                                  const point = sousActivite.historique.find((h) => h.id === pointId);
                                  if (point) setEditionPointSousActivite({ sousActiviteId: sousActivite.id, point });
                                }}
                                onDelete={handleSupprimerPoint}
                              />
                            </Card>
                          );
                        })}
                      </Stack>
                    )}
                  </Card>
                  );
                })}
              </Stack>

              <Title order={3}>{voc("Indicateurs")}</Title>
              {data.indicateurs.length > 0 && <LegendeGraphique />}
              <Stack gap="sm">
                {data.indicateurs.length === 0 && (
                  <Text c="dimmed">{voc("Aucun indicateur rattaché à ce projet.")}</Text>
                )}
                {data.indicateurs.length > 0 && indicateursFiltres.length === 0 && (
                  <Text c="dimmed">{voc("Aucun indicateur ne correspond à la recherche.")}</Text>
                )}
                {indicateursFiltres.map((indicateur) => {
                  const cible = Number(indicateur.valeur_cible);
                  const fenetreAttendue: FenetreAttendue | null =
                    indicateur.periode_debut_planifiee && indicateur.periode_fin_planifiee
                      ? {
                          debut: indicateur.periode_debut_planifiee,
                          fin: indicateur.periode_fin_planifiee,
                          depart: Number(indicateur.valeur_reference ?? 0),
                          arrivee: cible,
                        }
                      : null;
                  return (
                    <Card key={indicateur.id} withBorder padding="md" radius="md">
                      <Group justify="space-between" mb="xs" wrap="nowrap">
                        <Text size="lg" fw={700}>{indicateur.libelle}</Text>
                        <Group gap="xs" wrap="nowrap">
                          <AlerteBadge palier={indicateur.palier_actuel} taux={indicateur.taux_actuel} />
                          <Button size="sm" variant="light" onClick={() => setModalIndicateur(indicateur.id)}>
                            Saisir une valeur
                          </Button>
                        </Group>
                      </Group>
                      <BarreProgression
                        label={
                          fenetreAttendue ? `Planifié : ${fenetreAttendue.debut} → ${fenetreAttendue.fin}` : undefined
                        }
                        segments={indicateur.historique.map((h) => ({
                          key: h.id,
                          valeur: Number(h.valeur_realisee),
                          titre: `${h.periode_debut} → ${h.periode_fin} : ${h.valeur_realisee} ${indicateur.unite}`,
                        }))}
                        cible={cible}
                        attendu={fenetreAttendue ? valeurAttendueA(aujourdHui(), fenetreAttendue) : null}
                        unite={indicateur.unite}
                        couleur={indicateur.palier_actuel?.couleur}
                      />
                      <EvolutionChart
                        data={indicateur.historique.map((h) => ({ date: h.periode_fin, valeur: Number(h.valeur_cumulee) }))}
                        cible={cible}
                        unite={indicateur.unite}
                      />
                      <HistoriqueSuiviTable
                        editable={editionActive}
                        lignes={[...indicateur.historique]
                          .map((h) => {
                            const valeurAttendue = fenetreAttendue ? valeurAttendueA(h.periode_fin, fenetreAttendue) : null;
                            const tauxAttendu = valeurAttendue !== null ? tauxDe(valeurAttendue, cible) : null;
                            const ecart = ecartTexte(Number(h.valeur_cumulee), valeurAttendue, indicateur.unite);
                            return {
                              id: h.id,
                              periode: `${h.periode_debut} → ${h.periode_fin}`,
                              valeur: `${h.valeur_realisee} ${indicateur.unite}`,
                              cumule: `${h.valeur_cumulee} ${indicateur.unite} (${h.taux}%)`,
                              attendu:
                                valeurAttendue !== null
                                  ? `${Math.round(valeurAttendue)} ${indicateur.unite} (${tauxAttendu}%)${ecart ? " · " + ecart : ""}`
                                  : undefined,
                            };
                          })
                          .reverse()}
                        onEdit={(valeurId) => {
                          const valeur = indicateur.historique.find((h) => h.id === valeurId);
                          if (valeur) setEditionValeur({ indicateurId: indicateur.id, valeur });
                        }}
                        onDelete={handleSupprimerValeur}
                      />
                    </Card>
                  );
                })}
              </Stack>
          </Stack>
        </Tabs.Panel>
      </Tabs>

      <Modal
        opened={modalIndicateur !== null}
        onClose={() => setModalIndicateur(null)}
        title={voc("Nouvelle saisie — indicateur")}
        size="lg"
      >
        {modalIndicateur !== null && (
          <SaisieValeurIndicateurForm
            indicateurId={modalIndicateur}
            historiqueExistant={data.indicateurs.find((i) => i.id === modalIndicateur)?.historique}
            onDone={() => setModalIndicateur(null)}
          />
        )}
      </Modal>

      <Modal
        opened={modalActivite !== null}
        onClose={() => setModalActivite(null)}
        title={`${voc("Saisir un suivi")} — ${data.activites.find((a) => a.id === modalActivite)?.libelle ?? ""}`}
        size="lg"
      >
        {modalActivite !== null &&
          (data.activites.find((a) => a.id === modalActivite)?.methode_calcul_effective === "QUANTITE" ? (
            <SaisiePointSuiviForm
              activiteId={modalActivite}
              statutsDisponibles={STATUTS_ACTIVITE}
              avecBudget
              historiqueExistant={data.activites.find((a) => a.id === modalActivite)?.historique}
              onDone={() => setModalActivite(null)}
            />
          ) : (
            <SaisieSuiviMethode activiteId={modalActivite} modifiable={peutSaisir} onDone={() => setModalActivite(null)} />
          ))}
      </Modal>

      <Modal
        opened={modalSousActivite !== null}
        onClose={() => setModalSousActivite(null)}
        title={voc("Nouveau point de suivi — sous-activité")}
        size="lg"
      >
        {modalSousActivite !== null && (
          <SaisiePointSuiviForm
            sousActiviteId={modalSousActivite}
            statutsDisponibles={STATUTS_SOUS_ACTIVITE}
            avecBudget={false}
            historiqueExistant={data.activites
              .flatMap((a) => a.sous_activites)
              .find((sa) => sa.id === modalSousActivite)?.historique}
            onDone={() => setModalSousActivite(null)}
          />
        )}
      </Modal>

      <Modal
        opened={editionValeur !== null}
        onClose={() => setEditionValeur(null)}
        title={voc("Modifier la saisie — indicateur")}
        size="lg"
      >
        {editionValeur !== null && (
          <SaisieValeurIndicateurForm
            indicateurId={editionValeur.indicateurId}
            valeurExistante={editionValeur.valeur}
            historiqueExistant={data.indicateurs.find((i) => i.id === editionValeur.indicateurId)?.historique}
            onDone={() => setEditionValeur(null)}
          />
        )}
      </Modal>

      <Modal
        opened={editionPointActivite !== null}
        onClose={() => setEditionPointActivite(null)}
        title={voc("Modifier le point de suivi — activité")}
        size="lg"
      >
        {editionPointActivite !== null && (
          <SaisiePointSuiviForm
            activiteId={editionPointActivite.activiteId}
            statutsDisponibles={STATUTS_ACTIVITE}
            avecBudget
            historiqueExistant={data.activites.find((a) => a.id === editionPointActivite.activiteId)?.historique}
            pointExistant={editionPointActivite.point}
            avecQuantite={
              data.activites.find((a) => a.id === editionPointActivite.activiteId)?.methode_calcul_effective === "QUANTITE"
            }
            onDone={() => setEditionPointActivite(null)}
          />
        )}
      </Modal>

      <Modal
        opened={editionPointSousActivite !== null}
        onClose={() => setEditionPointSousActivite(null)}
        title={voc("Modifier le point de suivi — sous-activité")}
        size="lg"
      >
        {editionPointSousActivite !== null && (
          <SaisiePointSuiviForm
            sousActiviteId={editionPointSousActivite.sousActiviteId}
            statutsDisponibles={STATUTS_SOUS_ACTIVITE}
            avecBudget={false}
            historiqueExistant={
              data.activites
                .flatMap((a) => a.sous_activites)
                .find((sa) => sa.id === editionPointSousActivite.sousActiviteId)?.historique
            }
            pointExistant={editionPointSousActivite.point}
            onDone={() => setEditionPointSousActivite(null)}
          />
        )}
      </Modal>
    </Stack>
  );
}
