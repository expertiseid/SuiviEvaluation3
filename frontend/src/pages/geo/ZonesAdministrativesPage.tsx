import { useMemo, useState } from "react";
import {
  ArrowDown,
  ArrowUp,
  ChevronDown,
  ChevronRight,
  ListTree,
  MapPin,
  Pencil,
  Plus,
  Search,
  Settings2,
  Trash2,
} from "lucide-react";
import {
  ActionIcon,
  Badge,
  Box,
  Button,
  Card,
  Collapse,
  Group,
  Modal,
  NumberInput,
  Select,
  Stack,
  Switch,
  Tabs,
  Text,
  TextInput,
  Tooltip,
} from "@mantine/core";
import { notifications } from "@mantine/notifications";
import {
  useCreateNiveauAdministratif,
  useCreateZone,
  useDeleteNiveauAdministratif,
  useDeleteZone,
  useNiveauxAdministratifs,
  useUpdateNiveauAdministratif,
  useUpdateZone,
  useZones,
} from "../../api/geo";
import { BoutonModeEdition } from "../../components/common/BoutonModeEdition";
import { EmptyState } from "../../components/common/EmptyState";
import { confirmerSuppression } from "../../components/common/confirmerSuppression";
import { correspond } from "../../utils/recherche";
import { PAYS_MONDE } from "../../utils/pays";
import type { NiveauAdministratif, Zone } from "../../types";
import { TitreRubrique } from "../../components/common/TitreRubrique";
import { voc } from "../../utils/vocabulaire";
import { traduireDonnee } from "../../utils/i18n";

function messageErreurSuppression(defaut: string) {
  return voc`${defaut} — vérifie qu'aucune zone n'en dépend encore.`;
}

// ================== Onglet 1 : Configuration des niveaux ==================

function NiveauModal({
  opened,
  onClose,
  niveauExistant,
}: {
  opened: boolean;
  onClose: () => void;
  niveauExistant?: NiveauAdministratif | null;
}) {
  const updateNiveau = useUpdateNiveauAdministratif();
  const [nomNiveau, setNomNiveau] = useState(niveauExistant?.nom_niveau ?? "");
  const [sautAutorise, setSautAutorise] = useState(niveauExistant?.saut_niveau_autorise ?? true);
  const [aideCode, setAideCode] = useState(niveauExistant?.aide_code ?? "");

  function reinitialiser() {
    setNomNiveau(niveauExistant?.nom_niveau ?? "");
    setSautAutorise(niveauExistant?.saut_niveau_autorise ?? true);
    setAideCode(niveauExistant?.aide_code ?? "");
  }

  async function handleSave() {
    if (!nomNiveau.trim() || !niveauExistant) return;
    try {
      await updateNiveau.mutateAsync({
        id: niveauExistant.id,
        payload: { nom_niveau: nomNiveau.trim(), saut_niveau_autorise: sautAutorise, aide_code: aideCode },
      });
      notifications.show({ message: voc("Niveau modifié"), color: "green" });
      onClose();
    } catch {
      notifications.show({ message: voc("Erreur lors de la modification du niveau"), color: "red" });
    }
  }

  return (
    <Modal opened={opened} onClose={onClose} onExitTransitionEnd={reinitialiser} title={voc("Modifier le niveau")}>
      <Stack gap="sm">
        <TextInput
          label={voc("Nom du niveau")}
          description={voc("Ex : « Région », « Province », « Département », « Commune », « Village »...")}
          value={nomNiveau}
          onChange={(e) => setNomNiveau(e.currentTarget.value)}
          required
        />
        <TextInput
          label={voc("Aide à la saisie")}
          description={voc("Exemple affiché comme indication (facultatif)")}
          placeholder={voc("Ex : Kadiogo")}
          value={aideCode}
          onChange={(e) => setAideCode(e.currentTarget.value)}
        />
        <Switch
          label={voc("Autoriser à sauter ce niveau")}
          description={voc("Une zone du niveau suivant pourra alors être rattachée directement à un ancêtre plus haut, sans passer par ce niveau — utile car la précision des données de terrain varie.")}
          checked={sautAutorise}
          onChange={(e) => setSautAutorise(e.currentTarget.checked)}
        />
        <Group justify="flex-end">
          <Button onClick={handleSave} loading={updateNiveau.isPending}>{voc("Enregistrer")}</Button>
        </Group>
      </Stack>
    </Modal>
  );
}

function ConfigurationNiveaux({
  pays,
  niveaux,
  editionActive,
}: {
  pays: string;
  niveaux: NiveauAdministratif[];
  editionActive: boolean;
}) {
  const createNiveau = useCreateNiveauAdministratif();
  const updateNiveau = useUpdateNiveauAdministratif();
  const deleteNiveau = useDeleteNiveauAdministratif();
  const [nomNouveauNiveau, setNomNouveauNiveau] = useState("");
  const [niveauEnEdition, setNiveauEnEdition] = useState<NiveauAdministratif | null>(null);

  const tries = useMemo(() => [...niveaux].sort((a, b) => a.ordre - b.ordre), [niveaux]);

  async function deplacer(index: number, direction: -1 | 1) {
    const autre = tries[index + direction];
    const courant = tries[index];
    if (!autre) return;

    const apresEchange = tries
      .map((n) => {
        if (n.id === courant.id) return { ...n, ordre: autre.ordre };
        if (n.id === autre.id) return { ...n, ordre: courant.ordre };
        return n;
      })
      .sort((a, b) => a.ordre - b.ordre);

    try {
      await Promise.all(
        apresEchange.map((niveau, i) => {
          const original = tries.find((n) => n.id === niveau.id)!;
          const parentAttendu = i === 0 ? null : apresEchange[i - 1].id;
          const payload: Partial<NiveauAdministratif> = {};
          if (niveau.ordre !== original.ordre) payload.ordre = niveau.ordre;
          if (parentAttendu !== original.niveau_parent) payload.niveau_parent = parentAttendu;
          return Object.keys(payload).length > 0
            ? updateNiveau.mutateAsync({ id: niveau.id, payload })
            : Promise.resolve();
        }),
      );
    } catch {
      notifications.show({ message: voc("Erreur lors du réordonnancement"), color: "red" });
    }
  }

  async function ajouterNiveau() {
    if (!nomNouveauNiveau.trim()) {
      notifications.show({ message: voc("Le nom du niveau est requis."), color: "orange" });
      return;
    }
    const dernier = tries[tries.length - 1];
    try {
      await createNiveau.mutateAsync({
        pays,
        nom_niveau: nomNouveauNiveau.trim(),
        ordre: dernier ? dernier.ordre + 1 : 1,
        niveau_parent: dernier ? dernier.id : null,
        saut_niveau_autorise: true,
      });
      notifications.show({ message: voc("Niveau ajouté"), color: "green" });
      setNomNouveauNiveau("");
    } catch {
      notifications.show({ message: voc("Erreur lors de l'ajout du niveau"), color: "red" });
    }
  }

  function supprimerNiveau(niveau: NiveauAdministratif) {
    confirmerSuppression({
      message: voc`Supprimer le niveau « ${niveau.nom_niveau} » ? Cette action est irréversible.`,
      onConfirm: async () => {
        try {
          await deleteNiveau.mutateAsync(niveau.id);
          notifications.show({ message: voc("Niveau supprimé"), color: "green" });
        } catch {
          notifications.show({
            message: messageErreurSuppression(voc("Impossible de supprimer ce niveau")),
            color: "red",
          });
        }
      },
    });
  }

  return (
    <Card withBorder padding="lg" radius="md">
      <Text fw={600} mb="xs">{voc("Configuration des niveaux")}</Text>
      <Text size="sm" c="dimmed" mb="sm">
        {voc("Nous définissons ici les niveaux administratifs propres à ce pays (nombre, noms, ordre) — par exemple « Région » → « Province » → « Commune » → « Village », ou « Région » → « Département » → « Commune ». Propre à ce pays, sans effet sur les autres.")}
      </Text>

      {tries.length === 0 ? (
        <EmptyState icon={<ListTree size={32} strokeWidth={1.5} />} message={voc("Aucun niveau défini pour l'instant — commence par en ajouter un ci-dessous.")} />
      ) : (
        <Stack gap={6} mb="sm">
          {tries.map((niveau, index) => (
            <Group key={niveau.id} gap={6} wrap="nowrap" justify="space-between">
              <Group gap={6} wrap="nowrap">
                <Text size="sm" c="dimmed" w={20}>{niveau.ordre}.</Text>
                <Text size="sm" fw={500}>{traduireDonnee(niveau.nom_niveau)}</Text>
                {niveau.saut_niveau_autorise && (
                  <Badge size="xs" variant="light" color="gray">{voc("Saut autorisé")}</Badge>
                )}
              </Group>
              <Group gap={2} wrap="nowrap">
                <Tooltip label={voc("Monter")}>
                  <ActionIcon size="sm" variant="subtle" disabled={index === 0} onClick={() => deplacer(index, -1)}>
                    <ArrowUp size={13} />
                  </ActionIcon>
                </Tooltip>
                <Tooltip label={voc("Descendre")}>
                  <ActionIcon size="sm" variant="subtle" disabled={index === tries.length - 1} onClick={() => deplacer(index, 1)}>
                    <ArrowDown size={13} />
                  </ActionIcon>
                </Tooltip>
                {editionActive && (
                <Group gap={2} wrap="nowrap">
                  <Tooltip label={voc("Modifier")}>
                    <ActionIcon size="sm" variant="subtle" onClick={() => setNiveauEnEdition(niveau)}>
                      <Pencil size={13} />
                    </ActionIcon>
                  </Tooltip>
                  <Tooltip label={voc("Supprimer")}>
                    <ActionIcon size="sm" variant="subtle" color="red" loading={deleteNiveau.isPending} onClick={() => supprimerNiveau(niveau)}>
                      <Trash2 size={13} />
                    </ActionIcon>
                  </Tooltip>
                </Group>
                )}
              </Group>
            </Group>
          ))}
        </Stack>
      )}

      <Group gap="xs" align="flex-end">
        <TextInput
          size="xs"
          label={voc("Ajouter un niveau")}
          placeholder={voc("Ex : Région")}
          value={nomNouveauNiveau}
          onChange={(e) => setNomNouveauNiveau(e.currentTarget.value)}
          style={{ flex: 1 }}
        />
        <Button size="xs" variant="light" onClick={ajouterNiveau} loading={createNiveau.isPending}>
          {voc("Ajouter")}
        </Button>
      </Group>

      <NiveauModal opened={!!niveauEnEdition} onClose={() => setNiveauEnEdition(null)} niveauExistant={niveauEnEdition} />
    </Card>
  );
}

// ================== Onglet 2 : Arborescence & saisie ==================

function ZoneModal({
  opened,
  onClose,
  niveauAdministratif,
  zoneParent,
  zoneExistante,
  niveaux,
  zones,
}: {
  opened: boolean;
  onClose: () => void;
  niveauAdministratif: NiveauAdministratif | null;
  zoneParent: Zone | null;
  zoneExistante?: Zone | null;
  niveaux: NiveauAdministratif[];
  zones: Zone[];
}) {
  const createZone = useCreateZone();
  const updateZone = useUpdateZone();
  const [code, setCode] = useState(zoneExistante?.code ?? "");
  const [nom, setNom] = useState(zoneExistante?.nom ?? "");
  const [parentId, setParentId] = useState<string | null>(
    zoneExistante?.parent ? String(zoneExistante.parent) : null,
  );
  const [latitude, setLatitude] = useState<number | string>(zoneExistante?.latitude ?? "");
  const [longitude, setLongitude] = useState<number | string>(zoneExistante?.longitude ?? "");

  function reinitialiser() {
    setLatitude(zoneExistante?.latitude ?? "");
    setLongitude(zoneExistante?.longitude ?? "");
    setCode(zoneExistante?.code ?? "");
    setNom(zoneExistante?.nom ?? "");
    setParentId(zoneExistante?.parent ? String(zoneExistante.parent) : null);
  }

  const niveauDeLaZone = zoneExistante ? niveaux.find((n) => n.id === zoneExistante.niveau_administratif) : niveauAdministratif;
  const niveauParentAttendu = niveauDeLaZone ? niveaux.find((n) => n.id === niveauDeLaZone.niveau_parent) : undefined;
  const optionsParent = niveauParentAttendu
    ? zones
        .filter((z) => z.niveau_administratif === niveauParentAttendu.id && z.id !== zoneExistante?.id)
        .map((z) => ({ value: String(z.id), label: z.code ? `${z.code} — ${z.nom}` : z.nom }))
    : [];

  async function handleSave() {
    if (!nom.trim()) {
      notifications.show({ message: voc("Le nom est requis."), color: "orange" });
      return;
    }
    try {
      if (zoneExistante) {
        await updateZone.mutateAsync({
          id: zoneExistante.id,
          payload: {
            code: code.trim(),
            nom: nom.trim(),
            parent: parentId ? Number(parentId) : null,
            latitude: latitude === "" ? null : String(latitude),
            longitude: longitude === "" ? null : String(longitude),
          },
        });
        notifications.show({ message: voc("Zone modifiée"), color: "green" });
      } else if (niveauAdministratif) {
        await createZone.mutateAsync({
          niveau_administratif: niveauAdministratif.id,
          parent: zoneParent?.id ?? null,
          code: code.trim(),
          nom: nom.trim(),
        });
        notifications.show({ message: voc("Zone ajoutée"), color: "green" });
      }
      onClose();
    } catch {
      notifications.show({ message: voc("Erreur lors de l'enregistrement"), color: "red" });
    }
  }

  const niveauActif = zoneExistante ? null : niveauAdministratif;

  return (
    <Modal
      opened={opened}
      onClose={onClose}
      onExitTransitionEnd={reinitialiser}
      title={zoneExistante ? voc("Modifier la zone") : niveauActif ? voc`Ajouter — ${traduireDonnee(niveauActif.nom_niveau)}` : voc("Ajouter une zone")}
    >
      <Stack gap="sm">
        <TextInput
          label={voc("Code")}
          description={voc("Code administratif (pcode), si connu — facultatif")}
          placeholder={(zoneExistante ? undefined : niveauActif?.aide_code) || undefined}
          value={code}
          onChange={(e) => setCode(e.currentTarget.value)}
        />
        <TextInput label={voc("Nom")} value={nom} onChange={(e) => setNom(e.currentTarget.value)} required />
        {zoneExistante && niveauParentAttendu && (
          <Select
            label={voc`Rattachée à (${traduireDonnee(niveauParentAttendu.nom_niveau)})`}
            data={optionsParent}
            value={parentId}
            onChange={setParentId}
            searchable
            clearable={niveauDeLaZone?.saut_niveau_autorise}
          />
        )}
        {zoneExistante && (
          <Group grow>
            <NumberInput label={voc("Latitude du centre")} description={voc("Carte des bénéficiaires")} decimalScale={6} min={-90} max={90} value={latitude} onChange={setLatitude} />
            <NumberInput label={voc("Longitude du centre")} description={voc("Facultatif")} decimalScale={6} min={-180} max={180} value={longitude} onChange={setLongitude} />
          </Group>
        )}
        <Group justify="flex-end">
          <Button onClick={handleSave} loading={createZone.isPending || updateZone.isPending}>
            {zoneExistante ? voc("Enregistrer") : voc("Ajouter")}
          </Button>
        </Group>
      </Stack>
    </Modal>
  );
}

function NoeudZone({
  zone,
  niveaux,
  profondeur,
  enfantsParParent,
  niveauEnfant,
  onAjouter,
  onModifier,
  idsVisibles,
  editionActive,
}: {
  zone: Zone;
  niveaux: NiveauAdministratif[];
  profondeur: number;
  enfantsParParent: Map<number | null, Zone[]>;
  niveauEnfant: NiveauAdministratif | undefined;
  onAjouter: (niveau: NiveauAdministratif, parent: Zone) => void;
  onModifier: (zone: Zone) => void;
  idsVisibles: Set<number> | null;
  editionActive: boolean;
}) {
  const deleteZone = useDeleteZone();
  const [ouvert, setOuvert] = useState(true);
  const enfants = (enfantsParParent.get(zone.id) ?? []).filter((z) => !idsVisibles || idsVisibles.has(z.id));
  const enChercheOuvert = idsVisibles ? true : ouvert;
  const niveauPourEnfantsDesEnfants = niveauEnfant
    ? niveaux.find((n) => n.niveau_parent === niveauEnfant.id)
    : undefined;

  function supprimer() {
    confirmerSuppression({
      message: voc`Supprimer « ${zone.nom} » ? Cette action est irréversible.`,
      onConfirm: async () => {
        try {
          await deleteZone.mutateAsync(zone.id);
          notifications.show({ message: voc("Zone supprimée"), color: "green" });
        } catch {
          notifications.show({
            message: messageErreurSuppression(voc("Impossible de supprimer cette zone")),
            color: "red",
          });
        }
      },
    });
  }

  const estRacine = profondeur === 0;

  return (
    <Card
      withBorder
      padding={estRacine ? "md" : "sm"}
      radius="sm"
      mt={estRacine ? 0 : "xs"}
      ml={profondeur * 24}
      shadow={estRacine ? "xs" : undefined}
      style={{ borderLeft: `${estRacine ? 6 : 4}px solid var(--mantine-color-teal-6)` }}
    >
      <Group justify="space-between" gap={6} wrap="nowrap">
        <Group gap={6} wrap="nowrap">
          {enfants.length > 0 && (
            <ActionIcon size="sm" variant="subtle" color="gray" onClick={() => setOuvert((v) => !v)}>
              {ouvert ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
            </ActionIcon>
          )}
          <Badge color="teal" variant={estRacine ? "filled" : "light"} size="sm">{traduireDonnee(zone.niveau_administratif_nom)}</Badge>
          <Text size={estRacine ? "md" : "sm"} fw={estRacine ? 700 : 400}>
            {zone.code && <Text span fw={700}>{zone.code} — </Text>}
            {zone.nom}
          </Text>
        </Group>
        {editionActive && (
        <Group gap={4} wrap="nowrap">
          <Tooltip label={voc("Modifier")}>
            <ActionIcon size="sm" variant="subtle" onClick={() => onModifier(zone)}>
              <Pencil size={13} />
            </ActionIcon>
          </Tooltip>
          <Tooltip label={voc("Supprimer")}>
            <ActionIcon size="sm" variant="subtle" color="red" loading={deleteZone.isPending} onClick={supprimer}>
              <Trash2 size={13} />
            </ActionIcon>
          </Tooltip>
        </Group>
        )}
      </Group>

      {niveauEnfant && (
        <Button size="xs" variant="subtle" leftSection={<Plus size={13} />} mt={6} onClick={() => onAjouter(niveauEnfant, zone)}>
          {voc`Ajouter ${traduireDonnee(niveauEnfant.nom_niveau)}`}
        </Button>
      )}

      <Collapse expanded={enChercheOuvert}>
        {enfants.map((enfant) => (
          <NoeudZone
            key={enfant.id}
            zone={enfant}
            niveaux={niveaux}
            profondeur={profondeur + 1}
            enfantsParParent={enfantsParParent}
            niveauEnfant={niveauPourEnfantsDesEnfants}
            onAjouter={onAjouter}
            onModifier={onModifier}
            idsVisibles={idsVisibles}
            editionActive={editionActive}
          />
        ))}
      </Collapse>
    </Card>
  );
}

function Arborescence({
  niveaux,
  zones,
  editionActive,
}: {
  niveaux: NiveauAdministratif[];
  zones: Zone[];
  editionActive: boolean;
}) {
  const [modalAjout, setModalAjout] = useState<{ niveau: NiveauAdministratif; parent: Zone | null } | null>(null);
  const [zoneEnEdition, setZoneEnEdition] = useState<Zone | null>(null);
  const [recherche, setRecherche] = useState("");

  const niveauRacine = niveaux.find((n) => n.niveau_parent === null);

  const enfantsParParent = useMemo(() => {
    const map = new Map<number | null, Zone[]>();
    for (const z of zones) {
      const cle = z.parent;
      if (!map.has(cle)) map.set(cle, []);
      map.get(cle)!.push(z);
    }
    return map;
  }, [zones]);

  const racines = enfantsParParent.get(null) ?? [];
  const arbreVide = racines.length === 0;

  const idsVisibles = useMemo(() => {
    if (!recherche.trim()) return null;
    const visibles = new Set<number>();
    function visiter(zone: Zone): boolean {
      const enfants = enfantsParParent.get(zone.id) ?? [];
      const unEnfantVisible = enfants.map(visiter).some(Boolean);
      const soiMatch = correspond(zone.nom, recherche) || correspond(zone.code ?? "", recherche);
      if (soiMatch || unEnfantVisible) {
        visibles.add(zone.id);
        return true;
      }
      return false;
    }
    racines.forEach(visiter);
    return visibles;
  }, [racines, enfantsParParent, recherche]);

  const racinesFiltrees = idsVisibles ? racines.filter((r) => idsVisibles.has(r.id)) : racines;

  return (
    <Card withBorder padding="lg" radius="md" mih={480}>
      <Group justify="space-between" mb="sm">
        <Text fw={600}>{voc("Arborescence")}</Text>
        {niveauRacine && (
          <Button size="sm" leftSection={<Plus size={14} />} onClick={() => setModalAjout({ niveau: niveauRacine, parent: null })}>
            {arbreVide ? voc`Créer ${traduireDonnee(niveauRacine.nom_niveau)}` : voc`Ajouter ${traduireDonnee(niveauRacine.nom_niveau)}`}
          </Button>
        )}
      </Group>

      {!arbreVide && (
        <TextInput
          placeholder={voc("Rechercher une zone…")}
          leftSection={<Search size={15} />}
          value={recherche}
          onChange={(e) => setRecherche(e.currentTarget.value)}
          maw={400}
          mb="sm"
        />
      )}

      {!niveauRacine ? (
        <EmptyState
          icon={<ListTree size={32} strokeWidth={1.5} />}
          message={voc("Aucun niveau n'est configuré — passe d'abord par l'onglet « Configuration des niveaux ».")}
        />
      ) : arbreVide ? (
        <EmptyState icon={<ListTree size={32} strokeWidth={1.5} />} message={voc`Aucune zone « ${traduireDonnee(niveauRacine.nom_niveau)} » pour le moment.`} />
      ) : racinesFiltrees.length === 0 ? (
        <EmptyState icon={<ListTree size={32} strokeWidth={1.5} />} message={voc("Aucune zone ne correspond à la recherche.")} />
      ) : (
        <Box style={{ overflowX: "auto" }}>
          <Stack gap="lg">
            {racinesFiltrees.map((racine) => (
              <NoeudZone
                key={racine.id}
                zone={racine}
                niveaux={niveaux}
                profondeur={0}
                enfantsParParent={enfantsParParent}
                niveauEnfant={niveaux.find((n) => n.niveau_parent === racine.niveau_administratif)}
                onAjouter={(niveau, parent) => setModalAjout({ niveau, parent })}
                onModifier={setZoneEnEdition}
                idsVisibles={idsVisibles}
                editionActive={editionActive}
              />
            ))}
          </Stack>
        </Box>
      )}

      <ZoneModal
        opened={!!modalAjout}
        onClose={() => setModalAjout(null)}
        niveauAdministratif={modalAjout?.niveau ?? null}
        zoneParent={modalAjout?.parent ?? null}
        niveaux={niveaux}
        zones={zones}
      />
      <ZoneModal
        opened={!!zoneEnEdition}
        onClose={() => setZoneEnEdition(null)}
        niveauAdministratif={null}
        zoneParent={null}
        zoneExistante={zoneEnEdition}
        niveaux={niveaux}
        zones={zones}
      />
    </Card>
  );
}

// ================== Page ==================

export function ZonesAdministrativesPage() {
  const [pays, setPays] = useState<string | null>("BF");
  const [editionActive, setEditionActive] = useState(false);
  const { data: niveaux, isLoading: chargementNiveaux } = useNiveauxAdministratifs(pays);
  const { data: zones, isLoading: chargementZones } = useZones({ pays: pays ?? undefined });

  return (
    <Stack gap="md">
      <Group justify="space-between" align="flex-end">
        <div>
          <TitreRubrique route="/zones-administratives" defaut={voc("Zones administratives")} />
          <Text c="dimmed" size="sm">
            {voc("Nous définissons ici les niveaux administratifs propres à chaque pays (Région, Province, Commune, Village, ou autre) et leur arborescence — utilisés pour localiser bénéficiaires et projets.")}</Text>
        </div>
        <Group gap="xs" align="flex-end">
          <BoutonModeEdition actif={editionActive} onToggle={() => setEditionActive((v) => !v)} />
          <Select
            label={voc("Pays")}
            data={PAYS_MONDE.map((p) => ({ value: p.code, label: p.nom }))}
            value={pays}
            onChange={setPays}
            searchable
            maw={260}
          />
        </Group>
      </Group>

      {!pays ? (
        <Card withBorder padding="md" radius="md">
          <EmptyState icon={<MapPin size={32} strokeWidth={1.5} />} message={voc("Choisis un pays pour configurer ses zones administratives.")} />
        </Card>
      ) : chargementNiveaux || chargementZones ? (
        <Text c="dimmed">{voc("Chargement…")}</Text>
      ) : (
        <Tabs defaultValue="arborescence" keepMounted={false}>
          <Tabs.List>
            <Tabs.Tab value="configuration" leftSection={<Settings2 size={15} />}>
              {voc("Configuration des niveaux")}
            </Tabs.Tab>
            <Tabs.Tab value="arborescence" leftSection={<ListTree size={15} />}>
              Arborescence &amp; saisie
            </Tabs.Tab>
          </Tabs.List>

          <Tabs.Panel value="configuration" pt="md">
            <ConfigurationNiveaux pays={pays} niveaux={niveaux ?? []} editionActive={editionActive} />
          </Tabs.Panel>

          <Tabs.Panel value="arborescence" pt="md">
            <Arborescence niveaux={niveaux ?? []} zones={zones ?? []} editionActive={editionActive} />
          </Tabs.Panel>
        </Tabs>
      )}
    </Stack>
  );
}
