import { useEffect, useState } from "react";
import { Alert, Badge, Button, Card, Divider, Group, NumberInput, Select, Stack, Text, TextInput, Title } from "@mantine/core";
import { Crosshair } from "lucide-react";
import { DateInput } from "@mantine/dates";
import { notifications } from "@mantine/notifications";
import { useCreateBeneficiaire, useUpdateBeneficiaire, useVerifierDoublons } from "../../api/beneficiaries";
import {
  useCreateStatutParticulier,
  useCreateTypeActiviteBeneficiaire,
  useStatutsParticuliers,
  useTypesActiviteBeneficiaire,
} from "../../api/referentiels";
import { useNiveauxAdministratifs, useZones } from "../../api/geo";
import {
  ZoneCascadeFields,
  ZONE_CASCADE_VIDE,
  zoneCascadeDepuis,
  zoneResolueDe,
  type ZoneCascadeValue,
} from "../../components/common/ZoneCascadeFields";
import { MultiSelectOrCreate } from "../../components/common/MultiSelectOrCreate";
import { messageErreurApi } from "../../utils/erreurs";
import { codeDepuisLibelle } from "../../utils/texte";
import { PAYS_MONDE } from "../../utils/pays";
import type { Beneficiaire, SignalementDoublon } from "../../types";
import { voc } from "../../utils/vocabulaire";
import { ChampsVariables } from "./ChampsVariables";

const CHAMPS_VIDES = {
  nom: "",
  prenom: "",
  sexe: "F" as string | null,
  dateNaissance: null as string | null,
  telephone: "",
  numeroPiece: "",
  pays: "BF" as string | null,
  zoneCascade: ZONE_CASCADE_VIDE,
  statutsSelectionnes: [] as string[],
  typesActiviteSelectionnes: [] as string[],
};

export function BeneficiaireForm({ beneficiaire, onDone }: { beneficiaire?: Beneficiaire; onDone: () => void }) {
  const enEdition = !!beneficiaire;
  const { data: statuts } = useStatutsParticuliers();
  const { data: typesActivite } = useTypesActiviteBeneficiaire();
  const createBeneficiaire = useCreateBeneficiaire();
  const updateBeneficiaire = useUpdateBeneficiaire();
  const verifierDoublons = useVerifierDoublons();
  const createStatutParticulier = useCreateStatutParticulier();
  const createTypeActivite = useCreateTypeActiviteBeneficiaire();

  const [nom, setNom] = useState(beneficiaire?.nom ?? CHAMPS_VIDES.nom);
  const [prenom, setPrenom] = useState(beneficiaire?.prenom ?? CHAMPS_VIDES.prenom);
  const [sexe, setSexe] = useState<string | null>(beneficiaire?.sexe ?? CHAMPS_VIDES.sexe);
  const [dateNaissance, setDateNaissance] = useState<string | null>(beneficiaire?.date_naissance ?? CHAMPS_VIDES.dateNaissance);
  const [telephone, setTelephone] = useState(beneficiaire?.telephone ?? CHAMPS_VIDES.telephone);
  const [numeroPiece, setNumeroPiece] = useState(beneficiaire?.numero_piece_identite ?? CHAMPS_VIDES.numeroPiece);
  const [pays, setPays] = useState<string | null>(beneficiaire?.pays || CHAMPS_VIDES.pays);
  const [zoneCascade, setZoneCascade] = useState<ZoneCascadeValue>(CHAMPS_VIDES.zoneCascade);
  const [zoneCascadeInitialisee, setZoneCascadeInitialisee] = useState(false);
  const [latitude, setLatitude] = useState<number | string>(beneficiaire?.latitude ?? "");
  const [longitude, setLongitude] = useState<number | string>(beneficiaire?.longitude ?? "");
  const [localisationEnCours, setLocalisationEnCours] = useState(false);

  /** Position actuelle de l'appareil (téléphone sur le terrain), via le navigateur. */
  function positionActuelle() {
    if (!navigator.geolocation) {
      notifications.show({ message: voc("Ce navigateur ne donne pas accès à la position."), color: "orange" });
      return;
    }
    setLocalisationEnCours(true);
    navigator.geolocation.getCurrentPosition(
      (position) => {
        setLatitude(Number(position.coords.latitude.toFixed(6)));
        setLongitude(Number(position.coords.longitude.toFixed(6)));
        setLocalisationEnCours(false);
      },
      () => {
        notifications.show({ message: voc("Position indisponible (autorisation refusée ?)."), color: "orange" });
        setLocalisationEnCours(false);
      },
      { enableHighAccuracy: true, timeout: 15000 },
    );
  }
  const [statutsSelectionnes, setStatutsSelectionnes] = useState<string[]>(
    beneficiaire?.statuts_particuliers.map(String) ?? CHAMPS_VIDES.statutsSelectionnes,
  );
  const [reponses, setReponses] = useState<Beneficiaire["reponses"]>(beneficiaire?.reponses ?? {});
  const [typesActiviteSelectionnes, setTypesActiviteSelectionnes] = useState<string[]>(
    beneficiaire?.types_activite.map(String) ?? CHAMPS_VIDES.typesActiviteSelectionnes,
  );
  const [doublonsDetectes, setDoublonsDetectes] = useState<SignalementDoublon[] | null>(null);
  const [beneficiaireCree, setBeneficiaireCree] = useState<Beneficiaire | null>(null);

  const { data: niveaux } = useNiveauxAdministratifs(pays);
  const { data: zonesDuPays } = useZones({ pays: pays ?? undefined });

  // La cascade région/province/village ne peut être reconstituée qu'une fois
  // la liste des zones du pays chargée (asynchrone) — impossible dès le
  // premier rendu via un simple useState initial.
  useEffect(() => {
    if (!enEdition || zoneCascadeInitialisee || !zonesDuPays) return;
    setZoneCascade(zoneCascadeDepuis(beneficiaire?.zone, zonesDuPays));
    setZoneCascadeInitialisee(true);
  }, [enEdition, zoneCascadeInitialisee, zonesDuPays, beneficiaire]);

  function reinitialiserFormulaire() {
    setNom(CHAMPS_VIDES.nom);
    setPrenom(CHAMPS_VIDES.prenom);
    setSexe(CHAMPS_VIDES.sexe);
    setDateNaissance(CHAMPS_VIDES.dateNaissance);
    setTelephone(CHAMPS_VIDES.telephone);
    setNumeroPiece(CHAMPS_VIDES.numeroPiece);
    setPays(CHAMPS_VIDES.pays);
    setZoneCascade(CHAMPS_VIDES.zoneCascade);
    setLatitude("");
    setLongitude("");
    setStatutsSelectionnes(CHAMPS_VIDES.statutsSelectionnes);
    setTypesActiviteSelectionnes(CHAMPS_VIDES.typesActiviteSelectionnes);
    setReponses({});
    setDoublonsDetectes(null);
    setBeneficiaireCree(null);
  }

  async function handleCreerStatut(libelle: string): Promise<string | null> {
    try {
      const cree = await createStatutParticulier.mutateAsync({ code: codeDepuisLibelle(libelle), libelle });
      return String(cree.id);
    } catch (error) {
      notifications.show({ message: messageErreurApi(error, voc("Erreur lors de la création du statut")), color: "red" });
      return null;
    }
  }

  async function handleCreerTypeActivite(libelle: string): Promise<string | null> {
    try {
      const cree = await createTypeActivite.mutateAsync({ code: codeDepuisLibelle(libelle), libelle });
      return String(cree.id);
    } catch (error) {
      notifications.show({ message: messageErreurApi(error, voc("Erreur lors de la création du type d'activité")), color: "red" });
      return null;
    }
  }

  async function handleSubmit() {
    if (!nom || !prenom) {
      notifications.show({ message: voc("Nom et prénom requis."), color: "orange" });
      return;
    }
    const zone = zoneResolueDe(zoneCascade, niveaux ?? []);
    const payload = {
      nom,
      prenom,
      sexe: sexe as "F" | "M",
      date_naissance: dateNaissance,
      telephone,
      numero_piece_identite: numeroPiece,
      pays: pays ?? "",
      zone,
      latitude: latitude === "" ? null : String(latitude),
      longitude: longitude === "" ? null : String(longitude),
      statuts_particuliers: statutsSelectionnes.map(Number),
      types_activite: typesActiviteSelectionnes.map(Number),
      reponses,
    };

    if (enEdition) {
      try {
        await updateBeneficiaire.mutateAsync({ id: beneficiaire.id, payload });
        notifications.show({ message: voc("Bénéficiaire modifié"), color: "green" });
        onDone();
      } catch (error) {
        notifications.show({ message: messageErreurApi(error, voc("Erreur lors de la modification")), color: "red" });
      }
      return;
    }

    try {
      const created = await createBeneficiaire.mutateAsync(payload);
      const doublons = await verifierDoublons.mutateAsync(created.id);
      setBeneficiaireCree(created);
      if (doublons.length > 0) {
        setDoublonsDetectes(doublons);
        notifications.show({
          message: voc`${doublons.length} doublon(s) potentiel(s) détecté(s) — à traiter dans l'écran « Doublons d'enregistrement ».`,
          color: "orange",
        });
      } else {
        setDoublonsDetectes(null);
        notifications.show({ message: voc("Bénéficiaire créé, aucun doublon détecté."), color: "green" });
      }
    } catch {
      notifications.show({ message: voc("Erreur lors de la création."), color: "red" });
    }
  }

  if (beneficiaireCree) {
    const libellesStatuts = beneficiaireCree.statuts_particuliers
      .map((id) => statuts?.find((s) => s.id === id)?.libelle)
      .filter(Boolean);
    const libellesTypesActivite = beneficiaireCree.types_activite
      .map((id) => typesActivite?.find((t) => t.id === id)?.libelle)
      .filter(Boolean);

    return (
      <Stack gap="sm">
        {doublonsDetectes && (
          <Alert color="orange" title={voc("Doublons potentiels détectés")}>
            {doublonsDetectes.map((d) => (
              <div key={d.id}>{d.beneficiaire_1_nom} / {d.beneficiaire_2_nom} {voc("— score")} {d.score}</div>
            ))}
          </Alert>
        )}
        <Card withBorder padding="md" radius="md">
          <Title order={4} mb="xs">{voc("Bénéficiaire enregistré")}</Title>
          <Text fw={600}>{beneficiaireCree.nom} {beneficiaireCree.prenom}</Text>
          <Text size="sm" c="dimmed">
            {beneficiaireCree.sexe === "F" ? voc("Féminin") : voc("Masculin")}
            {beneficiaireCree.tranche_age && ` · ${beneficiaireCree.tranche_age}`}
          </Text>
          {libellesStatuts.length > 0 && (
            <Group gap={6} mt="sm">
              <Text size="xs" c="dimmed" fw={600} tt="uppercase">{voc("Statuts :")}</Text>
              {libellesStatuts.map((l) => (
                <Badge key={l} variant="light" color="grape">{l}</Badge>
              ))}
            </Group>
          )}
          {libellesTypesActivite.length > 0 && (
            <Group gap={6} mt="sm">
              <Text size="xs" c="dimmed" fw={600} tt="uppercase">{voc("Activités :")}</Text>
              {libellesTypesActivite.map((l) => (
                <Badge key={l} variant="light" color="teal">{l}</Badge>
              ))}
            </Group>
          )}
        </Card>
        <Group justify="flex-end">
          <Button variant="light" onClick={reinitialiserFormulaire}>{voc("Ajouter un autre bénéficiaire")}</Button>
          <Button onClick={onDone}>{voc("Terminer")}</Button>
        </Group>
      </Stack>
    );
  }

  return (
    <Stack gap="sm">
      <Divider label={voc("Localisation")} labelPosition="left" />
      <Select
        label={voc("Pays")}
        data={PAYS_MONDE.map((p) => ({ value: p.code, label: p.nom }))}
        value={pays}
        onChange={(v) => {
          setPays(v);
          setZoneCascade(ZONE_CASCADE_VIDE);
        }}
        searchable
        maw={300}
      />
      <ZoneCascadeFields pays={pays} value={zoneCascade} onChange={setZoneCascade} />
      <Group align="flex-end" wrap="nowrap">
        <NumberInput style={{ flex: 1 }} label={voc("Latitude")} description={voc("Facultatif (carte)")} placeholder="12.3714" decimalScale={6} min={-90} max={90} value={latitude} onChange={setLatitude} />
        <NumberInput style={{ flex: 1 }} label={voc("Longitude")} description={voc("Facultatif (carte)")} placeholder="-1.5197" decimalScale={6} min={-180} max={180} value={longitude} onChange={setLongitude} />
        <Button variant="light" leftSection={<Crosshair size={15} />} loading={localisationEnCours} onClick={positionActuelle}>
          {voc("Ma position actuelle")}
        </Button>
      </Group>
      <Divider label={voc("Identité")} labelPosition="left" />
      <Group grow>
        <TextInput label={voc("Nom")} value={nom} onChange={(e) => setNom(e.currentTarget.value)} required />
        <TextInput label={voc("Prénom")} value={prenom} onChange={(e) => setPrenom(e.currentTarget.value)} required />
      </Group>
      <Group grow>
        <Select label={voc("Sexe")} data={[{ value: "F", label: voc("Féminin") }, { value: "M", label: voc("Masculin") }]} value={sexe} onChange={setSexe} />
        <DateInput label={voc("Date de naissance")} value={dateNaissance} onChange={setDateNaissance} />
      </Group>
      <Group grow>
        <TextInput label={voc("Téléphone")} value={telephone} onChange={(e) => setTelephone(e.currentTarget.value)} />
        <TextInput label={voc("N° pièce d'identité")} value={numeroPiece} onChange={(e) => setNumeroPiece(e.currentTarget.value)} />
      </Group>
      <MultiSelectOrCreate
        label={voc("Statuts particuliers")}
        description={voc("PDI, jeune, femme cheffe de ménage, personne handicapée... — tape un nouveau statut s'il manque à la liste.")}
        data={statuts?.map((s) => ({ value: String(s.id), label: s.libelle })) ?? []}
        value={statutsSelectionnes}
        onChange={setStatutsSelectionnes}
        onCreate={handleCreerStatut}
        creating={createStatutParticulier.isPending}
      />
      <MultiSelectOrCreate
        label={voc("Types d'activité menée")}
        description={voc("Maraîchage, élevage, petit commerce... — tape un nouveau type s'il manque à la liste.")}
        data={typesActivite?.map((t) => ({ value: String(t.id), label: t.libelle })) ?? []}
        value={typesActiviteSelectionnes}
        onChange={setTypesActiviteSelectionnes}
        onCreate={handleCreerTypeActivite}
        creating={createTypeActivite.isPending}
      />
      <ChampsVariables
        projetIds={[...new Set((beneficiaire?.participations ?? []).map((p) => p.projet))]}
        value={reponses}
        onChange={setReponses}
      />
      <Group justify="flex-end">
        <Button
          onClick={handleSubmit}
          loading={createBeneficiaire.isPending || verifierDoublons.isPending || updateBeneficiaire.isPending}
        >
          {enEdition ? voc("Enregistrer") : voc("Créer")}
        </Button>
      </Group>
    </Stack>
  );
}
