import { Anchor, Group, Image, Stack, Text } from "@mantine/core";
import { useIdentiteOrganisation } from "../../api/identite";
import { voc } from "../../utils/vocabulaire";

/** Logo de la plateforme (marque) avec, au besoin, son nom. */
export function LogoPlateforme({ taille = 36, avecNom = true, clair = false }: { taille?: number; avecNom?: boolean; clair?: boolean }) {
  return (
    <Group gap={10} wrap="nowrap">
      <Image src="/logo-plateforme.svg" w={taille} h={taille} alt="Expertise-ID Monitora" />
      {avecNom && (
        <Stack gap={0}>
          <Text fw={800} size={taille > 40 ? "xl" : "md"} lh={1.1} c={clair ? "white" : undefined}>Expertise-ID Monitora</Text>
          <Text size="xs" lh={1.2} c={clair ? "teal.1" : "dimmed"}>{voc("Plateforme de suivi et d'évaluation de projets")}</Text>
        </Stack>
      )}
    </Group>
  );
}

/** Logo de l'organisation cliente, s'il a été ajouté dans les paramètres. */
export function LogoOrganisation({ hauteur = 32 }: { hauteur?: number }) {
  const { data } = useIdentiteOrganisation();
  if (!data?.logo) return null;
  return <Image src={data.logo} h={hauteur} w="auto" fit="contain" alt={data.nom || voc("Logo de l'organisation")} />;
}

/** « Développé par Expertise-ID » avec le logo de l'entreprise, en pied de chaque page (aussi dans l'en-tête des pages connectées). */
export function PiedDePage({ clair = false }: { clair?: boolean }) {
  return (
    <Group justify="center" gap={8} py="sm" wrap="nowrap">
      <Anchor href="https://www.expertise-id.com" target="_blank" rel="noopener" style={{ display: "flex", background: "white", borderRadius: 6, padding: 2 }}>
        <Image src="/logo-expertise-id.png" w={28} h={28} fit="contain" alt="Expertise-ID" />
      </Anchor>
      <Text size="xs" c={clair ? "teal.0" : "dimmed"}>
        {voc("Développé par")}{" "}
        <Anchor href="https://www.expertise-id.com" target="_blank" rel="noopener" size="xs" fw={700} c={clair ? "white" : "teal.8"} underline="hover">Expertise-ID</Anchor>
        {" · "}© {new Date().getFullYear()}
      </Text>
    </Group>
  );
}
