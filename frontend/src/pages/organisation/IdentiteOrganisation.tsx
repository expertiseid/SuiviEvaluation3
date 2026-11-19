import { useEffect, useState } from "react";
import { Alert, Box, Button, Card, FileInput, Group, Image, NumberInput, Stack, Switch, Text, TextInput } from "@mantine/core";
import { notifications } from "@mantine/notifications";
import { ImageUp, Trash2 } from "lucide-react";
import { useEnregistrerIdentite, useIdentiteOrganisation } from "../../api/identite";
import { messageErreurApi } from "../../utils/erreurs";
import { voc } from "../../utils/vocabulaire";

/** Nom et logo de l'organisation, affichés dans l'en-tête de la plateforme et sur la page de connexion. */
export function IdentiteOrganisation() {
  const { data: identite } = useIdentiteOrganisation();
  const enregistrer = useEnregistrerIdentite();
  const [nom, setNom] = useState("");
  const [inactivite, setInactivite] = useState<number | string>(30);
  const [bloquerCaptures, setBloquerCaptures] = useState(false);
  useEffect(() => { setBloquerCaptures(!!identite?.bloquer_captures); }, [identite?.bloquer_captures]);
  const [fichier, setFichier] = useState<File | null>(null);
  const [apercu, setApercu] = useState<string | null>(null);
  useEffect(() => { setNom(identite?.nom ?? ""); }, [identite?.nom]);
  useEffect(() => { if (identite?.session_inactivite_min) setInactivite(identite.session_inactivite_min); }, [identite?.session_inactivite_min]);
  useEffect(() => {
    if (!fichier) { setApercu(null); return; }
    const url = URL.createObjectURL(fichier);
    setApercu(url);
    return () => URL.revokeObjectURL(url);
  }, [fichier]);

  const sauver = async (options: { supprimerLogo?: boolean } = {}) => {
    try {
      await enregistrer.mutateAsync({
        nom, logo: fichier, bloquerCaptures, ...options,
        ...(identite?.session_inactivite_min ? { sessionInactiviteMin: Number(inactivite) } : {}),
      });
      setFichier(null);
      notifications.show({ color: "teal", message: voc("Identité enregistrée") });
    } catch (error) {
      notifications.show({ color: "red", message: messageErreurApi(error, voc("Erreur lors de l'enregistrement")) });
    }
  };
  const logo = apercu ?? identite?.logo ?? null;

  return (
    <Card withBorder radius="md" padding="lg" maw={720}>
      <Stack gap="md">
        <Text size="sm" c="dimmed">
          {voc("Le logo de votre organisation s'affiche en haut de toutes les pages de la plateforme et sur la page de connexion. Formats PNG, JPEG ou WebP, 2 Mo au plus ; un logo horizontal sur fond transparent ou blanc rend le mieux.")}
        </Text>
        <TextInput label={voc("Nom affiché de l'organisation")} value={nom} onChange={(e) => setNom(e.currentTarget.value)} />
        <Group align="flex-end" gap="md">
          <Box w={220} h={90} bg="gray.0" style={{ border: "1px dashed var(--mantine-color-gray-4)", borderRadius: 8, display: "flex", alignItems: "center", justifyContent: "center" }}>
            {logo ? <Image src={logo} mah={80} maw={200} fit="contain" alt={voc("Logo de l'organisation")} /> : <Text size="xs" c="dimmed">{voc("Aucun logo")}</Text>}
          </Box>
          <Stack gap="xs" style={{ flex: 1, minWidth: 220 }}>
            <FileInput label={voc("Nouveau logo")} placeholder={voc("Choisir une image")} accept="image/png,image/jpeg,image/webp"
              leftSection={<ImageUp size={14} />} value={fichier} onChange={setFichier} clearable />
            {identite?.logo && !fichier && (
              <Button variant="subtle" color="red" size="xs" leftSection={<Trash2 size={13} />} onClick={() => sauver({ supprimerLogo: true })} w="fit-content">
                {voc("Retirer le logo")}
              </Button>
            )}
          </Stack>
        </Group>
        {!!identite?.session_inactivite_min && (
          <NumberInput
            label={voc("Déconnexion après inactivité (minutes)")}
            description={voc("Tous les utilisateurs de l'organisation sont déconnectés après cette durée sans activité, avec un avertissement une minute avant. Entre 5 et 480 minutes ; 30 par défaut.")}
            min={5}
            max={480}
            allowDecimal={false}
            maw={320}
            value={inactivite}
            onChange={setInactivite}
          />
        )}
        <Switch
          checked={bloquerCaptures}
          onChange={(e) => setBloquerCaptures(e.currentTarget.checked)}
          label={voc("Bloquer les captures d'écran")}
          description={voc("Pour tous les utilisateurs sauf l'administrateur : filigrane à leur nom sur toutes les pages, écran masqué pendant une capture ou hors de la fenêtre, impression, copie et clic droit bloqués. Dans la fiche d'un utilisateur (Utilisateurs), vous pouvez les bloquer ou les permettre pour lui seul. Aucun site ne peut empêcher totalement une capture ou une photo de l'écran : le filigrane permet de retrouver qui l'a faite.")}
        />
        {fichier && <Alert color="blue" p="xs">{voc("Aperçu : cliquez sur « Enregistrer » pour l'appliquer.")}</Alert>}
        <Group justify="flex-end">
          <Button onClick={() => sauver()} loading={enregistrer.isPending}>{voc("Enregistrer")}</Button>
        </Group>
      </Stack>
    </Card>
  );
}
