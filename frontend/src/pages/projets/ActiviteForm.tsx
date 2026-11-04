import { useMemo, useState } from "react";
import { Alert, Autocomplete, Button, Divider, Group, MultiSelect, NumberInput, Select, Stack, Text, Textarea, TextInput } from "@mantine/core";
import { DateInput } from "@mantine/dates";
import { notifications } from "@mantine/notifications";
import { useCreateActivite, useCreateEquipe, useEquipes, useNommerNiveau, useUpdateActivite } from "../../api/projects";
import { useCreateIntervenant, useIntervenants } from "../../api/intervenants";
import { useElementsStrategiques, useTypesNiveaux } from "../../api/strategy";
import { useStructures } from "../../api/organisation";
import { optionsStructures } from "../../utils/organisation";
import { AttributsLibres } from "../../components/common/AttributsLibres";
import type { Attributs } from "../../utils/attributs";
import { IntervenantsMultiples } from "../../components/common/IntervenantsMultiples";
import { DocumentsTab } from "../../components/documents/DocumentsTab";
import { messageErreurApi } from "../../utils/erreurs";
import type { Activite, Intervenant } from "../../types";
import { AIDES_AGREGATION, AIDES_METHODE, optionsAgregation, optionsMethode } from "../../utils/methodesCalcul";
import { voc } from "../../utils/vocabulaire";
import { libelleDuree } from "../../utils/periode";

import { locale } from "../../utils/i18n";
/**
 * Création / modification d'un élément de la planification, à n'importe quel
 * niveau (objectif, résultat, pilier, activité... selon les niveaux du projet).
 */
export function ActiviteForm({
  activiteParentId,
  profondeur,
  nomNiveau,
  cadreStrategiqueId,
  projetId,
  budgetProjetTotal,
  budgetDejaAlloue,
  activite,
  nomsAttributs = [],
  onDone,
}: {
  /** Si fourni, l'élément créé est placé sous celui-ci (sinon : premier niveau du projet). */
  activiteParentId?: number;
  /** Niveau de l'élément créé (0 = premier niveau) — sert à nommer ce niveau s'il ne l'est pas encore. */
  profondeur?: number;
  /** Nom actuel de ce niveau, s'il en a un. */
  nomNiveau?: string | null;
  cadreStrategiqueId: number | null;
  projetId: number;
  budgetProjetTotal: number;
  budgetDejaAlloue: number;
  activite?: Activite;
  /** Noms d'attributs déjà utilisés dans le projet, proposés à la saisie. */
  nomsAttributs?: string[];
  onDone: () => void;
}) {
  const enEdition = !!activite;
  const { data: axes } = useElementsStrategiques(cadreStrategiqueId ? { cadre_strategique: cadreStrategiqueId } : undefined);
  const { data: niveaux } = useTypesNiveaux(cadreStrategiqueId);
  const { data: equipes } = useEquipes();
  const { data: intervenants } = useIntervenants();
  const createActivite = useCreateActivite();
  const nommerNiveau = useNommerNiveau(projetId);
  // À la création d'un élément sur un niveau encore sans nom, on demande ce nom
  // (ex : « Résultat », « Pilier ») : chaque niveau porte ainsi son propre nom.
  const demanderNomNiveau = !activite && profondeur !== undefined && !nomNiveau;
  const [nouveauNomNiveau, setNouveauNomNiveau] = useState("");
  const updateActivite = useUpdateActivite();
  const createEquipe = useCreateEquipe();
  const createIntervenant = useCreateIntervenant();

  const niveauFeuille = useMemo(
    () => (niveaux && niveaux.length > 0 ? niveaux.reduce((a, b) => (b.ordre > a.ordre ? b : a)) : null),
    [niveaux],
  );
  const activitesDuCadre = useMemo(
    () => (niveauFeuille ? (axes ?? []).filter((a) => a.type_niveau === niveauFeuille.id) : []),
    [axes, niveauFeuille],
  );

  const [codeActivite, setCodeActivite] = useState(activite?.code_activite ?? "");
  const [libelle, setLibelle] = useState(activite?.libelle ?? "");
  const [axeStrategique, setAxeStrategique] = useState<string | null>(
    activite?.axe_strategique ? String(activite.axe_strategique) : null,
  );
  const [responsablesIds, setResponsablesIds] = useState<number[]>(activite?.responsables ?? []);
  const [axesSecondaires, setAxesSecondaires] = useState<string[]>((activite?.axes_strategiques_secondaires ?? []).map(String));
  const [structuresIds, setStructuresIds] = useState<string[]>((activite?.structures ?? []).map(String));
  const { data: structures } = useStructures();
  const [equipeResponsable, setEquipeResponsable] = useState<string | null>(
    activite?.equipe_responsable ? String(activite.equipe_responsable) : null,
  );
  const [equipeModeCreation, setEquipeModeCreation] = useState(false);
  const [equipeNouveauNom, setEquipeNouveauNom] = useState("");
  const [equipeNouveauxMembresIds, setEquipeNouveauxMembresIds] = useState<number[]>([]);
  const [equipeNouveauDateDebutContrat, setEquipeNouveauDateDebutContrat] = useState<string | null>(null);
  const [equipeNouveauDateFinContrat, setEquipeNouveauDateFinContrat] = useState<string | null>(null);
  const [budgetAlloue, setBudgetAlloue] = useState<number | string>(activite?.budget_alloue ?? "");
  const [valeurReference, setValeurReference] = useState<number | string>(activite?.valeur_reference ?? "");
  const [quantitePrevue, setQuantitePrevue] = useState<number | string>(activite?.quantite_prevue ?? "");
  const [uniteQuantite, setUniteQuantite] = useState(activite?.unite_quantite ?? "");
  const [dateDebut, setDateDebut] = useState<string | null>(activite?.date_debut ?? null);
  const [dateFin, setDateFin] = useState<string | null>(activite?.date_fin ?? null);
  const [dateRappel, setDateRappel] = useState<string | null>(activite?.date_rappel ?? null);
  const [commentaire, setCommentaire] = useState(activite?.commentaire ?? "");
  const [description, setDescription] = useState(activite?.description ?? "");
  const [methodeCalcul, setMethodeCalcul] = useState<string>(activite?.methode_calcul ?? "");
  const [methodeAgregation, setMethodeAgregation] = useState<string>(activite?.methode_agregation ?? "");
  const [poids, setPoids] = useState<number | string>(activite?.poids ?? "");
  const [attributs, setAttributs] = useState<Attributs>(activite?.attributs ?? {});

  const budgetRestant = budgetProjetTotal - budgetDejaAlloue;
  const budgetAllouNumber = budgetAlloue === "" ? 0 : Number(budgetAlloue);
  const budgetDepasseLeRestant = budgetAllouNumber > budgetRestant;

  async function creerIntervenant(nom: string, prenom: string): Promise<Intervenant | null> {
    try {
      return await createIntervenant.mutateAsync({ nom, prenom, projets_associes: [projetId], activites_associees: [] });
    } catch {
      notifications.show({ message: voc("Erreur lors de la création de la personne"), color: "red" });
      return null;
    }
  }

  async function handleCreerEquipe() {
    if (!equipeNouveauNom.trim()) {
      notifications.show({ message: voc("Le nom de l'équipe est requis."), color: "orange" });
      return;
    }
    try {
      const cree = await createEquipe.mutateAsync({
        nom: equipeNouveauNom.trim(),
        membres: equipeNouveauxMembresIds,
        date_debut_contrat: equipeNouveauDateDebutContrat,
        date_fin_contrat: equipeNouveauDateFinContrat,
      });
      setEquipeResponsable(String(cree.id));
      setEquipeModeCreation(false);
      setEquipeNouveauNom("");
      setEquipeNouveauxMembresIds([]);
      setEquipeNouveauDateDebutContrat(null);
      setEquipeNouveauDateFinContrat(null);
    } catch (error) {
      notifications.show({ message: messageErreurApi(error, voc("Erreur lors de la création de l'équipe")), color: "red" });
    }
  }

  async function handleSubmit() {
    if (!libelle.trim()) {
      notifications.show({ message: voc("Le libellé est requis."), color: "orange" });
      return;
    }
    if (demanderNomNiveau && !nouveauNomNiveau.trim()) {
      notifications.show({ message: voc("Donne un nom à ce niveau (ex : Résultat, Composante, Activité)."), color: "orange" });
      return;
    }
    const payload = {
      projet: projetId,
      ...(enEdition ? {} : { activite_parent: activiteParentId ?? null }),
      code_activite: codeActivite,
      libelle: libelle.trim(),
      axe_strategique: axeStrategique ? Number(axeStrategique) : null,
      axes_strategiques_secondaires: axesSecondaires.filter((id) => id !== axeStrategique).map(Number),
      structures: structuresIds.map(Number),
      responsables: responsablesIds,
      equipe_responsable: equipeResponsable ? Number(equipeResponsable) : null,
      budget_alloue: budgetAlloue === "" ? null : Number(budgetAlloue),
      valeur_reference: valeurReference === "" ? null : Number(valeurReference),
      quantite_prevue: quantitePrevue === "" ? null : Number(quantitePrevue),
      unite_quantite: uniteQuantite,
      date_debut: dateDebut,
      date_fin: dateFin,
      date_rappel: dateRappel,
      commentaire,
      description,
      methode_calcul: methodeCalcul,
      methode_agregation: methodeAgregation,
      poids: poids === "" ? null : Number(poids),
      attributs,
    };
    try {
      if (enEdition) {
        await updateActivite.mutateAsync({ id: activite!.id, payload });
        notifications.show({ message: voc("Élément modifié"), color: "green" });
      } else {
        if (demanderNomNiveau) await nommerNiveau(profondeur!, nouveauNomNiveau.trim());
        await createActivite.mutateAsync(payload as never);
        notifications.show({ message: voc("Élément créé"), color: "green" });
      }
      onDone();
    } catch (error) {
      notifications.show({
        message: messageErreurApi(error, enEdition ? voc("Erreur lors de la modification de l'élément") : voc("Erreur lors de la création de l'élément")),
        color: "red",
      });
    }
  }

  return (
    <Stack gap="sm">
      {demanderNomNiveau && (
        <TextInput
          label={voc("Nom de ce niveau")}
          description={voc("Ce niveau n'a pas encore de nom : il s'appliquera à tous les éléments de ce niveau dans le projet.")}
          placeholder={voc("Ex : Résultat, Composante, Activité…")}
          value={nouveauNomNiveau}
          onChange={(e) => setNouveauNomNiveau(e.currentTarget.value)}
          required
          data-autofocus
        />
      )}
      <TextInput label={voc("Code")} placeholder={voc("Ex : R1, P1.2, A1.1")} value={codeActivite} onChange={(e) => setCodeActivite(e.currentTarget.value)} />
      {activitesDuCadre.length > 0 ? (
        <Autocomplete
          label={voc("Libellé")}
          description={voc`Suggestions issues du niveau « ${niveauFeuille!.nom_niveau} » du cadre stratégique — vous pouvez aussi taper un nouveau libellé.`}
          data={activitesDuCadre.map((a) => a.nom)}
          value={libelle}
          onChange={(v) => {
            setLibelle(v);
            const correspondance = activitesDuCadre.find((a) => a.nom === v);
            if (correspondance) setAxeStrategique(String(correspondance.id));
          }}
          required
        />
      ) : (
        <TextInput label={voc("Libellé")} value={libelle} onChange={(e) => setLibelle(e.currentTarget.value)} required />
      )}
      <Textarea
        label={voc("Description")}
        autosize
        minRows={1}
        value={description}
        onChange={(e) => setDescription(e.currentTarget.value)}
      />
      <Group grow>
        <DateInput label={voc("Date de début prévue")} value={dateDebut} onChange={setDateDebut} />
        <DateInput
          label={voc("Date de fin prévue")}
          value={dateFin}
          onChange={setDateFin}
          minDate={dateDebut ?? undefined}
          description={libelleDuree(dateDebut, dateFin) ? voc`Durée : ${libelleDuree(dateDebut, dateFin)}` : undefined}
        />
      </Group>
      <DateInput
        label={voc("Date de rappel (optionnel)")}
        description={voc("Déclenche une alerte à cette date précise, indépendamment du seuil de jours avant l'échéance.")}
        value={dateRappel}
        onChange={setDateRappel}
        clearable
      />
      <NumberInput
        label={voc("Budget alloué (FCFA)")}
        description={voc`Budget restant du projet : ${budgetRestant.toLocaleString(locale())} FCFA`}
        value={budgetAlloue}
        onChange={setBudgetAlloue}
        min={0}
        error={budgetDepasseLeRestant ? voc("Ce montant dépasse le budget restant du projet.") : undefined}
      />
      {budgetDepasseLeRestant && (
        <Alert color="orange" variant="light">
          {voc("Ce budget alloué (")}{budgetAllouNumber.toLocaleString(locale())} {voc(" FCFA) dépasse le budget restant du projet (")}{budgetRestant.toLocaleString(locale())} {voc("FCFA sur")} {budgetProjetTotal.toLocaleString(locale())} {voc("FCFA au total). Vérifie le montant avant d'enregistrer.")}
        </Alert>
      )}
      <Group grow>
        <TextInput label={voc("Unité")} placeholder={voc("Ex : producteurs")} value={uniteQuantite} onChange={(e) => setUniteQuantite(e.currentTarget.value)} />
        <NumberInput
          label={voc("Valeur de base")}
          description={voc("Avant le démarrage — l'activité se suit alors comme un indicateur.")}
          value={valeurReference}
          onChange={setValeurReference}
          min={0}
        />
        <NumberInput label={voc("Quantité prévue (cible)")} value={quantitePrevue} onChange={setQuantitePrevue} min={0} />
      </Group>
      <Divider label={voc("Calcul du taux d'exécution")} labelPosition="left" />
      <Group grow align="flex-start">
        <Select
          label={voc("Méthode de calcul")}
          description={
            methodeCalcul
              ? AIDES_METHODE[methodeCalcul as keyof typeof AIDES_METHODE]
              : voc("Vide : celle du niveau au-dessus, sinon du projet, sinon de l'organisation.")
          }
          data={optionsMethode(voc("Hériter (niveau au-dessus / projet)"))}
          value={methodeCalcul}
          onChange={(v) => setMethodeCalcul(v ?? "")}
          allowDeselect={false}
        />
        <Select
          label={voc("Agrégation des éléments en dessous")}
          description={
            methodeAgregation
              ? AIDES_AGREGATION[methodeAgregation as keyof typeof AIDES_AGREGATION]
              : voc("Utilisée si cet élément a des éléments en dessous.")
          }
          data={optionsAgregation(voc("Hériter (niveau au-dessus / projet)"))}
          value={methodeAgregation}
          onChange={(v) => setMethodeAgregation(v ?? "")}
          allowDeselect={false}
        />
        <NumberInput
          label={voc("Poids")}
          description={voc("Pour une agrégation « pondérée par les poids » du niveau au-dessus.")}
          min={0}
          value={poids}
          onChange={setPoids}
        />
      </Group>
      <Textarea
        label={voc("Commentaire")}
        description={voc("Note libre (ex : validation, remarque) — n'affecte ni le suivi ni les calculs.")}
        minRows={2}
        value={commentaire}
        onChange={(e) => setCommentaire(e.currentTarget.value)}
      />
      <AttributsLibres value={attributs} onChange={setAttributs} suggestions={nomsAttributs} />
      <Select
        label={voc("Élément stratégique")}
        description={
          cadreStrategiqueId
            ? voc("Peut être rattaché à n'importe quelle ligne du cadre stratégique (orientation, axe, activité, sous-activité…), limité au cadre de ce projet.")
            : voc("Ce projet n'a pas de cadre stratégique associé — tous les éléments existants sont proposés.")
        }
        data={axes?.map((a) => ({ value: String(a.id), label: `${a.type_niveau_nom} · ${a.code ? a.code + " — " : ""}${a.nom}` })) ?? []}
        value={axeStrategique}
        onChange={setAxeStrategique}
        clearable
        searchable
      />
      <MultiSelect
        label={voc("Contribue aussi à")}
        description={voc("Autres éléments stratégiques auxquels cet élément contribue. Seul l'élément stratégique ci-dessus compte dans les budgets et les taux ; ces liens sont informatifs.")}
        placeholder={voc("Aucun")}
        data={(axes ?? [])
          .filter((a) => String(a.id) !== axeStrategique)
          .map((a) => ({ value: String(a.id), label: `${a.type_niveau_nom} · ${a.code ? a.code + " — " : ""}${a.nom}` }))}
        value={axesSecondaires}
        onChange={setAxesSecondaires}
        clearable
        searchable
      />
      <MultiSelect
        label={voc("Services chargés")}
        description={voc("Services de l'organisation chargés de cette partie du projet (paramétrés dans Organisation).")}
        placeholder={voc("Aucun")}
        data={optionsStructures(structures ?? [])}
        value={structuresIds}
        onChange={setStructuresIds}
        clearable
        searchable
      />
      <IntervenantsMultiples
        label={voc("Responsables")}
        description={voc("Choisis une ou plusieurs personnes déjà enregistrées, ou crée-en une nouvelle.")}
        value={responsablesIds}
        onChange={setResponsablesIds}
        intervenants={intervenants ?? []}
        onCreerNouveau={creerIntervenant}
        creating={createIntervenant.isPending}
      />
      {equipeModeCreation ? (
        <Stack gap={4}>
          <Text size="sm" fw={500}>{voc("Nouvelle équipe")}</Text>
          <TextInput
            size="xs"
            label={voc("Nom de l'équipe")}
            value={equipeNouveauNom}
            onChange={(e) => setEquipeNouveauNom(e.currentTarget.value)}
          />
          <IntervenantsMultiples
            label={voc("Membres de l'équipe")}
            value={equipeNouveauxMembresIds}
            onChange={setEquipeNouveauxMembresIds}
            intervenants={intervenants ?? []}
            onCreerNouveau={creerIntervenant}
            creating={createIntervenant.isPending}
          />
          <Group grow>
            <DateInput
              label={voc("Date de début de contrat")}
              value={equipeNouveauDateDebutContrat}
              onChange={setEquipeNouveauDateDebutContrat}
              size="xs"
            />
            <DateInput
              label={voc("Date de fin de contrat")}
              value={equipeNouveauDateFinContrat}
              onChange={setEquipeNouveauDateFinContrat}
              size="xs"
            />
          </Group>
          <Group gap={6}>
            <Button size="xs" onClick={handleCreerEquipe} loading={createEquipe.isPending}>{voc("Créer l'équipe")}</Button>
            <Button
              size="xs"
              variant="subtle"
              color="gray"
              onClick={() => {
                setEquipeModeCreation(false);
                setEquipeNouveauNom("");
                setEquipeNouveauxMembresIds([]);
                setEquipeNouveauDateDebutContrat(null);
                setEquipeNouveauDateFinContrat(null);
              }}
            >
              {voc("Annuler")}
            </Button>
          </Group>
        </Stack>
      ) : (
        <Stack gap={4}>
          <Select
            label={voc("Équipe responsable")}
            placeholder={voc("Choisir une équipe…")}
            data={equipes?.map((e) => ({ value: String(e.id), label: e.nom })) ?? []}
            value={equipeResponsable}
            onChange={setEquipeResponsable}
            clearable
            searchable
          />
          {(() => {
            const equipeChoisie = equipes?.find((e) => String(e.id) === equipeResponsable);
            if (!equipeChoisie || (!equipeChoisie.date_debut_contrat && !equipeChoisie.date_fin_contrat)) return null;
            return (
              <Text size="xs" c="dimmed">
                {voc("Contrat de l'équipe :")} {equipeChoisie.date_debut_contrat ?? "?"} → {equipeChoisie.date_fin_contrat ?? "?"}
              </Text>
            );
          })()}
          <Button size="xs" variant="subtle" onClick={() => setEquipeModeCreation(true)}>
            {voc("+ Créer une nouvelle équipe")}
          </Button>
        </Stack>
      )}
      <Group justify="flex-end">
        <Button onClick={handleSubmit} loading={createActivite.isPending || updateActivite.isPending}>
          {enEdition ? voc("Enregistrer") : voc("Créer")}
        </Button>
      </Group>

      {enEdition && (
        <>
          <Divider label={voc("Documents liés")} labelPosition="left" mt="sm" />
          <DocumentsTab activiteId={activite!.id} />
        </>
      )}
    </Stack>
  );
}
