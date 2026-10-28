import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { BellRing, Calculator, CalendarClock, Check, Plus, RotateCcw, Sliders, Trash2 } from "lucide-react";
import {
  ActionIcon,
  Badge,
  Button,
  Card,
  Divider,
  Group,
  NumberInput,
  Select,
  Stack,
  Switch,
  Text,
  TextInput,
  UnstyledButton,
} from "@mantine/core";
import { notifications } from "@mantine/notifications";
import {
  useEnregistrerPaliersAlerte,
  useIndicateursPourProjet,
  usePaliersAlerte,
  useParametresAlerte,
  useUpdateParametresAlerte,
} from "../../api/indicators";
import { useEcheances } from "../../api/dashboard";
import { useActivitesPourProjet, useParametresCalcul, useProjets, useUpdateParametresCalcul } from "../../api/projects";
import {
  AIDES_AGREGATION,
  AIDES_METHODE,
  optionsAgregation,
  optionsMethode,
} from "../../utils/methodesCalcul";
import type { MethodeAgregation, MethodeCalcul } from "../../types";
import type { PorteeAlerte } from "../../types";
import { TitreRubrique } from "../../components/common/TitreRubrique";
import { RapportageCard } from "./RapportageCard";
import { voc } from "../../utils/vocabulaire";

// Palette restreinte à choisir au clic plutôt qu'un sélecteur de couleur
// libre (code hexa, roue teinte/saturation...) jugé trop compliqué pour ce
// réglage simple.
const PALETTE_COULEURS = [
  "#d03b3b",
  "#e8590c",
  "#f08c00",
  "#fab219",
  "#82c91e",
  "#0ca30c",
  "#12b886",
  "#15aabf",
  "#1c7ed6",
  "#4263eb",
  "#7048e8",
  "#9c36b5",
  "#e64980",
  "#495057",
];

function SelecteurCouleur({ value, onChange }: { value: string; onChange: (v: string) => void }) {
  return (
    <Group gap={6}>
      {PALETTE_COULEURS.map((couleur) => {
        const selectionnee = couleur.toLowerCase() === value.toLowerCase();
        return (
          <UnstyledButton
            key={couleur}
            onClick={() => onChange(couleur)}
            aria-label={couleur}
            style={{
              width: 26,
              height: 26,
              borderRadius: "50%",
              background: couleur,
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              outline: selectionnee ? "2px solid var(--mantine-color-dark-6)" : "2px solid transparent",
              outlineOffset: 2,
            }}
          >
            {selectionnee && <Check size={14} color="white" strokeWidth={3} />}
          </UnstyledButton>
        );
      })}
    </Group>
  );
}

function ApercuBadge({ libelle, couleur }: { libelle: string; couleur: string }) {
  return (
    <Badge
      color={couleur}
      variant="light"
      radius="sm"
      size="md"
      styles={{ root: { textTransform: "none", maxWidth: "none" }, label: { overflow: "visible", whiteSpace: "nowrap" } }}
    >
      {libelle || "…"}
    </Badge>
  );
}

interface LignePalier {
  borne_min: number | string;
  libelle: string;
  couleur: string;
}

// L'intervalle de chaque palier est déduit du seuil du palier suivant (trié) —
// pas besoin de saisir une borne haute séparément, mais on l'affiche pour que
// ce soit lisible comme un intervalle plutôt que comme un simple seuil isolé.
function intervalleTexte(lignesTriees: LignePalier[], position: number): string {
  const courant = Number(lignesTriees[position].borne_min);
  const suivant = lignesTriees[position + 1];
  if (!suivant) return `${courant}% et plus`;
  const max = Number(suivant.borne_min) - 1;
  return max > courant ? `${courant}% – ${max}%` : `${courant}%`;
}

const PALETTE_GLOBALE = "GLOBALE";
const NIVEAU_PROJET = "PROJET";

/**
 * Méthode de calcul et d'agrégation des taux d'exécution par défaut de l'organisation —
 * héritées par les projets et les éléments qui ne fixent pas les leurs.
 */
function CalculTauxCard() {
  const { data: parametres } = useParametresCalcul();
  const maj = useUpdateParametresCalcul();
  const enregistrer = (payload: Parameters<typeof maj.mutate>[0]) =>
    maj.mutate(payload, {
      onSuccess: () => notifications.show({ message: "Réglage enregistré", color: "green" }),
      onError: () => notifications.show({ message: "Erreur lors de l'enregistrement", color: "red" }),
    });
  if (!parametres) return null;
  return (
    <Card withBorder padding="lg" radius="md">
      <Group gap={8} mb={4}>
        <Calculator size={18} />
        <Text fw={600}>{voc("Calcul des taux d'exécution")}</Text>
      </Group>
      <Text size="sm" c="dimmed" mb="sm">
        {voc("Réglage par défaut de l'organisation : chaque projet peut fixer le sien (fiche projet, onglet Stratégie), et chaque élément de la planification aussi (son formulaire).")}
      </Text>
      <Group grow align="flex-start">
        <Select
          label="Méthode de calcul par défaut"
          description={AIDES_METHODE[parametres.methode_calcul]}
          data={optionsMethode()}
          value={parametres.methode_calcul}
          onChange={(v) => v && enregistrer({ methode_calcul: v as MethodeCalcul })}
          allowDeselect={false}
        />
        <Select
          label="Agrégation par défaut"
          description={AIDES_AGREGATION[parametres.methode_agregation]}
          data={optionsAgregation()}
          value={parametres.methode_agregation}
          onChange={(v) => v && enregistrer({ methode_agregation: v as MethodeAgregation })}
          allowDeselect={false}
        />
      </Group>
      <Switch
        mt="md"
        label="Plafonner à 100 % dans les agrégations"
        description="Un dépassement de cible (ex : 130 %) reste affiché, mais compte pour 100 % dans les moyennes."
        checked={parametres.plafonner_agregation}
        onChange={(e) => enregistrer({ plafonner_agregation: e.currentTarget.checked })}
      />
    </Card>
  );
}

export function ParametresAlertePage() {
  return (
    <Stack gap="md">
      <div>
        <TitreRubrique route="/parametres-alerte" defaut="Paramètres d'alerte" />
        <Text c="dimmed" size="sm">
          {voc("La grille d'interprétation des taux de réalisation (paliers, libellés, couleurs) se configure ici, projet par projet — un projet sans grille propre utilise la grille globale par défaut.")}</Text>
      </div>

      <CalculTauxCard />
      <RapportageCard />
      <GrilleInterpretationCard />
      <RappelsEcheanceCard />
    </Stack>
  );
}

function GrilleInterpretationCard() {
  const { data: projets } = useProjets();
  const [projetSelectionne, setProjetSelectionne] = useState<string>(PALETTE_GLOBALE);
  const projetId = projetSelectionne === PALETTE_GLOBALE ? null : Number(projetSelectionne);

  // Deuxième niveau, seulement pertinent quand un projet est choisi : la grille du
  // projet entier, ou celle d'un indicateur/une activité précis de ce projet — potentiellement
  // des centaines d'indicateurs/activités, chacun avec sa propre grille, indépendamment des autres.
  const [niveauSelectionne, setNiveauSelectionne] = useState<string>(NIVEAU_PROJET);
  const { data: indicateursDuProjet } = useIndicateursPourProjet(projetId);
  const { data: activitesDuProjet } = useActivitesPourProjet(projetId);

  const indicateurId = niveauSelectionne.startsWith("IND:") ? Number(niveauSelectionne.slice(4)) : null;
  const activiteId = niveauSelectionne.startsWith("ACT:") ? Number(niveauSelectionne.slice(4)) : null;
  const portee: PorteeAlerte = { projetId, indicateurId, activiteId };
  const cle = `${projetSelectionne}|${niveauSelectionne}`;

  const { data: resolu, isLoading } = usePaliersAlerte(portee);
  const enregistrer = useEnregistrerPaliersAlerte();

  const [lignes, setLignes] = useState<LignePalier[]>([]);
  const [cleChargee, setCleChargee] = useState<string | null>(null);

  useEffect(() => {
    if (!resolu || cleChargee === cle) return;
    setLignes(resolu.paliers.map((p) => ({ borne_min: p.borne_min, libelle: p.libelle, couleur: p.couleur })));
    setCleChargee(cle);
  }, [resolu, cle, cleChargee]);

  function changerProjet(v: string | null) {
    setProjetSelectionne(v ?? PALETTE_GLOBALE);
    setNiveauSelectionne(NIVEAU_PROJET);
  }

  function ajouterLigne() {
    setLignes((prev) => [...prev, { borne_min: 0, libelle: "", couleur: "#495057" }]);
  }

  function supprimerLigne(index: number) {
    setLignes((prev) => prev.filter((_, i) => i !== index));
  }

  function modifierLigne(index: number, champ: keyof LignePalier, valeur: string | number) {
    setLignes((prev) => prev.map((l, i) => (i === index ? { ...l, [champ]: valeur } : l)));
  }

  function validerLignes(): string | null {
    if (projetId === null && lignes.length === 0) {
      return "La grille globale doit contenir au moins un palier.";
    }
    if (lignes.some((l) => !String(l.libelle).trim())) {
      return "Chaque palier doit avoir un libellé.";
    }
    const bornes = lignes.map((l) => Number(l.borne_min));
    if (bornes.some((b) => Number.isNaN(b) || b < 0 || b > 100)) {
      return "Chaque seuil doit être un pourcentage entre 0 et 100.";
    }
    if (new Set(bornes).size !== bornes.length) {
      return "Deux paliers ne peuvent pas avoir le même seuil.";
    }
    return null;
  }

  async function handleEnregistrer() {
    const erreur = validerLignes();
    if (erreur) {
      notifications.show({ message: erreur, color: "orange" });
      return;
    }
    try {
      await enregistrer.mutateAsync({
        portee,
        paliers: lignes
          .map((l) => ({ borne_min: Number(l.borne_min), libelle: l.libelle.trim(), couleur: l.couleur }))
          .sort((a, b) => a.borne_min - b.borne_min),
      });
      notifications.show({ message: voc("Grille d'alerte enregistrée"), color: "green" });
    } catch {
      notifications.show({ message: "Erreur lors de l'enregistrement", color: "red" });
    }
  }

  async function handleRevenirHeritage() {
    try {
      await enregistrer.mutateAsync({ portee, paliers: [] });
      notifications.show({ message: "Grille héritée de nouveau en vigueur", color: "green" });
    } catch {
      notifications.show({ message: "Erreur lors de la réinitialisation", color: "red" });
    }
  }

  const lignesTriees = [...lignes].sort((a, b) => Number(a.borne_min) - Number(b.borne_min));

  const libelleNiveauCourant =
    indicateurId !== null
      ? voc("Cet indicateur")
      : activiteId !== null
        ? "Cette activité"
        : projetId !== null
          ? voc("Ce projet")
          : null;

  return (
    <Card withBorder padding="lg" radius="md">
      <Group gap="xs" mb="md">
        <Sliders size={18} />
        <Text fw={600}>Grille d'interprétation</Text>
      </Group>

      <Group align="flex-start" grow mb="md">
        <Select
          label={voc("Projet")}
          description={voc("Choisis un projet pour lui définir sa propre grille, ou reste sur la grille globale par défaut.")}
          data={[
            { value: PALETTE_GLOBALE, label: "Grille globale (par défaut)" },
            ...(projets ?? []).map((p) => ({ value: String(p.id), label: `${p.code} — ${p.nom}` })),
          ]}
          value={projetSelectionne}
          onChange={changerProjet}
          searchable
          maw={420}
        />
        {projetId !== null && (
          <Select
            label="Niveau"
            description={voc("La grille du projet entier, ou personnalise-la pour un indicateur ou une activité précis.")}
            data={[
              { value: NIVEAU_PROJET, label: voc("Grille du projet (par défaut)") },
              ...((indicateursDuProjet?.length ?? 0) > 0
                ? [
                    {
                      group: voc("Indicateurs"),
                      items: indicateursDuProjet!.map((i) => ({ value: `IND:${i.id}`, label: i.libelle })),
                    },
                  ]
                : []),
              ...((activitesDuProjet?.length ?? 0) > 0
                ? [
                    {
                      group: "Activités",
                      items: activitesDuProjet!.map((a) => ({ value: `ACT:${a.id}`, label: a.libelle })),
                    },
                  ]
                : []),
            ]}
            value={niveauSelectionne}
            onChange={(v) => setNiveauSelectionne(v ?? NIVEAU_PROJET)}
            searchable
            maw={420}
          />
        )}
      </Group>

      {isLoading ? (
        <Text c="dimmed">Chargement…</Text>
      ) : (
        <>
          {libelleNiveauCourant && !resolu?.personnalise && (
            <Text size="sm" c="dimmed" mb="sm">
              {libelleNiveauCourant} utilise actuellement la grille héritée — modifie les paliers ci-dessous et
              enregistre pour lui créer une grille propre.
            </Text>
          )}
          {libelleNiveauCourant && resolu?.personnalise && (
            <Group justify="flex-end" mb="sm">
              <Button
                variant="subtle"
                size="xs"
                color="gray"
                leftSection={<RotateCcw size={14} />}
                onClick={handleRevenirHeritage}
                loading={enregistrer.isPending}
              >
                Revenir à la grille héritée
              </Button>
            </Group>
          )}

          <Stack gap="sm">
            {lignesTriees.map((ligne, position) => {
              const index = lignes.indexOf(ligne);
              return (
                <Group key={index} align="flex-end" wrap="nowrap">
                  <NumberInput
                    label="Seuil bas (%)"
                    description={intervalleTexte(lignesTriees, position)}
                    value={ligne.borne_min}
                    onChange={(v) => modifierLigne(index, "borne_min", v)}
                    min={0}
                    max={100}
                    w={110}
                  />
                  <TextInput
                    label="Libellé"
                    value={ligne.libelle}
                    onChange={(e) => modifierLigne(index, "libelle", e.currentTarget.value)}
                    style={{ flex: 1 }}
                  />
                  <Stack gap={4}>
                    <Text size="xs" c="dimmed">Couleur</Text>
                    <SelecteurCouleur value={ligne.couleur} onChange={(v) => modifierLigne(index, "couleur", v)} />
                  </Stack>
                  <ApercuBadge libelle={ligne.libelle} couleur={ligne.couleur} />
                  <ActionIcon variant="subtle" color="red" onClick={() => supprimerLigne(index)}>
                    <Trash2 size={16} />
                  </ActionIcon>
                </Group>
              );
            })}
          </Stack>

          <Button variant="light" size="xs" leftSection={<Plus size={14} />} onClick={ajouterLigne} mt="md">
            Ajouter un palier
          </Button>

          <Group justify="flex-end" mt="lg">
            <Button onClick={handleEnregistrer} loading={enregistrer.isPending}>Enregistrer</Button>
          </Group>
        </>
      )}
    </Card>
  );
}

function RappelsAdateFixeListe() {
  const { data: echeances, isLoading } = useEcheances();
  const rappels = (echeances ?? []).filter((e) => e.est_rappel);

  return (
    <>
      <Divider my="lg" />
      <Group gap="xs" mb="xs">
        <CalendarClock size={16} />
        <Text fw={600} size="sm">Rappels à date calendaire programmés</Text>
      </Group>
      <Text size="sm" c="dimmed" mb="sm">
        {voc("En plus du seuil en jours ci-dessus, chaque activité ou projet peut avoir sa propre date de rappel fixe (indépendante du nombre de jours) — à définir directement dans sa fiche, champ « Date de rappel ». Voici celles actuellement programmées :")}</Text>
      {isLoading ? (
        <Text size="sm" c="dimmed">Chargement…</Text>
      ) : rappels.length === 0 ? (
        <Text size="sm" c="dimmed">Aucune date de rappel fixe n'est programmée pour le moment.</Text>
      ) : (
        <Stack gap={4}>
          {rappels.map((r) => (
            <Group key={`${r.type}-${r.id}`} justify="space-between" wrap="nowrap">
              <Text component={Link} to={r.lien} size="sm" c="teal.8">
                {r.libelle} <Text span c="dimmed">({r.projet_nom})</Text>
              </Text>
              <Badge variant="light" color="blue" size="sm">{r.date_fin}</Badge>
            </Group>
          ))}
        </Stack>
      )}
    </>
  );
}

function RappelsEcheanceCard() {
  const { data: parametres, isLoading } = useParametresAlerte();
  const update = useUpdateParametresAlerte();
  const [seuilEcheanceJours, setSeuilEcheanceJours] = useState<number | string>(7);
  const [initialise, setInitialise] = useState(false);

  useEffect(() => {
    if (initialise || !parametres) return;
    setSeuilEcheanceJours(parametres.seuil_echeance_jours);
    setInitialise(true);
  }, [initialise, parametres]);

  async function handleEnregistrer() {
    try {
      await update.mutateAsync({ seuil_echeance_jours: seuilEcheanceJours === "" ? 7 : Number(seuilEcheanceJours) });
      notifications.show({ message: voc("Paramètres d'alerte enregistrés"), color: "green" });
    } catch {
      notifications.show({ message: "Erreur lors de l'enregistrement", color: "red" });
    }
  }

  return (
    <Card withBorder padding="lg" radius="md">
      <Group gap="xs" mb="md">
        <BellRing size={18} />
        <Text fw={600}>Rappels d'échéance</Text>
      </Group>

      {isLoading ? (
        <Text c="dimmed">Chargement…</Text>
      ) : (
        <>
          <NumberInput
            label="Alerter avant l'échéance (jours)"
            description={voc("Seuil global par défaut : une activité, une sous-activité ou un projet non terminé déclenche une notification (et un email) dès que son échéance tombe dans cette fenêtre — et reste alerté si l'échéance est déjà dépassée.")}
            value={seuilEcheanceJours}
            onChange={setSeuilEcheanceJours}
            min={1}
            max={90}
            w={280}
          />
          <Group justify="flex-end" mt="lg">
            <Button onClick={handleEnregistrer} loading={update.isPending}>Enregistrer</Button>
          </Group>
        </>
      )}

      <RappelsAdateFixeListe />
    </Card>
  );
}
