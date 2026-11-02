import { useState } from "react";
import { ActionIcon, Badge, Button, Card, Group, Modal, Stack, Text, Tooltip } from "@mantine/core";
import { notifications } from "@mantine/notifications";
import { Download, FileAudio, FileImage, FileText, Paperclip, Trash2 } from "lucide-react";
import {
  type DossierDetail,
  type PieceJointe,
  ouvrirPieceJointe,
  tailleLisible,
  useAjouterPieces,
  useMecanisme,
} from "../../api/plaintes";
import { useAuth } from "../../auth/useAuth";
import { messageErreurApi } from "../../utils/erreurs";
import { locale } from "../../utils/i18n";
import { voc } from "../../utils/vocabulaire";
import { ChoixFichiers } from "./ChoixFichiers";
import { RetirerPiece } from "./OperationsDossier";
import { erreursParChamp } from "./saisieRetour";

function Icone({ type }: { type: string }) {
  if (type.startsWith("image/")) return <FileImage size={16} />;
  if (type.startsWith("audio/")) return <FileAudio size={16} />;
  return <FileText size={16} />;
}

function AjouterPieces({ dossier, onClose }: { dossier: DossierDetail; onClose: () => void }) {
  const { data: mecanisme } = useMecanisme();
  const ajouter = useAjouterPieces(dossier.id);
  const [fichiers, setFichiers] = useState<File[]>([]);
  const [erreur, setErreur] = useState<string>();
  const envoyer = async () => {
    setErreur(undefined);
    try {
      await ajouter.mutateAsync(fichiers);
      notifications.show({ message: voc("Pièces jointes ajoutées"), color: "teal" });
      onClose();
    } catch (error) {
      setErreur(erreursParChamp(error).fichiers ?? messageErreurApi(error, voc("Erreur lors de l'enregistrement")));
    }
  };
  return (
    <Modal opened onClose={onClose} title={voc("Ajouter des pièces jointes")} size="lg">
      <Stack>
        {mecanisme && <ChoixFichiers valeur={fichiers} onChange={setFichiers} limites={mecanisme.pieces_equipe} label={voc("Fichiers")} erreur={erreur} />}
        <Text size="xs" c="dimmed">
          {voc("Les fichiers sont chiffrés. Les métadonnées des photos et des documents (auteur, position GPS…) sont effacées à l'ajout.")}
        </Text>
        <Group justify="flex-end">
          <Button variant="default" onClick={onClose}>{voc("Annuler")}</Button>
          <Button onClick={envoyer} loading={ajouter.isPending} disabled={!fichiers.length}>{voc("Ajouter")}</Button>
        </Group>
      </Stack>
    </Modal>
  );
}

/**
 * Pièces jointes du dossier. Chaque ouverture demande un lien valable quelques minutes, après contrôle
 * d'accès ; le téléchargement est inscrit au journal.
 */
export function PiecesJointesDossier({ dossier, modifiable }: { dossier: DossierDetail; modifiable: boolean }) {
  const { user } = useAuth();
  const [ajout, setAjout] = useState(false);
  const [aRetirer, setARetirer] = useState<PieceJointe | null>(null);
  const [ouverture, setOuverture] = useState<number | null>(null);
  const peutAjouter = modifiable && !dossier.anonymise;
  if (!dossier.pieces.length && !peutAjouter) return null;

  const ouvrir = async (piece: PieceJointe) => {
    setOuverture(piece.id);
    try {
      await ouvrirPieceJointe(dossier.id, piece.id);
    } catch (error) {
      notifications.show({ color: "red", message: messageErreurApi(error, voc("Le fichier n'a pas pu être ouvert.")) });
    } finally {
      setOuverture(null);
    }
  };
  const peutRetirer = (p: PieceJointe) =>
    peutAjouter && (user?.role === "ADMIN" || dossier.responsable === user?.id || p.ajoute_par === user?.id);

  return (
    <Card withBorder>
      <Stack gap="xs">
        <Group justify="space-between">
          <Group gap="xs"><Paperclip size={16} /><Text fw={600} size="sm">{voc("Pièces jointes")}</Text></Group>
          {peutAjouter && <Button size="xs" variant="subtle" onClick={() => setAjout(true)}>{voc("Ajouter des fichiers")}</Button>}
        </Group>
        {dossier.pieces.map((p) => (
          <Group key={p.id} justify="space-between" wrap="nowrap" gap="xs">
            <Group gap="xs" wrap="nowrap" style={{ minWidth: 0 }}>
              <Icone type={p.type_mime} />
              <Stack gap={0} style={{ minWidth: 0 }}>
                <Text size="sm" truncate dir="auto">{p.nom}</Text>
                <Text size="xs" c="dimmed">
                  {tailleLisible(p.taille)} · {new Date(p.date).toLocaleDateString(locale())} ·{" "}
                  {p.source === "PLAIGNANT" ? voc("déposée par le plaignant") : p.ajoute_par_nom ?? voc("ajoutée par l'équipe")}
                </Text>
              </Stack>
              {!p.metadonnees_effacees && (
                <Tooltip label={voc("Ce format ne permet pas d'effacer les métadonnées : elles peuvent contenir des informations sur l'auteur.")} multiline w={260}>
                  <Badge size="xs" variant="light" color="yellow" tt="none">{voc("Métadonnées conservées")}</Badge>
                </Tooltip>
              )}
            </Group>
            <Group gap={4} wrap="nowrap">
              <Tooltip label={voc("Télécharger")}>
                <ActionIcon variant="subtle" onClick={() => ouvrir(p)} loading={ouverture === p.id} aria-label={voc("Télécharger")}>
                  <Download size={16} />
                </ActionIcon>
              </Tooltip>
              {peutRetirer(p) && (
                <Tooltip label={voc("Retirer")}>
                  <ActionIcon variant="subtle" color="red" onClick={() => setARetirer(p)} aria-label={voc("Retirer")}>
                    <Trash2 size={16} />
                  </ActionIcon>
                </Tooltip>
              )}
            </Group>
          </Group>
        ))}
        {dossier.pieces.length === 0 && <Text size="sm" c="dimmed">{voc("Aucune pièce jointe.")}</Text>}
      </Stack>
      {ajout && <AjouterPieces dossier={dossier} onClose={() => setAjout(false)} />}
      {aRetirer && <RetirerPiece dossier={dossier} piece={aRetirer} onClose={() => setARetirer(null)} />}
    </Card>
  );
}
