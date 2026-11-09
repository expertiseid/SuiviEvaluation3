import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Download, IdCard, ListChecks, Map as MapIcon, MapPin, Pencil, Phone, Search, Trash2, Upload } from "lucide-react";
import { Accordion, ActionIcon, Avatar, Badge, Button, Group, Modal, Pagination, Stack, Table, Text, TextInput, Tooltip } from "@mantine/core";
import { initiales } from "../../utils/texte";
import { useDebouncedValue } from "@mantine/hooks";
import { notifications } from "@mantine/notifications";
import { telechargerCartesBeneficiaires, useBeneficiaires, useDeleteBeneficiaire } from "../../api/beneficiaries";
import { useProjets } from "../../api/projects";
import { useStatutsParticuliers } from "../../api/referentiels";
import { confirmerSuppression } from "../../components/common/confirmerSuppression";
import { messageErreurApi } from "../../utils/erreurs";
import { BeneficiaireForm } from "./BeneficiaireForm";
import { VariablesBeneficiairesModal } from "./VariablesBeneficiairesModal";
import { useAuth } from "../../auth/useAuth";
import { ExportBeneficiairesModal } from "./ExportBeneficiairesModal";
import { ImportBeneficiairesModal } from "./ImportBeneficiairesModal";
import type { Beneficiaire, StatutParticulier } from "../../types";
import { TitreRubrique } from "../../components/common/TitreRubrique";
import { voc } from "../../utils/vocabulaire";

const TAILLE_PAGE = 25;
const CLE_SANS_PROJET = "sans-projet";
const SEXES: Record<string, { libelle: string; couleur: string }> = {
  F: { libelle: voc("Femme"), couleur: "grape" },
  M: { libelle: voc("Homme"), couleur: "blue" },
};

interface ActionsLigne {
  statuts: StatutParticulier[] | undefined;
  onModifier: (b: Beneficiaire) => void;
  onSupprimer: (b: Beneficiaire) => void;
  idEnSuppression: number | undefined;
}

/**
 * Un groupe de l'écran Bénéficiaires (un projet, ou « Sans projet ») : sa
 * propre requête filtrée et sa propre pagination. Un bénéficiaire inscrit à
 * plusieurs projets apparaît dans chacun de leurs groupes.
 */
function GroupeBeneficiaires({
  valeur,
  titre,
  projetId,
  search,
  actions,
}: {
  valeur: string;
  titre: string;
  projetId?: number;
  search: string;
  actions: ActionsLigne;
}) {
  const [page, setPage] = useState(1);
  const [impression, setImpression] = useState(false);
  const { data, isLoading } = useBeneficiaires(
    search || undefined,
    page,
    projetId ? { projet: projetId } : { sans_projet: true },
  );
  const nombrePages = data ? Math.ceil(data.count / TAILLE_PAGE) : 1;

  // Toute recherche repart de la première page — sinon on peut se retrouver
  // sur une page qui n'existe plus pour les nouveaux résultats filtrés.
  useEffect(() => {
    setPage(1);
  }, [search]);

  // Groupe vide masqué pendant une recherche (et toujours pour « Sans projet »).
  if (data && data.count === 0 && (search || !projetId)) return null;

  function libellesStatuts(b: Beneficiaire) {
    return b.statuts_particuliers.map((sid) => actions.statuts?.find((s) => s.id === sid)?.libelle).filter(Boolean);
  }

  return (
    <Accordion.Item value={valeur} bg="white">
      <Accordion.Control>
        <Group gap="sm" wrap="nowrap" style={{ minWidth: 0 }}>
          {titre.includes(" — ") ? (
            <>
              <Badge size="sm" variant="outline" color="gray" radius="sm" style={{ flexShrink: 0 }}>{titre.split(" — ")[0]}</Badge>
              <Text fw={600} size="sm" truncate>{titre.split(" — ").slice(1).join(" — ")}</Text>
            </>
          ) : <Text fw={600} size="sm">{titre}</Text>}
          {data && (
            <Badge variant="light" color={projetId ? "teal" : "gray"} size="sm">
              {data.count > 1 ? voc`${data.count} bénéficiaires` : voc`${data.count} bénéficiaire`}
            </Badge>
          )}
        </Group>
      </Accordion.Control>
      <Accordion.Panel>
        {projetId && (data?.count ?? 0) > 0 && (
          <Group justify="flex-end" mb="xs">
            <Button
              size="xs"
              variant="light"
              leftSection={<IdCard size={14} />}
              loading={impression}
              onClick={async () => {
                setImpression(true);
                try {
                  await telechargerCartesBeneficiaires({ projet: projetId }, `cartes_${titre.split(" — ")[0]}`);
                } finally {
                  setImpression(false);
                }
              }}
            >
              {voc("Imprimer les cartes de ce projet")}
            </Button>
          </Group>
        )}
        {isLoading ? (
          <Text size="sm" c="dimmed">{voc("Chargement…")}</Text>
        ) : data?.count === 0 ? (
          <Text size="sm" c="dimmed">{voc("Aucun bénéficiaire associé à ce projet pour l'instant.")}</Text>
        ) : (
          <Table.ScrollContainer minWidth={860}>
          <Table highlightOnHover verticalSpacing="xs">
            <Table.Thead>
              <Table.Tr>
                <Table.Th tt="uppercase" fz="xs" c="dimmed">{voc("Bénéficiaire")}</Table.Th>
                <Table.Th tt="uppercase" fz="xs" c="dimmed">{voc("Sexe et âge")}</Table.Th>
                <Table.Th tt="uppercase" fz="xs" c="dimmed">{voc("Téléphone")}</Table.Th>
                <Table.Th tt="uppercase" fz="xs" c="dimmed">{voc("Zone")}</Table.Th>
                <Table.Th tt="uppercase" fz="xs" c="dimmed">{voc("Statut particulier")}</Table.Th>
                {projetId && <Table.Th tt="uppercase" fz="xs" c="dimmed">{voc("Autres projets")}</Table.Th>}
                <Table.Th w={70} />
              </Table.Tr>
            </Table.Thead>
            <Table.Tbody>
              {data?.results.map((b) => {
                const autresProjets = [
                  ...new Set(b.participations.filter((p) => p.projet !== projetId).map((p) => p.projet_nom.split(" — ")[0])),
                ];
                return (
                  <Table.Tr key={b.id}>
                    <Table.Td>
                      <Group gap="sm" wrap="nowrap">
                        <Avatar size={34} radius="xl" variant="light" color={SEXES[b.sexe]?.couleur ?? "gray"}>{initiales(`${b.nom} ${b.prenom}`)}</Avatar>
                        <div style={{ minWidth: 0 }}>
                          <Text component={Link} to={`/beneficiaires/${b.id}`} size="sm" fw={600} c="dark.7" style={{ whiteSpace: "nowrap" }}>
                            {b.nom} {b.prenom}
                          </Text>
                          <Text size="xs" ff="monospace" c="dimmed">{b.identifiant}</Text>
                        </div>
                      </Group>
                    </Table.Td>
                    <Table.Td>
                      <Text size="sm" style={{ whiteSpace: "nowrap" }}>{SEXES[b.sexe]?.libelle ?? (b.sexe || "—")}</Text>
                      <Text size="xs" c="dimmed" style={{ whiteSpace: "nowrap" }}>{b.tranche_age ?? "—"}</Text>
                    </Table.Td>
                    <Table.Td>
                      {b.telephone ? (
                        <Group gap={6} wrap="nowrap">
                          <Phone size={13} color="var(--mantine-color-gray-6)" />
                          <Text size="sm" style={{ whiteSpace: "nowrap" }}>{b.telephone}</Text>
                        </Group>
                      ) : <Text size="sm" c="dimmed">—</Text>}
                    </Table.Td>
                    <Table.Td>
                      {b.zone_nom ? (
                        <Group gap={6} wrap="nowrap">
                          <MapPin size={13} color="var(--mantine-color-teal-6)" />
                          <Text size="sm" style={{ whiteSpace: "nowrap" }}>{b.zone_nom}</Text>
                        </Group>
                      ) : <Text size="sm" c="dimmed">—</Text>}
                    </Table.Td>
                    <Table.Td>
                      {libellesStatuts(b).length > 0 ? (
                        <Group gap={4} wrap="wrap">
                          {libellesStatuts(b).map((l) => (
                            <Badge key={l} variant="light" color="grape" size="sm" tt="none" fw={500}>{l}</Badge>
                          ))}
                        </Group>
                      ) : <Text size="sm" c="dimmed">—</Text>}
                    </Table.Td>
                    {projetId && (
                      <Table.Td>
                        {autresProjets.length ? (
                          <Group gap={4} wrap="wrap">
                            {autresProjets.map((code) => <Badge key={code} size="xs" variant="outline" color="gray" radius="sm">{code}</Badge>)}
                          </Group>
                        ) : <Text size="sm" c="dimmed">—</Text>}
                      </Table.Td>
                    )}
                    <Table.Td>
                      <Group gap={4} wrap="nowrap">
                        <Tooltip label={voc("Modifier")}>
                          <ActionIcon size="sm" variant="subtle" onClick={() => actions.onModifier(b)}>
                            <Pencil size={13} />
                          </ActionIcon>
                        </Tooltip>
                        <Tooltip label={voc("Supprimer")}>
                          <ActionIcon
                            size="sm"
                            variant="subtle"
                            color="red"
                            loading={actions.idEnSuppression === b.id}
                            onClick={() => actions.onSupprimer(b)}
                          >
                            <Trash2 size={13} />
                          </ActionIcon>
                        </Tooltip>
                      </Group>
                    </Table.Td>
                  </Table.Tr>
                );
              })}
            </Table.Tbody>
          </Table>
          </Table.ScrollContainer>
        )}

        {nombrePages > 1 && (
          <Group justify="center" mt="sm">
            <Pagination size="sm" value={page} onChange={setPage} total={nombrePages} />
          </Group>
        )}
      </Accordion.Panel>
    </Accordion.Item>
  );
}

export function BeneficiairesListPage() {
  const [search, setSearch] = useState("");
  const [searchDebounce] = useDebouncedValue(search, 300);
  const { data: total } = useBeneficiaires(searchDebounce || undefined, 1);
  const { data: projets } = useProjets();
  const { data: statuts } = useStatutsParticuliers();
  const deleteBeneficiaire = useDeleteBeneficiaire();
  const [modalOpen, setModalOpen] = useState(false);
  const [modalImportOpen, setModalImportOpen] = useState(false);
  const [modalVariablesOpen, setModalVariablesOpen] = useState(false);
  const { user } = useAuth();
  const [beneficiaireEnEdition, setBeneficiaireEnEdition] = useState<Beneficiaire | null>(null);

  const projetsTries = [...(projets ?? [])].sort((a, b) => a.code.localeCompare(b.code));
  const toutesLesCles = [...projetsTries.map((p) => String(p.id)), CLE_SANS_PROJET];
  // Premier groupe ouvert par défaut (tous pendant une recherche) ; ensuite, le choix de l'utilisateur.
  const [ouverts, setOuverts] = useState<string[] | null>(null);
  const valeurOuverte = ouverts ?? (searchDebounce ? toutesLesCles : toutesLesCles.slice(0, 1));

  function handleSupprimer(b: Beneficiaire) {
    confirmerSuppression({
      message: voc`Supprimer "${b.nom} ${b.prenom}" ? Ses participations aux projets et signalements de doublon associés seront aussi supprimés. Cette action est irréversible.`,
      onConfirm: async () => {
        try {
          await deleteBeneficiaire.mutateAsync(b.id);
          notifications.show({ message: voc("Bénéficiaire supprimé"), color: "green" });
        } catch (error) {
          notifications.show({
            message: messageErreurApi(error, voc("Erreur lors de la suppression du bénéficiaire")),
            color: "red",
          });
        }
      },
    });
  }

  const [modalExportOpen, setModalExportOpen] = useState(false);

  const actions: ActionsLigne = {
    statuts,
    onModifier: setBeneficiaireEnEdition,
    onSupprimer: handleSupprimer,
    idEnSuppression: deleteBeneficiaire.isPending ? deleteBeneficiaire.variables : undefined,
  };

  return (
    <Stack gap="md">
      <Group justify="space-between">
        <TitreRubrique route="/beneficiaires" defaut={voc("Bénéficiaires")} />
        <Group gap="xs">
          {user?.role === "ADMIN" && (
            <Button variant="light" color="grape" leftSection={<ListChecks size={16} />} onClick={() => setModalVariablesOpen(true)}>
              {voc("Variables à collecter")}
            </Button>
          )}
          <Button component={Link} to="/carte" variant="light" color="teal" leftSection={<MapIcon size={16} />}>
            {voc("Cartographie")}
          </Button>
          <Button variant="light" leftSection={<Download size={16} />} onClick={() => setModalExportOpen(true)}>
            {voc("Exporter")}
          </Button>
          <Button variant="light" leftSection={<Upload size={16} />} onClick={() => setModalImportOpen(true)}>
            {voc("Importer depuis Excel")}
          </Button>
          <Button onClick={() => setModalOpen(true)}>{voc("Nouveau bénéficiaire")}</Button>
        </Group>
      </Group>

      <Group justify="space-between" align="flex-end">
        <TextInput
          placeholder={voc("Rechercher par nom, téléphone, pièce d'identité…")}
          leftSection={<Search size={15} />}
          value={search}
          onChange={(e) => {
            setSearch(e.currentTarget.value);
            setOuverts(null);
          }}
          w={400}
          maw="100%"
        />
        <Group gap="xs">
          {total && <Text size="sm" c="dimmed">{total.count > 1 ? voc`${total.count} bénéficiaires au total` : voc`${total.count} bénéficiaire au total`}</Text>}
          <Button size="xs" variant="subtle" color="gray" onClick={() => setOuverts(toutesLesCles)}>{voc("Tout déplier")}</Button>
          <Button size="xs" variant="subtle" color="gray" onClick={() => setOuverts([])}>{voc("Tout replier")}</Button>
        </Group>
      </Group>

      <Accordion
        multiple
        variant="separated"
        radius="md"
        value={valeurOuverte}
        onChange={setOuverts}
      >
        {projetsTries.map((p) => (
          <GroupeBeneficiaires
            key={p.id}
            valeur={String(p.id)}
            titre={`${p.code} — ${p.nom}`}
            projetId={p.id}
            search={searchDebounce}
            actions={actions}
          />
        ))}
        <GroupeBeneficiaires valeur={CLE_SANS_PROJET} titre={voc("Sans projet")} search={searchDebounce} actions={actions} />
      </Accordion>

      <ExportBeneficiairesModal
        opened={modalExportOpen}
        onClose={() => setModalExportOpen(false)}
        projets={projetsTries}
      />

      <Modal opened={modalOpen} onClose={() => setModalOpen(false)} title={voc("Nouveau bénéficiaire")} size="lg">
        <BeneficiaireForm onDone={() => setModalOpen(false)} />
      </Modal>

      <Modal
        opened={!!beneficiaireEnEdition}
        onClose={() => setBeneficiaireEnEdition(null)}
        title={voc`Modifier — ${beneficiaireEnEdition?.nom ?? ""} ${beneficiaireEnEdition?.prenom ?? ""}`}
        size="lg"
      >
        {beneficiaireEnEdition && (
          <BeneficiaireForm
            key={beneficiaireEnEdition.id}
            beneficiaire={beneficiaireEnEdition}
            onDone={() => setBeneficiaireEnEdition(null)}
          />
        )}
      </Modal>

      <ImportBeneficiairesModal opened={modalImportOpen} onClose={() => setModalImportOpen(false)} />
      <VariablesBeneficiairesModal opened={modalVariablesOpen} onClose={() => setModalVariablesOpen(false)} />
    </Stack>
  );
}
