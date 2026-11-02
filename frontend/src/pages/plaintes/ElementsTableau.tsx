import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { CircleAlert, CircleCheck, Info, ListFilter, Lock, TriangleAlert } from "lucide-react";
import { Anchor, Badge, Card, Group, Menu, SimpleGrid, Stack, Table, Text, Tooltip } from "@mantine/core";
import { ChoixTypeGraphique, GraphiqueAdaptable } from "../../components/charts/GraphiqueAdaptable";
import type { ElementChiffre, ElementGraphique, ElementListe, ElementTableau } from "../../api/plaintes";
import { dateLisible } from "../../api/plaintes";
import { type TypeGraphique, typesPossibles } from "../../utils/typesGraphiques";
import { locale } from "../../utils/i18n";
import { voc } from "../../utils/vocabulaire";

const COULEUR = { ok: "teal", attention: "orange", alerte: "red" } as const;
const ICONE = { ok: CircleCheck, attention: TriangleAlert, alerte: CircleAlert } as const;

const lienDossiers = (params: Record<string, string>) => `/plaintes?${new URLSearchParams(params).toString()}`;

function formater(valeur: number | string | null, unite = "") {
  if (valeur === null || valeur === undefined) return "—";
  if (typeof valeur === "string") return valeur; // « moins de 5 »
  return `${valeur.toLocaleString(locale())}${unite === "%" ? " %" : unite === "j" ? ` ${voc("j")}` : ""}`;
}

function periode(p: { du?: string; au: string }) {
  return p.du ? `${dateLisible(p.du)} – ${dateLisible(p.au)}` : voc`au ${dateLisible(p.au)}`;
}

/** Chiffre clé : valeur, niveau d'alerte (libellé et icône en plus de la couleur), définition et dénominateur. */
function CarteChiffre({ e }: { e: ElementChiffre }) {
  const navigate = useNavigate();
  const Icone = ICONE[e.niveau];
  return (
    <Card withBorder padding="sm" style={{ cursor: e.lien ? "pointer" : undefined }} onClick={() => e.lien && navigate(lienDossiers(e.lien))}>
      <Stack gap={4}>
        <Group justify="space-between" wrap="nowrap" align="flex-start">
          <Text size="sm" c="dimmed" lh={1.3}>{e.libelle}</Text>
          <Tooltip multiline w={300} withArrow
            label={<Stack gap={2}><Text size="xs">{e.definition}</Text><Text size="xs" c="dimmed">{periode(e.periode)}</Text></Stack>}>
            <Info size={14} color="var(--mantine-color-gray-6)" style={{ flexShrink: 0 }} />
          </Tooltip>
        </Group>
        <Group gap={8} align="baseline">
          <Text fz={26} fw={700} c={e.niveau === "ok" ? undefined : `${COULEUR[e.niveau]}.8`}>{formater(e.valeur, e.unite)}</Text>
          {e.niveau !== "ok" && (
            <Badge size="xs" color={COULEUR[e.niveau]} variant="light" leftSection={<Icone size={10} />} tt="none">
              {e.niveau === "alerte" ? voc("Alerte") : voc("À surveiller")}
            </Badge>
          )}
        </Group>
        <Text size="xs" c="dimmed">
          {e.denominateur !== null && e.denominateur !== undefined
            ? e.numerateur !== null && e.numerateur !== undefined
              ? voc`${formater(e.numerateur)} sur ${formater(e.denominateur)}`
              : voc`sur ${formater(e.denominateur)} dossier(s)`
            : periode(e.periode)}
        </Text>
      </Stack>
    </Card>
  );
}

function CarteGraphique({ e, onType }: { e: ElementGraphique; onType?: (t: TypeGraphique) => void }) {
  const navigate = useNavigate();
  const [type, setType] = useState<TypeGraphique>((e.graphique as TypeGraphique) || "barres");
  // Les cases masquées (« moins de 5 ») ne se dessinent pas : elles restent lisibles dans le tableau.
  const masquees = e.valeurs.some((x) => typeof x === "string");
  const typeAffiche: TypeGraphique = masquees ? "tableau" : type;
  const liens = e.categories.map((c, i) => [c, e.liens[i]] as const).filter(([, l]) => l);
  return (
    <Card withBorder padding="sm">
      <Stack gap="xs">
        <Group justify="space-between" wrap="nowrap">
          <Text fw={600} size="sm">{e.libelle}</Text>
          <Group gap={4} wrap="nowrap">
            {liens.length > 0 && (
              <Menu withinPortal position="bottom-end">
                <Menu.Target>
                  <Tooltip label={voc("Voir les dossiers")}><ListFilter size={16} style={{ cursor: "pointer" }} /></Tooltip>
                </Menu.Target>
                <Menu.Dropdown>
                  {liens.map(([c, l]) => <Menu.Item key={c} onClick={() => navigate(lienDossiers(l!))}>{c}</Menu.Item>)}
                </Menu.Dropdown>
              </Menu>
            )}
            {!masquees && (
              <ChoixTypeGraphique valeur={type} types={typesPossibles(1)} onChange={(t) => { setType(t); onType?.(t); }} />
            )}
          </Group>
        </Group>
        {typeAffiche === "tableau" ? (
          <Table verticalSpacing={4}>
            <Table.Tbody>
              {e.categories.map((c, i) => (
                <Table.Tr key={c}>
                  <Table.Td>{c}</Table.Td>
                  <Table.Td ta="right" fw={600}>{formater(e.valeurs[i])}</Table.Td>
                </Table.Tr>
              ))}
            </Table.Tbody>
          </Table>
        ) : (
          <GraphiqueAdaptable type={typeAffiche} categories={e.categories} hauteur={240}
            series={[{ cle: "n", nom: voc("Dossiers"), couleur: "#0ca678", valeurs: e.valeurs.map((x) => (typeof x === "number" ? x : null)) }]} />
        )}
        <Group justify="space-between" gap={4}>
          <Text size="xs" c="dimmed">{periode(e.periode)}</Text>
          {e.confidentiels !== null && e.confidentiels !== 0 && (
            <Group gap={4}>
              <Lock size={11} color="var(--mantine-color-grape-7)" />
              <Text size="xs" c="dimmed">{voc`Dossiers confidentiels (total, hors répartition) : ${formater(e.confidentiels)}`}</Text>
            </Group>
          )}
        </Group>
      </Stack>
    </Card>
  );
}

function CarteListe({ e }: { e: ElementListe }) {
  const navigate = useNavigate();
  const versDossier = e.code === "liste_echeances";
  return (
    <Card withBorder padding="sm">
      <Stack gap="xs">
        <Text fw={600} size="sm">{e.libelle}</Text>
        {e.lignes.length === 0 ? (
          <Text size="sm" c="dimmed">{voc("Rien à signaler.")}</Text>
        ) : (
          <Table verticalSpacing={4} highlightOnHover>
            <Table.Thead><Table.Tr>{e.colonnes.map((c) => <Table.Th key={c}>{c}</Table.Th>)}</Table.Tr></Table.Thead>
            <Table.Tbody>
              {e.lignes.map((l) => (
                <Table.Tr key={l.id} style={{ cursor: "pointer" }}
                  onClick={() => navigate(versDossier ? `/plaintes/dossiers/${l.id}` : "/plaintes/actions-correctives")}>
                  {l.cellules.map((c, i) => (
                    <Table.Td key={i} c={l.retard && i === (versDossier ? 1 : 2) ? "red.8" : undefined}>
                      {typeof c === "string" && /^\d{4}-\d{2}-\d{2}$/.test(c) ? dateLisible(c) : c || "—"}
                    </Table.Td>
                  ))}
                </Table.Tr>
              ))}
            </Table.Tbody>
          </Table>
        )}
        {!versDossier && <Anchor size="xs" onClick={() => navigate("/plaintes/actions-correctives")}>{voc("Toutes les actions correctives")}</Anchor>}
      </Stack>
    </Card>
  );
}

/** Chiffres clés en grille, puis graphiques et listes. */
export function ElementsTableau({ elements, onType }: { elements: ElementTableau[]; onType?: (code: string, t: TypeGraphique) => void }) {
  const chiffres = elements.filter((e): e is ElementChiffre => e.nature === "chiffre");
  const autres = elements.filter((e) => e.nature !== "chiffre");
  return (
    <Stack>
      {chiffres.length > 0 && (
        <SimpleGrid cols={{ base: 1, xs: 2, md: 4 }} spacing="sm">
          {chiffres.map((e) => <CarteChiffre key={e.code} e={e} />)}
        </SimpleGrid>
      )}
      <SimpleGrid cols={{ base: 1, lg: 2 }} spacing="sm">
        {autres.map((e) =>
          e.nature === "graphique" ? (
            <CarteGraphique key={e.code} e={e} onType={(t) => onType?.(e.code, t)} />
          ) : (
            <CarteListe key={e.code} e={e as ElementListe} />
          ),
        )}
      </SimpleGrid>
    </Stack>
  );
}
