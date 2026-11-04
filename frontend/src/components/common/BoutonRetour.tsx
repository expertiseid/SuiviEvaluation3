import { Button } from "@mantine/core";
import { ArrowLeft } from "lucide-react";
import { useLocation, useNavigate } from "react-router-dom";
import { voc } from "../../utils/vocabulaire";

// Pages qui ont déjà leur propre lien de retour, vers une destination précise.
const AVEC_RETOUR_PROPRE = [/^\/strategie\/(?!type\/[^/]+$)/, /^\/plaintes\/dossiers\//];

/**
 * Flèche « Retour » en haut de chaque page (sauf le tableau de bord) : page précédente, ou, si la page
 * a été ouverte directement (lien, favori), la rubrique parente (/projets/12 → /projets).
 */
export function BoutonRetour() {
  const { pathname } = useLocation();
  const navigate = useNavigate();
  if (pathname === "/" || AVEC_RETOUR_PROPRE.some((motif) => motif.test(pathname))) return null;
  const retour = () => {
    if (((window.history.state as { idx?: number } | null)?.idx ?? 0) > 0) navigate(-1);
    else navigate(pathname.replace(/\/[^/]+\/?$/, "") || "/");
  };
  return (
    <Button variant="subtle" color="gray" size="compact-sm" leftSection={<ArrowLeft size={16} />} onClick={retour}
      w="fit-content" mb="xs" ml={-6}>
      {voc("Retour")}
    </Button>
  );
}
