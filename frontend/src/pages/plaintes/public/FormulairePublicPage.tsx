import { useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { CircleCheck, Copy, MessagesSquare, Search } from "lucide-react";
import { Alert, Anchor, Box, Button, Card, Checkbox, Container, CopyButton, Group, Loader, Stack, Text, TextInput, Title } from "@mantine/core";
import { type RecuDossier, type SaisieRetour, useDeposerRetour, useFormulairePublic } from "../../../api/plaintes";
import { ChoixLangue } from "../../../components/common/ChoixLangue";
import { messageErreurApi } from "../../../utils/erreurs";
import { langue } from "../../../utils/i18n";
import { voc } from "../../../utils/vocabulaire";
import { ChampsRetour } from "../ChampsRetour";
import { RETOUR_VIDE, erreursParChamp } from "../saisieRetour";

/** Cadre des pages publiques : léger, lisible sur téléphone, avec le choix de la langue. */
export function CadrePublic({ titre, children }: { titre: string; children: React.ReactNode }) {
  return (
    <Box bg="gray.0" mih="100vh" py="lg">
      <Container size="sm" px="md">
        <Stack gap="md">
          <Group justify="space-between" wrap="nowrap" align="flex-start">
            <Group gap="xs" wrap="nowrap" style={{ flex: 1 }}>
              <MessagesSquare size={26} color="var(--mantine-color-teal-7)" aria-hidden style={{ flexShrink: 0 }} />
              <Title order={2} size="h3">{titre}</Title>
            </Group>
            <div style={{ flexShrink: 0 }}>
              <ChoixLangue connecte={false} couleur="gray" />
            </div>
          </Group>
          {children}
        </Stack>
      </Container>
    </Box>
  );
}

/** Numéro de dossier et code de suivi, à noter : le code n'est affiché qu'une fois. */
export function RecuRetour({ recu, agent = false }: { recu: RecuDossier; agent?: boolean }) {
  return (
    <Stack gap="sm">
      <Group gap="xs">
        <Text size="sm">{voc("Numéro de dossier")}</Text>
        <Text fw={700}>{recu.numero}</Text>
      </Group>
      <Card withBorder bg="teal.0">
        <Stack gap={6} align="center">
          <Text size="sm">{agent ? voc("Code de suivi à remettre au plaignant") : voc("Votre code de suivi")}</Text>
          <Text ff="monospace" fz={28} fw={700} dir="ltr">{recu.code_suivi}</Text>
          <CopyButton value={recu.code_suivi}>
            {({ copied, copy }) => (
              <Button size="xs" variant="light" leftSection={<Copy size={13} />} onClick={copy}>
                {copied ? voc("Copié") : voc("Copier le code")}
              </Button>
            )}
          </CopyButton>
        </Stack>
      </Card>
      <Text size="sm" c="dimmed">
        {voc("Notez ce code : il ne sera plus affiché. Il permet de suivre l'état du dossier sur la page de suivi, sans jamais en montrer le contenu.")}
      </Text>
    </Stack>
  );
}

/** Formulaire public de dépôt d'un retour (sans compte) : /plainte, ou /plainte?projet=ID. */
export function FormulairePublicPage() {
  const [params] = useSearchParams();
  const projet = params.get("projet");
  const { data: formulaire, isLoading } = useFormulairePublic(projet);
  const deposer = useDeposerRetour();
  const [valeurs, setValeurs] = useState<SaisieRetour>(RETOUR_VIDE);
  const [piege, setPiege] = useState("");
  const [erreurs, setErreurs] = useState<Record<string, string>>({});
  const [recu, setRecu] = useState<RecuDossier | null>(null);

  if (isLoading || !formulaire) {
    return <CadrePublic titre={voc("Plaintes et retours")}><Loader mx="auto" /></CadrePublic>;
  }
  if (!formulaire.disponible) {
    return (
      <CadrePublic titre={formulaire.nom}>
        <Alert color="gray">{voc("Le dépôt de retours n'est pas ouvert pour le moment.")}</Alert>
      </CadrePublic>
    );
  }

  const envoyer = async () => {
    setErreurs({});
    const projetFixe = formulaire.projet_fixe && formulaire.projets?.[0] ? formulaire.projets[0].id : null;
    try {
      setRecu(await deposer.mutateAsync({ ...valeurs, projet: projetFixe ?? valeurs.projet, langue: langue(), site_web: piege }));
      window.scrollTo(0, 0);
    } catch (error) {
      const parChamp = erreursParChamp(error);
      setErreurs(Object.keys(parChamp).length ? parChamp : { detail: messageErreurApi(error, voc("L'envoi n'a pas abouti. Réessayez.")) });
    }
  };

  if (recu) {
    return (
      <CadrePublic titre={formulaire.nom}>
        <Card withBorder>
          <Stack>
            <Group gap="xs">
              <CircleCheck size={22} color="var(--mantine-color-teal-7)" aria-hidden />
              <Text fw={600}>{voc("Merci, votre retour a bien été reçu.")}</Text>
            </Group>
            <RecuRetour recu={recu} />
            <Group>
              <Button component={Link} to="/plainte/suivi" variant="light" leftSection={<Search size={14} />}>
                {voc("Suivre mon dossier")}
              </Button>
              <Button variant="subtle" onClick={() => { setRecu(null); setValeurs(RETOUR_VIDE); }}>
                {voc("Envoyer un autre retour")}
              </Button>
            </Group>
          </Stack>
        </Card>
      </CadrePublic>
    );
  }

  return (
    <CadrePublic titre={formulaire.nom}>
      {formulaire.texte_information && (
        <Card withBorder>
          <Text size="sm" dir="auto" style={{ whiteSpace: "pre-line" }}>{formulaire.texte_information}</Text>
        </Card>
      )}
      {formulaire.projet_fixe && formulaire.projets?.[0] && (
        <Text size="sm">{voc("Projet")} : <b>{formulaire.projets[0].nom}</b></Text>
      )}
      <Card withBorder>
        <Stack>
          <ChampsRetour
            valeurs={valeurs}
            onChange={(v) => setValeurs((ancien) => ({ ...ancien, ...v }))}
            types={formulaire.types ?? []}
            categories={formulaire.categories ?? []}
            projets={formulaire.projets ?? []}
            projetFixe={formulaire.projet_fixe}
            anonymatAutorise={!!formulaire.anonymat_autorise}
            erreurs={erreurs}
          />
          {/* Champ piège : invisible pour une personne, rempli par les robots. */}
          <TextInput
            aria-hidden
            tabIndex={-1}
            autoComplete="off"
            value={piege}
            onChange={(e) => setPiege(e.currentTarget.value)}
            style={{ position: "absolute", insetInlineStart: -10000, height: 1, overflow: "hidden" }}
          />
          <Checkbox
            label={voc("J'accepte que les informations de ce formulaire soient utilisées pour traiter mon retour.")}
            checked={valeurs.consentement}
            onChange={(e) => { const coche = e.currentTarget.checked; setValeurs((v) => ({ ...v, consentement: coche })); }}
            error={erreurs.consentement}
          />
          {erreurs.detail && <Alert color="red">{erreurs.detail}</Alert>}
          <Group justify="space-between">
            <Anchor component={Link} to="/plainte/suivi" size="sm">{voc("J'ai déjà un code de suivi")}</Anchor>
            <Button onClick={envoyer} loading={deposer.isPending}>{voc("Envoyer")}</Button>
          </Group>
        </Stack>
      </Card>
    </CadrePublic>
  );
}
