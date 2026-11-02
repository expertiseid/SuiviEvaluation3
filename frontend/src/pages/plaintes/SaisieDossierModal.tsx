import { useState } from "react";
import { Lock, ShieldAlert } from "lucide-react";
import { Alert, Button, Group, Modal, Select, SimpleGrid, Stack, Switch, Text } from "@mantine/core";
import { DateInput } from "@mantine/dates";
import {
  CANAUX_AGENT,
  type CanalPlainte,
  type RecuDossier,
  type SaisieAgent,
  libelleCanal,
  useCategoriesPlainte,
  useEnregistrerDossier,
  useMecanisme,
  usePrioritesPlainte,
  useTypesRetour,
} from "../../api/plaintes";
import { useProjets } from "../../api/projects";
import { useAuth } from "../../auth/useAuth";
import { messageErreurApi } from "../../utils/erreurs";
import { langue } from "../../utils/i18n";
import { voc } from "../../utils/vocabulaire";
import { ChampsRetour } from "./ChampsRetour";
import { RETOUR_VIDE, erreursParChamp } from "./saisieRetour";
import { RecuRetour } from "./public/FormulairePublicPage";

const aujourdhui = () => new Date().toISOString().slice(0, 10);

const SAISIE_VIDE = (): SaisieAgent => ({
  ...RETOUR_VIDE,
  canal: null,
  date_reception: aujourdhui(),
  recueilli_directement: true,
  priorite: null,
});

/**
 * Saisie d'un retour reçu par téléphone, oralement, sur le terrain, par courrier ou dans une
 * boîte à suggestions. Aucun champ n'oblige l'agent à saisir une information qu'il n'a pas.
 * Un retour sensible est transmis au circuit confidentiel : l'agent n'en garde que le numéro.
 */
export function SaisieDossierModal({ opened, onClose }: { opened: boolean; onClose: () => void }) {
  const { data: mecanisme } = useMecanisme();
  const { data: types = [] } = useTypesRetour();
  const { data: categories = [] } = useCategoriesPlainte();
  const { data: priorites = [] } = usePrioritesPlainte();
  const { data: tousProjets = [] } = useProjets();
  const enregistrer = useEnregistrerDossier();
  // L'Administrateur voit tous les dossiers, y compris confidentiels.
  const estAdmin = useAuth().user?.role === "ADMIN";
  const [valeurs, setValeurs] = useState<SaisieAgent>(SAISIE_VIDE);
  const [erreurs, setErreurs] = useState<Record<string, string>>({});
  const [recu, setRecu] = useState<RecuDossier | null>(null);

  const couverts = mecanisme?.projets ?? [];
  const projets = couverts.length ? tousProjets.filter((p) => couverts.includes(p.id)) : tousProjets;
  const categoriesActives = categories.filter((c) => c.actif);
  const categorie = categories.find((c) => c.id === valeurs.categorie);
  // Même règle que le serveur : catégorie sensible, ou retour visant le personnel.
  const sensible = !!categorie?.sensible_effective || valeurs.concerne_personnel === true;

  const fermer = () => {
    setValeurs(SAISIE_VIDE());
    setErreurs({});
    setRecu(null);
    onClose();
  };

  const envoyer = async () => {
    setErreurs({});
    try {
      setRecu(await enregistrer.mutateAsync({ ...valeurs, langue: langue() }));
    } catch (error) {
      const parChamp = erreursParChamp(error);
      setErreurs(Object.keys(parChamp).length ? parChamp : { detail: messageErreurApi(error, voc("Erreur lors de l'enregistrement")) });
    }
  };

  return (
    <Modal opened={opened} onClose={fermer} title={voc("Enregistrer un retour")} size="xl">
      {recu ? (
        <Stack>
          {recu.sensible && !recu.visible ? (
            <Alert color="grape" icon={<Lock size={18} />} title={voc("Transmis au circuit confidentiel")}>
              {voc("Ce dossier est désormais réservé aux personnes désignées. Il n'apparaîtra plus dans vos listes : seul son numéro vous reste.")}
            </Alert>
          ) : (
            <Alert color={recu.sensible ? "grape" : "teal"} icon={recu.sensible ? <Lock size={18} /> : undefined} title={recu.sensible ? voc("Transmis au circuit confidentiel") : voc("Retour enregistré")}>
              {voc("Le dossier figure maintenant dans la liste.")}
            </Alert>
          )}
          <RecuRetour recu={recu} agent />
          <Group justify="flex-end">
            <Button variant="light" onClick={() => { setValeurs(SAISIE_VIDE()); setRecu(null); }}>{voc("Enregistrer un autre retour")}</Button>
            <Button onClick={fermer}>{voc("Fermer")}</Button>
          </Group>
        </Stack>
      ) : (
        <Stack>
          <SimpleGrid cols={{ base: 1, sm: 3 }} spacing="sm">
            <Select
              label={voc("Canal de réception")}
              withAsterisk
              data={CANAUX_AGENT.map((c) => ({ value: c, label: libelleCanal(c) }))}
              value={valeurs.canal}
              onChange={(v) => setValeurs((s) => ({ ...s, canal: v as CanalPlainte | null }))}
              error={erreurs.canal}
            />
            <DateInput
              label={voc("Date de réception")}
              value={valeurs.date_reception}
              onChange={(v) => setValeurs((s) => ({ ...s, date_reception: v }))}
              valueFormat="DD/MM/YYYY"
              maxDate={aujourdhui()}
              error={erreurs.date_reception}
            />
            <Select
              label={voc("Priorité")}
              placeholder={voc("À évaluer plus tard")}
              data={priorites.filter((p) => p.actif).map((p) => ({ value: String(p.id), label: p.nom }))}
              value={valeurs.priorite ? String(valeurs.priorite) : null}
              onChange={(v) => setValeurs((s) => ({ ...s, priorite: v ? Number(v) : null }))}
              clearable
            />
          </SimpleGrid>
          <Switch
            label={voc("Recueilli directement auprès du plaignant")}
            checked={valeurs.recueilli_directement}
            onChange={(e) => { const coche = e.currentTarget.checked; setValeurs((s) => ({ ...s, recueilli_directement: coche })); }}
          />
          <ChampsRetour
            agent
            valeurs={valeurs}
            onChange={(v) => setValeurs((s) => ({ ...s, ...v }))}
            types={types.filter((t) => t.actif)}
            categories={categoriesActives}
            projets={projets}
            anonymatAutorise={!!mecanisme?.anonymat_autorise}
            erreurs={erreurs}
          />
          <Switch
            label={voc("Le plaignant accepte que ses informations soient utilisées pour traiter son retour")}
            checked={valeurs.consentement}
            onChange={(e) => { const coche = e.currentTarget.checked; setValeurs((s) => ({ ...s, consentement: coche })); }}
          />
          {sensible && (
            <Alert color="grape" icon={<ShieldAlert size={18} />} title={voc("Retour sensible : circuit confidentiel")}>
              <Text size="sm">
                {estAdmin
                  ? voc("Ce dossier sera traité dans le circuit confidentiel : seuls l'Administrateur et les personnes désignées par l'organisation y ont accès. N'en parlez qu'aux personnes prévues par les règles de confidentialité et de signalement de votre organisation.")
                  : voc("Dès l'envoi, ce dossier est réservé aux personnes désignées par l'organisation et vous ne pourrez plus le consulter ; seul son numéro vous restera. N'en parlez qu'aux personnes prévues par les règles de confidentialité et de signalement de votre organisation.")}
              </Text>
            </Alert>
          )}
          {erreurs.detail && <Alert color="red">{erreurs.detail}</Alert>}
          <Group justify="flex-end">
            <Button variant="default" onClick={fermer}>{voc("Annuler")}</Button>
            <Button color={sensible ? "grape" : undefined} leftSection={sensible ? <Lock size={14} /> : undefined} onClick={envoyer} loading={enregistrer.isPending}>
              {sensible ? voc("Transmettre au circuit confidentiel") : voc("Enregistrer")}
            </Button>
          </Group>
        </Stack>
      )}
    </Modal>
  );
}
