import { useState } from "react";
import { Link, useLocation } from "react-router-dom";
import { Alert, Badge, Button, Card, Container, Group, List, NumberInput, SegmentedControl, Select, SimpleGrid, Stack, Text, Textarea, ThemeIcon, Title } from "@mantine/core";
import { notifications } from "@mantine/notifications";
import { CircleCheck, CreditCard, Handshake, HardDrive, Lock, Rocket, Server } from "lucide-react";
import { type DemandeAbonnement, choisirOffre, payerOffre } from "../../api/identite";
import { messageErreurApi } from "../../utils/erreurs";
import { langue } from "../../utils/i18n";
import { voc } from "../../utils/vocabulaire";
import { CadreVitrine } from "./CadreVitrine";
import { CLE_ABONNEMENT } from "./InscriptionPage";

const PETITE = (go: number, code: string, prix: string) => ({
  code, icone: Rocket, nom: () => voc`Standard ${go} Go`, pour: () => voc`Toute l'offre Standard, avec ${go} Go de stockage`,
  prix: () => voc`${prix} HT par mois`, points: () => [
    voc("Nombre de projets illimité"), voc("Nombre d'utilisateurs illimité"), voc`${go} Go de stockage pour vos données`, voc("Tous les modules de la plateforme"), voc("Manuel d'utilisateur inclus dans l'offre"),
  ],
});

const OFFRES = [
  PETITE(25, "STANDARD_25", "34 $"),
  PETITE(50, "STANDARD_50", "52 $"),
  { code: "STANDARD", icone: Rocket, nom: () => voc("Standard"), pour: () => voc("Tout ce qu'il faut pour suivre vos projets"),
    prix: () => voc("86 $ HT par mois"), points: () => [
      voc("Nombre de projets illimité"), voc("Nombre d'utilisateurs illimité"), voc("100 Go de stockage pour vos données"), voc("Tous les modules de la plateforme"), voc("Manuel d'utilisateur inclus dans l'offre"),
    ] },
  { code: "PARTENARIAT", icone: Handshake, nom: () => voc("Partenariat"), pour: () => voc("Pour les structures qui confient une mission à Expertise-ID"),
    prix: () => voc("Tarif réduit, jusqu'à la gratuité pendant un an"), points: () => [
      voc("Expertise-ID réalise un marché, une étude ou un accompagnement pour votre structure : un arrangement adapté est convenu pour l'accès à la plateforme."),
      voc("Toute l'offre Standard : projets et utilisateurs illimités, 100 Go de stockage"), voc("Réduction possible, jusqu'à la gratuité pendant un an"), voc("Assistance comprise"), voc("Manuel d'utilisateur inclus dans l'offre"),
    ] },
];

/** « 50000 » → « 50 000 FCFA ». */
const somme = (n: number, devise: string) => `${n.toLocaleString("fr-FR")} ${devise === "XOF" ? "FCFA" : devise === "USD" ? "$" : devise}`;

/** « Vous devez vous abonner avant de continuer » : après la création du profil, ou à la connexion d'un profil non abonné. */
export function AbonnementPage() {
  const { state } = useLocation();
  const [demande, setDemande] = useState<DemandeAbonnement | null>(() => {
    if (state && (state as DemandeAbonnement).reference) return state as DemandeAbonnement;
    try { return JSON.parse(sessionStorage.getItem(CLE_ABONNEMENT) ?? "null"); } catch { return null; }
  });
  const [choix, setChoix] = useState<string | null>(null);
  const [message, setMessage] = useState("");
  const [envoi, setEnvoi] = useState(false);
  const [mois, setMois] = useState("12");
  const [tranches, setTranches] = useState(1);
  // Mobile money (FCFA) : payé en ligne. Carte bancaire (dollars) : Expertise-ID finalise le paiement avec le client.
  const [moyen, setMoyen] = useState<"mobile" | "carte">("mobile");
  const [carteEnvoyee, setCarteEnvoyee] = useState(false);

  // Offres Standard : payées en ligne (CinetPay), l'espace est créé aussitôt. Partenariat : demande à Expertise-ID.
  const tarifs = demande?.tarifs?.paiement ? demande.tarifs : null;
  const enLigne = !!tarifs && ["STANDARD_25", "STANDARD_50", "STANDARD", "STOCKAGE_PLUS"].includes(choix ?? "");
  // Prix d'un mois de l'offre (Standard + stockage : celui de Standard), en FCFA ou en dollars.
  const prixMois = (code: string, enDollars: boolean) => {
    const p = tarifs?.offres?.[code];
    return p ? (enDollars ? p.usd : p.mois) : enDollars ? (tarifs?.usd?.mois ?? 0) : (tarifs?.mois ?? 0);
  };
  const usd = tarifs?.usd;
  const carte = moyen === "carte" && !!usd;
  const n = choix === "STOCKAGE_PLUS" ? tranches : 0;
  const montant = !tarifs || !choix ? 0 : carte && usd ? Number(mois) * (prixMois(choix, true) + n * usd.tranche)
    : Number(mois) * (prixMois(choix, false) + n * tarifs.tranche);
  // Prix affichés en dollars, avec l'équivalent en FCFA (réglages de la plateforme).
  const prixEnLigne = (code: string) => !usd || !tarifs || !["STANDARD_25", "STANDARD_50", "STANDARD"].includes(code) ? null
    : `${somme(prixMois(code, true), "USD")} ${voc("HT par mois")} (${somme(prixMois(code, false), tarifs.devise)})`;
  // Formation gratuite à partir d'1 an (Standard 100 Go) ou de 2 ans (Standard 25 Go et 50 Go) de licence.
  const formationMinimum = choix ? tarifs?.formation?.[choix] : undefined;
  const pointEnLigne = (point: string) => usd && point === voc("+ 5 $ pour chaque tranche de 10 Go ajoutée")
    ? `+ ${somme(usd.tranche, "USD")} ${voc("pour chaque tranche de 10 Go ajoutée")}` : point;

  const valider = async () => {
    if (!demande || !choix) return;
    setEnvoi(true);
    if (enLigne && carte) {
      try {
        await choisirOffre(demande.reference, choix, message, { mois: Number(mois), tranches: n });
        setCarteEnvoyee(true);
      } catch (error) {
        notifications.show({ color: "red", message: messageErreurApi(error, voc("L'envoi n'a pas abouti. Réessayez.")) });
      } finally {
        setEnvoi(false);
      }
      return;
    }
    if (enLigne) {
      try {
        const { lien } = await payerOffre({ reference: demande.reference, offre: choix, mois: Number(mois),
          tranches: choix === "STOCKAGE_PLUS" ? tranches : 0, message, langue: langue() });
        // Page de paiement de CinetPay, qui ramène ensuite sur le site (confirmation et création de l'espace).
        if (!/^https:\/\/[a-z0-9.-]*cinetpay\.(net|co|com)\//.test(lien)) throw new Error("lien");
        window.location.assign(lien);
      } catch (error) {
        notifications.show({ color: "red", message: messageErreurApi(error, voc("Le paiement n'a pas pu être préparé. Réessayez dans un moment.")) });
        setEnvoi(false);
      }
      return;
    }
    try {
      const suite = await choisirOffre(demande.reference, choix, message);
      setDemande(suite);
      try { sessionStorage.setItem(CLE_ABONNEMENT, JSON.stringify(suite)); } catch { /* navigation privée */ }
    } catch (error) {
      notifications.show({ color: "red", message: messageErreurApi(error, voc("L'envoi n'a pas abouti. Réessayez.")) });
    } finally {
      setEnvoi(false);
    }
  };

  if (!demande) {
    return (
      <CadreVitrine>
        <Container size="sm" py="xl">
          <Alert color="gray" title={voc("Aucun profil en cours")}>
            {voc("Créez le profil de votre organisation, ou connectez-vous avec l'identifiant choisi.")}
            <Group mt="sm"><Button component={Link} to="/inscription">{voc("Créer le profil")}</Button><Button component={Link} to="/login" variant="default">{voc("Se connecter")}</Button></Group>
          </Alert>
        </Container>
      </CadreVitrine>
    );
  }

  const offreChoisie = demande.offre ? OFFRES.find((o) => o.code === demande.offre) : null;
  return (
    <CadreVitrine>
      <Container size="lg" py="xl">
        <Stack gap="lg">
          <Card withBorder radius="md" padding="lg" bg="orange.0" style={{ borderColor: "var(--mantine-color-orange-3)" }}>
            <Group gap="md" wrap="nowrap" align="flex-start">
              <ThemeIcon size={44} radius="xl" color="orange"><Lock size={22} /></ThemeIcon>
              <Stack gap={4}>
                <Title order={2}>{voc("Vous devez vous abonner avant de continuer")}</Title>
                <Text>{tarifs
                  ? voc`Le profil de ${demande.organisation} est créé. Pour accéder à la plateforme, choisissez une offre et réglez-la en ligne : votre espace est créé aussitôt.`
                  : voc`Le profil de ${demande.organisation} est créé. Pour accéder à la plateforme, choisissez une offre : l'équipe d'Expertise-ID vous contacte pour activer votre espace.`}</Text>
              </Stack>
            </Group>
          </Card>

          {carteEnvoyee ? (
            <Alert color="orange" icon={<CreditCard size={20} />} title={voc("Paiement par carte bancaire")}>
              <Text size="sm">{voc("Vous rencontrez des difficultés ? Contactez-nous au plus vite : notre équipe finalise le paiement avec vous et active votre espace.")}</Text>
              <Text size="sm" mt={6}>{voc("Nous avons bien reçu votre demande et nous vous contactons rapidement.")}</Text>
              <Group mt="sm">
                <Button component="a" href="mailto:contact@expertise-id.com">{voc("Nous écrire")}</Button>
                <Button variant="default" onClick={() => { setCarteEnvoyee(false); setMoyen("mobile"); }}>{voc("Payer par mobile money (FCFA)")}</Button>
              </Group>
            </Alert>
          ) : demande.espace ? (
            <Alert color="teal" icon={<CircleCheck size={20} />} title={voc("Votre espace est prêt")}>
              <Text size="sm">{voc("Connectez-vous avec l'adresse courriel et le mot de passe choisis à l'inscription.")}</Text>
              <Button mt="sm" component={Link} to="/login">{voc("Se connecter")}</Button>
            </Alert>
          ) : offreChoisie ? (
            <Alert color="teal" icon={<CircleCheck size={20} />} title={voc`Offre ${offreChoisie.nom()} choisie`}>
              {voc("Merci ! Expertise-ID a reçu votre demande et vous contactera rapidement pour finaliser l'abonnement et activer votre espace. Vous pourrez alors vous connecter avec votre adresse courriel.")}
              {demande.contact && <Text size="sm" mt={6}>{voc("Contact :")} <a href={`mailto:${demande.contact}`}>{demande.contact}</a></Text>}
            </Alert>
          ) : (
            <>
              <SimpleGrid cols={{ base: 1, sm: 2, lg: 4 }} spacing="md">
                {OFFRES.map(({ code, icone: Icone, nom, pour, prix, points }) => {
                  const actif = choix === code;
                  return (
                    <Card key={code} withBorder radius="md" padding="lg" onClick={() => setChoix(code)} style={{
                      cursor: "pointer", borderWidth: actif ? 2 : 1, borderColor: actif ? "var(--mantine-color-teal-6)" : undefined,
                      boxShadow: actif ? "var(--mantine-shadow-md)" : undefined,
                    }}>
                      <Stack gap="sm" h="100%">
                        <Group justify="space-between">
                          <ThemeIcon size={40} radius="md" variant="light" color="teal"><Icone size={20} /></ThemeIcon>
                          {code === "STOCKAGE_PLUS" && <Badge color="teal">{voc("Stockage à la demande")}</Badge>}
                        </Group>
                        <div>
                          <Text fw={800} size="xl">{nom()}</Text>
                          <Text size="sm" c="dimmed">{pour()}</Text>
                        </div>
                        <List size="sm" spacing={4} icon={<CircleCheck size={15} color="var(--mantine-color-teal-6)" />} style={{ flex: 1 }}>
                          {points().map((p) => <List.Item key={p}>{pointEnLigne(p)}</List.Item>)}
                        </List>
                        <Text size="lg" fw={700} c="teal.8">{prixEnLigne(code) ?? prix()}</Text>
                        <Button variant={actif ? "filled" : "light"} fullWidth>{actif ? voc("Offre sélectionnée") : voc("Choisir cette offre")}</Button>
                      </Stack>
                    </Card>
                  );
                })}
              </SimpleGrid>
              <Card withBorder radius="md" padding="lg">
                <Stack gap="sm">
                  {enLigne && tarifs && (
                    <>
                      {usd && (
                        <Stack gap={4}>
                          <Text size="sm" fw={500}>{voc("Moyen de paiement")}</Text>
                          <SegmentedControl value={moyen} onChange={(v) => setMoyen(v as "mobile" | "carte")} data={[
                            { value: "mobile", label: voc("Mobile money (FCFA)") }, { value: "carte", label: voc("Carte bancaire (dollars)") },
                          ]} />
                        </Stack>
                      )}
                      <Group grow align="flex-start">
                        <Select label={voc("Durée de l'abonnement")} value={mois} onChange={(v) => setMois(v ?? "12")} allowDeselect={false}
                          data={[
                            { value: "1", label: voc("1 mois") }, { value: "3", label: voc("3 mois") }, { value: "6", label: voc("6 mois") },
                            { value: "12", label: voc("1 an (12 mois)") }, { value: "24", label: voc("2 ans (24 mois)") }, { value: "36", label: voc("3 ans (36 mois)") },
                          ]} />
                        {choix === "STOCKAGE_PLUS" && (
                          <NumberInput label={voc("Stockage ajouté (tranches de 10 Go)")} min={1} max={tarifs.tranches_max} allowDecimal={false}
                            value={tranches} onChange={(v) => setTranches(Math.min(tarifs.tranches_max, Math.max(1, Number(v) || 1)))} />
                        )}
                      </Group>
                      {formationMinimum && (Number(mois) >= formationMinimum
                        ? <Badge color="teal" variant="light" size="lg">{voc("Formation gratuite incluse avec cette durée.")}</Badge>
                        : <Text size="sm" c="dimmed">{formationMinimum === 24 ? voc("Choisissez 2 ans de licence pour bénéficier de la formation gratuite.")
                          : voc("Choisissez 1 an de licence ou plus pour bénéficier de la formation gratuite.")}</Text>)}
                      <Text size="lg">{voc("Montant à payer (HT) :")} <b>{somme(montant, carte ? "USD" : tarifs.devise)}</b></Text>
                      <Text size="sm" c="dimmed">{carte
                        ? voc("Paiement par carte bancaire : notre équipe finalise le paiement avec vous et active votre espace.")
                        : voc("Paiement sécurisé par CinetPay (mobile money : Orange Money, Moov Money, Wave…). Dès qu'il est confirmé, votre espace est créé et vous recevez un courriel.")}</Text>
                    </>
                  )}
                  <Textarea label={voc("Précisions pour Expertise-ID (facultatif)")} autosize minRows={2} value={message} onChange={(e) => setMessage(e.currentTarget.value)} />
                  <Group justify="flex-end">
                    <Button size="md" onClick={valider} loading={envoi} disabled={!choix}>{!enLigne ? voc("Envoyer ma demande d'abonnement") : carte ? voc("Continuer avec la carte bancaire") : voc("Payer et créer mon espace")}</Button>
                  </Group>
                </Stack>
              </Card>
            </>
          )}
          <Alert color="teal" variant="light" ta="center">{voc("Formation gratuite : pour 2 ans de licence avec les offres Standard 25 Go et Standard 50 Go, et dès 1 an de licence avec l'offre Standard (100 Go).")}</Alert>
          <Text size="sm" ta="center">{voc("Besoin de plus de stockage ? Chaque offre peut être augmentée sur demande, après l'inscription.")}</Text>
          <Group justify="center">
            <Button variant="light" leftSection={<Server size={16} />} component="a"
              href={`mailto:contact@expertise-id.com?subject=${encodeURIComponent(voc("Hébergement de nos données"))}`}>
              {voc("Héberger mes données chez moi : nous contacter")}
            </Button>
          </Group>
          <Text size="xs" c="dimmed" ta="center">{voc("Les données peuvent aussi être placées sur le serveur de votre structure, ou enregistrées en local. Contact : contact@expertise-id.com · +226 25 65 84 75 · +226 73 69 42 38 · +226 75 64 77 91")}</Text>
        </Stack>
      </Container>
    </CadreVitrine>
  );
}
