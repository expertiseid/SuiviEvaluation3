import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Button, Group, Modal, Progress, Stack, Text, ThemeIcon } from "@mantine/core";
import { HardDrive } from "lucide-react";
import { useAuth } from "../../auth/useAuth";
import { EVENEMENT_STOCKAGE_PLEIN, type DetailStockagePlein } from "../../utils/erreurs";
import { volumeLisible } from "../../utils/stockage";
import { voc } from "../../utils/vocabulaire";

/**
 * Fichier refusé faute de place (réponse « stockage_plein » du serveur, ou vérifié avant l'envoi) : une
 * fenêtre explique la situation, au lieu d'une erreur. L'administrateur peut aller augmenter son stockage.
 */
export function FenetreStockagePlein() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const [detail, setDetail] = useState<DetailStockagePlein | null>(null);

  useEffect(() => {
    const ouvrir = (e: Event) => setDetail((e as CustomEvent<DetailStockagePlein>).detail);
    window.addEventListener(EVENEMENT_STOCKAGE_PLEIN, ouvrir);
    return () => window.removeEventListener(EVENEMENT_STOCKAGE_PLEIN, ouvrir);
  }, []);

  if (!detail) return null;
  const reste = Math.max(0, detail.limite - detail.utilise);
  const part = Math.min(100, (detail.utilise / detail.limite) * 100);
  const admin = user?.role === "ADMIN";
  return (
    <Modal opened onClose={() => setDetail(null)} centered size="md" withCloseButton={false}>
      <Stack gap="md" align="center" ta="center" py="sm">
        <ThemeIcon size={56} radius="xl" color="orange" variant="light"><HardDrive size={28} /></ThemeIcon>
        <Text fw={700} size="lg">{reste < 1024 ** 2 ? voc("Votre espace de stockage est plein") : voc("Pas assez de place pour ce fichier")}</Text>
        <Text size="sm" c="dimmed">
          {detail.taille
            ? voc`Ce que vous envoyez fait ${volumeLisible(detail.taille)}, mais il ne reste que ${volumeLisible(reste)} dans l'espace de votre organisation.`
            : voc`Il ne reste que ${volumeLisible(reste)} dans l'espace de votre organisation.`}
        </Text>
        <Stack gap={4} w="100%">
          <Progress value={part} color={part >= 100 ? "red" : "orange"} size="lg" radius="xl" />
          <Text size="xs" c="dimmed">{voc`${volumeLisible(detail.utilise)} utilisés sur ${volumeLisible(detail.limite)}`}</Text>
        </Stack>
        <Text size="sm">
          {admin
            ? voc("Supprimez des fichiers qui ne servent plus, ou augmentez votre stockage : il est agrandi dès le paiement.")
            : voc("Supprimez des fichiers qui ne servent plus, ou demandez à l'administrateur de votre organisation d'augmenter le stockage.")}
        </Text>
        <Group justify="center" w="100%">
          <Button variant="default" onClick={() => setDetail(null)}>{voc("Fermer")}</Button>
          {admin && (
            <Button leftSection={<HardDrive size={16} />} onClick={() => { setDetail(null); navigate("/stockage"); }}>
              {voc("Augmenter mon stockage")}
            </Button>
          )}
        </Group>
      </Stack>
    </Modal>
  );
}
