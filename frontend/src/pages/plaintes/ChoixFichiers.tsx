import { FileInput } from "@mantine/core";
import { Paperclip } from "lucide-react";
import type { PiecesAcceptees } from "../../api/plaintes";
import { voc } from "../../utils/vocabulaire";

/** Extensions proposées au choix ; le serveur contrôle de toute façon le type réel du contenu. */
const ACCEPTE = ".pdf,.docx,.xlsx,.odt,.ods,.txt,.jpg,.jpeg,.png,.webp,.mp3,.m4a,.ogg,.opus,.wav,.amr,.webm";

/** Fichiers joints (formulaire public, complément, saisie par un agent, ajout sur la fiche). */
export function ChoixFichiers({ valeur, onChange, limites, label, erreur }: {
  valeur: File[];
  onChange: (fichiers: File[]) => void;
  limites: PiecesAcceptees;
  label?: string;
  erreur?: string;
}) {
  const tropLourd = valeur.find((f) => f.size > limites.taille_max_mo * 1024 * 1024);
  return (
    <FileInput
      multiple
      clearable
      accept={ACCEPTE}
      label={label ?? voc("Fichiers joints (facultatif)")}
      placeholder={voc("Photos, documents, messages vocaux…")}
      leftSection={<Paperclip size={14} />}
      description={voc`Jusqu'à ${limites.nombre_max} fichiers de ${limites.taille_max_mo} Mo au plus. Formats : ${limites.formats}.`}
      value={valeur}
      onChange={(fichiers) => onChange(fichiers.slice(0, limites.nombre_max))}
      error={erreur ?? (tropLourd ? voc`« ${tropLourd.name} » dépasse ${limites.taille_max_mo} Mo.` : undefined)}
    />
  );
}
