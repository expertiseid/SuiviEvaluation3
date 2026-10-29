import { Bell, CheckCheck } from "lucide-react";
import { useNavigate } from "react-router-dom";
import { ActionIcon, Divider, Group, Indicator, Menu, ScrollArea, Stack, Text } from "@mantine/core";
import { useMarquerLu, useNonLuesCount, useNotifications, useToutMarquerLu } from "../../api/notifications";
import type { AppNotification } from "../../types";
import { voc } from "../../utils/vocabulaire";

function tempsRelatif(dateIso: string) {
  const minutes = Math.round((Date.now() - new Date(dateIso).getTime()) / 60000);
  if (minutes < 1) return voc("à l'instant");
  if (minutes < 60) return `il y a ${minutes} min`;
  const heures = Math.round(minutes / 60);
  if (heures < 24) return `il y a ${heures} h`;
  return `il y a ${Math.round(heures / 24)} j`;
}

export function NotificationBell() {
  const { data: notifs } = useNotifications();
  const { data: nonLues = 0 } = useNonLuesCount();
  const marquerLu = useMarquerLu();
  const toutMarquerLu = useToutMarquerLu();
  const navigate = useNavigate();

  function ouvrir(notif: AppNotification) {
    if (!notif.lu) marquerLu.mutate(notif.id);
    if (notif.lien) navigate(notif.lien);
  }

  return (
    <Menu shadow="md" width={360} position="bottom-end">
      <Menu.Target>
        <Indicator disabled={nonLues === 0} label={nonLues} size={16} color="red" offset={4}>
          <ActionIcon variant="subtle" color="gray.0" size="lg">
            <Bell size={18} color="white" />
          </ActionIcon>
        </Indicator>
      </Menu.Target>
      <Menu.Dropdown>
        <Group justify="space-between" px="sm" py={4}>
          <Text size="sm" fw={600}>{voc("Notifications")}</Text>
          {nonLues > 0 && (
            <ActionIcon variant="subtle" size="sm" onClick={() => toutMarquerLu.mutate()} title={voc("Tout marquer comme lu")}>
              <CheckCheck size={16} />
            </ActionIcon>
          )}
        </Group>
        <Divider />
        <ScrollArea.Autosize mah={400}>
          {!notifs || notifs.length === 0 ? (
            <Text c="dimmed" size="sm" ta="center" py="lg">
              {voc("Aucune notification.")}
            </Text>
          ) : (
            <Stack gap={0}>
              {notifs.map((n) => (
                <Menu.Item key={n.id} onClick={() => ouvrir(n)} py={8}>
                  <Group justify="space-between" wrap="nowrap" gap="xs">
                    <div style={{ minWidth: 0 }}>
                      <Text size="sm" fw={n.lu ? 400 : 600} truncate>
                        {n.titre}
                      </Text>
                      {n.message && (
                        <Text size="xs" c="dimmed" lineClamp={2}>
                          {n.message}
                        </Text>
                      )}
                      <Text size="xs" c="dimmed" mt={2}>{tempsRelatif(n.created_at)}</Text>
                    </div>
                    {!n.lu && (
                      <span
                        style={{
                          width: 8,
                          height: 8,
                          borderRadius: "50%",
                          background: "var(--mantine-color-teal-6)",
                          flexShrink: 0,
                          marginTop: 6,
                        }}
                      />
                    )}
                  </Group>
                </Menu.Item>
              ))}
            </Stack>
          )}
        </ScrollArea.Autosize>
      </Menu.Dropdown>
    </Menu>
  );
}
