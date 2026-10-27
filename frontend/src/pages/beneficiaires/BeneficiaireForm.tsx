import { useEffect, useState } from "react";
import { Alert, Badge, Button, Card, Group, Select, Stack, Text, TextInput, Title } from "@mantine/core";
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
  const [statutsSelectionnes, setStatutsSelectionnes] = useState<string[]>(
    beneficiaire?.statuts_particuliers.map(String) ?? CHAMPS_VIDES.statutsSelectionnes,
  );
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
    setStatutsSelectionnes(CHAMPS_VIDES.statutsSelectionnes);
    setTypesActiviteSelectionnes(CHAMPS_VIDES.typesActiviteSelectionnes);
    setDoublonsDetectes(null);
    setBeneficiaireCree(null);
  }

  async function handleCreerStatut(libelle: string): Promise<string | null> {
    try {
      const cree = await createStatutParticulier.mutateAsync({ code: codeDepuisLibelle(libelle), libelle });
      return String(cree.id);
    } catch (error) {
      notifications.show({ message: messageErreurApi(error, "Erreur lors de la création du statut"), color: "red" });
      return null;
    }
  }

  async function handleCreerTypeActivite(libelle: string): Promise<string | null> {
    try {
      const cree = await createTypeActivite.mutateAsync({ code: codeDepuisLibelle(libelle), libelle });
      return String(cree.id);
    } catch (error) {
      notifications.show({ message: messageErreurApi(error, "Erreur lors de la création du type d'activité"), color: "red" });
      return null;
    }
  }

  async function handleSubmit() {
    if (!nom || !prenom) {
      notifications.show({ message: "Nom et prénom requis.", color: "orange" });
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
      statuts_particuliers: statutsSelectionnes.map(Number),
      types_activite: typesActiviteSelectionnes.map(Number),
    };

    if (enEdition) {
      try {
        await updateBeneficiaire.mutateAsync({ id: beneficiaire.id, payload });
        notifications.show({ message: voc("Bénéficiaire modifié"), color: "green" });
        onDone();
      } catch (error) {
        notifications.show({ message: messageErreurApi(error, "Erreur lors de la modification"), color: "red" });
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
          message: voc`${doublons.length} doublon(s) potentiel(s) détecté(s) — à traiter dans l'écran "Doublons signalés".`,
          color: "orange",
        });
      } else {
        setDoublonsDetectes(null);
        notifications.show({ message: voc("Bénéficiaire créé, aucun doublon détecté."), color: "green" });
      }
    } catch {
      notifications.show({ message: "Erreur lors de la création.", color: "red" });
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
              <div key={d.id}>{d.beneficiaire_1_nom} / {d.beneficiaire_2_nom} — score {d.score}</div>
            ))}
          </Alert>
        )}
        <Card withBorder padding="md" radius="md">
          <Title order={4} mb="xs">{voc("Bénéficiaire enregistré")}</Title>
          <Text fw={600}>{beneficiaireCree.nom} {beneficiaireCree.prenom}</Text>
          <Text size="sm" c="dimmed">
            {beneficiaireCree.sexe === "F" ? "Féminin" : "Masculin"}
            {beneficiaireCree.tranche_age && ` · ${beneficiaireCree.tranche_age}`}
          </Text>
          {libellesStatuts.length > 0 && (
            <Group gap={6} mt="sm">
              <Text size="xs" c="dimmed" fw={600} tt="uppercase">Statuts :</Text>
              {libellesStatuts.map((l) => (
                <Badge key={l} variant="light" color="grape">{l}</Badge>
              ))}
            </Group>
          )}
          {libellesTypesActivite.length > 0 && (
            <Group gap={6} mt="sm">
              <Text size="xs" c="dimmed" fw={600} tt="uppercase">Activités :</Text>
              {libellesTypesActivite.map((l) => (
                <Badge key={l} variant="light" color="teal">{l}</Badge>
              ))}
            </Group>
          )}
        </Card>
        <Group justify="flex-end">
          <Button variant="light" onClick={reinitialiserFormulaire}>{voc("Ajouter un autre bénéficiaire")}</Button>
          <Button onClick={onDone}>Terminer</Button>
        </Group>
      </Stack>
    );
  }

  return (
    <Stack gap="sm">
      <Group grow>
        <TextInput label="Nom" value={nom} onChange={(e) => setNom(e.currentTarget.value)} required />
        <TextInput label="Prénom" value={prenom} onChange={(e) => setPrenom(e.currentTarget.value)} required />
      </Group>
      <Group grow>
        <Select label="Sexe" data={[{ value: "F", label: "Féminin" }, { value: "M", label: "Masculin" }]} value={sexe} onChange={setSexe} />
        <DateInput label="Date de naissance" value={dateNaissance} onChange={setDateNaissance} />
      </Group>
      <Group grow>
        <TextInput label="Téléphone" value={telephone} onChange={(e) => setTelephone(e.currentTarget.value)} />
        <TextInput label="N° pièce d'identité" value={numeroPiece} onChange={(e) => setNumeroPiece(e.currentTarget.value)} />
      </Group>
      <Select
        label="Pays"
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
      <MultiSelectOrCreate
        label="Statuts particuliers"
        description="PDI, jeune, femme cheffe de ménage, personne handicapée... — tape un nouveau statut s'il manque à la liste."
        data={statuts?.map((s) => ({ value: String(s.id), label: s.libelle })) ?? []}
        value={statutsSelectionnes}
        onChange={setStatutsSelectionnes}
        onCreate={handleCreerStatut}
        creating={createStatutParticulier.isPending}
      />
      <MultiSelectOrCreate
        label="Types d'activité menée"
        description="Maraîchage, élevage, petit commerce... — tape un nouveau type s'il manque à la liste."
        data={typesActivite?.map((t) => ({ value: String(t.id), label: t.libelle })) ?? []}
        value={typesActiviteSelectionnes}
        onChange={setTypesActiviteSelectionnes}
        onCreate={handleCreerTypeActivite}
        creating={createTypeActivite.isPending}
      />
      <Group justify="flex-end">
        <Button
          onClick={handleSubmit}
          loading={createBeneficiaire.isPending || verifierDoublons.isPending || updateBeneficiaire.isPending}
        >
          {enEdition ? "Enregistrer" : "Créer"}
        </Button>
      </Group>
    </Stack>
  );
}
