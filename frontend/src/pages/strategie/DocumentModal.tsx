import { useMemo, useState } from "react";
import { AlertTriangle } from "lucide-react";
import {
  Alert,
  Autocomplete,
  Button,
  Checkbox,
  Group,
  Modal,
  MultiSelect,
  NumberInput,
  Pill,
  PillGroup,
  Select,
  Stack,
  Tabs,
  Text,
  Textarea,
  TextInput,
} from "@mantine/core";
import { DateInput } from "@mantine/dates";
import { notifications } from "@mantine/notifications";
import {
  useCadresStrategiques,
  useCreateCadreStrategique,
  useElementsStrategiques,
  useUpdateCadreStrategique,
} from "../../api/strategy";
import { useUtilisateurs } from "../../api/accounts";
import { useCreatePartenaire } from "../../api/referentiels";
import { usePartiesPrenantes, useStructures, useTousPartenaires } from "../../api/organisation";
import { useNiveauxAdministratifs, useZones } from "../../api/geo";
import { BailleursMontants } from "../projets/BailleursMontants";
import { type LigneBailleur, nouvelleLigneBailleur, totalBailleurs } from "../projets/lignesBailleurs";
import { SelectOrCreate } from "../../components/common/SelectOrCreate";
import {
  ZoneCascadeFields,
  ZONE_CASCADE_VIDE,
  zoneResolueDe,
  type ZoneCascadeValue,
} from "../../components/common/ZoneCascadeFields";
import type { CadreStrategique, StatutProjet, TypeDocument } from "../../types";
import { PROJET_STATUT_LABEL } from "../../utils/statusTones";
import { PAYS_MONDE } from "../../utils/pays";
import { optionsStructures } from "../../utils/organisation";
import { maillonsSautes, optionsDocumentsAuDessus, rangMaillon } from "../../utils/chaineDocuments";
import { messageErreurApi } from "../../utils/erreurs";
import { voc } from "../../utils/vocabulaire";

type Cible = "cible_totale" | "cible_hommes" | "cible_femmes" | "cible_jeunes" | "cible_pdi";
const CIBLES: [Cible, string][] = [
  ["cible_hommes", "Dont hommes"],
  ["cible_femmes", "Dont femmes"],
  ["cible_jeunes", "Dont jeunes"],
  ["cible_pdi", "Dont PDI"],
];

/** Nombre facultatif d'un NumberInput : "" → null. */
const nombreOuNull = (v: string | number) => (v === "" ? null : Number(v));

/**
 * Création ou modification d'un document d'un maillon.
 *
 * Premier maillon (cadre stratégique) : nom, description, services et parties prenantes.
 * Maillons suivants (Programme, Piliers…) : la fiche complète, sur le modèle de celle d'un projet
 * — Général (code, budget et bailleurs, dates, statut, responsable, partenaires, zones), Cibles
 * bénéficiaires, Rattachement & capitalisation (document au-dessus, élément, maillons sautés),
 * Organisation.
 */
export function DocumentModal({
  opened,
  onClose,
  cadreExistant,
  maillon,
  maillons,
}: {
  opened: boolean;
  onClose: () => void;
  cadreExistant?: CadreStrategique | null;
  maillon: TypeDocument | undefined;
  maillons: TypeDocument[];
}) {
  const c = cadreExistant;
  const createCadre = useCreateCadreStrategique();
  const updateCadre = useUpdateCadreStrategique();
  const createPartenaire = useCreatePartenaire();
  const [onglet, setOnglet] = useState<string | null>("general");

  // Champs simples, initialisés depuis le document (le modal est remonté à chaque document).
  const [nom, setNom] = useState(c?.nom ?? "");
  const [description, setDescription] = useState(c?.description ?? "");
  const [code, setCode] = useState(c?.code ?? "");
  const [fondsPropres, setFondsPropres] = useState(Number(c?.fonds_propres ?? 0));
  const [budgetTotal, setBudgetTotal] = useState(Number(c?.budget_total ?? 0));
  const [dateDebut, setDateDebut] = useState<string | null>(c?.date_debut ?? null);
  const [dateFin, setDateFin] = useState<string | null>(c?.date_fin ?? null);
  const [statut, setStatut] = useState<string>(c?.statut || "EN_PREPARATION");
  const [typeMiseEnOeuvre, setTypeMiseEnOeuvre] = useState(c?.type_mise_en_oeuvre ?? "DIRECT");
  const [responsable, setResponsable] = useState(c?.responsable_nom ?? "");
  const [utilisateursIds, setUtilisateursIds] = useState<string[]>((c?.utilisateurs_affectes ?? []).map(String));
  const [lignesBailleurs, setLignesBailleurs] = useState<LigneBailleur[]>(
    (c?.financements ?? []).map((f) => nouvelleLigneBailleur(f.bailleur_nom, Number(f.montant))),
  );
  const [partenaireMO, setPartenaireMO] = useState<string | null>(c?.partenaire_mise_en_oeuvre ? String(c.partenaire_mise_en_oeuvre) : null);
  const [consortiumIds, setConsortiumIds] = useState<string[]>((c?.partenaires_consortium ?? []).map(String));
  const [pays, setPays] = useState<string[]>(c?.pays ?? []);
  const [toutLePays, setToutLePays] = useState(c?.tout_le_pays ?? false);
  const [zonesAjoutees, setZonesAjoutees] = useState<{ id: number; label: string }[]>(
    (c?.zones ?? []).map((id, i) => ({ id, label: c?.zones_noms?.[i] ?? String(id) })),
  );
  const [zoneCascade, setZoneCascade] = useState<ZoneCascadeValue>(ZONE_CASCADE_VIDE);
  const [paysZone, setPaysZone] = useState<string | null>(c?.pays?.[0] ?? null);
  const [cibles, setCibles] = useState<Record<Cible, number | null>>({
    cible_totale: c?.cible_totale ?? null,
    cible_hommes: c?.cible_hommes ?? null,
    cible_femmes: c?.cible_femmes ?? null,
    cible_jeunes: c?.cible_jeunes ?? null,
    cible_pdi: c?.cible_pdi ?? null,
  });
  const [capitalisation, setCapitalisation] = useState(c?.elements_capitalisation ?? "");
  const [structuresIds, setStructuresIds] = useState<string[]>((c?.structures ?? []).map(String));
  const [partiesIds, setPartiesIds] = useState<string[]>((c?.parties_prenantes ?? []).map(String));
  const [parentId, setParentId] = useState<string | null>(c?.document_parent ? String(c.document_parent) : null);
  const [elementId, setElementId] = useState<string | null>(c?.element_parent ? String(c.element_parent) : null);
  const [secondairesIds, setSecondairesIds] = useState<string[]>((c?.elements_parents_secondaires ?? []).map(String));

  const { data: structures } = useStructures();
  const { data: partiesPrenantes } = usePartiesPrenantes();
  const { data: partenaires } = useTousPartenaires();
  const { data: utilisateurs } = useUtilisateurs();
  const { data: tousDocuments } = useCadresStrategiques();
  const { data: elementsParent } = useElementsStrategiques(parentId ? { cadre_strategique: Number(parentId) } : undefined, !!parentId);
  const { data: niveauxPaysZone } = useNiveauxAdministratifs(paysZone);
  const { data: zonesPays } = useZones({ pays: paysZone ?? undefined });

  const rang = rangMaillon(maillon?.id, maillons);
  const fiche = rang > 0;
  const parent = (tousDocuments ?? []).find((d) => String(d.id) === parentId);
  const sautes = parent ? maillonsSautes(rangMaillon(parent.type_document, maillons), rang, maillons) : [];
  const totalFinancements = totalBailleurs(lignesBailleurs);

  const optionsPartenaires = useMemo(
    () => (partenaires ?? []).filter((p) => p.type !== "BAILLEUR").map((p) => ({ value: String(p.id), label: p.nom })),
    [partenaires],
  );
  const nomUtilisateur = (u: { first_name: string; last_name: string; username: string }) =>
    `${u.first_name} ${u.last_name}`.trim() || u.username;

  function ajouterZone() {
    const zoneId = zoneResolueDe(zoneCascade, niveauxPaysZone ?? []);
    const zone = zonesPays?.find((z) => z.id === zoneId);
    if (zone && !zonesAjoutees.some((z) => z.id === zone.id)) setZonesAjoutees((prev) => [...prev, { id: zone.id, label: zone.nom }]);
    setZoneCascade(ZONE_CASCADE_VIDE);
  }

  async function handleSave() {
    if (!nom.trim()) {
      setOnglet("general");
      notifications.show({ message: voc("Le nom est requis."), color: "orange" });
      return;
    }
    const bailleurs = lignesBailleurs.filter((l) => l.nom.trim()).map((l) => ({ nom: l.nom.trim(), montant: l.montant ?? 0 }));
    const champs: Partial<CadreStrategique> = {
      nom: nom.trim(),
      description,
      structures: structuresIds.map(Number),
      parties_prenantes: partiesIds.map(Number),
      type_document: maillon?.id ?? null,
      document_parent: parentId ? Number(parentId) : null,
      element_parent: parentId && elementId ? Number(elementId) : null,
      elements_parents_secondaires: parentId ? secondairesIds.filter((id) => id !== elementId).map(Number) : [],
      ...(fiche && {
        code: code.trim(),
        fonds_propres: String(fondsPropres),
        // Avec des bailleurs, le serveur recalcule : fonds propres + financements.
        budget_total: String(bailleurs.length ? fondsPropres + totalFinancements : budgetTotal),
        date_debut: dateDebut || null,
        date_fin: dateFin || null,
        statut: statut as StatutProjet,
        type_mise_en_oeuvre: typeMiseEnOeuvre,
        responsable_nom: responsable,
        utilisateurs_affectes: utilisateursIds.map(Number),
        partenaire_mise_en_oeuvre: partenaireMO ? Number(partenaireMO) : null,
        partenaires_consortium: typeMiseEnOeuvre === "CONSORTIUM" ? consortiumIds.map(Number) : [],
        pays,
        tout_le_pays: toutLePays,
        zones: toutLePays ? [] : zonesAjoutees.map((z) => z.id),
        ...cibles,
        elements_capitalisation: capitalisation,
        bailleurs,
      }),
    };
    try {
      const enregistre = c
        ? await updateCadre.mutateAsync({ id: c.id, payload: champs })
        : await createCadre.mutateAsync(champs);
      notifications.show({ message: voc("Document enregistré"), color: "green" });
      for (const message of enregistre?.alertes_chaine ?? []) notifications.show({ message: voc(message), color: "orange" });
      onClose();
    } catch (error) {
      notifications.show({ message: messageErreurApi(error, voc("Erreur lors de l'enregistrement")), color: "red" });
    }
  }

  const libelleMaillon = maillon?.nom ?? voc("Cadre stratégique");

  const rattachement = fiche && (
    <>
      <Select
        label={voc("Rattaché à (document)")}
        description={voc("Document d'un maillon au-dessus. Sauter un maillon est permis.")}
        placeholder={voc("Aucun pour l'instant")}
        data={optionsDocumentsAuDessus(rang, tousDocuments ?? [], maillons, c?.id)}
        value={parentId}
        onChange={(v) => {
          setParentId(v);
          setElementId(null);
          setSecondairesIds([]);
        }}
        searchable
        clearable
      />
      {parentId && (
        <Select
          label={voc("Élément de ce document")}
          description={voc("Vide : rattaché au document lui-même.")}
          placeholder={voc("Le document lui-même")}
          data={(elementsParent ?? []).map((e) => ({ value: String(e.id), label: `${e.type_niveau_nom} : ${e.code ? `${e.code} — ` : ""}${e.nom}` }))}
          value={elementId}
          onChange={setElementId}
          searchable
          clearable
        />
      )}
      {parentId && (
        <MultiSelect
          label={voc("Rattaché aussi à (pour information)")}
          description={voc("Autres éléments de ce document servis par celui-ci : affichés, mais seul l'élément ci-dessus compte dans les budgets et les taux (pas de double compte). Pour répartir réellement, utiliser « Contribue à » sur chaque élément de la structuration.")}
          placeholder={voc("Aucun")}
          data={(elementsParent ?? [])
            .filter((e) => String(e.id) !== elementId)
            .map((e) => ({ value: String(e.id), label: `${e.type_niveau_nom} : ${e.code ? `${e.code} — ` : ""}${e.nom}` }))}
          value={secondairesIds.filter((id) => id !== elementId)}
          onChange={setSecondairesIds}
          searchable
          clearable
        />
      )}
      {sautes.length > 0 && (
        <Alert color="orange" variant="light" icon={<AlertTriangle size={16} />} py={6}>
          {voc`Maillon(s) sauté(s) : ${sautes.join(", ")}.`}
        </Alert>
      )}
    </>
  );

  const organisation = (
    <>
      <MultiSelect
        label={voc("Services chargés")}
        placeholder={voc("Aucun")}
        data={optionsStructures(structures ?? [])}
        value={structuresIds}
        onChange={setStructuresIds}
        searchable
        clearable
      />
      <MultiSelect
        label={voc("Parties prenantes")}
        placeholder={voc("Aucune")}
        data={(partiesPrenantes ?? []).map((p) => ({ value: String(p.id), label: p.nom }))}
        value={partiesIds}
        onChange={setPartiesIds}
        searchable
        clearable
      />
    </>
  );

  return (
    <Modal
      opened={opened}
      onClose={onClose}
      size={fiche ? "xl" : "md"}
      title={c ? voc`Modifier — ${c.nom}` : voc`Nouveau document — ${libelleMaillon}`}
    >
      {!fiche ? (
        <Stack gap="sm">
          <TextInput label={voc("Nom")} description={voc("Ex : « Cadre stratégique 2022-2026 »")} value={nom} onChange={(e) => setNom(e.currentTarget.value)} required />
          <Textarea label={voc("Description")} minRows={2} value={description} onChange={(e) => setDescription(e.currentTarget.value)} />
          {organisation}
        </Stack>
      ) : (
        <Tabs value={onglet} onChange={setOnglet}>
          <Tabs.List>
            <Tabs.Tab value="general">{voc("Général")}</Tabs.Tab>
            <Tabs.Tab value="cibles">{voc("Cibles bénéficiaires")}</Tabs.Tab>
            <Tabs.Tab value="rattachement">{voc("Rattachement & capitalisation")}</Tabs.Tab>
            <Tabs.Tab value="organisation">{voc("Organisation")}</Tabs.Tab>
          </Tabs.List>

          <Tabs.Panel value="general" pt="sm">
            <Stack gap="sm">
              <TextInput label={voc`Nom — ${libelleMaillon}`} value={nom} onChange={(e) => setNom(e.currentTarget.value)} required />
              <TextInput label={voc("Code")} value={code} onChange={(e) => setCode(e.currentTarget.value)} />
              <Textarea label={voc("Description")} minRows={2} autosize value={description} onChange={(e) => setDescription(e.currentTarget.value)} />
              <Group grow>
                {totalFinancements > 0 ? (
                  <NumberInput
                    label={voc("Budget total (FCFA)")}
                    description={voc("Fonds propres + financements des bailleurs")}
                    value={fondsPropres + totalFinancements}
                    thousandSeparator=" "
                    disabled
                  />
                ) : (
                  <NumberInput label={voc("Budget total (FCFA)")} value={budgetTotal} onChange={(v) => setBudgetTotal(Number(v) || 0)} min={0} thousandSeparator=" " />
                )}
                <NumberInput label={voc("Fonds propres (FCFA)")} value={fondsPropres} onChange={(v) => setFondsPropres(Number(v) || 0)} min={0} thousandSeparator=" " />
              </Group>
              <Group grow>
                <DateInput label={voc("Date de début prévue")} value={dateDebut} onChange={setDateDebut} clearable />
                <DateInput label={voc("Date de fin prévue")} value={dateFin} onChange={setDateFin} minDate={dateDebut ?? undefined} clearable />
              </Group>
              <Group grow>
                <Select
                  label={voc("Statut")}
                  data={Object.entries(PROJET_STATUT_LABEL).map(([value, label]) => ({ value, label }))}
                  value={statut}
                  onChange={(v) => setStatut(v ?? "EN_PREPARATION")}
                  allowDeselect={false}
                />
                <Select
                  label={voc("Type de mise en œuvre")}
                  data={[{ value: "DIRECT", label: voc("Direct") }, { value: "CONSORTIUM", label: voc("En consortium") }]}
                  value={typeMiseEnOeuvre}
                  onChange={(v) => setTypeMiseEnOeuvre((v ?? "DIRECT") as "DIRECT" | "CONSORTIUM")}
                  allowDeselect={false}
                />
              </Group>
              <Autocomplete
                label={voc("Responsable")}
                description={voc("Choisis un utilisateur ou tape librement un nom (structure, direction…) : simple intitulé affiché.")}
                data={[...new Set((utilisateurs ?? []).map(nomUtilisateur))]}
                value={responsable}
                onChange={setResponsable}
              />
              <MultiSelect
                label={voc("Utilisateurs affectés (accès à la plateforme)")}
                description={voc("Les utilisateurs à visibilité restreinte affectés ici voient ce document, en plus de ceux de leurs projets.")}
                placeholder={voc("Rechercher un utilisateur…")}
                data={(utilisateurs ?? []).map((u) => ({ value: String(u.id), label: `${nomUtilisateur(u)} (${u.username})` }))}
                value={utilisateursIds}
                onChange={setUtilisateursIds}
                searchable
                clearable
              />
              <BailleursMontants
                lignes={lignesBailleurs}
                onChange={setLignesBailleurs}
                messageVide={voc("Aucun bailleur : financé sur fonds propres.")}
              />
              <SelectOrCreate
                label={voc("Partenaire de mise en œuvre")}
                data={optionsPartenaires}
                value={partenaireMO}
                onChange={setPartenaireMO}
                clearable
                creating={createPartenaire.isPending}
                onCreate={async (nomPartenaire) => {
                  try {
                    const cree = await createPartenaire.mutateAsync({ nom: nomPartenaire, type: "MISE_EN_OEUVRE" });
                    setPartenaireMO(String(cree.id));
                  } catch {
                    notifications.show({ message: voc("Erreur lors de la création du partenaire"), color: "red" });
                  }
                }}
              />
              {typeMiseEnOeuvre === "CONSORTIUM" && (
                <MultiSelect
                  label={voc("Partenaires du consortium")}
                  placeholder={voc("Aucun")}
                  data={optionsPartenaires}
                  value={consortiumIds}
                  onChange={setConsortiumIds}
                  searchable
                  clearable
                />
              )}
              <MultiSelect
                label={voc("Pays d'intervention")}
                placeholder={voc("Rechercher un ou plusieurs pays…")}
                data={PAYS_MONDE.map((p) => ({ value: p.code, label: p.nom }))}
                value={pays}
                onChange={(v) => {
                  setPays(v);
                  if (!paysZone || !v.includes(paysZone)) {
                    setPaysZone(v[0] ?? null);
                    setZoneCascade(ZONE_CASCADE_VIDE);
                  }
                }}
                searchable
                clearable
              />
              <div>
                <Text size="sm" fw={500} mb={4}>{voc("Zones d'intervention")}</Text>
                <Checkbox
                  label={voc("Tout le pays (ensemble du territoire des pays d'intervention)")}
                  checked={toutLePays}
                  onChange={(e) => setToutLePays(e.currentTarget.checked)}
                  mb="xs"
                />
                {!toutLePays && (
                  <>
                    {pays.length > 1 && (
                      <Select
                        size="xs"
                        label={voc("Pays de la zone à ajouter")}
                        data={pays.map((p) => ({ value: p, label: PAYS_MONDE.find((x) => x.code === p)?.nom ?? p }))}
                        value={paysZone}
                        onChange={(v) => {
                          setPaysZone(v);
                          setZoneCascade(ZONE_CASCADE_VIDE);
                        }}
                        mb={4}
                        maw={250}
                      />
                    )}
                    <ZoneCascadeFields pays={paysZone} value={zoneCascade} onChange={setZoneCascade} />
                    <Group justify="flex-end" mt={4}>
                      <Button size="xs" variant="light" onClick={ajouterZone}>{voc("Ajouter cette zone")}</Button>
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
              <NumberInput
                label={voc("Cible totale")}
                value={cibles.cible_totale ?? ""}
                onChange={(v) => setCibles((p) => ({ ...p, cible_totale: nombreOuNull(v) }))}
                min={0}
                thousandSeparator=" "
              />
              <Group grow>
                {CIBLES.slice(0, 2).map(([champ, libelle]) => (
                  <NumberInput key={champ} label={voc(libelle)} value={cibles[champ] ?? ""} onChange={(v) => setCibles((p) => ({ ...p, [champ]: nombreOuNull(v) }))} min={0} thousandSeparator=" " />
                ))}
              </Group>
              <Group grow>
                {CIBLES.slice(2).map(([champ, libelle]) => (
                  <NumberInput key={champ} label={voc(libelle)} value={cibles[champ] ?? ""} onChange={(v) => setCibles((p) => ({ ...p, [champ]: nombreOuNull(v) }))} min={0} thousandSeparator=" " />
                ))}
              </Group>
            </Stack>
          </Tabs.Panel>

          <Tabs.Panel value="rattachement" pt="sm">
            <Stack gap="sm">
              {rattachement}
              <Textarea
                label={voc("Éléments de capitalisation")}
                description={voc("Leçons apprises, bonnes pratiques.")}
                minRows={3}
                autosize
                value={capitalisation}
                onChange={(e) => setCapitalisation(e.currentTarget.value)}
              />
            </Stack>
          </Tabs.Panel>

          <Tabs.Panel value="organisation" pt="sm">
            <Stack gap="sm">{organisation}</Stack>
          </Tabs.Panel>
        </Tabs>
      )}
      <Group justify="flex-end" mt="md">
        <Button onClick={handleSave} loading={createCadre.isPending || updateCadre.isPending}>
          {c ? voc("Enregistrer") : voc("Créer")}
        </Button>
      </Group>
    </Modal>
  );
}
