import { useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { Alert, Anchor, Badge, Box, Button, Center, Divider, Group, Paper, PasswordInput, PinInput, Stack, Text, TextInput } from "@mantine/core";
import { LiensLegaux, LogoOrganisation, LogoPlateforme, PiedDePage } from "../components/common/Logos";
import { CLE_ABONNEMENT } from "../pages/accueil/InscriptionPage";
import { KeyRound, Mail, MailCheck } from "lucide-react";
import { type EtapeDoubleAuth, connexionCode, demanderNouveauMotDePasse, renvoyerCode } from "../api/doubleAuth";
import { useIdentiteOrganisation } from "../api/identite";
import { useAuth } from "./useAuth";
import { messageErreurApi } from "../utils/erreurs";
import { voc } from "../utils/vocabulaire";
import { langue } from "../utils/i18n";
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
  // ?suite=/mon-abonnement (bouton « J'ai déjà un espace : choisir une offre » du site) : page ouverte après la
  // connexion ; seulement une page de la plateforme (« /… », jamais « //autre-site »).
  const [parametres] = useSearchParams();
  const suite = parametres.get("suite") ?? "";
  const destination = operateur ? "/console" : /^\/(?![/\\])/.test(suite) ? suite : "/";
  const pourAbonnement = destination === "/mon-abonnement";
  const multi = !!plateforme?.multi_organisations;
  const navigate = useNavigate();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  // Essai gratuit terminé : connexion refusée (sauf pour s'abonner), message et lien vers le site.
  const [essaiTermine, setEssaiTermine] = useState(parametres.get("essai") === "termine");
  // Session fermée après une période d'inactivité (auth/inactivite.ts).
  const inactif = parametres.get("inactif") === "1";
  const [info, setInfo] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [etape, setEtape] = useState<EtapeDoubleAuth | null>(null);
  const [code, setCode] = useState("");
  // Mot de passe oublié : adresse saisie, puis message « lien envoyé ».
  const [oubli, setOubli] = useState(false);

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
      const suite = await login(username, password, operateur, pourAbonnement);
      if (suite) setEtape(suite);
      else navigate(destination);
    } catch (erreur) {
      // Profil d'organisation créé mais pas encore abonné : page « Vous devez vous abonner ».
      const reponse = (erreur as { response?: { status?: number; data?: { code?: string; espace?: string; detail?: string } } }).response;
      if (reponse?.status === 403 && reponse.data?.code === "essai_termine") {
        setEssaiTermine(true);
        return;
      }
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

  async function demanderLien(event: React.FormEvent) {
    event.preventDefault();
    setError(null);
    setInfo(null);
    setSubmitting(true);
    try {
      setInfo(voc((await demanderNouveauMotDePasse(username.trim(), langue())).detail));
    } catch (erreur) {
      setError(messageErreurApi(erreur, voc("La demande n'a pas pu être envoyée. Réessayez dans un instant.")));
    } finally {
      setSubmitting(false);
    }
  }

  const ouvrirOubli = (ouvert: boolean) => {
    setOubli(ouvert);
    setError(null);
    setInfo(null);
  };

  // Plateforme multi-organisations : on se connecte avec son adresse courriel (installation unique : identifiant).
  const parCourriel = multi || operateur;
  const formulaire = (
    <>
      {essaiTermine && !pourAbonnement && (
        <Alert color="orange" title={voc("Essai gratuit terminé")}>
          <Text size="sm">{voc("Votre essai gratuit est terminé : la plateforme n'est plus accessible. Pour continuer, abonnez-vous depuis le site.")}</Text>
          <Button mt="sm" size="xs" component="a" href={`${plateforme?.url_site ?? ""}/inscription.html?lang=${langue()}`}>{voc("S'abonner sur le site")}</Button>
        </Alert>
      )}
      {inactif && !error && (
        <Alert color="blue">{voc("Vous avez été déconnecté après une période d'inactivité, pour protéger vos données. Reconnectez-vous pour continuer.")}</Alert>
      )}
      {error && <Alert color="red">{error}</Alert>}
      <form onSubmit={handleSubmit}>
        <Stack gap="sm">
          <TextInput label={parCourriel ? voc("Adresse courriel") : voc("Identifiant")} type={parCourriel ? "email" : "text"}
            autoComplete={parCourriel ? "email" : "username"} dir="ltr" value={username}
            onChange={(e) => setUsername(e.currentTarget.value)} required />
          <PasswordInput label={voc("Mot de passe")} value={password} onChange={(e) => setPassword(e.currentTarget.value)} required />
          {!operateur && (
            <Group justify="flex-end" mt={-6}>
              <Anchor size="xs" component="button" type="button" onClick={() => ouvrirOubli(true)}>{voc("Mot de passe oublié ?")}</Anchor>
            </Group>
          )}
          <Button type="submit" loading={submitting} fullWidth mt="sm">{voc("Se connecter")}</Button>
          <Text size="xs" c="dimmed" ta="center">
            {voc("En vous connectant, vous acceptez les conditions d'utilisation et la politique de confidentialité de la plateforme.")}
          </Text>
          <LiensLegaux />
        </Stack>
      </form>
    </>
  );

  const formulaireOubli = (
    <form onSubmit={demanderLien}>
      <Stack gap="sm">
        <Text size="sm">{voc("Indiquez l'adresse courriel de votre compte : nous vous enverrons un lien pour choisir un nouveau mot de passe.")}</Text>
        {error && <Alert color="red" p="xs">{error}</Alert>}
        {info && <Alert color="teal" p="xs">{info}</Alert>}
        <TextInput label={voc("Adresse courriel")} type="email" autoComplete="email" dir="ltr" value={username}
          onChange={(e) => setUsername(e.currentTarget.value)} required />
        <Button type="submit" loading={submitting} fullWidth leftSection={<Mail size={16} />}>{voc("Recevoir le lien")}</Button>
        <Group justify="center">
          <Anchor size="sm" component="button" type="button" onClick={() => ouvrirOubli(false)}>{voc("Revenir à la connexion")}</Anchor>
        </Group>
      </Stack>
    </form>
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
              {etape ? username : oubli ? voc("Mot de passe oublié") : operateur ? voc("Connexion réservée à l'équipe d'Expertise-ID") : voc("Connectez-vous pour accéder à vos projets")}
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
          ) : oubli ? formulaireOubli : (
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
    <PiedDePage clair liens={false} />
    </Box>
  );
}
