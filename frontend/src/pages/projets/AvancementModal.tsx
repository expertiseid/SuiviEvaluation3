import { useState } from "react";
import { Plus, Trash2 } from "lucide-react";
import {
  ActionIcon,
  Alert,
  Badge,
  Button,
  Checkbox,
  Group,
  NumberInput,
  Stack,
  Table,
  Text,
  TextInput,
  Textarea,
  Tooltip,
} from "@mantine/core";
import { DateInput } from "@mantine/dates";
import { notifications } from "@mantine/notifications";
import dayjs from "dayjs";
import {
  useCreateJalonLivrable,
  useCreateTauxManuel,
  useDeleteJalonLivrable,
  useTauxManuels,
  useUpdateJalonLivrable,
  useUpdateSousActivite,
} from "../../api/projects";
import { AIDES_METHODE, libelleMethodeEffective } from "../../utils/methodesCalcul";
import { messageErreurApi } from "../../utils/erreurs";
import { voc } from "../../utils/vocabulaire";
import type { Activite, JalonLivrable } from "../../types";

const nombre = (v: string | number | null | undefined) => (v === null || v === undefined || v === "" ? null : Number(v));

function afficherErreur(error: unknown) {
  notifications.show({ message: messageErreurApi(error, "Erreur lors de l'enregistrement"), color: "red" });
}

/** Total des poids, signalé s'il ne fait pas 100 %. */
function TotalPoids({ poids }: { poids: (string | null)[] }) {
  const saisis = poids.filter((p) => p !== null && p !== "");
  if (saisis.length === 0) return <Text size="xs" c="dimmed">Aucun poids saisi : poids égaux.</Text>;
  const total = saisis.reduce((s, p) => s + Number(p), 0);
  return (
    <Text size="xs" c={Math.abs(total - 100) < 0.01 ? "teal" : "orange"}>
      Total des poids : {total.toLocaleString("fr-FR")} %{Math.abs(total - 100) < 0.01 ? "" : " (attendu : 100 %)"}
    </Text>
  );
}

function TachesPonderees({ element, modifiable }: { element: Activite; modifiable: boolean }) {
  const maj = useUpdateSousActivite();
  if (element.sous_activites.length === 0) {
    return <Text size="sm" c="dimmed">Aucune sous-activité : ajoute-en depuis la planification (bouton ≡+).</Text>;
  }
  const enregistrer = (id: number, champ: "poids" | "avancement", valeur: string | number) =>
    maj.mutate({ id, payload: { [champ]: valeur === "" ? null : valeur } }, { onError: afficherErreur });
  return (
    <Stack gap={6}>
      <Table withTableBorder verticalSpacing={4}>
        <Table.Thead>
          <Table.Tr>
            <Table.Th>Tâche (sous-activité)</Table.Th>
            <Table.Th w={110}>Poids (%)</Table.Th>
            <Table.Th w={150}>Avancement (%)</Table.Th>
          </Table.Tr>
        </Table.Thead>
        <Table.Tbody>
          {element.sous_activites.map((sa) => (
            <Table.Tr key={sa.id}>
              <Table.Td>
                <Text size="sm">{sa.libelle}</Text>
              </Table.Td>
              <Table.Td>
                <NumberInput
                  size="xs"
                  min={0}
                  defaultValue={nombre(sa.poids) ?? ""}
                  disabled={!modifiable}
                  onBlur={(e) => enregistrer(sa.id, "poids", e.currentTarget.value)}
                />
              </Table.Td>
              <Table.Td>
                <NumberInput
                  size="xs"
                  min={0}
                  max={100}
                  placeholder="Auto"
                  defaultValue={nombre(sa.avancement) ?? ""}
                  disabled={!modifiable}
                  onBlur={(e) => enregistrer(sa.id, "avancement", e.currentTarget.value)}
                />
              </Table.Td>
            </Table.Tr>
          ))}
        </Table.Tbody>
      </Table>
      <TotalPoids poids={element.sous_activites.map((s) => s.poids)} />
      <Text size="xs" c="dimmed">
        Avancement vide : déduit des quantités de la sous-activité, sinon de son statut (Terminée = 100 %).
      </Text>
    </Stack>
  );
}

function JalonsOuLivrables({
  element,
  type,
  modifiable,
}: {
  element: Activite;
  type: "JALON" | "LIVRABLE";
  modifiable: boolean;
}) {
  const creer = useCreateJalonLivrable();
  const maj = useUpdateJalonLivrable();
  const supprimer = useDeleteJalonLivrable();
  const [libelle, setLibelle] = useState("");
  const [poids, setPoids] = useState<string | number>("");
  const liste = element.jalons_livrables.filter((j) => j.type === type);
  const estJalon = type === "JALON";
  const majChamp = (j: JalonLivrable, payload: Partial<JalonLivrable>) =>
    maj.mutate({ id: j.id, payload }, { onError: afficherErreur });

  return (
    <Stack gap={6}>
      {liste.length > 0 && (
        <Table withTableBorder verticalSpacing={4}>
          <Table.Thead>
            <Table.Tr>
              <Table.Th>{estJalon ? "Jalon" : "Livrable"}</Table.Th>
              <Table.Th w={100}>Poids (%)</Table.Th>
              <Table.Th w={140}>{estJalon ? "Achèvement (%)" : "Validé"}</Table.Th>
              {modifiable && <Table.Th w={40} />}
            </Table.Tr>
          </Table.Thead>
          <Table.Tbody>
            {liste.map((j) => (
              <Table.Tr key={j.id}>
                <Table.Td>
                  <Text size="sm">{j.libelle}</Text>
                  {j.date_prevue && <Text size="xs" c="dimmed">Prévu le {dayjs(j.date_prevue).format("DD/MM/YYYY")}</Text>}
                </Table.Td>
                <Table.Td>
                  <NumberInput
                    size="xs"
                    min={0}
                    defaultValue={nombre(j.poids) ?? ""}
                    disabled={!modifiable}
                    onBlur={(e) => majChamp(j, { poids: e.currentTarget.value === "" ? null : e.currentTarget.value })}
                  />
                </Table.Td>
                <Table.Td>
                  {estJalon ? (
                    <NumberInput
                      size="xs"
                      min={0}
                      max={100}
                      defaultValue={nombre(j.achevement) ?? 0}
                      disabled={!modifiable}
                      onBlur={(e) => majChamp(j, { achevement: e.currentTarget.value || "0" })}
                    />
                  ) : (
                    <Stack gap={2}>
                      <Checkbox
                        checked={j.valide}
                        disabled={!modifiable}
                        onChange={(e) => majChamp(j, { valide: e.currentTarget.checked })}
                        label={j.valide ? "Validé" : "Non validé"}
                      />
                      {j.valide && (
                        <Text size="xs" c="dimmed">
                          {j.valide_par_nom ?? "—"}, {j.date_validation ? dayjs(j.date_validation).format("DD/MM/YYYY") : ""}
                        </Text>
                      )}
                    </Stack>
                  )}
                </Table.Td>
                {modifiable && (
                  <Table.Td>
                    <Tooltip label="Supprimer">
                      <ActionIcon
                        size="sm"
                        variant="subtle"
                        color="red"
                        onClick={() => supprimer.mutate(j.id, { onError: afficherErreur })}
                      >
                        <Trash2 size={13} />
                      </ActionIcon>
                    </Tooltip>
                  </Table.Td>
                )}
              </Table.Tr>
            ))}
          </Table.Tbody>
        </Table>
      )}
      {liste.length > 0 && <TotalPoids poids={liste.map((j) => j.poids)} />}
      {modifiable && (
        <Group gap="xs" align="flex-end">
          <TextInput
            size="xs"
            label={estJalon ? "Nouveau jalon" : "Nouveau livrable"}
            value={libelle}
            onChange={(e) => setLibelle(e.currentTarget.value)}
            style={{ flex: 1 }}
          />
          <NumberInput size="xs" label="Poids (%)" min={0} value={poids} onChange={setPoids} w={100} />
          <Button
            size="xs"
            variant="light"
            leftSection={<Plus size={13} />}
            disabled={!libelle.trim()}
            loading={creer.isPending}
            onClick={() =>
              creer.mutate(
                { activite: element.id, type, libelle: libelle.trim(), poids: poids === "" ? null : String(poids) },
                {
                  onSuccess: () => {
                    setLibelle("");
                    setPoids("");
                  },
                  onError: afficherErreur,
                },
              )
            }
          >
            Ajouter
          </Button>
        </Group>
      )}
    </Stack>
  );
}

function SaisieManuelle({ element, modifiable }: { element: Activite; modifiable: boolean }) {
  const { data: historique } = useTauxManuels(element.id);
  const creer = useCreateTauxManuel();
  const [taux, setTaux] = useState<string | number>("");
  const [date, setDate] = useState<string | null>(dayjs().format("YYYY-MM-DD"));
  const [commentaire, setCommentaire] = useState("");
  return (
    <Stack gap={6}>
      {modifiable && (
        <Group gap="xs" align="flex-end">
          <NumberInput size="xs" label="Taux (%)" min={0} max={100} value={taux} onChange={setTaux} w={110} />
          <DateInput size="xs" label="À la date du" value={date} onChange={setDate} valueFormat="DD/MM/YYYY" w={140} />
          <Textarea
            size="xs"
            label="Commentaire"
            autosize
            minRows={1}
            value={commentaire}
            onChange={(e) => setCommentaire(e.currentTarget.value)}
            style={{ flex: 1 }}
          />
          <Button
            size="xs"
            disabled={taux === "" || !date}
            loading={creer.isPending}
            onClick={() =>
              creer.mutate(
                { activite: element.id, taux: Number(taux), date: date!, commentaire },
                {
                  onSuccess: () => {
                    setTaux("");
                    setCommentaire("");
                  },
                  onError: afficherErreur,
                },
              )
            }
          >
            Enregistrer
          </Button>
        </Group>
      )}
      <Text size="xs" fw={600} c="dimmed" mt={4}>
        Historique des taux saisis
      </Text>
      {(historique ?? []).length === 0 ? (
        <Text size="sm" c="dimmed">Aucun taux saisi.</Text>
      ) : (
        <Table withTableBorder verticalSpacing={4}>
          <Table.Tbody>
            {historique!.map((t, i) => (
              <Table.Tr key={t.id}>
                <Table.Td w={110}>{dayjs(t.date).format("DD/MM/YYYY")}</Table.Td>
                <Table.Td w={80}>
                  <Text size="sm" fw={i === 0 ? 700 : 400}>{Number(t.taux).toLocaleString("fr-FR")} %</Text>
                </Table.Td>
                <Table.Td>
                  <Text size="xs" c="dimmed">
                    {t.saisi_par_nom ?? ""}
                    {t.commentaire ? ` — ${t.commentaire}` : ""}
                  </Text>
                </Table.Td>
              </Table.Tr>
            ))}
          </Table.Tbody>
        </Table>
      )}
    </Stack>
  );
}

/**
 * Taux d'exécution physique d'un élément et saisies propres à sa méthode de calcul
 * (tâches, jalons, livrables, saisie manuelle).
 */
export function AvancementModal({ element, modifiable }: { element: Activite; modifiable: boolean }) {
  const methode = element.methode_calcul_effective;
  return (
    <Stack gap="sm">
      <Group gap="sm">
        <Text size="xl" fw={700}>
          {element.taux_realisation === null ? "—" : `${element.taux_realisation.toLocaleString("fr-FR")} %`}
        </Text>
        <Badge variant="light">{libelleMethodeEffective(methode)}</Badge>
      </Group>
      <Text size="sm" c="dimmed">
        {methode === "AGREGATION"
          ? voc("Cet élément a des éléments en dessous : son taux est calculé à partir des leurs, selon sa méthode d'agrégation (modifiable dans le formulaire de l'élément).")
          : AIDES_METHODE[methode]}
      </Text>
      {element.taux_avertissements.map((a) => (
        <Alert key={a} color="orange" variant="light" py={6}>
          {a}
        </Alert>
      ))}
      {methode === "TACHES" && <TachesPonderees element={element} modifiable={modifiable} />}
      {methode === "JALONS" && <JalonsOuLivrables element={element} type="JALON" modifiable={modifiable} />}
      {methode === "LIVRABLES" && <JalonsOuLivrables element={element} type="LIVRABLE" modifiable={modifiable} />}
      {methode === "MANUELLE" && <SaisieManuelle element={element} modifiable={modifiable} />}
      {methode === "QUANTITE" && (
        <Text size="sm">
          {voc("Réalisé")} : {element.quantite_realisee ?? 0} / {element.quantite_prevue ?? "—"} {element.unite_quantite}
          {voc(" — les quantités réalisées se saisissent dans le module Suivi.")}
        </Text>
      )}
      {methode === "BINAIRE" && (
        <Text size="sm">
          Statut actuel : <strong>{element.statut === "REALISEE" ? "Réalisée" : element.statut === "EN_COURS" ? "En cours" : "Non réalisée"}</strong>
        </Text>
      )}
    </Stack>
  );
}
