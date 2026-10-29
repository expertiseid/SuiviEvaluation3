import { useState } from "react";
import { CalendarCheck, Trash2 } from "lucide-react";
import { ActionIcon, Badge, Button, Card, Group, Select, Stack, Switch, Table, Text, TextInput, Tooltip } from "@mantine/core";
import { DatePickerInput } from "@mantine/dates";
import { notifications } from "@mantine/notifications";
import {
  useCreateFenetreRapportage,
  useDeleteFenetreRapportage,
  useFenetresRapportage,
  useParametresRapportage,
  useProjets,
  useUpdateParametresRapportage,
} from "../../api/projects";
import { useAuth } from "../../auth/useAuth";
import { confirmerSuppression } from "../../components/common/confirmerSuppression";
import { messageErreurApi } from "../../utils/erreurs";
import { fmtDate } from "../../utils/periode";
import { voc } from "../../utils/vocabulaire";
import type { PerimetreFermeture } from "../../types";
import { AIDES_PERIMETRE, LIBELLES_PERIMETRE } from "../../utils/rapportage";

function etatFenetre(debut: string, fin: string): { libelle: string; couleur: string } {
  const aujourdhui = new Date().toISOString().slice(0, 10);
  if (fin < aujourdhui) return { libelle: voc("Passée"), couleur: "gray" };
  if (debut > aujourdhui) return { libelle: voc("À venir"), couleur: "blue" };
  return { libelle: voc("Ouverte"), couleur: "green" };
}

/**
 * Périodes de rapportage (Paramètres) : contrôle général de l'ouverture de la saisie, ce qui
 * est fermé hors période, et les périodes d'ouverture, générales ou propres à un projet.
 * Chaque projet peut aussi être « toujours ouvert » ou « fermé sauf ses propres périodes »
 * (formulaire du projet). L'administrateur n'est jamais bloqué.
 */
export function RapportageCard() {
  const { user } = useAuth();
  const admin = user?.role === "ADMIN";
  const { data: parametres } = useParametresRapportage();
  const { data: fenetres } = useFenetresRapportage();
  const { data: projets } = useProjets();
  const maj = useUpdateParametresRapportage();
  const creer = useCreateFenetreRapportage();
  const supprimer = useDeleteFenetreRapportage();
  const [libelle, setLibelle] = useState("");
  const [dates, setDates] = useState<[string | null, string | null]>([null, null]);
  const [projet, setProjet] = useState<string | null>(null);

  if (!parametres) return null;

  const enregistrer = (payload: Parameters<typeof maj.mutate>[0]) =>
    maj.mutate(payload, {
      onSuccess: () => notifications.show({ message: voc("Réglage enregistré"), color: "green" }),
      onError: (error) => notifications.show({ message: messageErreurApi(error, "Erreur"), color: "red" }),
    });

  function ajouter() {
    const [debut, fin] = dates;
    if (!libelle.trim() || !debut || !fin) {
      notifications.show({ message: voc("Donne un nom à la période et choisis ses dates."), color: "orange" });
      return;
    }
    creer.mutate(
      { libelle: libelle.trim(), date_debut: debut, date_fin: fin, projet: projet ? Number(projet) : null },
      {
        onSuccess: () => {
          setLibelle("");
          setDates([null, null]);
          setProjet(null);
          notifications.show({ message: voc("Période de rapportage ajoutée"), color: "green" });
        },
        onError: (error) => notifications.show({ message: messageErreurApi(error, "Erreur"), color: "red" }),
      },
    );
  }

  return (
    <Card withBorder padding="lg" radius="md">
      <Group gap={8} mb={4}>
        <CalendarCheck size={18} />
        <Text fw={600}>{voc("Périodes de rapportage")}</Text>
      </Group>
      <Text size="sm" c="dimmed" mb="sm">
        {voc("Quand le contrôle est actif, la saisie n'est ouverte que pendant les périodes de rapportage ; le reste du temps, la plateforme est en lecture seule pour la partie choisie. Chaque projet peut aussi être toujours ouvert, ou fermé sauf pendant ses propres périodes (formulaire du projet). L'administrateur peut toujours corriger.")}
      </Text>
      <Stack gap="sm">
        <Switch
          label={voc("Contrôler l'ouverture de la saisie par périodes de rapportage")}
          checked={parametres.controle_actif}
          onChange={(e) => enregistrer({ controle_actif: e.currentTarget.checked })}
          disabled={!admin}
        />
        <Select
          label={voc("Hors période de rapportage, fermer")}
          description={AIDES_PERIMETRE[parametres.perimetre]}
          data={Object.entries(LIBELLES_PERIMETRE).map(([value, label]) => ({ value, label }))}
          value={parametres.perimetre}
          onChange={(v) => v && enregistrer({ perimetre: v as PerimetreFermeture })}
          allowDeselect={false}
          disabled={!admin}
          maw={420}
        />

        {(fenetres ?? []).length > 0 ? (
          <Table fz="sm" verticalSpacing={4}>
            <Table.Thead>
              <Table.Tr>
                <Table.Th>{voc("Période")}</Table.Th>
                <Table.Th>{voc("Dates")}</Table.Th>
                <Table.Th>{voc("Projets")}</Table.Th>
                <Table.Th>{voc("État")}</Table.Th>
                <Table.Th />
              </Table.Tr>
            </Table.Thead>
            <Table.Tbody>
              {(fenetres ?? []).map((f) => {
                const etat = etatFenetre(f.date_debut, f.date_fin);
                return (
                  <Table.Tr key={f.id}>
                    <Table.Td>{f.libelle}</Table.Td>
                    <Table.Td>
                      {fmtDate(f.date_debut)} → {fmtDate(f.date_fin)}
                    </Table.Td>
                    <Table.Td>{f.projet_code ?? voc("Tous les projets")}</Table.Td>
                    <Table.Td>
                      <Badge variant="light" color={etat.couleur}>{etat.libelle}</Badge>
                    </Table.Td>
                    <Table.Td style={{ width: 1 }}>
                      {admin && (
                        <Tooltip label={voc("Supprimer cette période")}>
                          <ActionIcon
                            size="sm"
                            variant="subtle"
                            color="red"
                            onClick={() =>
                              confirmerSuppression({
                                message: voc`Supprimer la période « ${f.libelle} » ?`,
                                onConfirm: () => supprimer.mutate(f.id),
                              })
                            }
                          >
                            <Trash2 size={14} />
                          </ActionIcon>
                        </Tooltip>
                      )}
                    </Table.Td>
                  </Table.Tr>
                );
              })}
            </Table.Tbody>
          </Table>
        ) : (
          <Text size="sm" c="dimmed">{voc("Aucune période de rapportage pour l'instant.")}</Text>
        )}

        {admin && (
          <Group align="flex-end" wrap="wrap">
            <TextInput
              label={voc("Nouvelle période")}
              placeholder={voc("Ex : Rapport du 1er trimestre 2026")}
              value={libelle}
              onChange={(e) => setLibelle(e.currentTarget.value)}
              w={260}
            />
            <DatePickerInput
              type="range"
              label={voc("Dates d'ouverture")}
              placeholder={voc("Début – fin")}
              value={dates}
              onChange={(v) => setDates(v as [string | null, string | null])}
              allowSingleDateInRange
              w={240}
            />
            <Select
              label={voc("Projet")}
              placeholder={voc("Tous les projets")}
              data={(projets ?? []).map((p) => ({ value: String(p.id), label: `${p.code} — ${p.nom}` }))}
              value={projet}
              onChange={setProjet}
              searchable
              clearable
              w={260}
            />
            <Button onClick={ajouter} loading={creer.isPending}>
              {voc("Ajouter")}
            </Button>
          </Group>
        )}
      </Stack>
    </Card>
  );
}
