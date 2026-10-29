import { Languages } from "lucide-react";
import { Button, Menu } from "@mantine/core";
import { apiClient } from "../../api/client";
import { changerLangue, langue, LANGUES, type Langue } from "../../utils/i18n";

/**
 * Choix de la langue de l'interface : enregistré dans le compte quand on est connecté (et
 * retenu par ce navigateur), puis la page est rechargée dans la nouvelle langue.
 */
export function ChoixLangue({ connecte, couleur = "gray.0" }: { connecte: boolean; couleur?: string }) {
  const courante = LANGUES.find((l) => l.code === langue());

  async function choisir(code: Langue) {
    if (code === langue()) return;
    if (connecte) {
      try {
        await apiClient.patch("/utilisateurs/me/", { langue: code });
      } catch {
        /* la langue reste au moins retenue par ce navigateur */
      }
    }
    changerLangue(code);
  }

  return (
    <Menu position="bottom-end" withinPortal>
      <Menu.Target>
        <Button variant="subtle" color={couleur} size="xs" leftSection={<Languages size={15} />} px={8}>
          {courante?.code.toUpperCase()}
        </Button>
      </Menu.Target>
      <Menu.Dropdown>
        {LANGUES.map((l) => (
          <Menu.Item key={l.code} onClick={() => choisir(l.code)} fw={l.code === langue() ? 700 : undefined} dir={l.code === "ar" ? "rtl" : "ltr"}>
            {l.nom}
          </Menu.Item>
        ))}
      </Menu.Dropdown>
    </Menu>
  );
}
