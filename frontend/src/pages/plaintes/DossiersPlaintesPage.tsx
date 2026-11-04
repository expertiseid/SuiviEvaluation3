import { useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { Bookmark, Copy, FileSpreadsheet, Download, ExternalLink, Lock, Plus, QrCode, Search, Siren, SlidersHorizontal, Trash2, X } from "lucide-react";
import {
  ActionIcon,
  Alert,
  Anchor,
  Badge,
  Button,
  Card,
  Collapse,
  CopyButton,
  Grid,
  Group,
  Menu,
  Modal,
  NavLink,
  Pagination,
  Select,
  Stack,
  Table,
  Text,
  TextInput,
} from "@mantine/core";
import { DatePickerInput } from "@mantine/dates";
import { useDebouncedValue, useDisclosure } from "@mantine/hooks";
import { notifications } from "@mantine/notifications";
import {
  type CanalPlainte,
  type FiltresDossiers,
  STATUTS_DOSSIER,
  adresseFormulairePublic,
  couleurStatutDossier,
  dateLisible,
  exporterListeDossiers,
  libelleCanal,
  libelleStatutDossier,
  telechargerQrFormulaire,
  useCategoriesPlainte,
  useCompteursVues,
  useDossiersPlainte,
  useEnregistrerVue,
  useMecanisme,
  usePrioritesPlainte,
  useSupprimerVue,
  useVuesEnregistrees,
} from "../../api/plaintes";
import { useUtilisateurs } from "../../api/accounts";
import { useAuth } from "../../auth/useAuth";
import { useProjets } from "../../api/projects";
import { messageErreurApi } from "../../utils/erreurs";
import { useAccesModules } from "../../utils/modules";
import { voc } from "../../utils/vocabulaire";
import { BadgeDelai } from "./DelaiDossier";
import { EnTetePlaintes } from "./EnTetePlaintes";
import { SaisieDossierModal } from "./SaisieDossierModal";
import { optionsCategories } from "./saisieRetour";

const CANAUX: CanalPlainte[] = ["FORMULAIRE", "TELEPHONE", "EN_PERSONNE", "REUNION", "BOITE", "COURRIER", "COURRIEL", "AUTRE"];
const PAR_PAGE = 25;

// Vues prêtes (6.8 du cahier des charges), regroupées dans la colonne de gauche.
const GROUPES_VUES = [
  { titre: () => voc("Dossiers"), vues: [
    { value: "tous", label: () => voc("Tous") },
    { value: "mes_dossiers", label: () => voc("Mes dossiers") },
  ] },
  { titre: () => voc("Suivi"), vues: [
    { value: "a_traiter", label: () => voc("À traiter") },
    { value: "urgents", label: () => voc("Urgents"), couleur: "red" },
    { value: "en_retard", label: () => voc("En retard"), couleur: "red" },
    { value: "sans_responsable", label: () => voc("Sans responsable"), couleur: "orange" },
  ] },
  { titre: () => voc("Décision et clôture"), vues: [
    { value: "attente_decision", label: () => voc("En attente de décision") },
    { value: "a_cloturer", label: () => voc("À clôturer") },
    { value: "recours", label: () => voc("Recours"), couleur: "red" },
  ] },
  { titre: () => voc("Protection"), vues: [
    { value: "confidentiels", label: () => voc("Confidentiels"), couleur: "grape" },
    { value: "a_anonymiser", label: () => voc("À anonymiser") },
  ] },
];

/** Colonne des vues prêtes, avec le nombre de dossiers de chacune. */
function ColonneVues({ vue, choisir }: { vue: string; choisir: (v: string) => void }) {
  const { data: compteurs } = useCompteursVues();
  return (
    <Card withBorder p="xs">
      <Stack gap={8}>
        {GROUPES_VUES.map((groupe) => (
          <Stack key={groupe.titre()} gap={0}>
            <Text size="xs" fw={700} c="dimmed" tt="uppercase" px="xs" pb={2}>{groupe.titre()}</Text>
            {groupe.vues.map((v) => {
              const nombre = compteurs?.[v.value];
              return (
                <NavLink
                  key={v.value}
                  label={v.label()}
                  active={vue === v.value}
                  onClick={() => choisir(v.value)}
                  variant="light"
                  py={6}
                  style={{ borderRadius: "var(--mantine-radius-sm)" }}
                  rightSection={nombre !== undefined && (
                    <Badge size="sm" variant={nombre && v.couleur ? "filled" : "light"} color={nombre && v.couleur ? v.couleur : "gray"} circle={nombre < 100}>
                      {nombre}
                    </Badge>
                  )}
                />
              );
            })}
          </Stack>
        ))}
      </Stack>
    </Card>
  );
}

type Filtres = Omit<FiltresDossiers, "page">;
const SANS_FILTRE: Filtres = { vue: "", search: "", statut: null, canal: null, projet: null, categorie: null, priorite: null, responsable: null, date_du: null, date_au: null };

/** Adresse et QR code du formulaire public, général ou propre à un projet. */
function FormulairePublicModal({ opened, onClose }: { opened: boolean; onClose: () => void }) {
  const { data: mecanisme } = useMecanisme();
  const { data: tousProjets = [] } = useProjets();
  const [projet, setProjet] = useState<number | null>(null);
  const couverts = mecanisme?.projets ?? [];
  const projets = couverts.length ? tousProjets.filter((p) => couverts.includes(p.id)) : tousProjets;
  const adresse = adresseFormulairePublic(projet);
  return (
    <Modal opened={opened} onClose={onClose} title={voc("Formulaire public")} size="lg">
      <Stack>
        <Text size="sm" c="dimmed">
          {voc("Accessible sans compte, sur téléphone, dans les langues choisies. Affichez l'adresse ou le QR code dans les lieux d'intervention, sur les affiches et les documents du projet.")}
        </Text>
        <Select
          label={voc("Formulaire")}
          data={[{ value: "", label: voc("Général (tous les projets couverts)") }, ...projets.map((p) => ({ value: String(p.id), label: p.code ? `${p.code} — ${p.nom}` : p.nom }))]}
          value={projet ? String(projet) : ""}
          onChange={(v) => setProjet(v ? Number(v) : null)}
          allowDeselect={false}
          searchable
        />
        <Group gap="xs" wrap="nowrap">
          <TextInput value={adresse} readOnly style={{ flex: 1 }} dir="ltr" />
          <CopyButton value={adresse}>
            {({ copied, copy }) => (
              <Button variant="light" leftSection={<Copy size={14} />} onClick={copy}>{copied ? voc("Copié") : voc("Copier")}</Button>
            )}
          </CopyButton>
        </Group>
        <Group>
          <Button leftSection={<Download size={14} />} onClick={() => telechargerQrFormulaire(projet)}>{voc("Télécharger le QR code")}</Button>
          <Button component="a" href={adresse} target="_blank" variant="subtle" leftSection={<ExternalLink size={14} />}>{voc("Ouvrir le formulaire")}</Button>
          <Button component="a" href="/plainte/suivi" target="_blank" variant="subtle" leftSection={<Search size={14} />}>{voc("Page de suivi")}</Button>
        </Group>
      </Stack>
    </Modal>
  );
}

/** Enregistrer les filtres du moment sous un nom, ou rappeler une vue enregistrée. */
function MesVues({ filtres, appliquer }: { filtres: Filtres; appliquer: (f: Filtres) => void }) {
  const { data: vues = [] } = useVuesEnregistrees();
  const enregistrer = useEnregistrerVue();
  const supprimer = useSupprimerVue();
  const [nom, setNom] = useState("");
  const [ouvert, setOuvert] = useState(false);
  const sauver = async () => {
    try {
      await enregistrer.mutateAsync({ nom: nom.trim(), filtres });
      setNom("");
      setOuvert(false);
      notifications.show({ message: voc("Vue enregistrée"), color: "teal" });
    } catch (error) {
      notifications.show({ message: messageErreurApi(error, voc("Erreur lors de l'enregistrement")), color: "red" });
    }
  };
  return (
    <>
      <Menu position="bottom-end" withinPortal>
        <Menu.Target>
          <Button variant="default" size="sm" leftSection={<Bookmark size={14} />}>{voc("Mes vues")}</Button>
        </Menu.Target>
        <Menu.Dropdown>
          {vues.map((v) => (
            <Menu.Item key={v.id} onClick={() => appliquer({ ...SANS_FILTRE, ...v.filtres })}
              rightSection={
                <ActionIcon size="xs" variant="subtle" color="red" aria-label={voc("Supprimer")}
                  onClick={(e) => { e.stopPropagation(); supprimer.mutate(v.id); }}>
                  <Trash2 size={12} />
                </ActionIcon>
              }>
              {v.nom}
            </Menu.Item>
          ))}
          {vues.length > 0 && <Menu.Divider />}
          <Menu.Item leftSection={<Plus size={13} />} onClick={() => setOuvert(true)}>{voc("Enregistrer les filtres actuels")}</Menu.Item>
        </Menu.Dropdown>
      </Menu>
      <Modal opened={ouvert} onClose={() => setOuvert(false)} title={voc("Enregistrer la vue")} size="sm">
        <Stack>
          <TextInput label={voc("Nom de la vue")} placeholder={voc("Ex : Urgences du projet PAEF")} value={nom} onChange={(e) => setNom(e.currentTarget.value)} data-autofocus />
          <Group justify="flex-end">
            <Button onClick={sauver} disabled={!nom.trim()} loading={enregistrer.isPending}>{voc("Enregistrer")}</Button>
          </Group>
        </Stack>
      </Modal>
    </>
  );
}

/** Mécanisme de plaintes et retours : dossiers (vues, filtres), saisie par un agent, formulaire public. */
export function DossiersPlaintesPage() {
  const navigate = useNavigate();
  const { data: mecanisme } = useMecanisme();
  const { data: projets = [] } = useProjets();
  const { data: categories = [] } = useCategoriesPlainte();
  const { data: priorites = [] } = usePrioritesPlainte();
  const { data: utilisateurs = [] } = useUtilisateurs();
  const modifiable = useAccesModules().peutEcrire("/plaintes");
  const [page, setPage] = useState(1);
  // ?vue=… : lien d'une notification (ex : dossiers à anonymiser).
  const [parametres] = useSearchParams();
  // Filtres repris de l'adresse : clic depuis le tableau de bord ou une notification.
  const [filtres, setFiltres] = useState<Filtres>(() => ({
    ...SANS_FILTRE,
    ...Object.fromEntries(Object.keys(SANS_FILTRE).filter((cle) => parametres.get(cle)).map((cle) => [cle, parametres.get(cle)])),
  }));
  const [rechercheDifferee] = useDebouncedValue(filtres.search ?? "", 300);
  const { data } = useDossiersPlainte({ ...filtres, search: rechercheDifferee, page });
  const [saisie, saisieControles] = useDisclosure(false);
  const [formulaire, formulaireControles] = useDisclosure(false);
  const [plusDeFiltres, setPlusDeFiltres] = useState(false);
  const dossiers = data?.results ?? [];
  const pages = Math.ceil((data?.count ?? 0) / PAR_PAGE);
  const changer = (f: Partial<Filtres>) => { setFiltres((ancien) => ({ ...ancien, ...f })); setPage(1); };
  const filtresActifs = Object.entries(filtres).some(([cle, valeur]) => cle !== "vue" && valeur);
  const { user } = useAuth();
  const exporter = async (coordonnees: boolean) => {
    try {
      await exporterListeDossiers({ ...filtres, search: rechercheDifferee }, coordonnees);
    } catch (error) {
      notifications.show({ message: messageErreurApi(error, voc("Export impossible")), color: "red" });
    }
  };

  // Filtres secondaires repliés, sauf s'ils sont déjà utilisés (lien d'un tableau de bord…).
  const secondairesActifs = !!(filtres.priorite || filtres.responsable || filtres.canal || filtres.date_du || filtres.date_au);
  const vueCourante = filtres.vue || "tous";
  const choisirVue = (v: string) => changer({ vue: v === "tous" ? "" : v });

  return (
    <Stack>
      <EnTetePlaintes
        actions={
          <>
            {mecanisme?.actif && (
              <Button variant="light" leftSection={<QrCode size={14} />} onClick={formulaireControles.open}>{voc("Formulaire public")}</Button>
            )}
            {mecanisme?.actif && modifiable && (
              <Button leftSection={<Plus size={14} />} onClick={saisieControles.open}>{voc("Enregistrer un retour")}</Button>
            )}
          </>
        }
      />
      {mecanisme && !mecanisme.actif && (
        <Alert color="orange" title={voc("Le mécanisme n'est pas encore ouvert")}>
          {voc("Les retours ne peuvent être reçus qu'une fois le mécanisme paramétré et activé.")}{" "}
          <Anchor component={Link} to="/plaintes/parametrage" size="sm">{voc("Ouvrir le paramétrage")}</Anchor>
        </Alert>
      )}
      <Grid gutter="md">
        {/* Vues : colonne sur grand écran, liste déroulante sur téléphone. */}
        <Grid.Col span={{ base: 12, md: 3, xl: 2 }}>
          <Select hiddenFrom="md" label={voc("Vue")} allowDeselect={false} value={vueCourante} onChange={(v) => v && choisirVue(v)}
            data={GROUPES_VUES.map((g) => ({ group: g.titre(), items: g.vues.map((v) => ({ value: v.value, label: v.label() })) }))} />
          <div style={{ position: "sticky", top: 70 }}>
            <Stack visibleFrom="md" gap={0}><ColonneVues vue={vueCourante} choisir={choisirVue} /></Stack>
          </div>
        </Grid.Col>
        <Grid.Col span={{ base: 12, md: 9, xl: 10 }}>
          <Stack gap="sm">
            <Card withBorder p="sm">
              <Stack gap="xs">
                <Group gap="sm" align="flex-end">
                  <TextInput placeholder={voc("Numéro de dossier")} leftSection={<Search size={14} />} value={filtres.search ?? ""}
                    onChange={(e) => changer({ search: e.currentTarget.value })} w={200} />
                  <Select placeholder={voc("Tous les statuts")} data={STATUTS_DOSSIER.map((s) => ({ value: s, label: libelleStatutDossier(s) }))}
                    value={filtres.statut ?? null} onChange={(v) => changer({ statut: v })} clearable w={190} />
                  <Select placeholder={voc("Tous les projets")} data={projets.map((p) => ({ value: String(p.id), label: p.code || p.nom }))}
                    value={filtres.projet ?? null} onChange={(v) => changer({ projet: v })} clearable searchable w={180} />
                  <Select placeholder={voc("Toutes les catégories")} data={optionsCategories(categories)}
                    value={filtres.categorie ?? null} onChange={(v) => changer({ categorie: v })} clearable searchable w={220} />
                  <Button variant={plusDeFiltres || secondairesActifs ? "light" : "subtle"} leftSection={<SlidersHorizontal size={14} />}
                    onClick={() => setPlusDeFiltres((x) => !x)}>
                    {plusDeFiltres ? voc("Moins de filtres") : voc("Plus de filtres")}
                  </Button>
                  {filtresActifs && (
                    <Button variant="subtle" color="gray" leftSection={<X size={14} />} onClick={() => changer({ ...SANS_FILTRE, vue: filtres.vue })}>
                      {voc("Effacer les filtres")}
                    </Button>
                  )}
                </Group>
                <Collapse expanded={plusDeFiltres || secondairesActifs}>
                  <Group gap="sm" align="flex-end">
                    <Select placeholder={voc("Toutes les priorités")} data={priorites.map((p) => ({ value: String(p.id), label: p.nom }))}
                      value={filtres.priorite ?? null} onChange={(v) => changer({ priorite: v })} clearable w={190} />
                    <Select placeholder={voc("Tous les gestionnaires")} data={utilisateurs.map((u) => ({ value: String(u.id), label: `${u.first_name} ${u.last_name}`.trim() || u.username }))}
                      value={filtres.responsable ?? null} onChange={(v) => changer({ responsable: v })} clearable searchable w={200} />
                    <Select placeholder={voc("Tous les canaux")} data={CANAUX.map((c) => ({ value: c, label: libelleCanal(c) }))}
                      value={filtres.canal ?? null} onChange={(v) => changer({ canal: v })} clearable w={200} />
                    <DatePickerInput type="range" placeholder={voc("Période de réception")} valueFormat="DD/MM/YYYY" clearable w={230}
                      value={[filtres.date_du ?? null, filtres.date_au ?? null]} onChange={([du, au]) => changer({ date_du: du, date_au: au })} />
                  </Group>
                </Collapse>
              </Stack>
            </Card>
            <Group justify="space-between">
              <Text size="sm" c="dimmed">{voc`${data?.count ?? 0} dossier(s)`}</Text>
              <Group gap="xs">
                <MesVues filtres={filtres} appliquer={(f) => { setFiltres(f); setPage(1); }} />
                <Menu position="bottom-end" withinPortal>
                  <Menu.Target>
                    <Button variant="default" size="xs" leftSection={<FileSpreadsheet size={14} />}>{voc("Exporter")}</Button>
                  </Menu.Target>
                  <Menu.Dropdown>
                    <Menu.Label>{voc("Dossiers de la liste filtrée, hors confidentiels ; l'export est inscrit au journal.")}</Menu.Label>
                    <Menu.Item onClick={() => exporter(false)}>{voc("Excel, sans coordonnées")}</Menu.Item>
                    {user?.role === "ADMIN" && <Menu.Item onClick={() => exporter(true)}>{voc("Excel, avec coordonnées des plaignants")}</Menu.Item>}
                  </Menu.Dropdown>
                </Menu>
              </Group>
            </Group>
            <Table.ScrollContainer minWidth={900}>
              <Table withTableBorder highlightOnHover verticalSpacing={8}>
                <Table.Thead>
                  <Table.Tr>
                    <Table.Th>{voc("Numéro")}</Table.Th>
                    <Table.Th>{voc("Reçu le")}</Table.Th>
                    <Table.Th>{voc("Catégorie")}</Table.Th>
                    <Table.Th>{voc("Projet")}</Table.Th>
                    <Table.Th>{voc("Gestionnaire")}</Table.Th>
                    <Table.Th>{voc("Étape")}</Table.Th>
                    <Table.Th>{voc("Échéance")}</Table.Th>
                    <Table.Th>{voc("Statut")}</Table.Th>
                  </Table.Tr>
                </Table.Thead>
                <Table.Tbody>
                  {dossiers.map((d) => (
                    <Table.Tr key={d.id} onClick={() => navigate(`/plaintes/dossiers/${d.id}`)} style={{ cursor: "pointer" }}>
                      <Table.Td>
                        <Group gap={6} wrap="nowrap">
                          <Text size="sm" fw={600} style={{ whiteSpace: "nowrap" }}>{d.numero}</Text>
                          {d.sensible && <Lock size={13} color="var(--mantine-color-grape-7)" aria-label={voc("Confidentiel")} />}
                          {d.priorite_urgente && <Siren size={13} color="var(--mantine-color-red-7)" aria-label={voc("Urgente")} />}
                        </Group>
                      </Table.Td>
                      <Table.Td>
                        <Text size="sm" style={{ whiteSpace: "nowrap" }}>{dateLisible(d.date_reception)}</Text>
                        <Text size="xs" c="dimmed">{libelleCanal(d.canal)}</Text>
                      </Table.Td>
                      <Table.Td>
                        {d.categorie_nom ? <Text size="sm">{d.categorie_nom}</Text> : <Text size="sm" c="dimmed" fs="italic">{voc("À classer")}</Text>}
                        <Text size="xs" c="dimmed">{d.type_retour_nom}</Text>
                      </Table.Td>
                      <Table.Td>
                        <Text size="sm" style={{ whiteSpace: "nowrap" }} title={d.projet_nom ?? undefined}>{d.projet_code || d.projet_nom || "—"}</Text>
                      </Table.Td>
                      <Table.Td>{d.responsable_nom ?? <Text size="sm" c="orange.8">{voc("Sans responsable")}</Text>}</Table.Td>
                      <Table.Td><Text size="sm">{d.etape_nom ?? "—"}</Text></Table.Td>
                      <Table.Td style={{ whiteSpace: "nowrap" }}><BadgeDelai dossier={d} compact /></Table.Td>
                      <Table.Td>
                        <Group gap={4} wrap="nowrap">
                          <Badge color={couleurStatutDossier(d.statut)} variant="light" tt="none">{libelleStatutDossier(d.statut)}</Badge>
                          {d.en_recours && <Badge color="red" variant="outline" tt="none">{voc("Recours")}</Badge>}
                        </Group>
                      </Table.Td>
                    </Table.Tr>
                  ))}
                  {dossiers.length === 0 && (
                    <Table.Tr>
                      <Table.Td colSpan={8}><Text size="sm" c="dimmed" ta="center" py="md">{voc("Aucun dossier.")}</Text></Table.Td>
                    </Table.Tr>
                  )}
                </Table.Tbody>
              </Table>
            </Table.ScrollContainer>
            {pages > 1 && <Pagination value={page} onChange={setPage} total={pages} size="sm" />}
          </Stack>
        </Grid.Col>
      </Grid>
      <SaisieDossierModal opened={saisie} onClose={saisieControles.close} />
      <FormulairePublicModal opened={formulaire} onClose={formulaireControles.close} />
    </Stack>
  );
}
