import { useState } from "react";
import { Link } from "react-router-dom";
import { Alert, Anchor, Button, Card, Group, Stack, Text, Textarea, TextInput, Timeline } from "@mantine/core";
import { CircleCheck } from "lucide-react";
import { dateLisible, libelleStatutDossier, STATUTS_DOSSIER, type SuiviPublic, useCompleterDossier, useSuiviPublic } from "../../../api/plaintes";
import { messageErreurApi } from "../../../utils/erreurs";
import { voc } from "../../../utils/vocabulaire";
import { ChoixFichiers } from "../ChoixFichiers";
import { erreursParChamp } from "../saisieRetour";
import { CadrePublic } from "./FormulairePublicPage";

/** Le plaignant ajoute une précision ou des fichiers ; rien du dossier n'est montré. */
function Complement({ code, suivi }: { code: string; suivi: SuiviPublic }) {
  const completer = useCompleterDossier();
  const [ouvert, setOuvert] = useState(false);
  const [texte, setTexte] = useState("");
  const [fichiers, setFichiers] = useState<File[]>([]);
  const [erreurs, setErreurs] = useState<Record<string, string>>({});
  const [envoye, setEnvoye] = useState(false);

  const envoyer = async () => {
    setErreurs({});
    try {
      await completer.mutateAsync({ code, texte, fichiers });
      setEnvoye(true);
      setTexte("");
      setFichiers([]);
      setOuvert(false);
    } catch (error) {
      const parChamp = erreursParChamp(error);
      setErreurs(Object.keys(parChamp).length ? parChamp : { detail: messageErreurApi(error, voc("L'envoi n'a pas abouti. Réessayez.")) });
    }
  };

  return (
    <Stack gap="sm">
      {envoye && (
        <Group gap="xs">
          <CircleCheck size={18} color="var(--mantine-color-teal-7)" aria-hidden />
          <Text size="sm">{voc("Merci, votre complément a été ajouté au dossier.")}</Text>
        </Group>
      )}
      {!ouvert ? (
        <Button variant="light" onClick={() => { setOuvert(true); setEnvoye(false); }} style={{ alignSelf: "flex-start" }}>
          {voc("Ajouter une précision ou un fichier")}
        </Button>
      ) : (
        <>
          <Textarea
            label={voc("Votre précision")}
            description={voc("Ce que vous voulez ajouter à votre retour (facultatif si vous joignez un fichier).")}
            autosize
            minRows={3}
            maxLength={5000}
            value={texte}
            onChange={(e) => setTexte(e.currentTarget.value)}
            error={erreurs.texte}
            dir="auto"
          />
          {suivi.pieces && <ChoixFichiers valeur={fichiers} onChange={setFichiers} limites={suivi.pieces} erreur={erreurs.fichiers} />}
          {erreurs.detail && <Alert color="red">{erreurs.detail}</Alert>}
          <Group justify="flex-end">
            <Button variant="default" onClick={() => setOuvert(false)}>{voc("Annuler")}</Button>
            <Button onClick={envoyer} loading={completer.isPending} disabled={!texte.trim() && !fichiers.length}>
              {voc("Envoyer")}
            </Button>
          </Group>
        </>
      )}
    </Stack>
  );
}

/** Suivi d'un dossier par son code (sans compte) : état général seulement, jamais le contenu. */
export function SuiviPublicPage() {
  const suivi = useSuiviPublic();
  const [code, setCode] = useState("");
  const [erreur, setErreur] = useState<string | null>(null);

  const chercher = async () => {
    setErreur(null);
    try {
      await suivi.mutateAsync(code.trim());
    } catch (error) {
      suivi.reset();
      setErreur(messageErreurApi(error, voc("Code de suivi inconnu. Vérifiez qu'il est recopié sans erreur.")));
    }
  };
  const resultat = suivi.data;

  return (
    <CadrePublic titre={voc("Suivre mon dossier")}>
      <Card withBorder>
        <Stack>
          <Group align="flex-end">
            <TextInput
              label={voc("Code de suivi")}
              placeholder="ABCD-EFGH-JKLM"
              value={code}
              onChange={(e) => setCode(e.currentTarget.value)}
              onKeyDown={(e) => e.key === "Enter" && chercher()}
              dir="ltr"
              style={{ flex: 1 }}
              styles={{ input: { fontFamily: "var(--mantine-font-family-monospace)" } }}
            />
            <Button onClick={chercher} loading={suivi.isPending} disabled={!code.trim()}>{voc("Voir l'état")}</Button>
          </Group>
          {erreur && <Alert color="orange">{erreur}</Alert>}
        </Stack>
      </Card>
      {resultat && (
        <Card withBorder>
          <Stack>
            <Text size="sm">
              {voc`Dossier ${resultat.numero}, reçu le ${dateLisible(resultat.date_reception)}`}
            </Text>
            {/* Étapes atteintes en couleur, jusqu'à l'état actuel. */}
            <Timeline active={STATUTS_DOSSIER.indexOf(resultat.statut)} bulletSize={18} lineWidth={2}>
              {STATUTS_DOSSIER.map((s) => (
                <Timeline.Item key={s} title={libelleStatutDossier(s)} fw={s === resultat.statut ? 700 : undefined} />
              ))}
            </Timeline>
            {resultat.complement_possible && <Complement code={suivi.variables ?? ""} suivi={resultat} />}
          </Stack>
        </Card>
      )}
      <Anchor component={Link} to="/plainte" size="sm">{voc("Envoyer un nouveau retour")}</Anchor>
    </CadrePublic>
  );
}
