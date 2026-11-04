import { type ReactNode, useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { AlertTriangle, Building2, Calendar, Landmark, Link2, LayoutGrid, Network, Pencil, Search, Trash2, UserRound, Wallet } from "lucide-react";
import { ActionIcon, Alert, Badge, Button, Card, Group, SimpleGrid, Stack, Text, TextInput, Title, Tooltip } from "@mantine/core";
import { notifications } from "@mantine/notifications";
import { useCadresStrategiques, useDeleteCadreStrategique, useTypesDocuments } from "../../api/strategy";
import { BoutonModeEdition } from "../../components/common/BoutonModeEdition";
import { EmptyState } from "../../components/common/EmptyState";
import { confirmerSuppression } from "../../components/common/confirmerSuppression";
import { correspond } from "../../utils/recherche";
import type { CadreStrategique } from "../../types";
import { TitreRubrique } from "../../components/common/TitreRubrique";
import { voc } from "../../utils/vocabulaire";
import { messageErreurApi } from "../../utils/erreurs";
import { useAuth } from "../../auth/useAuth";
import { lienDocument, rangMaillon } from "../../utils/chaineDocuments";
import { PROJET_STATUT_LABEL, PROJET_STATUT_TONE } from "../../utils/statusTones";
import { StatusBadge } from "../../components/common/StatusBadge";
import { locale } from "../../utils/i18n";
import { ChaineDocumentsModal } from "./ChaineDocumentsModal";
import { DocumentModal } from "./DocumentModal";

/** Date courte dans la langue de l'interface (jj/mm/aaaa en français). */
const dateCourte = (iso?: string | null) => (iso ? new Date(`${iso}T00:00:00`).toLocaleDateString(locale()) : "…");

/** Ligne « icône · libellé · valeur » d'une carte de document ; rien si la valeur est vide. */
function InfoLigne({ icone: Icone, libelle, children }: { icone: typeof Calendar; libelle: string; children: ReactNode }) {
  if (children == null || children === "" || children === false) return null;
  return (
    <Group gap={8} wrap="nowrap" align="flex-start">
      <Icone size={14} color="var(--mantine-color-dimmed)" style={{ marginTop: 2, flexShrink: 0 }} />
      <Text size="xs" c="dimmed" w={82} style={{ flexShrink: 0 }}>{libelle}</Text>
      <Text size="xs" lineClamp={3} style={{ flex: 1 }}>{children}</Text>
    </Group>
  );
}

/**
 * Documents d'un maillon de la chaîne (rubrique du menu) : « /strategie » pour le premier
 * maillon (cadres stratégiques), « /strategie/type/:typeId » pour les suivants.
 */
export function CadresStrategiquesListPage() {
  const { typeId } = useParams();
  const { user } = useAuth();
  const { data: maillons = [] } = useTypesDocuments();
  const maillon = typeId ? maillons.find((m) => String(m.id) === typeId) : maillons[0];
  const rang = rangMaillon(maillon?.id, maillons);
  const { data: cadres, isLoading } = useCadresStrategiques(maillon?.id);
  const { data: tousDocuments } = useCadresStrategiques();
  const deleteCadre = useDeleteCadreStrategique();
  // Compteur : un nouveau formulaire vierge à chaque ouverture (le modal garde son état sinon).
  const [modalOuvert, setModalOuvert] = useState(0);
  const [chaineOuverte, setChaineOuverte] = useState(false);
  const [cadreEnEdition, setCadreEnEdition] = useState<CadreStrategique | null>(null);
  const [recherche, setRecherche] = useState("");
  const [editionActive, setEditionActive] = useState(false);

  const cadresFiltres = useMemo(
    () => (cadres ?? []).filter((c) => correspond(c.nom, recherche) || correspond(c.description, recherche)),
    [cadres, recherche],
  );

  function handleSupprimer(cadre: CadreStrategique) {
    confirmerSuppression({
      message: voc`Supprimer « ${cadre.nom} » ainsi que tous ses niveaux et éléments ? Cette action est irréversible.`,
      onConfirm: async () => {
        try {
          await deleteCadre.mutateAsync(cadre.id);
          notifications.show({ message: voc("Document supprimé"), color: "green" });
        } catch (error) {
          notifications.show({ message: messageErreurApi(error, voc("Erreur lors de la suppression")), color: "red" });
        }
      },
    });
  }

  const lienParent = (c: CadreStrategique) => {
    const parent = (tousDocuments ?? []).find((d) => d.id === c.document_parent);
    return parent ? lienDocument(parent, maillons) : "#";
  };

  return (
    <Stack gap="md">
      <Group justify="space-between">
        {rang === 0 ? (
          <TitreRubrique route="/strategie" defaut={maillon?.nom_pluriel || voc("Cadres stratégiques")} />
        ) : (
          <Title order={2}>{maillon?.nom_pluriel}</Title>
        )}
        <Group gap="xs">
          <BoutonModeEdition actif={editionActive} onToggle={() => setEditionActive((v) => !v)} />
          {user?.role === "ADMIN" && (
            <Button variant="light" color="grape" leftSection={<Network size={16} />} onClick={() => setChaineOuverte(true)}>
              {voc("Chaîne des documents")}
            </Button>
          )}
          <Button onClick={() => setModalOuvert((n) => Math.abs(n) + 1)}>
            {maillon ? voc`Nouveau document — ${maillon.nom}` : voc("Nouveau cadre stratégique")}
          </Button>
        </Group>
      </Group>

      <TextInput
        placeholder={voc("Rechercher un document…")}
        leftSection={<Search size={15} />}
        value={recherche}
        onChange={(e) => setRecherche(e.currentTarget.value)}
        maw={400}
      />

      {isLoading ? (
        <Text c="dimmed">{voc("Chargement…")}</Text>
      ) : !cadres || cadres.length === 0 ? (
        <Card withBorder padding="md" radius="md">
          <EmptyState
            icon={<LayoutGrid size={32} strokeWidth={1.5} />}
            message={voc("Aucun document pour le moment — crée le premier pour définir sa structuration.")}
          />
        </Card>
      ) : cadresFiltres.length === 0 ? (
        <Card withBorder padding="md" radius="md">
          <EmptyState icon={<LayoutGrid size={32} strokeWidth={1.5} />} message={voc("Aucun document ne correspond à la recherche.")} />
        </Card>
      ) : (
        <SimpleGrid cols={{ base: 1, sm: 2, lg: 3 }}>
          {cadresFiltres.map((cadre) => (
            <Card key={cadre.id} withBorder padding="md" radius="md" style={{ display: "flex", flexDirection: "column" }}>
              <Group justify="space-between" align="flex-start" wrap="nowrap">
                <Text component={Link} to={lienDocument(cadre, maillons)} fw={700} size="md" c="teal.8" style={{ flex: 1 }}>
                  {cadre.nom}
                </Text>
                {editionActive && (
                  <Group gap={4} wrap="nowrap">
                    <Tooltip label={voc("Modifier")}>
                      <ActionIcon variant="subtle" onClick={() => setCadreEnEdition(cadre)}>
                        <Pencil size={15} />
                      </ActionIcon>
                    </Tooltip>
                    <Tooltip label={voc("Supprimer")}>
                      <ActionIcon variant="subtle" color="red" loading={deleteCadre.isPending} onClick={() => handleSupprimer(cadre)}>
                        <Trash2 size={15} />
                      </ActionIcon>
                    </Tooltip>
                  </Group>
                )}
              </Group>
              {/* En-tête : code, statut et documents rattachés. */}
              {(cadre.code || cadre.statut || (cadre.documents_rattaches?.length ?? 0) > 0) && (
                <Group gap={6} mt={6}>
                  {cadre.code && <Badge size="sm" variant="outline" color="gray">{cadre.code}</Badge>}
                  {cadre.statut && <StatusBadge tone={PROJET_STATUT_TONE[cadre.statut]}>{PROJET_STATUT_LABEL[cadre.statut]}</StatusBadge>}
                  {(cadre.documents_rattaches?.length ?? 0) > 0 && (
                    <Badge size="sm" variant="light" color="grape">
                      {voc`${cadre.documents_rattaches!.length} document(s) rattaché(s)`}
                    </Badge>
                  )}
                </Group>
              )}
              {cadre.description && (
                <Text size="sm" c="dimmed" mt={6} lineClamp={2} title={cadre.description}>{cadre.description}</Text>
              )}
              {/* Informations clés, alignées : rattachement, période, budget, bailleurs, responsable, services. */}
              <Stack gap={5} mt="sm" pt="sm" style={{ borderTop: "1px solid var(--mantine-color-default-border)" }}>
                <InfoLigne icone={Link2} libelle={voc("Rattaché à")}>
                  {cadre.document_parent ? (
                    <>
                      <Text component={Link} to={lienParent(cadre)} span size="xs" c="teal.8" fw={600}>{cadre.document_parent_nom}</Text>
                      {/* Codes seulement (« P3-K2 ») : la ligne reste lisible sur la carte. */}
                      {cadre.element_parent_nom ? ` › ${cadre.element_parent_nom.split(" — ")[0]}` : ""}
                      {(cadre.elements_parents_secondaires_noms ?? []).length > 0 &&
                        ` (+ ${cadre.elements_parents_secondaires_noms!.map((n) => n.split(" — ")[0]).join(", ")} ${voc("pour information")})`}
                    </>
                  ) : null}
                </InfoLigne>
                <InfoLigne icone={Calendar} libelle={voc("Période")}>
                  {cadre.date_debut || cadre.date_fin ? `${dateCourte(cadre.date_debut)} → ${dateCourte(cadre.date_fin)}` : null}
                </InfoLigne>
                <InfoLigne icone={Wallet} libelle={voc("Budget")}>
                  {Number(cadre.budget_total ?? 0) > 0 ? `${Number(cadre.budget_total).toLocaleString(locale())} FCFA` : null}
                </InfoLigne>
                <InfoLigne icone={Landmark} libelle={voc("Bailleurs")}>
                  {(cadre.financements ?? []).map((f) => f.bailleur_nom).join(", ")}
                </InfoLigne>
                <InfoLigne icone={UserRound} libelle={voc("Responsable")}>{cadre.responsable_nom}</InfoLigne>
                <InfoLigne icone={Building2} libelle={voc("Services")}>
                  {(cadre.structures_noms ?? []).map((n) => n.split(" — ")[0]).join(", ")}
                </InfoLigne>
              </Stack>
              {(cadre.alertes_chaine ?? []).map((m) => (
                <Alert key={m} color="orange" variant="light" p={6} mt="xs" icon={<AlertTriangle size={14} />}>
                  <Text size="xs">{voc(m)}</Text>
                </Alert>
              ))}
              <div style={{ flex: 1 }} />
              <Button component={Link} to={lienDocument(cadre, maillons)} variant="light" size="xs" mt="sm" fullWidth>
                {voc("Ouvrir")}
              </Button>
            </Card>
          ))}
        </SimpleGrid>
      )}

      <DocumentModal
        key={`nouveau-${Math.abs(modalOuvert)}`}
        opened={modalOuvert > 0}
        onClose={() => setModalOuvert((n) => -n)}
        maillon={maillon}
        maillons={maillons}
      />
      <DocumentModal
        key={cadreEnEdition?.id ?? "aucun"}
        opened={!!cadreEnEdition}
        onClose={() => setCadreEnEdition(null)}
        cadreExistant={cadreEnEdition}
        maillon={maillons.find((m) => m.id === cadreEnEdition?.type_document) ?? maillon}
        maillons={maillons}
      />
      <ChaineDocumentsModal opened={chaineOuverte} onClose={() => setChaineOuverte(false)} />
    </Stack>
  );
}
