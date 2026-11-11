import { Anchor, Box, Group, Image, Stack, Text } from "@mantine/core";
import { useIdentiteOrganisation } from "../../api/identite";
import { langue } from "../../utils/i18n";
import { voc } from "../../utils/vocabulaire";

/** Logo de la plateforme : symbole, nom et devise dans la langue de l'interface (public/logos/logo-<langue>.svg).
 * Sur fond foncé (`clair`), le symbole seul sur une pastille blanche, et le nom en blanc. */
export function LogoPlateforme({ taille = 36, avecNom = true, clair = false }: { taille?: number; avecNom?: boolean; clair?: boolean }) {
  if (avecNom && !clair) return <Image src={`/logos/logo-${langue()}.svg?v=20261105c`} h={Math.round(taille * 1.5)} w="auto" fit="contain" alt="Expertise-ID Monitora" />;
  return (
    <Group gap={10} wrap="nowrap">
      <SymbolePlateforme taille={taille} pastille={clair} />
      {avecNom && (
        <Stack gap={0}>
          <Text fw={800} size={taille > 40 ? "xl" : "md"} lh={1.1} c="white">Expertise-ID Monitora</Text>
          <Text size="xs" lh={1.2} c="teal.1">{voc("Plateforme de monitoring")}</Text>
        </Stack>
      )}
    </Group>
  );
}

/** Le symbole seul ; `pastille` le pose sur un rond blanc pour les fonds foncés. */
export function SymbolePlateforme({ taille = 36, pastille = false }: { taille?: number; pastille?: boolean }) {
  const image = <Image src="/logo-plateforme.svg?v=20261105c" w={taille} h={taille} alt="Expertise-ID Monitora" />;
  return pastille ? <Box bg="white" p={2} style={{ borderRadius: "50%", display: "flex", flexShrink: 0 }}>{image}</Box> : image;
}

/** Logo complet (avec la phrase d'accroche), dans la langue de l'interface. */
export function LogoComplet({ largeur = 320 }: { largeur?: number }) {
  return <Image src={`/logos/logo-complet-${langue()}.svg?v=20261105c`} w={largeur} maw="100%" h="auto" alt="Expertise-ID Monitora" />;
}

/** Logo de l'organisation cliente, s'il a été ajouté dans les paramètres. */
export function LogoOrganisation({ hauteur = 32 }: { hauteur?: number }) {
  const { data } = useIdentiteOrganisation();
  if (!data?.logo) return null;
  return <Image src={data.logo} h={hauteur} w="auto" fit="contain" alt={data.nom || voc("Logo de l'organisation")} />;
}

/** « Développé par Expertise-ID » avec le logo de l'entreprise, en pied de chaque page (aussi dans l'en-tête des pages connectées). */
export function PiedDePage({ clair = false, liens = true }: { clair?: boolean; liens?: boolean }) {
  return (
    <Stack gap={2} py="sm" align="center">
    <Group justify="center" gap={8} wrap="nowrap">
      <Anchor href="https://www.expertise-id.com" target="_blank" rel="noopener" style={{ display: "flex", background: "white", borderRadius: 6, padding: 2 }}>
        <Image src="/logo-expertise-id.png" w={28} h={28} fit="contain" alt="Expertise-ID" />
      </Anchor>
      <Text size="xs" c={clair ? "teal.0" : "dimmed"}>
        {voc("Développé par")}{" "}
        <Anchor href="https://www.expertise-id.com" target="_blank" rel="noopener" size="xs" fw={700} c={clair ? "white" : "teal.8"} underline="hover">Expertise-ID</Anchor>
        {" · "}© {new Date().getFullYear()}
      </Text>
    </Group>
    {liens && <LiensLegaux clair={clair} />}
    </Stack>
  );
}

/** Pages du site vitrine : conditions d'utilisation, politique de confidentialité, cookies. */
export function LiensLegaux({ clair = false }: { clair?: boolean }) {
  const { data } = useIdentiteOrganisation();
  const site = data?.url_site ?? "";
  const lien = (page: string) => `${site}/${page}?lang=${langue()}`;
  const couleur = clair ? "teal.0" : "dimmed";
  return (
    <Group justify="center" gap={6} wrap="wrap">
      <Anchor href={lien("conditions-utilisation.html")} target="_blank" rel="noopener" size="xs" c={couleur}>{voc("Conditions d'utilisation")}</Anchor>
      <Text size="xs" c={couleur} aria-hidden>·</Text>
      <Anchor href={lien("confidentialite.html")} target="_blank" rel="noopener" size="xs" c={couleur}>{voc("Politique de confidentialité")}</Anchor>
      <Text size="xs" c={couleur} aria-hidden>·</Text>
      <Anchor href={lien("cookies.html")} target="_blank" rel="noopener" size="xs" c={couleur}>{voc("Cookies")}</Anchor>
    </Group>
  );
}
