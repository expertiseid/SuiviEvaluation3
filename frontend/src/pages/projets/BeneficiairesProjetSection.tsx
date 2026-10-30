import { useEffect, useState } from "react";
import { Search, Upload, UserPlus } from "lucide-react";
import { Badge, Button, Checkbox, Divider, Group, Pagination, Stack, Table, Text, TextInput, Title } from "@mantine/core";
import { useDebouncedValue } from "@mantine/hooks";
import { notifications } from "@mantine/notifications";
import { useQueryClient } from "@tanstack/react-query";
import { useBeneficiaires, useCreateParticipation } from "../../api/beneficiaries";
import { ImportBeneficiairesModal } from "../beneficiaires/ImportBeneficiairesModal";
import type { Beneficiaire, ProjetResume } from "../../types";
import { voc } from "../../utils/vocabulaire";

const TAILLE_PAGE = 25;

/**
 * Onglet « Cibles bénéficiaires » de la fiche projet : associe des
 * bénéficiaires au projet, soit par import Excel (même modèle que l'écran
 * Bénéficiaires), soit en les recherchant dans la base — ceux déjà associés
 * au projet sont grisés, les autres peuvent être cochés puis ajoutés d'un coup.
 */
export function BeneficiairesProjetSection({ projet }: { projet: ProjetResume }) {
  const queryClient = useQueryClient();
  const [search, setSearch] = useState("");
  const [searchDebounce] = useDebouncedValue(search, 300);
  const [page, setPage] = useState(1);
  const { data, isLoading } = useBeneficiaires(searchDebounce || undefined, page);
  const nombrePages = data ? Math.ceil(data.count / TAILLE_PAGE) : 1;
  const createParticipation = useCreateParticipation();
  const [selection, setSelection] = useState<Map<number, Beneficiaire>>(new Map());
  const [ajoutEnCours, setAjoutEnCours] = useState(false);
  const [modalImportOpen, setModalImportOpen] = useState(false);

  // Toute recherche repart de la première page (voir BeneficiairesListPage).
  useEffect(() => {
    setPage(1);
  }, [searchDebounce]);

  function dejaAssocie(b: Beneficiaire) {
    return b.participations.some((p) => p.projet === projet.id);
  }

  function basculer(b: Beneficiaire) {
    setSelection((prev) => {
      const suivante = new Map(prev);
      if (suivante.has(b.id)) suivante.delete(b.id);
      else suivante.set(b.id, b);
      return suivante;
    });
  }

  const selectionnables = data?.results.filter((b) => !dejaAssocie(b)) ?? [];
  const toutePageCochee = selectionnables.length > 0 && selectionnables.every((b) => selection.has(b.id));
  const pagePartiellementCochee = !toutePageCochee && selectionnables.some((b) => selection.has(b.id));

  function basculerPage() {
    setSelection((prev) => {
      const suivante = new Map(prev);
      selectionnables.forEach((b) => (toutePageCochee ? suivante.delete(b.id) : suivante.set(b.id, b)));
      return suivante;
    });
  }

  async function ajouterSelection() {
    const aujourdhui = new Date().toISOString().slice(0, 10);
    setAjoutEnCours(true);
    let ajoutes = 0;
    const echecs: string[] = [];
    for (const b of selection.values()) {
      try {
        await createParticipation.mutateAsync({ beneficiaire: b.id, projet: projet.id, date_inscription: aujourdhui });
        ajoutes += 1;
      } catch {
        echecs.push(`${b.nom} ${b.prenom}`);
      }
    }
    setAjoutEnCours(false);
    setSelection(new Map());
    queryClient.invalidateQueries({ queryKey: ["beneficiaires"] });
    if (ajoutes > 0) {
      notifications.show({ message: voc`${ajoutes} bénéficiaire(s) associé(s) au projet`, color: "green" });
    }
    if (echecs.length > 0) {
      notifications.show({ message: voc`Échec de l'association pour : ${echecs.join(", ")}`, color: "red", autoClose: 8000 });
    }
  }

  return (
    <Stack gap="sm">
      <Divider mt="xs" />
      <Group justify="space-between" align="center">
        <Title order={5}>{voc("Bénéficiaires associés au projet")}</Title>
        <Button variant="light" size="xs" leftSection={<Upload size={14} />} onClick={() => setModalImportOpen(true)}>
          {voc("Importer une liste (Excel)")}
        </Button>
      </Group>

      <TextInput
        leftSection={<Search size={14} />}
        placeholder={voc("Rechercher un bénéficiaire par nom, téléphone, pièce d'identité…")}
        value={search}
        onChange={(e) => setSearch(e.currentTarget.value)}
        // Entrée ne doit pas soumettre le formulaire du projet qui englobe cet onglet.
        onKeyDown={(e) => {
          if (e.key === "Enter") e.preventDefault();
        }}
      />

      {isLoading ? (
        <Text size="sm" c="dimmed">{voc("Chargement…")}</Text>
      ) : data && data.results.length === 0 ? (
        <Text size="sm" c="dimmed">{voc("Aucun bénéficiaire trouvé.")}</Text>
      ) : (
        <Table highlightOnHover verticalSpacing={4} fz="sm">
          <Table.Thead>
            <Table.Tr>
              <Table.Th w={36}>
                <Checkbox
                  size="xs"
                  checked={toutePageCochee}
                  indeterminate={pagePartiellementCochee}
                  disabled={selectionnables.length === 0}
                  onChange={basculerPage}
                  aria-label={voc("Tout cocher sur cette page")}
                />
              </Table.Th>
              <Table.Th>{voc("Nom")}</Table.Th>
              <Table.Th>{voc("Sexe")}</Table.Th>
              <Table.Th>{voc("Zone")}</Table.Th>
              <Table.Th>{voc("Téléphone")}</Table.Th>
              <Table.Th />
            </Table.Tr>
          </Table.Thead>
          <Table.Tbody>
            {data?.results.map((b) => {
              const associe = dejaAssocie(b);
              return (
                <Table.Tr
                  key={b.id}
                  style={{ opacity: associe ? 0.5 : 1, cursor: associe ? "default" : "pointer" }}
                  onClick={() => !associe && basculer(b)}
                >
                  <Table.Td>
                    <Checkbox
                      size="xs"
                      checked={associe || selection.has(b.id)}
                      disabled={associe}
                      onChange={() => basculer(b)}
                      onClick={(e) => e.stopPropagation()}
                      aria-label={voc`Sélectionner ${b.nom} ${b.prenom}`}
                    />
                  </Table.Td>
                  <Table.Td>{b.nom} {b.prenom}</Table.Td>
                  <Table.Td>{b.sexe}</Table.Td>
                  <Table.Td>{b.zone_nom ?? "—"}</Table.Td>
                  <Table.Td>{b.telephone || "—"}</Table.Td>
                  <Table.Td>
                    {associe && <Badge size="xs" variant="light" color="gray">{voc("Déjà associé")}</Badge>}
                  </Table.Td>
                </Table.Tr>
              );
            })}
          </Table.Tbody>
        </Table>
      )}

      <Group justify="space-between">
        {nombrePages > 1 ? <Pagination size="sm" value={page} onChange={setPage} total={nombrePages} /> : <div />}
        <Button
          size="xs"
          leftSection={<UserPlus size={14} />}
          disabled={selection.size === 0}
          loading={ajoutEnCours}
          onClick={ajouterSelection}
        >
          {voc("Ajouter la sélection")}{selection.size > 0 ? ` (${selection.size})` : ""}
        </Button>
      </Group>

      <ImportBeneficiairesModal
        opened={modalImportOpen}
        onClose={() => setModalImportOpen(false)}
        projet={{ id: projet.id, nom: projet.nom }}
      />
    </Stack>
  );
}
