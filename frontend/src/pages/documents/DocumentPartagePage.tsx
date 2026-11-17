import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { Alert, Box, Button, Card, Container, Group, Loader, PasswordInput, Stack, Table, Text, Title } from "@mantine/core";
import { Clock, Download, Eye, FileText, Folder, Lock } from "lucide-react";
import { type DocumentPartage, lireDocumentPartage, ouvrirDocumentPartage } from "../../api/documents";
import { ChoixLangue } from "../../components/common/ChoixLangue";
import { LogoOrganisation, PiedDePage } from "../../components/common/Logos";
import { messageErreurApi } from "../../utils/erreurs";
import { locale } from "../../utils/i18n";
import { voc } from "../../utils/vocabulaire";

const statut = (erreur: unknown) => (erreur as { response?: { status?: number } }).response?.status;

const taille = (octets: number | null) =>
  octets == null ? "" : octets < 1024 * 1024 ? `${Math.max(1, Math.round(octets / 1024))} Ko` : `${(octets / 1024 / 1024).toFixed(1)} Mo`;

/**
 * Page publique d'un document partagé par lien (/document/<jeton>?org=…) : sans compte. Mot de passe
 * si le lien en a un ; aperçu dans la page (PDF, images, vidéos, texte) ; téléchargement si permis.
 * Lien vers un dossier : la liste de ses fichiers (et de ses sous-dossiers), à télécharger un par un ou en zip.
 */
export function DocumentPartagePage() {
  const { jeton = "" } = useParams();
  const [info, setInfo] = useState<DocumentPartage | null>(null);
  const [ouvert, setOuvert] = useState<DocumentPartage | null>(null);
  const [introuvable, setIntrouvable] = useState(false);
  const [motDePasse, setMotDePasse] = useState("");
  const [erreur, setErreur] = useState<string | null>(null);
  const [envoi, setEnvoi] = useState(false);

  const ouvrir = async () => {
    setErreur(null);
    setEnvoi(true);
    try {
      setOuvert(await ouvrirDocumentPartage(jeton, motDePasse));
    } catch (e) {
      if (statut(e) === 410) setInfo((i) => (i ? { ...i, etat: (e as { response: { data: DocumentPartage } }).response.data.etat ?? "EXPIRE" } : i));
      else setErreur(messageErreurApi(e, voc("Le document n'a pas pu être ouvert.")));
    } finally {
      setEnvoi(false);
    }
  };

  useEffect(() => {
    lireDocumentPartage(jeton)
      .then((d) => setInfo(d))
      .catch(() => setIntrouvable(true));
  }, [jeton]);

  // Sans mot de passe : le document s'ouvre tout de suite.
  useEffect(() => {
    if (info && info.etat === "ACTIF" && !info.mot_de_passe && !ouvert) ouvrir();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [info]);

  const valable = info?.etat === "ACTIF";
  const fin = info ? new Date(info.expire_le).toLocaleString(locale(), { dateStyle: "long", timeStyle: "short" }) : "";

  return (
    <Box bg="gray.0" mih="100vh" py="lg">
      <Container size="lg" px="md">
        <Stack gap="md">
          <Group justify="space-between" wrap="nowrap">
            <Group gap="sm" wrap="nowrap">
              <LogoOrganisation hauteur={40} />
              {info && <Text fw={700}>{info.organisation}</Text>}
            </Group>
            <ChoixLangue connecte={false} couleur="gray" />
          </Group>
          {introuvable ? (
            <Alert color="red" title={voc("Lien introuvable")}>{voc("Ce lien n'existe pas ou le document a été retiré.")}</Alert>
          ) : !info ? (
            <Loader />
          ) : (
            <Card withBorder radius="md" padding="lg">
              <Stack gap="md">
                <Group gap="sm" wrap="nowrap">
                  {info.dossier
                    ? <Folder size={28} color="var(--mantine-color-yellow-7)" style={{ flexShrink: 0 }} />
                    : <FileText size={28} color="var(--mantine-color-teal-7)" style={{ flexShrink: 0 }} />}
                  <div>
                    <Title order={2} size="h3">{info.dossier ?? info.document}</Title>
                    <Text size="sm" c="dimmed">
                      {info.dossier ? voc("Dossier partagé : téléchargez les fichiers pour les lire")
                        : info.droit === "TELECHARGER" ? voc("Consultation et téléchargement") : voc("Consultation seulement")}
                    </Text>
                  </div>
                </Group>
                {!valable ? (
                  <Alert color="orange" icon={<Clock size={18} />} title={voc("Ce lien n'est plus valable")}>
                    {info.etat === "REVOQUE" ? voc("Le lien a été désactivé par la personne qui l'a partagé.")
                      : info.etat === "EPUISE" ? voc("Le nombre d'ouvertures prévu est atteint.")
                        : voc("La date d'expiration est passée.")}{" "}
                    {voc("Demandez un nouveau lien à la personne qui vous l'a envoyé.")}
                  </Alert>
                ) : !ouvert ? (
                  info.mot_de_passe ? (
                    <Stack gap="sm" maw={420}>
                      <Group gap="xs"><Lock size={16} /><Text size="sm">
                        {info.dossier ? voc("Ce dossier est protégé par un mot de passe.") : voc("Ce document est protégé par un mot de passe.")}
                      </Text></Group>
                      <PasswordInput value={motDePasse} onChange={(e) => setMotDePasse(e.currentTarget.value)} placeholder={voc("Mot de passe")}
                        onKeyDown={(e) => e.key === "Enter" && motDePasse && ouvrir()} autoFocus />
                      {erreur && <Alert color="red" p="xs">{erreur}</Alert>}
                      <Button onClick={ouvrir} loading={envoi} disabled={!motDePasse}>
                        {info.dossier ? voc("Ouvrir le dossier") : voc("Ouvrir le document")}
                      </Button>
                    </Stack>
                  ) : erreur ? <Alert color="red">{erreur}</Alert> : <Loader size="sm" />
                ) : ouvert.fichiers ? (
                  <Stack gap="sm">
                    {ouvert.fichiers.length === 0 ? (
                      <Text c="dimmed">{voc("Ce dossier ne contient aucun fichier pour l'instant.")}</Text>
                    ) : (
                      <>
                        {ouvert.zip_url && (
                          <Group>
                            <Button component="a" href={ouvert.zip_url} leftSection={<Download size={16} />}>
                              {voc`Tout télécharger (${ouvert.fichiers.length} fichiers, zip)`}
                            </Button>
                          </Group>
                        )}
                        <Table.ScrollContainer minWidth={420}>
                          <Table verticalSpacing="xs" striped>
                            <Table.Tbody>
                              {ouvert.fichiers.map((f) => (
                                <Table.Tr key={f.telechargement_url}>
                                  <Table.Td>
                                    <Group gap={8} wrap="nowrap">
                                      <FileText size={16} color="var(--mantine-color-teal-7)" style={{ flexShrink: 0 }} />
                                      <div>
                                        <Text size="sm">{f.nom}</Text>
                                        {f.chemin && <Text size="xs" c="dimmed">{f.chemin.replace(/\/$/, "")}</Text>}
                                      </div>
                                    </Group>
                                  </Table.Td>
                                  <Table.Td w={80}><Text size="xs" c="dimmed">{taille(f.taille)}</Text></Table.Td>
                                  <Table.Td w={140} ta="right">
                                    <Button component="a" href={f.telechargement_url} size="xs" variant="light" leftSection={<Download size={14} />}>
                                      {voc("Télécharger")}
                                    </Button>
                                  </Table.Td>
                                </Table.Tr>
                              ))}
                            </Table.Tbody>
                          </Table>
                        </Table.ScrollContainer>
                      </>
                    )}
                    <Text size="xs" c="dimmed">
                      {voc`Lien valable jusqu'au ${fin}.`} {voc("Pour un téléchargement plus tard, rechargez la page.")}
                    </Text>
                  </Stack>
                ) : (
                  <Stack gap="sm">
                    <Group gap="sm">
                      {ouvert.telechargement_url && (
                        <Button component="a" href={ouvert.telechargement_url} leftSection={<Download size={16} />}>{voc("Télécharger")}</Button>
                      )}
                      {ouvert.apercu_url && ouvert.droit === "TELECHARGER" && (
                        <Button component="a" href={ouvert.apercu_url} target="_blank" rel="noopener" variant="light" leftSection={<Eye size={16} />}>
                          {voc("Ouvrir dans un nouvel onglet")}
                        </Button>
                      )}
                    </Group>
                    {ouvert.apercu_url && (
                      <Apercu url={ouvert.apercu_url} type={ouvert.type} nom={ouvert.document ?? ""} lectureSeule={ouvert.droit === "CONSULTER"} />
                    )}
                    <Text size="xs" c="dimmed">{voc`Lien valable jusqu'au ${fin}.`}</Text>
                  </Stack>
                )}
              </Stack>
            </Card>
          )}
          <PiedDePage />
        </Stack>
      </Container>
    </Box>
  );
}

/**
 * Aperçu dans la page. En consultation seule : sans barre d'outils du lecteur PDF (téléchargement,
 * impression), sans menu « enregistrer » sur les vidéos et images. Cela décourage la copie sans
 * l'empêcher tout à fait (une capture d'écran reste possible) : un document affiché peut toujours être recopié.
 */
function Apercu({ url, type, nom, lectureSeule }: { url: string; type: string; nom: string; lectureSeule: boolean }) {
  const style = { width: "100%", border: "1px solid var(--mantine-color-gray-3)", borderRadius: 8, background: "white" };
  const sansMenu = lectureSeule ? { onContextMenu: (e: React.MouseEvent) => e.preventDefault() } : {};
  if (type.startsWith("image/")) return <img src={url} alt={nom} draggable={!lectureSeule} {...sansMenu} style={{ ...style, height: "auto", maxHeight: "75vh", objectFit: "contain" }} />;
  if (type.startsWith("video/")) {
    return <video src={url} controls controlsList={lectureSeule ? "nodownload" : undefined} {...sansMenu} style={{ ...style, maxHeight: "75vh" }} />;
  }
  const adresse = lectureSeule && type === "application/pdf" ? `${url}#toolbar=0&navpanes=0` : url;
  return <iframe src={adresse} title={nom} style={{ ...style, height: "75vh" }} />;
}
