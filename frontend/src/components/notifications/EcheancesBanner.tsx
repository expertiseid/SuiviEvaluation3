import { useNavigate } from "react-router-dom";
import { AlertTriangle, BellRing } from "lucide-react";
import { Group, Text, UnstyledButton } from "@mantine/core";
import { useEcheances } from "../../api/dashboard";
import type { Echeance } from "../../types";
import { voc } from "../../utils/vocabulaire";

function texteEcheance(echeance: Echeance): string {
  const prefixe = echeance.est_rappel ? voc("Rappel") : echeance.en_retard ? voc("En retard") : voc("Échéance proche");
  return `${prefixe} · ${echeance.libelle} (${echeance.projet_nom}) — ${echeance.date_fin}`;
}

export function EcheancesBanner() {
  const { data: echeances } = useEcheances();
  const navigate = useNavigate();

  if (!echeances || echeances.length === 0) return null;

  // Le contenu est dupliqué pour un défilement en boucle sans à-coup : l'animation
  // translate de 0 à -50% (soit exactement une copie), puis reprend à 0 sans saut visible.
  const items = [...echeances, ...echeances];

  return (
    <div
      style={{
        height: 32,
        overflow: "hidden",
        position: "relative",
        background: "var(--mantine-color-red-8)",
        borderTop: "1px solid rgba(255,255,255,0.2)",
        // Durée du défilement (index.css, .defilement-echeances-piste) : selon le nombre d'échéances.
        ["--duree-defilement" as string]: `${Math.max(35, echeances.length * 12)}s`,
      }}
    >
      <Group
        className="defilement-echeances-piste"
        gap="xl"
        wrap="nowrap"
        style={{ position: "absolute", left: 0, top: 0, height: "100%", whiteSpace: "nowrap", paddingLeft: 16 }}
      >
        {items.map((echeance, index) => (
          <UnstyledButton
            key={`${echeance.type}-${echeance.id}-${index}`}
            onClick={() => navigate(echeance.lien)}
            style={{ display: "flex", alignItems: "center", gap: 6 }}
          >
            {echeance.est_rappel ? (
              <BellRing size={13} color="var(--mantine-color-blue-2)" />
            ) : (
              <AlertTriangle size={13} color={echeance.en_retard ? "white" : "var(--mantine-color-yellow-3)"} />
            )}
            <Text size="xs" c="white" fw={500}>
              {texteEcheance(echeance)}
            </Text>
          </UnstyledButton>
        ))}
      </Group>
    </div>
  );
}
