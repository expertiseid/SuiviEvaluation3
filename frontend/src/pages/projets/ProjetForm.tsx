import { useEffect, useMemo, useState } from "react";
import { zodResolver } from "@hookform/resolvers/zod";
import { useForm, Controller } from "react-hook-form";
import { z } from "zod";
import { Alert, Autocomplete, Button, Checkbox, Group, MultiSelect, NumberInput, Pill, PillGroup, Select, Stack, Tabs, Text, Textarea, TextInput } from "@mantine/core";
import { DateInput } from "@mantine/dates";
import { notifications } from "@mantine/notifications";
import { modals } from "@mantine/modals";
import { useUtilisateurs } from "../../api/accounts";
import { useCreateProjet, useParametresCalcul, useUpdateProjet } from "../../api/projects";
import {
  AIDES_AGREGATION,
  LIBELLES_AGREGATION,
  LIBELLES_METHODE,
  optionsAgregation,
  optionsMethode,
} from "../../utils/methodesCalcul";
import { usePartenaires, useCreatePartenaire } from "../../api/referentiels";
import { useNiveauxAdministratifs, useZones } from "../../api/geo";
import { useCadresStrategiques, useElementsStrategiques } from "../../api/strategy";
import {
  ZoneCascadeFields,
  ZONE_CASCADE_VIDE,
  zoneResolueDe,
  type ZoneCascadeValue,
} from "../../components/common/ZoneCascadeFields";
import { SelectOrCreate } from "../../components/common/SelectOrCreate";
import { BeneficiairesProjetSection } from "./BeneficiairesProjetSection";
import { PROJET_STATUT_LABEL } from "../../utils/statusTones";
import { PAYS_MONDE } from "../../utils/pays";
import type { Projet, StatutProjet } from "../../types";
import { voc } from "../../utils/vocabulaire";

const schema = z.object({
  nom: z.string().min(1, "Requis"),
  code: z.string().min(1, "Requis"),
  pays: z.array(z.string()).optional(),
  budget_total: z.number().min(0),
  fonds_propres: z.number().min(0),
  date_debut: z.string().min(1, "Requis"),
  date_fin: z.string().min(1, "Requis"),
  date_rappel: z.string().nullable().optional(),
  statut: z.enum(["EN_PREPARATION", "EN_COURS", "CLOTURE"]),
  type_mise_en_oeuvre: z.enum(["DIRECT", "CONSORTIUM"]),
  partenaire_bailleur: z.string().nullable().optional(),
  partenaire_mise_en_oeuvre: z.string().nullable().optional(),
  chef_de_projet_nom: z.string().optional(),
  utilisateurs_affectes: z.array(z.string()).optional(),
  cadre_strategique: z.string().optional(),
  element_strategique: z.string().optional(),
  methode_calcul: z.string().optional(),
  methode_agregation: z.string().optional(),
  cible_totale: z.number().nullable().optional(),
  cible_hommes: z.number().nullable().optional(),
  cible_femmes: z.number().nullable().optional(),
  cible_jeunes: z.number().nullable().optional(),
  cible_pdi: z.number().nullable().optional(),
  elements_capitalisation: z.string().optional(),
});

type FormValues = z.infer<typeof schema>;

const ONGLET_PAR_CHAMP: Record<string, string> = {
  nom: "general",
  code: "general",
  date_debut: "general",
  date_fin: "general",
  date_rappel: "general",
  cible_totale: "cibles",
  cible_hommes: "cibles",
  cible_femmes: "cibles",
  cible_jeunes: "cibles",
  cible_pdi: "cibles",
};

export function ProjetForm({ projet, onDone }: { projet?: Projet; onDone: () => void }) {
  const enEdition = !!projet;
  const { data: partenaires } = usePartenaires();
  const partenairesBailleurs = useMemo(() => (partenaires ?? []).filter((p) => p.type === "BAILLEUR"), [partenaires]);
  const partenairesMiseEnOeuvre = useMemo(
    () => (partenaires ?? []).filter((p) => p.type === "MISE_EN_OEUVRE"),
    [partenaires],
  );
  const { data: cadres } = useCadresStrategiques();
  const { data: parametresCalcul } = useParametresCalcul();
  const { data: utilisateurs } = useUtilisateurs();
  const optionsChefsDeProjet = useMemo(
    () =>
      (utilisateurs ?? [])
        .map((u) => `${u.first_name} ${u.last_name}`.trim() || u.username)
        .filter((nom, index, tous) => nom && tous.indexOf(nom) === index),
    [utilisateurs],
  );
  const optionsUtilisateursAffectes = useMemo(
    () =>
      (utilisateurs ?? []).map((u) => ({
        value: String(u.id),
        label: `${(`${u.first_name} ${u.last_name}`.trim()) || u.username} (${u.username})`,
      })),
    [utilisateurs],
  );
  const { data: zones } = useZones();
  const createProjet = useCreateProjet();
  const updateProjet = useUpdateProjet();
  const createPartenaire = useCreatePartenaire();

  const [zoneCascade, setZoneCascade] = useState<ZoneCascadeValue>(ZONE_CASCADE_VIDE);
  const [zonesAjoutees, setZonesAjoutees] = useState<{ id: number; label: string }[]>([]);
  const [zonesInitialisees, setZonesInitialisees] = useState(false);
  const [toutLePays, setToutLePays] = useState(projet?.tout_le_pays ?? false);
  const [partenairesConsortium, setPartenairesConsortium] = useState<{ id: number; label: string }[]>([]);
  const [partenaireConsortiumChoisi, setPartenaireConsortiumChoisi] = useState<string | null>(null);
  const [consortiumInitialise, setConsortiumInitialise] = useState(false);
  const [ongletActif, setOngletActif] = useState<string | null>("general");
  const [paysZoneActif, setPaysZoneActif] = useState<string | null>(projet?.pays[0] ?? null);
  const { data: niveauxPaysZone } = useNiveauxAdministratifs(paysZoneActif);
  const { data: zonesPaysActif } = useZones({ pays: paysZoneActif ?? undefined });

  useEffect(() => {
    if (!enEdition || zonesInitialisees || !zones) return;
    setZonesAjoutees(
      projet!.zones.flatMap((id) => {
        const zone = zones.find((z) => z.id === id);
        return zone ? [{ id: zone.id, label: zone.nom }] : [];
      }),
    );
    setZonesInitialisees(true);
  }, [enEdition, zonesInitialisees, zones, projet]);

  useEffect(() => {
    if (!enEdition || consortiumInitialise || !partenaires) return;
    setPartenairesConsortium(
      projet!.partenaires_consortium.flatMap((id) => {
        const p = partenaires.find((pt) => pt.id === id);
        return p ? [{ id: p.id, label: p.nom }] : [];
      }),
    );
    setConsortiumInitialise(true);
  }, [enEdition, consortiumInitialise, partenaires, projet]);

  const { control, register, handleSubmit, watch, setValue, formState: { errors } } = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: projet
      ? {
          nom: projet.nom,
          code: projet.code,
          pays: projet.pays,
          budget_total: Number(projet.budget_total),
          fonds_propres: Number(projet.fonds_propres),
          date_debut: projet.date_debut,
          date_fin: projet.date_fin,
          date_rappel: projet.date_rappel,
          statut: projet.statut,
          type_mise_en_oeuvre: projet.type_mise_en_oeuvre,
          partenaire_bailleur: projet.partenaire_bailleur ? String(projet.partenaire_bailleur) : null,
          partenaire_mise_en_oeuvre: projet.partenaire_mise_en_oeuvre ? String(projet.partenaire_mise_en_oeuvre) : null,
          chef_de_projet_nom: projet.chef_de_projet_nom ?? "",
          utilisateurs_affectes: projet.utilisateurs_affectes.map(String),
          cadre_strategique: projet.cadre_strategique ? String(projet.cadre_strategique) : "",
          element_strategique: projet.element_strategique ? String(projet.element_strategique) : "",
          methode_calcul: projet.methode_calcul ?? "",
          methode_agregation: projet.methode_agregation ?? "",
          cible_totale: projet.cible_totale,
          cible_hommes: projet.cible_hommes,
          cible_femmes: projet.cible_femmes,
          cible_jeunes: projet.cible_jeunes,
          cible_pdi: projet.cible_pdi,
          elements_capitalisation: projet.elements_capitalisation ?? "",
        }
      : {
          pays: [],
          budget_total: 0,
          fonds_propres: 0,
          statut: "EN_PREPARATION",
          type_mise_en_oeuvre: "DIRECT",
          cadre_strategique: "",
          element_strategique: "",
          methode_calcul: "",
          methode_agregation: "",
          elements_capitalisation: "",
          utilisateurs_affectes: [],
        },
  });

  function handleAjouterZone() {
    const zoneId = zoneResolueDe(zoneCascade, niveauxPaysZone ?? []);
    if (!zoneId) return;
    const zone = zonesPaysActif?.find((z) => z.id === zoneId);
    if (zone && !zonesAjoutees.some((z) => z.id === zone.id)) {
      setZonesAjoutees((prev) => [...prev, { id: zone.id, label: zone.nom }]);
    }
    setZoneCascade(ZONE_CASCADE_VIDE);
  }


  // Rattachement du projet : n'importe quel élément du cadre choisi, regroupé par niveau.
  const cadreChoisi = watch("cadre_strategique");
  const { data: elementsDuCadre } = useElementsStrategiques(
    cadreChoisi ? { cadre_strategique: Number(cadreChoisi) } : undefined,
  );
  const optionsRattachement = useMemo(() => {
    if (!cadreChoisi) return [];
    const groupes = new Map<string, { value: string; label: string }[]>();
    for (const el of elementsDuCadre ?? []) {
      const liste = groupes.get(el.type_niveau_nom) ?? [];
      liste.push({ value: String(el.id), label: `${el.code ? el.code + " — " : ""}${el.nom}` });
      groupes.set(el.type_niveau_nom, liste);
    }
    return [...groupes.entries()].map(([group, items]) => ({ group, items }));
  }, [cadreChoisi, elementsDuCadre]);

  async function enregistrer(values: FormValues) {
    const payload = {
      nom: values.nom,
      code: values.code,
      pays: values.pays ?? [],
      budget_total: values.budget_total,
      fonds_propres: values.fonds_propres,
      date_debut: values.date_debut,
      date_fin: values.date_fin,
      date_rappel: values.date_rappel || null,
      statut: values.statut as StatutProjet,
      type_mise_en_oeuvre: values.type_mise_en_oeuvre,
      partenaire_bailleur: values.partenaire_bailleur ? Number(values.partenaire_bailleur) : null,
      partenaire_mise_en_oeuvre: values.partenaire_mise_en_oeuvre ? Number(values.partenaire_mise_en_oeuvre) : null,
      partenaires_consortium: partenairesConsortium.map((p) => p.id),
      chef_de_projet_nom: values.chef_de_projet_nom ?? "",
      utilisateurs_affectes: (values.utilisateurs_affectes ?? []).map(Number),
      zones: toutLePays ? [] : zonesAjoutees.map((z) => z.id),
      tout_le_pays: toutLePays,
      cadre_strategique: values.cadre_strategique ? Number(values.cadre_strategique) : null,
      element_strategique: values.element_strategique ? Number(values.element_strategique) : null,
      methode_calcul: values.methode_calcul ?? "",
      methode_agregation: values.methode_agregation ?? "",
      cible_totale: values.cible_totale ?? null,
      cible_hommes: values.cible_hommes ?? null,
      cible_femmes: values.cible_femmes ?? null,
      cible_jeunes: values.cible_jeunes ?? null,
      cible_pdi: values.cible_pdi ?? null,
      elements_capitalisation: values.elements_capitalisation ?? "",
    };
    try {
      if (enEdition) {
        await updateProjet.mutateAsync({ id: projet.id, payload: payload as never });
        notifications.show({ message: voc("Projet modifié"), color: "green" });
      } else {
        await createProjet.mutateAsync(payload as never);
        notifications.show({ message: voc("Projet créé"), color: "green" });
      }
      onDone();
    } catch {
      notifications.show({
        message: enEdition ? voc("Erreur lors de la modification du projet") : voc("Erreur lors de la création du projet"),
        color: "red",
      });
    }
  }

  function onSubmit(values: FormValues) {
    if (!values.cadre_strategique) {
      modals.openConfirmModal({
        title: voc("Aucun cadre stratégique associé"),
        children: (
          <Text size="sm">
            {voc("Vous n'avez pas associé de cadre stratégique à ce projet. Voulez-vous continuer sans cadre stratégique, ou l'associer d'abord ?")}</Text>
        ),
        labels: { confirm: "Continuer", cancel: "Associer un cadre" },
        onConfirm: () => enregistrer(values),
        onCancel: () => setOngletActif("strategie"),
      });
      return;
    }
    enregistrer(values);
  }

  const enCours = createProjet.isPending || updateProjet.isPending;

  function onInvalid(formErrors: typeof errors) {
    const premierChamp = Object.keys(formErrors)[0] as keyof FormValues | undefined;
    const onglet = premierChamp ? ONGLET_PAR_CHAMP[premierChamp] : undefined;
    if (onglet) setOngletActif(onglet);
    const messageChamp = premierChamp ? formErrors[premierChamp]?.message : undefined;
    notifications.show({
      title: "Champ obligatoire manquant",
      message: messageChamp ?? "Merci de compléter les champs obligatoires — voir l'onglet mis en évidence.",
      color: "red",
      autoClose: 8000,
    });
  }

  return (
    <form onSubmit={handleSubmit(onSubmit, onInvalid)}>
      <Tabs value={ongletActif} onChange={setOngletActif}>
        <Tabs.List>
          <Tabs.Tab value="general">Général</Tabs.Tab>
          <Tabs.Tab value="cibles">{voc("Cibles bénéficiaires")}</Tabs.Tab>
          <Tabs.Tab value="strategie">Stratégie & capitalisation</Tabs.Tab>
        </Tabs.List>

        <Tabs.Panel value="general" pt="sm">
          <Stack gap="sm">
            <TextInput label={voc("Nom du projet")} {...register("nom")} error={errors.nom?.message} required />
            <TextInput label="Code" {...register("code")} error={errors.code?.message} required />
            <Group grow>
              <Controller
                control={control}
                name="budget_total"
                render={({ field }) => (
                  <NumberInput label="Budget total (FCFA)" value={field.value} onChange={(v) => field.onChange(Number(v) || 0)} min={0} />
                )}
              />
              <Controller
                control={control}
                name="fonds_propres"
                render={({ field }) => (
                  <NumberInput label="Fonds propres (FCFA)" value={field.value} onChange={(v) => field.onChange(Number(v) || 0)} min={0} />
                )}
              />
            </Group>
            <Group grow>
              <Controller
                control={control}
                name="date_debut"
                render={({ field }) => (
                  <DateInput label="Date de début prévue" value={field.value} onChange={field.onChange} error={errors.date_debut?.message} required />
                )}
              />
              <Controller
                control={control}
                name="date_fin"
                render={({ field }) => (
                  <DateInput label="Date de fin prévue" value={field.value} onChange={field.onChange} error={errors.date_fin?.message} required />
                )}
              />
            </Group>
            <Controller
              control={control}
              name="date_rappel"
              render={({ field }) => (
                <DateInput
                  label="Date de rappel (optionnel)"
                  description={voc("Déclenche une alerte à cette date précise, indépendamment du seuil de jours avant l'échéance.")}
                  value={field.value ?? null}
                  onChange={field.onChange}
                  clearable
                />
              )}
            />
            <Group grow>
              <Controller
                control={control}
                name="statut"
                render={({ field }) => (
                  <Select
                    label="Statut"
                    data={Object.entries(PROJET_STATUT_LABEL).map(([value, label]) => ({ value, label }))}
                    value={field.value}
                    onChange={(v) => field.onChange(v ?? "EN_PREPARATION")}
                  />
                )}
              />
              <Controller
                control={control}
                name="type_mise_en_oeuvre"
                render={({ field }) => (
                  <Select
                    label="Type de mise en œuvre"
                    data={[{ value: "DIRECT", label: "Direct" }, { value: "CONSORTIUM", label: "En consortium" }]}
                    value={field.value}
                    onChange={(v) => field.onChange(v ?? "DIRECT")}
                  />
                )}
              />
            </Group>
            <Controller
              control={control}
              name="chef_de_projet_nom"
              render={({ field }) => (
                <Autocomplete
                  label={voc("Chef de projet")}
                  description={voc("Choisis un utilisateur existant dans la liste, ou tape librement un nom — la personne n'a pas besoin d'avoir un compte sur la plateforme. Ceci est juste un intitulé affiché : ça ne donne accès à rien tout seul.")}
                  data={optionsChefsDeProjet}
                  value={field.value ?? ""}
                  onChange={field.onChange}
                />
              )}
            />
            <Controller
              control={control}
              name="utilisateurs_affectes"
              render={({ field }) => (
                <MultiSelect
                  label={voc("Utilisateurs affectés (accès à la plateforme)")}
                  description={voc("Indispensable pour qu'un chef de projet, animateur, etc. puisse se connecter et voir ce projet — sans ça, même désigné ci-dessus, il ne verra rien après connexion.")}
                  placeholder={voc("Rechercher un utilisateur…")}
                  data={optionsUtilisateursAffectes}
                  value={field.value ?? []}
                  onChange={field.onChange}
                  searchable
                  clearable
                />
              )}
            />
            <Controller
              control={control}
              name="partenaire_bailleur"
              render={({ field }) => (
                <SelectOrCreate
                  label="Bailleur"
                  data={partenairesBailleurs.map((p) => ({ value: String(p.id), label: p.nom }))}
                  value={field.value ?? null}
                  onChange={field.onChange}
                  clearable
                  creating={createPartenaire.isPending}
                  onCreate={async (nom) => {
                    try {
                      const cree = await createPartenaire.mutateAsync({ nom, type: "BAILLEUR" });
                      field.onChange(String(cree.id));
                    } catch {
                      notifications.show({ message: "Erreur lors de la création du bailleur", color: "red" });
                    }
                  }}
                />
              )}
            />
            <Controller
              control={control}
              name="partenaire_mise_en_oeuvre"
              render={({ field }) => (
                <SelectOrCreate
                  label="Partenaire de mise en œuvre"
                  data={partenairesMiseEnOeuvre.map((p) => ({ value: String(p.id), label: p.nom }))}
                  value={field.value ?? null}
                  onChange={field.onChange}
                  clearable
                  creating={createPartenaire.isPending}
                  onCreate={async (nom) => {
                    try {
                      const cree = await createPartenaire.mutateAsync({ nom, type: "MISE_EN_OEUVRE" });
                      field.onChange(String(cree.id));
                    } catch {
                      notifications.show({ message: "Erreur lors de la création du partenaire", color: "red" });
                    }
                  }}
                />
              )}
            />
            {watch("type_mise_en_oeuvre") === "CONSORTIUM" && (
              <div>
                <SelectOrCreate
                  label="Partenaires du consortium"
                  data={partenairesMiseEnOeuvre.map((p) => ({ value: String(p.id), label: p.nom }))}
                  value={partenaireConsortiumChoisi}
                  onChange={setPartenaireConsortiumChoisi}
                  clearable
                  creating={createPartenaire.isPending}
                  onCreate={async (nom) => {
                    try {
                      const cree = await createPartenaire.mutateAsync({ nom, type: "MISE_EN_OEUVRE" });
                      if (!partenairesConsortium.some((p) => p.id === cree.id)) {
                        setPartenairesConsortium((prev) => [...prev, { id: cree.id, label: cree.nom }]);
                      }
                    } catch {
                      notifications.show({ message: "Erreur lors de la création du partenaire", color: "red" });
                    }
                  }}
                />
                <Group justify="flex-end" mt={4}>
                  <Button
                    size="xs"
                    variant="light"
                    onClick={() => {
                      if (!partenaireConsortiumChoisi) return;
                      const p = partenaires?.find((pt) => String(pt.id) === partenaireConsortiumChoisi);
                      if (p && !partenairesConsortium.some((x) => x.id === p.id)) {
                        setPartenairesConsortium((prev) => [...prev, { id: p.id, label: p.nom }]);
                      }
                      setPartenaireConsortiumChoisi(null);
                    }}
                  >
                    Ajouter ce partenaire
                  </Button>
                </Group>
                {partenairesConsortium.length > 0 && (
                  <PillGroup mt="xs">
                    {partenairesConsortium.map((p) => (
                      <Pill
                        key={p.id}
                        withRemoveButton
                        onRemove={() => setPartenairesConsortium((prev) => prev.filter((x) => x.id !== p.id))}
                      >
                        {p.label}
                      </Pill>
                    ))}
                  </PillGroup>
                )}
              </div>
            )}

            <Controller
              control={control}
              name="pays"
              render={({ field }) => (
                <MultiSelect
                  label="Pays d'intervention"
                  placeholder="Rechercher un ou plusieurs pays…"
                  data={PAYS_MONDE.map((p) => ({ value: p.code, label: p.nom }))}
                  value={field.value ?? []}
                  onChange={(v) => {
                    field.onChange(v);
                    if (!paysZoneActif || !v.includes(paysZoneActif)) {
                      setPaysZoneActif(v[0] ?? null);
                      setZoneCascade(ZONE_CASCADE_VIDE);
                    }
                  }}
                  searchable
                  clearable
                />
              )}
            />

            <div>
              <Text size="sm" fw={500} mb={4}>Zones d'intervention</Text>
              <Checkbox
                label="Tout le pays (ensemble du territoire des pays d'intervention)"
                checked={toutLePays}
                onChange={(e) => setToutLePays(e.currentTarget.checked)}
                mb="xs"
              />
              {!toutLePays && (
                <>
                  {(watch("pays")?.length ?? 0) > 1 && (
                    <Select
                      size="xs"
                      label="Pays de la zone à ajouter"
                      data={(watch("pays") ?? []).map((code) => ({
                        value: code,
                        label: PAYS_MONDE.find((p) => p.code === code)?.nom ?? code,
                      }))}
                      value={paysZoneActif}
                      onChange={(v) => {
                        setPaysZoneActif(v);
                        setZoneCascade(ZONE_CASCADE_VIDE);
                      }}
                      mb={4}
                      maw={250}
                    />
                  )}
                  <ZoneCascadeFields pays={paysZoneActif} value={zoneCascade} onChange={setZoneCascade} />
                  <Group justify="flex-end" mt={4}>
                    <Button size="xs" variant="light" onClick={handleAjouterZone}>
                      Ajouter cette zone
                    </Button>
                  </Group>
                  {zonesAjoutees.length > 0 && (
                    <PillGroup mt="xs">
                      {zonesAjoutees.map((z) => (
                        <Pill key={z.id} withRemoveButton onRemove={() => setZonesAjoutees((prev) => prev.filter((x) => x.id !== z.id))}>
                          {z.label}
                        </Pill>
                      ))}
                    </PillGroup>
                  )}
                </>
              )}
            </div>
          </Stack>
        </Tabs.Panel>

        <Tabs.Panel value="cibles" pt="sm">
          <Stack gap="sm">
            <Controller
              control={control}
              name="cible_totale"
              render={({ field }) => (
                <NumberInput label="Cible totale" value={field.value ?? ""} onChange={(v) => field.onChange(v === "" ? null : Number(v))} min={0} />
              )}
            />
            <Group grow>
              <Controller
                control={control}
                name="cible_hommes"
                render={({ field }) => (
                  <NumberInput label="Dont hommes" value={field.value ?? ""} onChange={(v) => field.onChange(v === "" ? null : Number(v))} min={0} />
                )}
              />
              <Controller
                control={control}
                name="cible_femmes"
                render={({ field }) => (
                  <NumberInput label="Dont femmes" value={field.value ?? ""} onChange={(v) => field.onChange(v === "" ? null : Number(v))} min={0} />
                )}
              />
            </Group>
            <Group grow>
              <Controller
                control={control}
                name="cible_jeunes"
                render={({ field }) => (
                  <NumberInput label="Dont jeunes" value={field.value ?? ""} onChange={(v) => field.onChange(v === "" ? null : Number(v))} min={0} />
                )}
              />
              <Controller
                control={control}
                name="cible_pdi"
                render={({ field }) => (
                  <NumberInput label="Dont PDI" value={field.value ?? ""} onChange={(v) => field.onChange(v === "" ? null : Number(v))} min={0} />
                )}
              />
            </Group>
            {projet ? (
              <BeneficiairesProjetSection projet={projet} />
            ) : (
              <Alert color="blue" variant="light" py={6}>
                {voc("Enregistre d'abord le projet pour pouvoir y associer des bénéficiaires (import Excel ou recherche dans la base).")}</Alert>
            )}
          </Stack>
        </Tabs.Panel>

        <Tabs.Panel value="strategie" pt="sm">
          <Stack gap="sm">
            <Controller
              control={control}
              name="cadre_strategique"
              render={({ field }) => (
                <Stack gap={4}>
                  <Select
                    label={voc("Cadre stratégique")}
                    placeholder={voc("Choisir le cadre stratégique associé…")}
                    description={voc("Détermine les éléments (axes, orientations…) proposés ensuite pour les activités de ce projet.")}
                    data={cadres?.map((c) => ({ value: String(c.id), label: c.nom })) ?? []}
                    value={field.value ?? null}
                    onChange={(v) => {
                      field.onChange(v ?? "");
                      // Le rattachement appartient au cadre : il ne survit pas à un changement de cadre.
                      setValue("element_strategique", "");
                    }}
                    searchable
                    clearable
                  />
                  {!field.value && (
                    <Alert color="orange" variant="light" py={6}>
                      {voc("Aucun cadre stratégique choisi — tu peux quand même créer le projet, mais ses activités ne pourront pas être rattachées à une structuration stratégique tant qu'un cadre n'est pas renseigné.")}</Alert>
                  )}
                </Stack>
              )}
            />
            <Controller
              control={control}
              name="element_strategique"
              render={({ field }) => (
                <Select
                  label={voc("Rattachement dans le cadre stratégique")}
                  placeholder={cadreChoisi ? voc("Choisir l'élément dont relève le projet…") : voc("Choisis d'abord un cadre stratégique")}
                  description={voc("Facultatif — l'élément du cadre dont relève ce projet, à n'importe quel niveau (programme, axe, pilier…). Permet de regrouper les projets par élément.")}
                  data={optionsRattachement}
                  value={field.value || null}
                  onChange={(v) => field.onChange(v ?? "")}
                  disabled={!cadreChoisi}
                  searchable
                  clearable
                />
              )}
            />
            <Group grow align="flex-start">
              <Controller
                control={control}
                name="methode_calcul"
                render={({ field }) => (
                  <Select
                    label="Méthode de calcul des taux"
                    description={voc("Pour tous les éléments du projet qui ne fixent pas la leur.")}
                    data={optionsMethode(
                      `Hériter de l'organisation (${parametresCalcul ? LIBELLES_METHODE[parametresCalcul.methode_calcul] : "…"})`,
                    )}
                    value={field.value ?? ""}
                    onChange={(v) => field.onChange(v ?? "")}
                    allowDeselect={false}
                  />
                )}
              />
              <Controller
                control={control}
                name="methode_agregation"
                render={({ field }) => (
                  <Select
                    label={voc("Agrégation du taux du projet")}
                    description={
                      field.value
                        ? AIDES_AGREGATION[field.value as keyof typeof AIDES_AGREGATION]
                        : voc("Calcul du taux global à partir des éléments de la planification.")
                    }
                    data={optionsAgregation(
                      `Hériter de l'organisation (${parametresCalcul ? LIBELLES_AGREGATION[parametresCalcul.methode_agregation] : "…"})`,
                    )}
                    value={field.value ?? ""}
                    onChange={(v) => field.onChange(v ?? "")}
                    allowDeselect={false}
                  />
                )}
              />
            </Group>
            <Textarea
              label="Éléments de capitalisation"
              description={voc("À compléter en fin de projet : leçons apprises, bonnes pratiques.")}
              minRows={3}
              {...register("elements_capitalisation")}
            />
          </Stack>
        </Tabs.Panel>
      </Tabs>

      <Group justify="flex-end" mt="md">
        <Button type="submit" loading={enCours}>{enEdition ? "Enregistrer" : "Créer"}</Button>
      </Group>
    </form>
  );
}
