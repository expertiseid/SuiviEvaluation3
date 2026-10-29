import { useState } from "react";
import { Pencil } from "lucide-react";
import { ActionIcon, Badge, Button, Group, Popover, Select, Stack, Text, Tooltip } from "@mantine/core";
import { notifications } from "@mantine/notifications";
import { useUpdateActivite } from "../../api/projects";
import { AIDES_METHODE, LIBELLES_METHODE, libelleMethodeEffective, optionsMethode } from "../../utils/methodesCalcul";
import { messageErreurApi } from "../../utils/erreurs";
import { voc } from "../../utils/vocabulaire";
import type { MethodeCalcul } from "../../types";

import { locale } from "../../utils/i18n";
/**
 * Méthode de calcul d'une activité, expliquée en une phrase, et modifiable sur place
 * (pour qui a le droit de modifier) — page Suivi.
 */
export function MethodeCalculLigne({
  activite,
  modifiable,
}: {
  activite: {
    id: number;
    methode_calcul: MethodeCalcul | "";
    methode_calcul_effective: MethodeCalcul | "AGREGATION";
    quantite_prevue: string | null;
    quantite_realisee?: string | null;
    unite_quantite: string;
    taux_realisation: number | null;
    taux_avertissements: string[];
  };
  modifiable: boolean;
}) {
  const [ouvert, setOuvert] = useState(false);
  const [choix, setChoix] = useState<string>(activite.methode_calcul);
  const maj = useUpdateActivite();
  const methode = activite.methode_calcul_effective;

  let explication: string;
  if (methode === "AGREGATION") {
    explication = voc("Calculé à partir des éléments placés en dessous.");
  } else if (methode === "QUANTITE") {
    explication = activite.quantite_prevue
      ? voc`${Number(activite.quantite_realisee ?? 0).toLocaleString(locale())} ${activite.unite_quantite} réalisé(s) sur ${Number(activite.quantite_prevue).toLocaleString(locale())} prévu(s).`
      : voc("Aucune quantité prévue : renseigne-la dans la planification pour obtenir un taux.");
  } else {
    explication = AIDES_METHODE[methode];
  }

  return (
    <Stack gap={2} mb="xs">
      <Group gap={6}>
        <Text size="sm" c="dimmed">
          {voc("Méthode de calcul :")}
        </Text>
        <Badge variant="light" color="indigo">
          {libelleMethodeEffective(methode)}
        </Badge>
        {!activite.methode_calcul && methode !== "AGREGATION" && (
          <Text size="xs" c="dimmed">{voc("(héritée du projet ou de l'organisation)")}</Text>
        )}
        {modifiable && (
          <Popover opened={ouvert} onChange={setOuvert} position="bottom-start" withArrow shadow="md">
            <Popover.Target>
              <Tooltip label={voc("Changer la méthode de calcul")}>
                <ActionIcon size="sm" variant="subtle" onClick={() => setOuvert((o) => !o)}>
                  <Pencil size={13} />
                </ActionIcon>
              </Tooltip>
            </Popover.Target>
            <Popover.Dropdown maw={360}>
              <Stack gap="xs">
                <Select
                  label={voc("Méthode de calcul")}
                  data={optionsMethode(voc("Hériter (niveau au-dessus / projet)"))}
                  value={choix}
                  onChange={(v) => setChoix(v ?? "")}
                  allowDeselect={false}
                  comboboxProps={{ withinPortal: false }}
                />
                <Text size="xs" c="dimmed">
                  {choix ? AIDES_METHODE[choix as MethodeCalcul] : voc("Celle du niveau au-dessus, sinon du projet, sinon de l'organisation.")}
                </Text>
                <Group justify="flex-end">
                  <Button
                    size="xs"
                    loading={maj.isPending}
                    onClick={() =>
                      maj.mutate(
                        { id: activite.id, payload: { methode_calcul: choix } },
                        {
                          onSuccess: () => {
                            setOuvert(false);
                            notifications.show({
                              message: voc`Méthode : ${choix ? LIBELLES_METHODE[choix as MethodeCalcul] : "héritée"}`,
                              color: "green",
                            });
                          },
                          onError: (error) =>
                            notifications.show({ message: messageErreurApi(error, voc("Erreur lors du changement")), color: "red" }),
                        },
                      )
                    }
                  >
                    {voc("Enregistrer")}
                  </Button>
                </Group>
              </Stack>
            </Popover.Dropdown>
          </Popover>
        )}
      </Group>
      <Text size="sm">{explication}</Text>
      {activite.taux_avertissements.map((a) => (
        <Text key={a} size="xs" c="orange">
          {a}
        </Text>
      ))}
    </Stack>
  );
}
