import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { Alert, Anchor, Badge, Box, Button, Center, Divider, Group, Paper, PasswordInput, PinInput, Stack, Text, TextInput } from "@mantine/core";
import { LogoOrganisation, LogoPlateforme, PiedDePage } from "../components/common/Logos";
import { CLE_ABONNEMENT } from "../pages/accueil/InscriptionPage";
import { KeyRound, MailCheck } from "lucide-react";
import { type EtapeDoubleAuth, connexionCode, renvoyerCode } from "../api/doubleAuth";
import { useIdentiteOrganisation } from "../api/identite";
import { useAuth } from "./useAuth";
import { messageErreurApi } from "../utils/erreurs";
import { voc } from "../utils/vocabulaire";
import { ChoixLangue } from "../components/common/ChoixLangue";

const statut = (erreur: unknown) => (erreur as { response?: { status?: number } }).response?.status;

/**
 * Connexion : adresse courriel et mot de passe, puis le code à 6 chiffres envoyé par courriel (à chaque
 * connexion). Plateforme multi-organisations : une seule adresse pour tous, l'organisation est celle du
 * compte. operateur : page à part des opérateurs Expertise-ID (/expertise-id), vers la console.
 */
export function LoginPage({ operateur = false }: { operateur?: boolean }) {
  const { login, ouvrirSession } = useAuth();
  const { data: plateforme } = useIdentiteOrganisation();
  const destination = operateur ? "/console" : "/";
  const multi = !!plateforme?.multi_organisations;
  const navigate = useNavigate();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [info, setInfo] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [etape, setEtape] = useState<EtapeDoubleAuth | null>(null);
  const [code, setCode] = useState("");

  const recommencer = (message?: string) => {
    setEtape(null);
    setCode("");
    setPassword("");
    setInfo(null);
    setError(message ?? null);
  };

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      const suite = await login(username, password, operateur);
      if (suite) setEtape(suite);
      else navigate(destination);
    } catch (erreur) {
      // Profil d'organisation créé mais pas encore abonné : page « Vous devez vous abonner ».
      const reponse = (erreur as { response?: { status?: number; data?: { code?: string; espace?: string; detail?: string } } }).response;
      if (reponse?.status === 403 && reponse.data?.code === "organisation_suspendue") {
        setError(voc("L'abonnement de votre organisation est suspendu. Contactez Expertise-ID."));
        return;
      }
      if (reponse?.status === 403 && reponse.data?.code === "abonnement_requis") {
        try { sessionStorage.setItem(CLE_ABONNEMENT, JSON.stringify(reponse.data)); } catch { /* navigation privée */ }
        navigate("/abonnement", { state: reponse.data });
        return;
      }
      // 400 : mot de passe juste mais code impossible à envoyer (pas d'adresse réelle, serveur de courriel).
      const invalide = multi ? voc("Adresse courriel ou mot de passe incorrect.") : voc("Identifiants invalides.");
      setError(statut(erreur) === 400 ? messageErreurApi(erreur, invalide) : invalide);
    } finally {
      setSubmitting(false);
    }
  }

  async function validerCode(valeur: string) {
    if (!etape || valeur.length !== 6) return;
    setError(null);
    setSubmitting(true);
    try {
      await ouvrirSession(await connexionCode(etape.jeton, valeur), destination);
      navigate(destination);
    } catch (erreur) {
      setCode("");
      // Code expiré, trop d'essais, étape expirée : retour à l'identifiant et au mot de passe.
      if (statut(erreur) === 401 || statut(erreur) === 403) recommencer(messageErreurApi(erreur, voc("Étape de connexion expirée : reconnectez-vous.")));
      else setError(messageErreurApi(erreur, voc("Code incorrect.")));
    } finally {
      setSubmitting(false);
    }
  }

  async function renvoyer() {
    if (!etape) return;
    setError(null);
    setInfo(null);
    try {
      setEtape(await renvoyerCode(etape.jeton));
      setCode("");
      setInfo(voc("Un nouveau code vous a été envoyé."));
    } catch (erreur) {
      if (statut(erreur) === 401 || statut(erreur) === 403) recommencer(voc("Étape de connexion expirée : reconnectez-vous."));
      else setError(messageErreurApi(erreur, voc("Le code de connexion n'a pas pu être envoyé. Réessayez dans un instant.")));
    }
  }

  // Plateforme multi-organisations : on se connecte avec son adresse courriel (installation unique : identifiant).
  const parCourriel = multi || operateur;
  const formulaire = (
    <>
      {error && <Alert color="red">{error}</Alert>}
      <form onSubmit={handleSubmit}>
        <Stack gap="sm">
          <TextInput label={parCourriel ? voc("Adresse courriel") : voc("Identifiant")} type={parCourriel ? "email" : "text"}
            autoComplete={parCourriel ? "email" : "username"} dir="ltr" value={username}
            onChange={(e) => setUsername(e.currentTarget.value)} required />
          <PasswordInput label={voc("Mot de passe")} value={password} onChange={(e) => setPassword(e.currentTarget.value)} required />
          <Button type="submit" loading={submitting} fullWidth mt="sm">{voc("Se connecter")}</Button>
        </Stack>
      </form>
    </>
  );

  return (
    <Box mih="100vh" bg="teal.9" style={{ display: "flex", flexDirection: "column" }}>
    <Center style={{ flex: 1 }} py="lg">
      <Paper shadow="md" radius="md" p="xl" w={420} maw="calc(100vw - 32px)" withBorder pos="relative">
        <div style={{ position: "absolute", top: 8, insetInlineEnd: 8 }}>
          <ChoixLangue connecte={false} couleur="gray" />
        </div>
        <Stack gap="md">
          <Stack gap="xs">
            <Group justify="space-between" align="center" pe={40}>
              <LogoPlateforme taille={38} />
            </Group>
            <LogoOrganisation hauteur={40} />
            {operateur && <Badge color="dark" variant="light" leftSection={<KeyRound size={12} />}>{voc("Espace Expertise-ID")}</Badge>}
            <Text size="sm" c="dimmed">
              {etape ? username : operateur ? voc("Connexion réservée à l'équipe d'Expertise-ID") : voc("Connectez-vous pour accéder à vos projets")}
            </Text>
          </Stack>
          {etape ? (
            <Stack gap="sm">
              <Group gap="xs" wrap="nowrap" align="flex-start">
                <MailCheck size={20} color="var(--mantine-color-teal-7)" style={{ flexShrink: 0 }} aria-hidden />
                <Text size="sm">
                  {voc`Un code de connexion a été envoyé à ${etape.destination}. Il est valable ${etape.validite_minutes} minutes.`}
                </Text>
              </Group>
              <Stack gap={4} align="center">
                <PinInput length={6} type="number" oneTimeCode autoFocus value={code} aria-label={voc("Code reçu par courriel")}
                  onChange={setCode} onComplete={validerCode} disabled={submitting} />
              </Stack>
              {error && <Alert color="red" p="xs">{error}</Alert>}
              {info && <Alert color="teal" p="xs">{info}</Alert>}
              <Button onClick={() => validerCode(code)} loading={submitting} disabled={code.length !== 6} fullWidth>
                {voc("Valider")}
              </Button>
              <Text size="xs" c="dimmed">{voc("Pas de courriel ? Regardez dans les indésirables, ou demandez un nouveau code.")}</Text>
              <Group justify="space-between">
                <Anchor size="xs" component="button" type="button" onClick={renvoyer}>{voc("Renvoyer le code")}</Anchor>
                <Anchor size="xs" component="button" type="button" onClick={() => recommencer()}>
                {parCourriel ? voc("Revenir à l'adresse courriel") : voc("Revenir à l'identifiant")}
              </Anchor>
              </Group>
            </Stack>
          ) : (
            <>
              {formulaire}
              {!operateur && plateforme?.demo_disponible && (
                <Button component={Link} to="/accueil?demo=1" variant="light" fullWidth>{voc("Essayer la démo sans compte")}</Button>
              )}
              {!operateur && (
                <>
                  <Divider label={voc("Pas encore de compte ?")} labelPosition="center" />
                  <Group justify="space-between">
                    <Anchor component={Link} to="/inscription" size="sm">{voc("Créer le profil de mon organisation")}</Anchor>
                    <Anchor component={Link} to="/accueil" size="sm" c="dimmed">{voc("Accueil")}</Anchor>
                  </Group>
                </>
              )}
              {operateur && (
                <Group justify="center">
                  <Anchor component={Link} to="/login" size="sm" c="dimmed">{voc("Connexion des organisations")}</Anchor>
                </Group>
              )}
            </>
          )}
        </Stack>
      </Paper>
    </Center>
    <PiedDePage clair />
    </Box>
  );
}
