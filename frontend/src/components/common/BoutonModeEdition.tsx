import { Button } from "@mantine/core";
import { Pencil, X } from "lucide-react";
import { voc } from "../../utils/vocabulaire";

/**
 * Bascule un mode « édition » propre à la page/section : tant qu'il n'est
 * pas activé, les boutons Modifier/Supprimer restent masqués pour alléger
 * l'interface — les activer les rend visibles jusqu'à ce qu'on quitte ce mode.
 */
export function BoutonModeEdition({ actif, onToggle }: { actif: boolean; onToggle: () => void }) {
  return (
    <Button
      variant={actif ? "filled" : "light"}
      color={actif ? "teal" : "gray"}
      size="sm"
      leftSection={actif ? <X size={15} /> : <Pencil size={15} />}
      onClick={onToggle}
    >
      {actif ? voc("Terminer l'édition") : voc("Éditer")}
    </Button>
  );
}
