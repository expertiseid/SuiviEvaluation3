import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { Alert, Anchor, Button, Card, Checkbox, Container, Divider, Group, PasswordInput, Select, SimpleGrid, Stack, Text, Textarea, TextInput, Title } from "@mantine/core";
import { Building2, KeyRound, UserRound } from "lucide-react";
import { type ProfilOrganisation, creerProfil } from "../../api/identite";
import { messageErreurApi } from "../../utils/erreurs";
import { voc } from "../../utils/vocabulaire";
import { erreursParChamp } from "../plaintes/saisieRetour";
import { CadreVitrine } from "./CadreVitrine";

// Valeur enregistrée en français ; libellé traduit à l'affichage.
const TYPES = () => [
  ["ONG", voc("ONG")], ["Association", voc("Association")], ["Entreprise", voc("Entreprise")],
  ["Administration publique", voc("Administration publique")], ["Collectivité territoriale", voc("Collectivité territoriale")],
  ["Agence des Nations unies", voc("Agence des Nations unies")], ["Bailleur de fonds", voc("Bailleur de fonds")],
  ["Bureau d'études", voc("Bureau d'études")], ["Autre", voc("Autre")],
];
const TAILLES = () => [
  ["1 à 5 projets", voc("1 à 5 projets")], ["6 à 20 projets", voc("6 à 20 projets")],
  ["21 à 50 projets", voc("21 à 50 projets")], ["Plus de 50 projets", voc("Plus de 50 projets")],
];
const VIDE: ProfilOrganisation = {
  organisation: "", type_organisation: "", pays: "", secteur: "", taille: "", contact_nom: "", contact_fonction: "",
  courriel: "", telephone: "", mot_de_passe: "", message: "", conditions: false,
};
export const CLE_ABONNEMENT = "abonnement-en-cours";

function Section({ icone, titre, children }: { icone: React.ReactNode; titre: string; children: React.ReactNode }) {
  return (
    <Stack gap="sm">
      <Group gap="xs">{icone}<Text fw={700}>{titre}</Text></Group>
      {children}
    </Stack>
  );
}

/** Création du profil d'une organisation ; suite : page d'abonnement. */
export function InscriptionPage() {
  const navigate = useNavigate();
  const [v, setV] = useState<ProfilOrganisation>(VIDE);
  const [confirmation, setConfirmation] = useState("");
  const [piege, setPiege] = useState("");
  const [erreurs, setErreurs] = useState<Record<string, string>>({});
  const [envoi, setEnvoi] = useState(false);
  const changer = (x: Partial<ProfilOrganisation>) => setV((a) => ({ ...a, ...x }));
  const champ = (cle: keyof ProfilOrganisation) => ({
    value: String(v[cle] ?? ""),
    onChange: (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) => changer({ [cle]: e.currentTarget.value }),
    error: erreurs[cle],
  });

  const envoyer = async () => {
    setErreurs({});
    if (v.mot_de_passe !== confirmation) {
      setErreurs({ confirmation: voc("Les deux mots de passe ne sont pas identiques.") });
      return;
    }
    setEnvoi(true);
    try {
      const demande = await creerProfil({ ...v, site_web: piege });
      try { sessionStorage.setItem(CLE_ABONNEMENT, JSON.stringify(demande)); } catch { /* navigation privée */ }
      navigate("/abonnement", { state: demande });
    } catch (error) {
      const parChamp = erreursParChamp(error);
      setErreurs(Object.keys(parChamp).length ? parChamp : { detail: messageErreurApi(error, voc("L'envoi n'a pas abouti. Réessayez.")) });
      window.scrollTo(0, 0);
    } finally {
      setEnvoi(false);
    }
  };

  return (
    <CadreVitrine>
      <Container size="md" py="xl">
        <Stack gap="md">
          <div>
            <Title order={2}>{voc("Créer le profil de mon organisation")}</Title>
            <Text c="dimmed">{voc("Renseignez votre organisation et la personne de contact. Vous choisirez ensuite une offre d'abonnement ; votre espace sera activé par Expertise-ID.")}</Text>
          </div>
          {erreurs.detail && <Alert color="red">{erreurs.detail}</Alert>}
          <Card withBorder radius="md" padding="lg">
            <Stack gap="lg">
              <Section icone={<Building2 size={18} />} titre={voc("Organisation")}>
                <SimpleGrid cols={{ base: 1, sm: 2 }}>
                  <TextInput label={voc("Nom de l'organisation")} withAsterisk {...champ("organisation")} />
                  <Select label={voc("Type d'organisation")} withAsterisk data={TYPES().map(([value, label]) => ({ value, label }))} searchable
                    value={v.type_organisation || null} onChange={(x) => changer({ type_organisation: x ?? "" })} error={erreurs.type_organisation} />
                  <TextInput label={voc("Pays")} withAsterisk placeholder="Burkina Faso" {...champ("pays")} />
                  <TextInput label={voc("Secteur d'intervention")} placeholder={voc("Ex : eau et assainissement, éducation…")} {...champ("secteur")} />
                  <Select label={voc("Taille du portefeuille")} data={TAILLES().map(([value, label]) => ({ value, label }))}
                    value={v.taille || null} onChange={(x) => changer({ taille: x ?? "" })} clearable />
                </SimpleGrid>
              </Section>
              <Divider />
              <Section icone={<UserRound size={18} />} titre={voc("Personne de contact")}>
                <SimpleGrid cols={{ base: 1, sm: 2 }}>
                  <TextInput label={voc("Nom et prénom")} withAsterisk {...champ("contact_nom")} />
                  <TextInput label={voc("Fonction")} {...champ("contact_fonction")} />
                  <TextInput label={voc("Courriel")} withAsterisk type="email" dir="ltr"
                    description={voc("Vous vous connecterez avec cette adresse ; le code de connexion y sera envoyé.")} {...champ("courriel")} />
                  <TextInput label={voc("Téléphone")} withAsterisk {...champ("telephone")} />
                </SimpleGrid>
              </Section>
              <Divider />
              <Section icone={<KeyRound size={18} />} titre={voc("Accès à la plateforme")}>
                <SimpleGrid cols={{ base: 1, sm: 2 }}>
                  <PasswordInput label={voc("Mot de passe")} withAsterisk autoComplete="new-password" value={v.mot_de_passe}
                    onChange={(e) => changer({ mot_de_passe: e.currentTarget.value })} error={erreurs.mot_de_passe}
                    description={voc("8 caractères au moins, pas trop simple.")} />
                  <PasswordInput label={voc("Confirmer le mot de passe")} withAsterisk autoComplete="new-password" value={confirmation}
                    onChange={(e) => setConfirmation(e.currentTarget.value)} error={erreurs.confirmation} />
                </SimpleGrid>
              </Section>
              <Textarea label={voc("Message (facultatif)")} autosize minRows={2} placeholder={voc("Vos besoins, le nombre d'utilisateurs prévus…")} {...champ("message")} />
              {/* Champ piège : invisible pour une personne, rempli par les robots. */}
              <TextInput aria-hidden tabIndex={-1} autoComplete="off" value={piege} onChange={(e) => setPiege(e.currentTarget.value)}
                style={{ position: "absolute", insetInlineStart: -10000, height: 1, overflow: "hidden" }} />
              <Checkbox checked={v.conditions} onChange={(e) => changer({ conditions: e.currentTarget.checked })} error={erreurs.conditions}
                label={voc("J'accepte qu'Expertise-ID utilise ces informations pour me contacter et activer l'espace de mon organisation.")} />
              <Group justify="space-between">
                <Anchor component={Link} to="/login" size="sm">{voc("J'ai déjà un compte")}</Anchor>
                <Button size="md" onClick={envoyer} loading={envoi}>{voc("Créer le profil")}</Button>
              </Group>
            </Stack>
          </Card>
        </Stack>
      </Container>
    </CadreVitrine>
  );
}
