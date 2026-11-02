import { useMemo, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import {
  ChevronDown,
  ChevronRight,
  ChevronsDownUp,
  ChevronsUpDown,
  Copy,
  Download,
  FileText,
  Gauge,
  ListPlus,
  ListTree,
  MapPin,
  Paperclip,
  Pencil,
  Plus,
  Search,
  ShieldCheck,
  Target,
  Trash2,
  Users,
  Wallet,
  MessagesSquare,
} from "lucide-react";
import { RetoursProjet } from "../plaintes/RetoursProjet";
import {
  ActionIcon,
  Badge,
  Box,
  Button,
  Card,
  Group,
  Menu,
  Modal,
  Popover,
  SegmentedControl,
  Stack,
  Table,
  Tabs,
  Text,
  TextInput,
  Title,
  Tooltip,
} from "@mantine/core";
import { notifications } from "@mantine/notifications";
import { messageErreurApi } from "../../utils/erreurs";
import {
  useProjet,
  useCreateActivite,
  useDeleteActivite,
  useDupliquerActivite,
  useDeleteSousActivite,
  useDeleteProjet,
  useNiveauxActivite,
  useNommerNiveau,
  telechargerExportProjet,
} from "../../api/projects";
import { useDashboardProjet } from "../../api/dashboard";
import {
  telechargerExportSuiviExcel,
  telechargerExportSuiviPdf,
  telechargerExportSuiviPeriode,
  telechargerExportSuiviWord,
  usePeriodesPlanification,
} from "../../api/suivi";
import { RapportFinancierModal } from "./RapportFinancierModal";
import { CadreLogiqueTab } from "./CadreLogiqueTab";
import { RisquesTab } from "./RisquesTab";
import { AlerteBadge } from "../../components/indicators/AlerteBadge";
import { confirmerSuppression } from "../../components/common/confirmerSuppression";
import { HistoriqueModification } from "../../components/audit/HistoriqueModification";
import { DocumentsTab } from "../../components/documents/DocumentsTab";
import { BeneficiairesTab } from "../../components/beneficiaires/BeneficiairesTab";
import { PlanificationPeriodeTab } from "./PlanificationPeriodeTab";
import { BandeauProjetCloture } from "../../components/common/BandeauProjetCloture";
import { BandeauSaisieFermee } from "../../components/common/BandeauSaisieFermee";
import { saisieBloquee } from "../../utils/rapportage";
import { useAccesModules } from "../../utils/modules";
import { BoutonModeEdition } from "../../components/common/BoutonModeEdition";
import { ResumeAttributs } from "../../components/common/AttributsLibres";
import { nomsAttributs } from "../../utils/attributs";
import { ActiviteForm } from "./ActiviteForm";
import { PlanificationTableau } from "./PlanificationTableau";
import { type ModeAffichage, useModeAffichage, usePreference } from "../../utils/affichage";
import { ImportPlanification, MenuExportPlanification } from "./ExportPlanification";
import { AvancementModal } from "./AvancementModal";
import { useAuth } from "../../auth/useAuth";
import { libelleMethodeEffective } from "../../utils/methodesCalcul";
import { NiveauxActiviteTab } from "./NiveauxActiviteTab";
import { SousActiviteForm } from "./SousActiviteForm";
import { FinancementsTab } from "./FinancementsTab";
import { EquipeTab } from "./EquipeTab";
import { CoherenceTab } from "./CoherenceTab";
import { PartenairesProjetTab } from "./PartenairesProjetTab";
import { ProjetForm } from "./ProjetForm";
import { TauxParIndicateurChart } from "../../components/charts/TauxParIndicateurChart";
import { PAYS_MONDE } from "../../utils/pays";
import { PROJET_STATUT_LABEL } from "../../utils/statusTones";
import { correspond } from "../../utils/recherche";
import type { Activite, SousActivite } from "../../types";
import { voc } from "../../utils/vocabulaire";
import { libelleDuree } from "../../utils/periode";

import { langue, locale, traduireDonnee } from "../../utils/i18n";
function AjoutInline({
  placeholder,
  demanderNomNiveau,
  onAdd,
}: {
  placeholder: string;
  /** Le niveau n'a pas encore de nom : on le demande en même temps que le premier élément. */
  demanderNomNiveau?: boolean;
  onAdd: (libelle: string, nomNiveau: string) => void;
}) {
  const [value, setValue] = useState("");
  const [nomNiveau, setNomNiveau] = useState("");
  const pret = value.trim() && (!demanderNomNiveau || nomNiveau.trim());
  return (
    <Group gap="xs" mt={4} align="flex-end">
      {demanderNomNiveau && (
        <TextInput
          size="xs"
          label={voc("Nom de ce niveau")}
          placeholder={voc("Ex : Résultat, Objectif, Pilier…")}
          value={nomNiveau}
          onChange={(e) => setNomNiveau(e.currentTarget.value)}
          w={220}
        />
      )}
      <TextInput
        size="xs"
        label={demanderNomNiveau ? voc("Libellé") : undefined}
        placeholder={placeholder}
        value={value}
        onChange={(e) => setValue(e.currentTarget.value)}
        w={360}
      />
      <Button
        size="xs"
        variant="light"
        disabled={!pret}
        onClick={() => {
          if (pret) {
            onAdd(value.trim(), nomNiveau.trim());
            setValue("");
            setNomNiveau("");
          }
        }}
      >
        {voc("Ajouter")}
      </Button>
    </Group>
  );
}

/**
 * Étiquette du niveau d'un élément — un clic permet de nommer (ou renommer)
 * ce niveau pour tout le projet, directement depuis l'arbre.
 */
function BadgeNiveau({
  nom,
  nomme,
  couleur,
  onRenommer,
}: {
  nom: string;
  /** false : niveau encore sans nom (affiché avec le nom par défaut). */
  nomme: boolean;
  couleur: string;
  onRenommer: (nouveauNom: string) => Promise<void>;
}) {
  const [ouvert, setOuvert] = useState(false);
  const [valeur, setValeur] = useState(nomme ? nom : "");
  return (
    <Popover opened={ouvert} onChange={setOuvert} position="bottom-start" withArrow shadow="md" trapFocus>
      <Popover.Target>
        <Tooltip label={nomme ? voc("Renommer ce niveau") : voc("Niveau sans nom — clique pour le nommer")}>
          <Badge
            color={couleur}
            variant={nomme ? "light" : "outline"}
            size="xs"
            style={{ cursor: "pointer", borderStyle: nomme ? undefined : "dashed" }}
            onClick={() => {
              setValeur(nomme ? nom : "");
              setOuvert((o) => !o);
            }}
          >
            {nom}
          </Badge>
        </Tooltip>
      </Popover.Target>
      <Popover.Dropdown>
        <Stack gap={6}>
          <Text size="xs" c="dimmed">{voc("Nom de ce niveau (pour tous ses éléments dans le projet)")}</Text>
          <Group gap={6} wrap="nowrap">
            <TextInput
              size="xs"
              placeholder={voc("Ex : Résultat, Pilier…")}
              value={valeur}
              onChange={(e) => setValeur(e.currentTarget.value)}
              w={200}
            />
            <Button
              size="xs"
              disabled={!valeur.trim()}
              onClick={async () => {
                try {
                  await onRenommer(valeur.trim());
                  setOuvert(false);
                } catch {
                  notifications.show({ message: voc("Erreur lors de l'enregistrement du nom du niveau"), color: "red" });
                }
              }}
            >
              {voc("OK")}
            </Button>
          </Group>
        </Stack>
      </Popover.Dropdown>
    </Popover>
  );
}

// Couleur de la bordure et du badge selon la profondeur, pour distinguer les
// niveaux d'un coup d'œil quel que soit leur nombre.
const COULEURS_NIVEAUX = ["teal", "blue", "grape", "orange", "cyan", "pink", "lime", "indigo"];

function nomDuNiveau(niveauxNoms: Record<number, string>, profondeur: number) {
  return niveauxNoms[profondeur] ?? voc("Activité");
}

/** Tous les éléments de l'arbre, à plat (tous niveaux). */
function aplatir(elements: Activite[]): Activite[] {
  return elements.flatMap((e) => [e, ...aplatir(e.enfants)]);
}

/**
 * Garde un élément s'il correspond à la recherche, ou si l'un de ses
 * descendants y correspond — pour ne jamais masquer le chemin vers un
 * résultat trouvé en profondeur.
 */
function filtrerArbre(elements: Activite[], recherche: string): Activite[] {
  return elements
    .map((e) => {
      const correspondDirectement = correspond(e.libelle, recherche) || correspond(e.code_activite ?? "", recherche);
      if (correspondDirectement) return e;
      const enfants = filtrerArbre(e.enfants, recherche);
      const sousActivites = e.sous_activites.filter((sa) => correspond(sa.libelle, recherche));
      if (enfants.length === 0 && sousActivites.length === 0) return null;
      return { ...e, enfants, sous_activites: sousActivites };
    })
    .filter((e): e is Activite => e !== null);
}

// Un élément de la planification, à n'importe quel niveau : il s'affiche
// lui-même pour chacun de ses enfants (profondeur illimitée). Le nom affiché
// par profondeur vient de niveauxNoms (NiveauActivite du projet).
function CarteActivite({
  act,
  profondeur,
  editionActive,
  niveauxNoms,
  onRenommerNiveau,
  onDocuments,
  onBeneficiaires,
  onEditer,
  onAjouterEnfant,
  onAjouterSousActivite,
  onAvancement,
  onSupprimer,
  onDocumentsSousActivite,
  onBeneficiairesSousActivite,
  onSupprimerSousActivite,
  onEditerSousActivite,
  onDupliquer,
  replies,
  onBasculer,
}: {
  act: Activite;
  profondeur: number;
  /** Éléments repliés : leurs niveaux en dessous et leurs sous-activités sont masqués. */
  replies: Set<number>;
  onBasculer: (id: number) => void;
  editionActive: boolean;
  niveauxNoms: Record<number, string>;
  onRenommerNiveau: (profondeur: number, nom: string) => Promise<void>;
  onDocuments: (id: number) => void;
  onBeneficiaires: (id: number) => void;
  onEditer: (act: Activite) => void;
  /** Absents : projet en lecture seule (clôturé), pas d'ajout possible. */
  onAjouterEnfant?: (act: Activite, profondeurEnfant: number) => void;
  onAjouterSousActivite?: (id: number) => void;
  onAvancement: (act: Activite) => void;
  onSupprimer: (act: Activite, profondeur: number) => void;
  /** Absent : projet en lecture seule (clôturé) ou utilisateur sans droit d'écriture. */
  onDupliquer?: (act: Activite) => void;
  onDocumentsSousActivite: (id: number) => void;
  onBeneficiairesSousActivite: (id: number) => void;
  onSupprimerSousActivite: (sa: SousActivite) => void;
  onEditerSousActivite: (sa: SousActivite) => void;
}) {
  const nomNiveau = nomDuNiveau(niveauxNoms, profondeur);
  const nomNiveauSuivant = niveauxNoms[profondeur + 1];
  const couleur = COULEURS_NIVEAUX[profondeur % COULEURS_NIVEAUX.length];
  const { estMasque } = useAccesModules();
  const repliable = act.enfants.length > 0 || act.sous_activites.length > 0;
  const replie = repliable && replies.has(act.id);

  return (
    <Card
      withBorder
      radius="sm"
      padding="xs"
      bg={profondeur === 0 ? "white" : "gray.0"}
      style={{ borderLeft: `3px solid var(--mantine-color-${couleur}-5)` }}
    >
      <Group justify="space-between" align="flex-start" wrap="wrap">
        <div>
          <Group gap={6} wrap="wrap">
            {repliable && (
              <Tooltip label={replie ? voc("Déplier") : voc("Replier")}>
                <ActionIcon size="sm" variant="subtle" color="gray" onClick={() => onBasculer(act.id)}>
                  {replie ? <ChevronRight size={14} /> : <ChevronDown size={14} />}
                </ActionIcon>
              </Tooltip>
            )}
            <BadgeNiveau
              nom={nomNiveau}
              nomme={profondeur in niveauxNoms}
              couleur={couleur}
              onRenommer={(nom) => onRenommerNiveau(profondeur, nom)}
            />
            {act.code_activite && <Text size="xs" c="dimmed">{act.code_activite}</Text>}
            <Text size="sm" fw={profondeur === 0 ? 700 : 500}>{act.libelle}</Text>
          </Group>
          {act.description && (
            <Text size="xs" c="dimmed" mt={2}>
              {act.description}
            </Text>
          )}
          <ResumeAttributs attributs={act.attributs} />
          {(act.date_debut || act.date_fin) && (
            <Text size="xs" c="dimmed" mt={2}>
              {act.date_debut ?? "?"} → {act.date_fin ?? "?"}
              {libelleDuree(act.date_debut, act.date_fin) && ` · ${libelleDuree(act.date_debut, act.date_fin)}`}
            </Text>
          )}
          {act.commentaire && (
            <Text size="xs" c="dimmed" fs="italic" mt={2}>
              {act.commentaire}
            </Text>
          )}
          {((act.structures_noms?.length ?? 0) > 0 || (act.partenaires_charges_noms?.length ?? 0) > 0) && (
            <Group gap={4} mt={4}>
              {act.structures_noms?.map((nom) => (
                <Badge key={`s-${nom}`} size="xs" variant="light" color="indigo">{nom}</Badge>
              ))}
              {act.partenaires_charges_noms?.map((nom) => (
                <Badge key={`p-${nom}`} size="xs" variant="light" color="teal">{nom}</Badge>
              ))}
            </Group>
          )}
          {(act.axes_strategiques_secondaires_noms?.length ?? 0) > 0 && (
            <Text size="xs" c="dimmed" mt={2}>
              {voc("Contribue aussi à :")} {act.axes_strategiques_secondaires_noms?.join(" · ")}
            </Text>
          )}
          {act.budget_avertissements.map((message) => (
            <Text key={message} size="xs" c="orange.8" mt={2}>
              {message}
            </Text>
          ))}
        </div>
        <Group gap={4} wrap="nowrap">
          <Tooltip
            label={`${voc("Taux d'exécution")} — ${libelleMethodeEffective(act.methode_calcul_effective)}${
              act.taux_avertissements.length ? ` · ${act.taux_avertissements[0]}` : ""
            }`}
          >
            <Button
              size="compact-xs"
              variant="light"
              color={act.taux_avertissements.length ? "orange" : "teal"}
              onClick={() => onAvancement(act)}
              miw={56}
            >
              {act.taux_realisation === null ? "—" : `${act.taux_realisation.toLocaleString(locale())} %`}
            </Button>
          </Tooltip>
          {!estMasque("/documents") && (
            <Tooltip label={voc("Documents liés")}>
              <ActionIcon size="sm" variant="subtle" onClick={() => onDocuments(act.id)}>
                <Paperclip size={12} />
              </ActionIcon>
            </Tooltip>
          )}
          {!estMasque("/beneficiaires") && (
            <Tooltip label={voc("Bénéficiaires liés")}>
              <ActionIcon size="sm" variant="subtle" onClick={() => onBeneficiaires(act.id)}>
                <Users size={12} />
              </ActionIcon>
            </Tooltip>
          )}
          {editionActive && (
            <Tooltip label={voc`Modifier ce « ${nomNiveau} »`}>
              <ActionIcon size="sm" variant="subtle" onClick={() => onEditer(act)}>
                <Pencil size={12} />
              </ActionIcon>
            </Tooltip>
          )}
          {onAjouterEnfant && (
            <Tooltip label={nomNiveauSuivant ? voc`Ajouter un « ${nomNiveauSuivant} » en dessous` : voc("Ajouter un niveau en dessous")}>
              <ActionIcon size="sm" variant="subtle" onClick={() => onAjouterEnfant(act, profondeur + 1)}>
                <Plus size={14} />
              </ActionIcon>
            </Tooltip>
          )}
          {onAjouterSousActivite && (
            <Tooltip label={voc("Ajouter une sous-activité")}>
              <ActionIcon size="sm" variant="subtle" onClick={() => onAjouterSousActivite(act.id)}>
                <ListPlus size={14} />
              </ActionIcon>
            </Tooltip>
          )}
          {onDupliquer && (
            <Tooltip label={voc`Dupliquer ce « ${nomNiveau} » avec tout ce qui est en dessous (sans les réalisations)`}>
              <ActionIcon size="sm" variant="subtle" onClick={() => onDupliquer(act)}>
                <Copy size={14} />
              </ActionIcon>
            </Tooltip>
          )}
          {editionActive && (
            <Tooltip label={voc`Supprimer ce « ${nomNiveau} »`}>
              <ActionIcon size="sm" variant="subtle" color="red" onClick={() => onSupprimer(act, profondeur)}>
                <Trash2 size={12} />
              </ActionIcon>
            </Tooltip>
          )}
        </Group>
      </Group>

      {!replie && act.enfants.length > 0 && (
        <Stack mt={6} gap={6} pl="md">
          {act.enfants.map((enfant) => (
            <CarteActivite
              key={enfant.id}
              act={enfant}
              profondeur={profondeur + 1}
              editionActive={editionActive}
              niveauxNoms={niveauxNoms}
              onRenommerNiveau={onRenommerNiveau}
              onDocuments={onDocuments}
              onBeneficiaires={onBeneficiaires}
              onEditer={onEditer}
              onAjouterEnfant={onAjouterEnfant}
              onAjouterSousActivite={onAjouterSousActivite}
              onAvancement={onAvancement}
              onSupprimer={onSupprimer}
              onDupliquer={onDupliquer}
              onDocumentsSousActivite={onDocumentsSousActivite}
              onBeneficiairesSousActivite={onBeneficiairesSousActivite}
              onSupprimerSousActivite={onSupprimerSousActivite}
              onEditerSousActivite={onEditerSousActivite}
              replies={replies}
              onBasculer={onBasculer}
            />
          ))}
        </Stack>
      )}

      {!replie && act.sous_activites.length > 0 && (
        <Stack mt={6} gap={6} pl="md">
          {act.sous_activites.map((sa) => (
            <Card key={sa.id} withBorder radius="sm" padding={6} bg="white" style={{ borderLeft: "3px solid var(--mantine-color-gray-5)" }}>
              <Group justify="space-between" align="center" wrap="wrap">
                <div>
                  <Group gap={6} wrap="wrap">
                    <Badge color="gray" variant="light" size="xs">{voc("Sous-activité")}</Badge>
                    <Text size="sm">{sa.libelle}</Text>
                  </Group>
                  {(sa.date_debut || sa.date_fin) && (
                    <Text size="xs" c="dimmed" mt={2}>
                      {sa.date_debut ?? "?"} → {sa.date_fin ?? "?"}
              {libelleDuree(sa.date_debut, sa.date_fin) && ` · ${libelleDuree(sa.date_debut, sa.date_fin)}`}
                    </Text>
                  )}
                  <ResumeAttributs attributs={sa.attributs} />
                </div>
                <Group gap={4} wrap="nowrap">
                  {!estMasque("/documents") && (
                    <Tooltip label={voc("Documents liés")}>
                      <ActionIcon size="sm" variant="subtle" onClick={() => onDocumentsSousActivite(sa.id)}>
                        <Paperclip size={12} />
                      </ActionIcon>
                    </Tooltip>
                  )}
                  {!estMasque("/beneficiaires") && (
                    <Tooltip label={voc("Bénéficiaires liés")}>
                      <ActionIcon size="sm" variant="subtle" onClick={() => onBeneficiairesSousActivite(sa.id)}>
                        <Users size={12} />
                      </ActionIcon>
                    </Tooltip>
                  )}
                  {editionActive && (
                    <Tooltip label={voc("Modifier la sous-activité")}>
                      <ActionIcon size="sm" variant="subtle" onClick={() => onEditerSousActivite(sa)}>
                        <Pencil size={12} />
                      </ActionIcon>
                    </Tooltip>
                  )}
                  {editionActive && (
                    <Tooltip label={voc("Supprimer la sous-activité")}>
                      <ActionIcon size="sm" variant="subtle" color="red" onClick={() => onSupprimerSousActivite(sa)}>
                        <Trash2 size={12} />
                      </ActionIcon>
                    </Tooltip>
                  )}
                </Group>
              </Group>
            </Card>
          ))}
        </Stack>
      )}
    </Card>
  );
}

export function ProjetDetailPage() {
  const { id } = useParams();
  const navigate = useNavigate();
  const projetId = Number(id);
  const { data: projet, isLoading } = useProjet(projetId);
  const { data: dashboard } = useDashboardProjet(projetId);
  const { data: niveauxActivite } = useNiveauxActivite(projetId);
  const niveauxNoms = useMemo(
    () => Object.fromEntries((niveauxActivite ?? []).map((n) => [n.profondeur, n.nom_niveau])),
    [niveauxActivite],
  );

  const createActivite = useCreateActivite();
  const nommerNiveau = useNommerNiveau(projetId);
  const deleteActivite = useDeleteActivite();
  const dupliquerActivite = useDupliquerActivite();
  const deleteSousActivite = useDeleteSousActivite();
  const deleteProjet = useDeleteProjet();

  const [modalActiviteEdition, setModalActiviteEdition] = useState<Activite | null>(null);
  const [modalActiviteEnfantFor, setModalActiviteEnfantFor] = useState<{ parent: Activite; profondeur: number } | null>(
    null,
  );
  const [modalSousActiviteFor, setModalSousActiviteFor] = useState<number | null>(null);
  const [sousActiviteEdition, setSousActiviteEdition] = useState<SousActivite | null>(null);
  const [avancementForId, setAvancementForId] = useState<number | null>(null);
  const setAvancementFor = (act: Activite) => setAvancementForId(act.id);
  const { user } = useAuth();
  const { estMasque, peutEcrire } = useAccesModules();
  const peutModifier = peutEcrire("/projets");
  // Projet clôturé : lecture seule (voir BandeauProjetCloture), mode édition indisponible.
  const cloture = projet?.statut === "CLOTURE";
  // Lecture seule : projet clôturé, ou fermé en entier hors période de rapportage (sauf administrateur).
  const lectureSeule = cloture || saisieBloquee(projet, user?.role).tout;
  const realisationsFermees = cloture || saisieBloquee(projet, user?.role).realisations;
  const [documentsActiviteId, setDocumentsActiviteId] = useState<number | null>(null);
  const [documentsSousActiviteId, setDocumentsSousActiviteId] = useState<number | null>(null);
  const [beneficiairesActiviteId, setBeneficiairesActiviteId] = useState<number | null>(null);
  const [beneficiairesSousActiviteId, setBeneficiairesSousActiviteId] = useState<number | null>(null);
  const [modalEditionOuvert, setModalEditionOuvert] = useState(false);
  const [rapportFinancierOuvert, setRapportFinancierOuvert] = useState(false);
  const [recherchePlan, setRecherchePlan] = useState("");
  // Éléments repliés dans l'arbre de la planification (tout est déplié à l'ouverture).
  const [replies, setReplies] = useState<Set<number>>(new Set());
  const basculer = (id: number) =>
    setReplies((avant) => {
      const apres = new Set(avant);
      if (!apres.delete(id)) apres.add(id);
      return apres;
    });
  const [editionDemandee, setEditionActive] = useState(false);
  const editionActive = editionDemandee && !lectureSeule;

  const [affichagePlan, setAffichagePlan] = useModeAffichage("planification-projet");
  // Périodes de planification : le suivi de chacune s'exporte aussi depuis le menu Exporter.
  const { data: periodesSuivi } = usePeriodesPlanification(projetId);
  // Programmation choisie dans le mode Tableau : reprise par l'export depuis le mode Arbre.
  const [programmationPlan] = usePreference("programmation-planification", ["trimestres", "dates"] as const);
  const supprimerElement = (a: Activite, profondeur: number) =>
    supprimerAvecConfirmation(
      voc`Supprimer « ${a.libelle} » (${nomDuNiveau(niveauxNoms, profondeur)}) ainsi que tout ce qui se trouve en dessous (niveaux inférieurs, sous-activités, indicateurs liés) ? Cette action est irréversible.`,
      () => deleteActivite.mutateAsync(a.id),
      voc("Élément supprimé"),
    );
  const supprimerSousActivite = (sa: SousActivite) =>
    supprimerAvecConfirmation(
      voc`Supprimer la sous-activité "${sa.libelle}" ? Cette action est irréversible.`,
      () => deleteSousActivite.mutateAsync(sa.id),
      voc("Sous-activité supprimée"),
    );
  const [onglet, setOnglet] = useState("hierarchie");
  const groupesOnglets = [
    {
      cle: "planification", label: voc("Planification"), icone: <ListTree size={15} />,
      onglets: [
        // L'arborescence d'abord : c'est elle qu'ouvre un clic sur le thème.
        { valeur: "hierarchie", label: voc("Planification"), masque: null },
        { valeur: "niveaux", label: voc("Configuration des niveaux"), masque: "projet:niveaux" },
        { valeur: "periode", label: voc("Planification par période"), masque: "projet:periode" },
      ],
    },
    {
      cle: "cadre", label: voc("Cadre logique"), icone: <Target size={15} />,
      onglets: [
        { valeur: "cadre-logique", label: voc("Cadre logique"), masque: "projet:cadre-logique" },
        { valeur: "risques", label: voc("Risques"), masque: "projet:risques" },
      ],
    },
    {
      cle: "acteurs", label: voc("Équipe"), icone: <Users size={15} />,
      onglets: [
        { valeur: "equipe", label: voc("Équipe de projet"), masque: "projet:equipe" },
        { valeur: "partenaires", label: voc("Partenaires"), masque: "projet:partenaires" },
      ],
    },
    { cle: "indicateurs", label: voc("Indicateurs"), icone: <Gauge size={15} />, onglets: [{ valeur: "indicateurs", label: voc("Indicateurs"), masque: "projet:indicateurs" }] },
    { cle: "financement", label: voc("Financement"), icone: <Wallet size={15} />, onglets: [{ valeur: "financement", label: voc("Financement"), masque: "projet:financement" }] },
    { cle: "documents", label: voc("Documents"), icone: <FileText size={15} />, onglets: [{ valeur: "documents", label: voc("Documents"), masque: "projet:documents" }] },
    { cle: "retours", label: voc("Retours des communautés"), icone: <MessagesSquare size={15} />, onglets: [{ valeur: "retours", label: voc("Retours des communautés"), masque: "/plaintes" }] },
    {
      cle: "controle", label: voc("Contrôle"), icone: <ShieldCheck size={15} />,
      onglets: [
        { valeur: "coherence", label: voc("Contrôle de cohérence"), masque: "projet:coherence" },
        { valeur: "historique", label: voc("Historique"), masque: "projet:historique" },
      ],
    },
  ]
    .map((g) => ({ ...g, onglets: g.onglets.filter((o) => !o.masque || !estMasque(o.masque)) }))
    .filter((g) => g.onglets.length > 0);
  const groupeActif = groupesOnglets.find((g) => g.onglets.some((o) => o.valeur === onglet));
  const nomsAttributsProjet = useMemo(() => nomsAttributs(projet?.activites ?? [], projet?.ordre_attributs), [projet]);

  const elementsFiltres = useMemo(() => {
    const racines = projet?.activites ?? [];
    return recherchePlan.trim() ? filtrerArbre(racines, recherchePlan) : racines;
  }, [projet, recherchePlan]);

  if (isLoading || !projet) return <Text>{voc("Chargement…")}</Text>;

  const budgetDejaAlloue = aplatir(projet.activites).reduce(
    (somme, act) => somme + (act.budget_alloue ? Number(act.budget_alloue) : 0),
    0,
  );
  const nomPremierNiveau = nomDuNiveau(niveauxNoms, 0);
  // Relu dans l'arbre à chaque rechargement du projet : la fenêtre suit les saisies.
  const elementAvancement = aplatir(projet.activites).find((a) => a.id === avancementForId) ?? null;

  function handleSupprimer() {
    if (!projet) return;
    confirmerSuppression({
      message: voc`Supprimer le projet "${projet.nom}" ainsi que toute sa planification et ses indicateurs ? Cette action est irréversible.`,
      onConfirm: async () => {
        try {
          await deleteProjet.mutateAsync(projetId);
          notifications.show({ message: voc("Projet supprimé"), color: "green" });
          navigate("/projets");
        } catch {
          notifications.show({ message: voc("Erreur lors de la suppression du projet"), color: "red" });
        }
      },
    });
  }

  function supprimerAvecConfirmation(message: string, supprimer: () => Promise<unknown>, labelSucces: string) {
    confirmerSuppression({
      message,
      onConfirm: async () => {
        try {
          await supprimer();
          notifications.show({ message: labelSucces, color: "green" });
        } catch {
          notifications.show({ message: voc("Erreur lors de la suppression"), color: "red" });
        }
      },
    });
  }

  return (
    <Stack gap="lg">
      <Group justify="space-between">
        <div>
          <Title order={2}>{projet.nom}</Title>
          <Text c="dimmed">
            {projet.code} · {PROJET_STATUT_LABEL[projet.statut] ?? projet.statut}
            {projet.pays.length > 0 &&
              ` · ${projet.pays.map((code) => PAYS_MONDE.find((p) => p.code === code)?.nom ?? code).join(", ")}`}
            {projet.cadre_strategique_nom && projet.cadre_strategique && (
              <>
                {" · "}
                <Text component={Link} to={`/strategie/${projet.cadre_strategique}`} span c="teal.8" fw={500}>
                  {projet.cadre_strategique_nom}
                </Text>
                {projet.element_strategique_libelle && ` › ${projet.element_strategique_libelle}`}
              </>
            )}
          </Text>
          {projet.tout_le_pays && (
            <Badge mt={4} variant="light" color="cyan" leftSection={<MapPin size={12} />}>
              {voc("Tout le pays")}
            </Badge>
          )}
          {!projet.tout_le_pays && dashboard && dashboard.zones_couvertes.length > 0 && (
            <Group gap={6} mt={4}>
              {dashboard.zones_couvertes.map((z) => (
                <Badge key={z.niveau} variant="light" color="cyan" leftSection={<MapPin size={12} />}>
                  {z.count} {traduireDonnee(z.niveau)}{langue() === "fr" && z.count > 1 ? "s" : ""}
                </Badge>
              ))}
            </Group>
          )}
        </div>
        <Group gap="lg">
          {dashboard && dashboard.indicateurs_par_statut.length > 0 && (
            <Group gap="xs">
              {dashboard.indicateurs_par_statut.map((p) => (
                <Group key={p.libelle} gap={4} wrap="nowrap">
                  <AlerteBadge palier={p} />
                  <Text size="sm">{p.count}</Text>
                </Group>
              ))}
            </Group>
          )}
          <Menu shadow="md" width={220}>
            <Menu.Target>
              <Button variant="light" leftSection={<Download size={16} />}>{voc("Exporter")}</Button>
            </Menu.Target>
            <Menu.Dropdown>
              <Menu.Label>{voc("Planification et suivi")}</Menu.Label>
              <Menu.Item onClick={() => telechargerExportSuiviExcel(projetId, projet.code)}>
                {voc("Excel")}
              </Menu.Item>
              <Menu.Item onClick={() => telechargerExportSuiviPdf(projetId, projet.code)}>
                {voc("PDF")}
              </Menu.Item>
              <Menu.Item onClick={() => telechargerExportSuiviWord(projetId, projet.code)}>
                {voc("Word")}
              </Menu.Item>
              {(periodesSuivi?.length ?? 0) > 0 && (
                <>
                  <Menu.Label>{voc("Suivi par période")}</Menu.Label>
                  {periodesSuivi!.map((periode) => (
                    <Menu.Sub key={periode.id}>
                      <Menu.Sub.Target>
                        <Menu.Sub.Item>{periode.libelle || voc("Période sans nom")}</Menu.Sub.Item>
                      </Menu.Sub.Target>
                      <Menu.Sub.Dropdown>
                        <Menu.Item onClick={() => telechargerExportSuiviPeriode(periode, projet.code, "excel")}>{voc("Excel")}</Menu.Item>
                        <Menu.Item onClick={() => telechargerExportSuiviPeriode(periode, projet.code, "pdf")}>{voc("PDF")}</Menu.Item>
                        <Menu.Item onClick={() => telechargerExportSuiviPeriode(periode, projet.code, "word")}>{voc("Word")}</Menu.Item>
                      </Menu.Sub.Dropdown>
                    </Menu.Sub>
                  ))}
                </>
              )}
              {!estMasque("projet:financement") && (
                <>
                  <Menu.Label>{voc("Finances")}</Menu.Label>
                  <Menu.Item onClick={() => setRapportFinancierOuvert(true)}>{voc("Rapport financier…")}</Menu.Item>
                </>
              )}
              <Menu.Label>{voc("Collecte")}</Menu.Label>
              <Menu.Item onClick={() => telechargerExportProjet(projetId, "xlsform")}>
                {voc("XLSForm")}
              </Menu.Item>
            </Menu.Dropdown>
          </Menu>
          {rapportFinancierOuvert && (
            <RapportFinancierModal projetId={projetId} codeProjet={projet.code} onClose={() => setRapportFinancierOuvert(false)} />
          )}
          {!lectureSeule && <BoutonModeEdition actif={editionActive} onToggle={() => setEditionActive((v) => !v)} />}
          {editionActive && (
          <Group gap="lg">
            <Tooltip label={voc("Modifier le projet")}>
              <ActionIcon variant="subtle" size="lg" onClick={() => setModalEditionOuvert(true)}>
                <Pencil size={18} />
              </ActionIcon>
            </Tooltip>
            <Tooltip label={voc("Supprimer le projet")}>
              <ActionIcon variant="subtle" color="red" size="lg" loading={deleteProjet.isPending} onClick={handleSupprimer}>
                <Trash2 size={18} />
              </ActionIcon>
            </Tooltip>
          </Group>
          )}
        </Group>
      </Group>

      {cloture ? <BandeauProjetCloture projetId={projetId} /> : <BandeauSaisieFermee projet={projet} />}

      {/* Onglets regroupés par thème sur une ligne ; un thème à plusieurs écrans a ses sous-onglets. */}
      <Tabs value={groupeActif?.cle ?? null} onChange={(cle) => setOnglet(groupesOnglets.find((g) => g.cle === cle)!.onglets[0].valeur)}>
        <Tabs.List>
          {groupesOnglets.map((g) => (
            <Tabs.Tab key={g.cle} value={g.cle} leftSection={g.icone}>
              {g.onglets.length === 1 ? g.onglets[0].label : g.label}
            </Tabs.Tab>
          ))}
        </Tabs.List>
      </Tabs>
      {groupeActif && groupeActif.onglets.length > 1 && (
        <SegmentedControl
          size="sm"
          mt="sm"
          style={{ alignSelf: "flex-start" }}
          value={onglet}
          onChange={setOnglet}
          data={groupeActif.onglets.map((o) => ({ value: o.valeur, label: o.label }))}
        />
      )}

      <Tabs value={onglet} onChange={(v) => v && setOnglet(v)}>

        <Tabs.Panel value="hierarchie" pt="md">
          <Card withBorder padding="md">
            <Text size="sm" c="dimmed">
              {voc("Les niveaux sont libres : leur nom et leur nombre sont propres à ce projet. Clique sur l'étiquette d'un élément pour nommer ou renommer son niveau ; le bouton + ajoute un élément au niveau en dessous.")}</Text>
            {!lectureSeule && (
              <AjoutInline
                placeholder={0 in niveauxNoms ? voc`Nouveau « ${nomPremierNiveau} »…` : voc("Libellé du premier élément…")}
                demanderNomNiveau={!(0 in niveauxNoms)}
                onAdd={async (libelle, nomNiveau) => {
                  if (nomNiveau) await nommerNiveau(0, nomNiveau);
                  createActivite.mutate({ projet: projetId, libelle });
                }}
              />
            )}
            {/* Planification vide : elle peut aussi être chargée d'un coup depuis le canevas Excel. */}
            {projet.activites.length === 0 && !lectureSeule && (
              <Group mt="sm"><ImportPlanification projetId={projetId} code={projet.code} /></Group>
            )}
            {projet.activites.length > 0 && (
              <Group mt="sm" justify="space-between">
                <TextInput
                  placeholder={voc("Rechercher dans la planification…")}
                  leftSection={<Search size={15} />}
                  value={recherchePlan}
                  onChange={(e) => setRecherchePlan(e.currentTarget.value)}
                  w={400}
                  maw="100%"
                />
                <Group gap="xs">
                  {affichagePlan === "arbre" && !recherchePlan.trim() && (
                    <>
                      <Button
                        size="compact-xs"
                        variant="subtle"
                        leftSection={<ChevronsDownUp size={14} />}
                        onClick={() =>
                          setReplies(
                            new Set(
                              aplatir(projet.activites)
                                .filter((e) => e.enfants.length > 0 || e.sous_activites.length > 0)
                                .map((e) => e.id),
                            ),
                          )
                        }
                      >
                        {voc("Tout replier")}
                      </Button>
                      <Button
                        size="compact-xs"
                        variant="subtle"
                        leftSection={<ChevronsUpDown size={14} />}
                        onClick={() => setReplies(new Set())}
                      >
                        {voc("Tout déplier")}
                      </Button>
                    </>
                  )}
                  {!lectureSeule && <ImportPlanification projetId={projetId} code={projet.code} />}
                  {/* En mode Tableau, le menu est au-dessus du tableau (avec l'année choisie). */}
                  {affichagePlan === "arbre" && (
                    <MenuExportPlanification projetId={projetId} code={projet.code} programmation={programmationPlan} />
                  )}
                  <SegmentedControl
                    size="xs"
                    value={affichagePlan}
                    onChange={(v) => setAffichagePlan(v as ModeAffichage)}
                    data={[
                      { value: "arbre", label: voc("Arbre") },
                      { value: "tableau", label: voc("Tableau") },
                    ]}
                  />
                </Group>
              </Group>
            )}
            {recherchePlan.trim() && elementsFiltres.length === 0 && (
              <Text c="dimmed" size="sm" mt="sm">{voc("Aucun résultat ne correspond à la recherche.")}</Text>
            )}
            {affichagePlan === "tableau" && elementsFiltres.length > 0 && (
              <Box mt="sm">
                <PlanificationTableau
                  outils={(programmation, annee) => (
                    <MenuExportPlanification projetId={projetId} code={projet.code} programmation={programmation} annee={annee} />
                  )}
                  elements={elementsFiltres}
                  nomNiveau={(p) => nomDuNiveau(niveauxNoms, p)}
                  nomsAttributs={nomsAttributsProjet}
                  editionActive={editionActive}
                  onAvancement={setAvancementFor}
                  onEditer={setModalActiviteEdition}
                  onAjouterEnfant={lectureSeule ? undefined : (parent, profondeur) => setModalActiviteEnfantFor({ parent, profondeur })}
                  onAjouterSousActivite={lectureSeule ? undefined : setModalSousActiviteFor}
                  onSupprimer={supprimerElement}
                  onEditerSousActivite={setSousActiviteEdition}
                  onSupprimerSousActivite={supprimerSousActivite}
                />
              </Box>
            )}
            <Stack mt="sm" gap="sm" display={affichagePlan === "tableau" ? "none" : undefined}>
              {elementsFiltres.map((element) => (
                <CarteActivite
                  key={element.id}
                  act={element}
                  profondeur={0}
                  editionActive={editionActive}
                  niveauxNoms={niveauxNoms}
                  onRenommerNiveau={nommerNiveau}
                  onDocuments={setDocumentsActiviteId}
                  onBeneficiaires={setBeneficiairesActiviteId}
                  onEditer={setModalActiviteEdition}
                  onAjouterEnfant={lectureSeule ? undefined : (parent, profondeur) => setModalActiviteEnfantFor({ parent, profondeur })}
                  onAjouterSousActivite={lectureSeule ? undefined : setModalSousActiviteFor}
                  onAvancement={setAvancementFor}
                  onSupprimer={supprimerElement}
                  onDupliquer={lectureSeule || !peutModifier ? undefined : (a) =>
                    dupliquerActivite.mutate(a.id, {
                      onSuccess: (copie) => notifications.show({ message: voc`« ${copie.libelle} » créé`, color: "green" }),
                      onError: (error) =>
                        notifications.show({ message: messageErreurApi(error, voc("Erreur lors de la duplication")), color: "red" }),
                    })
                  }
                  onDocumentsSousActivite={setDocumentsSousActiviteId}
                  onBeneficiairesSousActivite={setBeneficiairesSousActiviteId}
                  onSupprimerSousActivite={supprimerSousActivite}
                  onEditerSousActivite={setSousActiviteEdition}
                  // Pendant une recherche, tout ce qui correspond reste visible.
                  replies={recherchePlan.trim() ? new Set() : replies}
                  onBasculer={basculer}
                />
              ))}
            </Stack>
          </Card>
        </Tabs.Panel>

        {!estMasque("/plaintes") && (
          <Tabs.Panel value="retours" pt="md">
            {onglet === "retours" && <RetoursProjet projetId={projet.id} />}
          </Tabs.Panel>
        )}

        {!estMasque("projet:periode") && (
          <Tabs.Panel value="periode" pt="md">
            <PlanificationPeriodeTab projet={projet} niveauxNoms={niveauxNoms} editionActive={editionActive} />
          </Tabs.Panel>
        )}

        {!estMasque("projet:niveaux") && (
          <Tabs.Panel value="niveaux" pt="md">
            <NiveauxActiviteTab projetId={projetId} />
          </Tabs.Panel>
        )}

        {!estMasque("projet:partenaires") && (
          <Tabs.Panel value="partenaires" pt="md">
            <PartenairesProjetTab projet={projet} editable={peutModifier && !lectureSeule} />
          </Tabs.Panel>
        )}

        {!estMasque("projet:equipe") && (
          <Tabs.Panel value="equipe" pt="md">
            <EquipeTab projetId={projetId} />
          </Tabs.Panel>
        )}

        {!estMasque("projet:indicateurs") && (
          <Tabs.Panel value="indicateurs" pt="md">
            {dashboard && dashboard.indicateurs.length > 0 && (
              <Card withBorder padding="md" radius="md" mb="md">
                <Text size="xs" c="dimmed" fw={600} tt="uppercase" mb="sm" style={{ letterSpacing: 0.4 }}>
                  {voc("Taux de réalisation par indicateur")}</Text>
                <TauxParIndicateurChart indicateurs={dashboard.indicateurs} />
              </Card>
        )}
          <Table striped>
            <Table.Thead>
              <Table.Tr>
                <Table.Th>{voc("Indicateur")}</Table.Th>
                <Table.Th>{voc("Taux de réalisation")}</Table.Th>
              </Table.Tr>
            </Table.Thead>
            <Table.Tbody>
              {dashboard?.indicateurs.map((i) => (
                <Table.Tr key={i.id}>
                  <Table.Td>{i.libelle}</Table.Td>
                  <Table.Td>
                    <AlerteBadge palier={i.palier_actuel} taux={i.taux_realisation} />
                  </Table.Td>
                </Table.Tr>
              ))}
            </Table.Tbody>
          </Table>
        </Tabs.Panel>
        )}

        {!estMasque("projet:financement") && (
          <Tabs.Panel value="financement" pt="md">
            <FinancementsTab projetId={projetId} lectureSeule={lectureSeule} />
          </Tabs.Panel>
        )}

        {!estMasque("projet:documents") && (
          <Tabs.Panel value="documents" pt="md">
            <DocumentsTab projetId={projetId} />
          </Tabs.Panel>
        )}

        {!estMasque("projet:cadre-logique") && (
          <Tabs.Panel value="cadre-logique" pt="md">
            <CadreLogiqueTab projetId={projetId} codeProjet={projet.code} modifiable={!lectureSeule && peutModifier} />
          </Tabs.Panel>
        )}

        {!estMasque("projet:risques") && (
          <Tabs.Panel value="risques" pt="md">
            <RisquesTab projetId={projetId} codeProjet={projet.code} modifiable={!lectureSeule && peutEcrire("projet:risques")} />
          </Tabs.Panel>
        )}

        {!estMasque("projet:coherence") && (
          <Tabs.Panel value="coherence" pt="md">
            <CoherenceTab projetId={projetId} />
          </Tabs.Panel>
        )}

        {!estMasque("projet:historique") && (
          <Tabs.Panel value="historique" pt="md">
            <HistoriqueModification appLabel="projects" modelName="projet" objectId={projetId} />
          </Tabs.Panel>
        )}
      </Tabs>

      <Modal opened={modalActiviteEdition !== null} onClose={() => setModalActiviteEdition(null)} title={voc("Modifier l'élément")} size="lg">
        {modalActiviteEdition !== null && (
          <ActiviteForm
            cadreStrategiqueId={projet.cadre_strategique}
            projetId={projetId}
            budgetProjetTotal={Number(projet.budget_total)}
            budgetDejaAlloue={budgetDejaAlloue - (modalActiviteEdition.budget_alloue ? Number(modalActiviteEdition.budget_alloue) : 0)}
            activite={modalActiviteEdition}
            nomsAttributs={nomsAttributsProjet}
            onDone={() => setModalActiviteEdition(null)}
          />
        )}
      </Modal>

      <Modal
        opened={modalActiviteEnfantFor !== null}
        onClose={() => setModalActiviteEnfantFor(null)}
        title={
          modalActiviteEnfantFor
            ? modalActiviteEnfantFor.profondeur in niveauxNoms
              ? voc`Nouveau « ${niveauxNoms[modalActiviteEnfantFor.profondeur]} » sous « ${modalActiviteEnfantFor.parent.libelle} »`
              : voc`Nouvel élément sous « ${modalActiviteEnfantFor.parent.libelle} »`
            : ""
        }
        size="lg"
      >
        {modalActiviteEnfantFor !== null && (
          <ActiviteForm
            activiteParentId={modalActiviteEnfantFor.parent.id}
            profondeur={modalActiviteEnfantFor.profondeur}
            nomNiveau={niveauxNoms[modalActiviteEnfantFor.profondeur] ?? null}
            cadreStrategiqueId={projet.cadre_strategique}
            projetId={projetId}
            budgetProjetTotal={Number(projet.budget_total)}
            budgetDejaAlloue={budgetDejaAlloue}
            nomsAttributs={nomsAttributsProjet}
            onDone={() => setModalActiviteEnfantFor(null)}
          />
        )}
      </Modal>

      <Modal opened={modalSousActiviteFor !== null} onClose={() => setModalSousActiviteFor(null)} title={voc("Nouvelle sous-activité")} size="lg">
        {modalSousActiviteFor !== null && (
          <SousActiviteForm
            activiteId={modalSousActiviteFor}
            cadreStrategiqueId={projet.cadre_strategique}
            nomsAttributs={nomsAttributsProjet}
            onDone={() => setModalSousActiviteFor(null)}
          />
        )}
      </Modal>

      <Modal
        opened={sousActiviteEdition !== null}
        onClose={() => setSousActiviteEdition(null)}
        title={voc`Modifier la sous-activité « ${sousActiviteEdition?.libelle ?? ""} »`}
        size="lg"
      >
        {sousActiviteEdition !== null && (
          <SousActiviteForm
            activiteId={sousActiviteEdition.activite}
            cadreStrategiqueId={projet.cadre_strategique}
            sousActivite={sousActiviteEdition}
            nomsAttributs={nomsAttributsProjet}
            onDone={() => setSousActiviteEdition(null)}
          />
        )}
      </Modal>

      <Modal
        opened={avancementForId !== null}
        onClose={() => setAvancementForId(null)}
        title={`${voc("Avancement")} — ${elementAvancement?.libelle ?? ""}`}
        size="lg"
      >
        {elementAvancement && <AvancementModal element={elementAvancement} modifiable={peutModifier && !realisationsFermees} />}
      </Modal>

      <Modal opened={modalEditionOuvert} onClose={() => setModalEditionOuvert(false)} title={voc("Modifier le projet")} size="lg">
        <ProjetForm projet={projet} onDone={() => setModalEditionOuvert(false)} />
      </Modal>

      <Modal
        opened={documentsActiviteId !== null}
        onClose={() => setDocumentsActiviteId(null)}
        title={voc("Documents liés à l'élément")}
        size="lg"
      >
        {documentsActiviteId !== null && <DocumentsTab activiteId={documentsActiviteId} />}
      </Modal>

      <Modal
        opened={documentsSousActiviteId !== null}
        onClose={() => setDocumentsSousActiviteId(null)}
        title={voc("Documents liés à la sous-activité")}
        size="lg"
      >
        {documentsSousActiviteId !== null && <DocumentsTab sousActiviteId={documentsSousActiviteId} />}
      </Modal>

      <Modal
        opened={beneficiairesActiviteId !== null}
        onClose={() => setBeneficiairesActiviteId(null)}
        title={voc("Bénéficiaires liés à l'élément")}
        size="lg"
      >
        {beneficiairesActiviteId !== null && (
          <BeneficiairesTab projetId={projetId} activiteId={beneficiairesActiviteId} />
        )}
      </Modal>

      <Modal
        opened={beneficiairesSousActiviteId !== null}
        onClose={() => setBeneficiairesSousActiviteId(null)}
        title={voc("Bénéficiaires liés à la sous-activité")}
        size="lg"
      >
        {beneficiairesSousActiviteId !== null && (
          <BeneficiairesTab projetId={projetId} sousActiviteId={beneficiairesSousActiviteId} />
        )}
      </Modal>

    </Stack>
  );
}
