import { useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { Alert, Anchor, Box, Button, Center, Loader, Paper, PasswordInput, Stack, Text } from "@mantine/core";
import { useQuery } from "@tanstack/react-query";
import { CircleCheck } from "lucide-react";
import { changerMotDePasse, verifierLienMotDePasse } from "../api/doubleAuth";
import { LogoPlateforme, PiedDePage } from "../components/common/Logos";
import { ChoixLangue } from "../components/common/ChoixLangue";
import { messageErreurApi } from "../utils/erreurs";
import { voc } from "../utils/vocabulaire";

const LONGUEUR_MIN = 8;

/**
 * Lien « mot de passe oublié » reçu par courriel (?jeton=) : choix d'un nouveau mot de passe. Le lien est
 * vérifié à l'ouverture (déjà servi, expiré) ; une fois le mot de passe changé, on se connecte normalement.
 */
export function NouveauMotDePassePage() {
  const [params] = useSearchParams();
  const jeton = params.get("jeton") ?? "";
  const lien = useQuery({
    queryKey: ["lien-mot-de-passe", jeton],
    queryFn: () => verifierLienMotDePasse(jeton),
    enabled: !!jeton,
    retry: false,
    staleTime: Infinity,
  });
  const [motDePasse, setMotDePasse] = useState("");
  const [confirmation, setConfirmation] = useState("");
  const [erreur, setErreur] = useState<string | null>(null);
  const [envoi, setEnvoi] = useState(false);
  const [fait, setFait] = useState(false);

  async function enregistrer(event: React.FormEvent) {
    event.preventDefault();
    setErreur(null);
    if (motDePasse.length < LONGUEUR_MIN) return setErreur(voc`Le mot de passe doit contenir au moins ${LONGUEUR_MIN} caractères.`);
    if (/^\d+$/.test(motDePasse)) return setErreur(voc("Le mot de passe ne peut pas être composé uniquement de chiffres."));
    if (motDePasse !== confirmation) return setErreur(voc("Les deux mots de passe ne sont pas identiques."));
    setEnvoi(true);
    try {
      await changerMotDePasse(jeton, motDePasse);
      setFait(true);
    } catch (e) {
      setErreur(messageErreurApi(e, voc("Le mot de passe n'a pas pu être changé.")));
    } finally {
      setEnvoi(false);
    }
  }

  const invalide = !jeton || lien.isError;
  return (
    <Box mih="100vh" bg="teal.9" style={{ display: "flex", flexDirection: "column" }}>
      <Center style={{ flex: 1 }} py="lg">
        <Paper shadow="md" radius="md" p="xl" w={420} maw="calc(100vw - 32px)" withBorder pos="relative">
          <div style={{ position: "absolute", top: 8, insetInlineEnd: 8 }}>
            <ChoixLangue connecte={false} couleur="gray" />
          </div>
          <Stack gap="md">
            <LogoPlateforme taille={38} />
            <Text fw={600}>{voc("Choisir un nouveau mot de passe")}</Text>
            {fait ? (
              <Stack gap="sm">
                <Alert color="teal" icon={<CircleCheck size={18} />}>{voc("Votre mot de passe a été changé. Vous pouvez vous connecter.")}</Alert>
                <Button component={Link} to="/login" fullWidth>{voc("Se connecter")}</Button>
              </Stack>
            ) : invalide ? (
              <Stack gap="sm">
                <Alert color="red">
                  {lien.isError
                    ? messageErreurApi(lien.error, "Ce lien n'est plus valable : il a déjà servi ou a expiré. Demandez-en un nouveau.")
                    : voc("Ce lien n'est plus valable : il a déjà servi ou a expiré. Demandez-en un nouveau.")}
                </Alert>
                <Button component={Link} to="/login" variant="light" fullWidth>{voc("Revenir à la connexion")}</Button>
              </Stack>
            ) : lien.isLoading ? (
              <Center py="md"><Loader size="sm" /></Center>
            ) : (
              <form onSubmit={enregistrer}>
                <Stack gap="sm">
                  <Text size="sm" c="dimmed" dir="ltr" ta="start">{lien.data?.compte}</Text>
                  {erreur && <Alert color="red" p="xs">{erreur}</Alert>}
                  <PasswordInput label={voc("Nouveau mot de passe")} autoComplete="new-password" value={motDePasse} required autoFocus
                    description={voc`Au moins ${LONGUEUR_MIN} caractères, pas seulement des chiffres.`}
                    onChange={(e) => setMotDePasse(e.currentTarget.value)} />
                  <PasswordInput label={voc("Confirmer le mot de passe")} autoComplete="new-password" value={confirmation} required
                    onChange={(e) => setConfirmation(e.currentTarget.value)} />
                  <Button type="submit" loading={envoi} fullWidth mt="sm">{voc("Enregistrer le mot de passe")}</Button>
                  <Anchor component={Link} to="/login" size="sm" ta="center">{voc("Revenir à la connexion")}</Anchor>
                </Stack>
              </form>
            )}
          </Stack>
        </Paper>
      </Center>
      <PiedDePage clair />
    </Box>
  );
}
