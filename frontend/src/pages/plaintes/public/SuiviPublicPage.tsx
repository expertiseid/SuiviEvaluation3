import { useState } from "react";
import { Link } from "react-router-dom";
import { Alert, Anchor, Button, Card, Group, Stack, Text, TextInput, Timeline } from "@mantine/core";
import { dateLisible, libelleStatutDossier, STATUTS_DOSSIER, useSuiviPublic } from "../../../api/plaintes";
import { messageErreurApi } from "../../../utils/erreurs";
import { voc } from "../../../utils/vocabulaire";
import { CadrePublic } from "./FormulairePublicPage";

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
          </Stack>
        </Card>
      )}
      <Anchor component={Link} to="/plainte" size="sm">{voc("Envoyer un nouveau retour")}</Anchor>
    </CadrePublic>
  );
}
