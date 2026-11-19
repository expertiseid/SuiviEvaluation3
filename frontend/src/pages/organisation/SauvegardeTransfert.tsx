import { useState } from "react";
import { useAuth } from "../../auth/useAuth";
import { Alert, Button, Card, Checkbox, FileInput, Group, List, Loader, Modal, MultiSelect, Progress, Radio, SegmentedControl, Stack, Text, TextInput, Title } from "@mantine/core";
import { notifications } from "@mantine/notifications";
import { useQueryClient } from "@tanstack/react-query";
import { CircleCheck, DatabaseBackup, Download, Trash2, TriangleAlert, Upload } from "lucide-react";
import { tokenStorage } from "../../api/client";
import { useProjets } from "../../api/projects";
import { useCadresStrategiques } from "../../api/strategy";
import {
  type ManifesteSauvegarde, type ModeReprise, analyserSauvegarde, envoyerSauvegarde, reprendreSauvegarde, retirerExtrait,
  telechargerSauvegarde,
} from "../../api/transfert";
import type { CadreStrategique } from "../../types";
import { messageErreurApi } from "../../utils/erreurs";
import { locale } from "../../utils/i18n";
import { voc } from "../../utils/vocabulaire";

const MOT = "REMPLACER";
const MOT_VIDER = "VIDER";

/** Cadres choisis et, de proche en proche, les documents qui leur sont rattachés (programmes…). */
function cadresEtProgrammes(cadres: CadreStrategique[], choisis: string[]): Set<number> {
  const ids = new Set(choisis.map(Number));
  let ajout = true;
  while (ajout) {
    ajout = false;
    for (const c of cadres) {
      if (c.document_parent && ids.has(c.document_parent) && !ids.has(c.id)) {
        ids.add(c.id);
        ajout = true;
      }
    }
  }
  return ids;
}

/**
 * Sauvegarde complète de l'espace (toutes les données et tous les fichiers, un seul zip) et reprise
 * d'une sauvegarde, par exemple pour passer d'une plateforme à une autre (Administrateur).
 */
export function SauvegardeTransfert() {
  // Par défaut, l'Administrateur seulement ; un autre utilisateur, s'il y est autorisé (fiche Utilisateurs).
  // Vider l'espace, retirer un extrait et remplacer tout le contenu restent à l'Administrateur.
  const { user } = useAuth();
  const estAdmin = user?.role === "ADMIN";
  const peutExporter = estAdmin || !!user?.export_global;
  const peutImporter = estAdmin || !!user?.import_global;
  const [exportEnCours, setExportEnCours] = useState(false);
  const [etendue, setEtendue] = useState<"tout" | "selection">("tout");
  const [projetsChoisis, setProjetsChoisis] = useState<string[]>([]);
  const [cadresChoisis, setCadresChoisis] = useState<string[]>([]);
  const { data: projets = [] } = useProjets();
  const { data: cadres = [] } = useCadresStrategiques();
  // Cadres choisis d'abord : leurs programmes (et maillons suivants) comptent avec eux, et la liste des
  // projets se limite aux projets rattachés à l'un d'eux.
  const projetsDes = (choisis: string[]) => {
    const perimetre = cadresEtProgrammes(cadres, choisis);
    return projets.filter((p) => p.cadre_strategique != null && perimetre.has(p.cadre_strategique));
  };
  const projetsProposes = cadresChoisis.length > 0 ? projetsDes(cadresChoisis) : projets;
  const choisirCadres = (valeurs: string[]) => {
    setCadresChoisis(valeurs);
    // Par défaut, tous les projets de ces cadres : on retire ensuite ceux qu'on ne veut pas emporter.
    if (valeurs.length > 0) setProjetsChoisis(projetsDes(valeurs).map((p) => String(p.id)));
  };
  const selectionVide = etendue === "selection" && projetsChoisis.length === 0 && cadresChoisis.length === 0;
  // Retrait après l'extrait : impossible si un projet de ces cadres reste ici (il se retrouverait sans cadre).
  const [retirer, setRetirer] = useState(false);
  const projetsLaisses = cadresChoisis.length > 0 ? projetsProposes.filter((p) => !projetsChoisis.includes(String(p.id))).length : 0;
  const retraitPossible = etendue === "tout" || projetsLaisses === 0;
  const [avertissement, setAvertissement] = useState(false);
  const [motVider, setMotVider] = useState("");
  const queryClient = useQueryClient();
  const [fichier, setFichier] = useState<File | null>(null);
  const [envoi, setEnvoi] = useState<number | null>(null);
  const [identifiant, setIdentifiant] = useState<string | null>(null);
  const [manifeste, setManifeste] = useState<ManifesteSauvegarde | null>(null);
  const [confirmation, setConfirmation] = useState("");
  const [mode, setMode] = useState<ModeReprise>("ajouter");
  const [repriseEnCours, setRepriseEnCours] = useState(false);
  // Avancement de l'ajout (éléments traités / total), donné par le serveur pendant la reprise.
  const [avancement, setAvancement] = useState<{ traites: number; total: number } | null>(null);
  // Message de fin, gardé à l'écran sous le bouton (téléchargement, reprise).
  const [exportTermine, setExportTermine] = useState<string | null>(null);
  const [repriseTerminee, setRepriseTerminee] = useState<string | null>(null);

  const exporter = async () => {
    setAvertissement(false);
    setMotVider("");
    setExportTermine(null);
    setExportEnCours(true);
    let recu = null;
    try {
      recu = await telechargerSauvegarde(etendue === "selection"
        ? { projets: projetsChoisis.map(Number), cadres: cadresChoisis.map(Number), avecProjets: false }
        : undefined);
    } catch (error) {
      notifications.show({ color: "red", message: messageErreurApi(error, voc("La sauvegarde n'a pas pu être créée.")) });
      setExportEnCours(false);
      return;
    }
    setExportTermine(voc("Données téléchargées : le fichier zip se trouve dans les téléchargements de votre ordinateur."))
    // Le fichier est arrivé entier dans le navigateur : on retire seulement maintenant.
    if (retirer && retraitPossible && recu) {
      try {
        const retrait = await retirerExtrait(recu);
        notifications.show({
          color: "teal", autoClose: false,
          message: retrait.vide
            ? voc`Sauvegarde téléchargée, puis données de l'espace effacées : ${(retrait.objets ?? 0).toLocaleString(locale())} éléments supprimés. Les comptes et les réglages sont gardés.`
            : voc`Extrait téléchargé, puis retiré de la plateforme : ${retrait.projets ?? 0} projet(s) et ${retrait.cadres ?? 0} cadre(s) stratégique(s) supprimés.`,
        });
        setProjetsChoisis([]);
        setCadresChoisis([]);
        setRetirer(false);
        await queryClient.invalidateQueries();
      } catch (error) {
        notifications.show({
          color: "red", autoClose: false,
          message: messageErreurApi(error, voc("Le fichier est téléchargé, mais la suppression a échoué : rien n'a été supprimé.")),
        });
      }
    }
    setExportEnCours(false);
  };

  const projetsPartants = projets.filter((p) => projetsChoisis.includes(String(p.id)));
  const cadresPartants = cadres.filter((c) => cadresChoisis.includes(String(c.id)));

  const analyser = async () => {
    if (!fichier) return;
    setManifeste(null);
    setEnvoi(0);
    try {
      const id = await envoyerSauvegarde(fichier, setEnvoi);
      setIdentifiant(id);
      const lu = await analyserSauvegarde(id);
      if (lu.selection) setMode("ajouter");
      setManifeste(lu);
    } catch (error) {
      notifications.show({ color: "red", message: messageErreurApi(error, voc("Ce fichier ne peut pas être repris.")) });
      setEnvoi(null);
    }
  };

  const reprendre = async () => {
    if (!identifiant) return;
    setRepriseTerminee(null);
    setRepriseEnCours(true);
    setAvancement(null);
    try {
      const compteRendu = await reprendreSauvegarde(identifiant, mode, (traites, total) => setAvancement({ traites, total }));
      if (compteRendu.mode === "ajouter") {
        setRepriseTerminee(
          voc`Données importées : ${(compteRendu.crees ?? 0).toLocaleString(locale())} éléments créés, ${(compteRendu.reutilises ?? 0).toLocaleString(locale())} déjà présents réutilisés, ${(compteRendu.renommes ?? 0).toLocaleString(locale())} codes suffixés « -R ».`
            + (compteRendu.comptes_desactives
              ? " " + voc`${compteRendu.comptes_desactives} compte(s) ajouté(s) désactivé(s) : activez-les dans Utilisateurs si besoin.`
              : ""),
        );
        setManifeste(null);
        setFichier(null);
        setEnvoi(null);
        setIdentifiant(null);
        setRepriseEnCours(false);
        await queryClient.invalidateQueries();
        return;
      }
      setRepriseTerminee(voc`Données importées : ${compteRendu.objets.toLocaleString(locale())} éléments. Reconnectez-vous avec les comptes de l'espace sauvegardé : retour à la connexion dans quelques secondes.`);
      setRepriseEnCours(false);
      // Les comptes ont été remplacés : la session en cours ne vaut plus.
      tokenStorage.clear();
      window.setTimeout(() => window.location.assign("/login"), 8000);
    } catch (error) {
      notifications.show({ color: "red", message: messageErreurApi(error, voc("La reprise a échoué : rien n'a été modifié.")) });
      setRepriseEnCours(false);
    }
  };

  return (
    <Stack gap="md" maw={820}>
      <Card withBorder radius="md" padding="lg">
        <Group gap="xs" mb="xs"><Download size={18} /><Title order={4}>{voc("Exporter les données")}</Title></Group>
        {!peutExporter && <Alert color="gray" mb="sm">{voc("L'export global est réservé à l'administrateur : demandez-lui l'autorisation.")}</Alert>}
        <SegmentedControl
          mb="sm"
          value={etendue}
          onChange={(v) => { setEtendue(v as "tout" | "selection"); setRetirer(false); }}
          data={[{ value: "tout", label: voc("Tout l'espace") }, { value: "selection", label: voc("Une sélection") }]}
        />
        {etendue === "tout" ? (
          <Stack gap="xs" mb="sm">
            <Text size="sm">
              {voc("Un seul fichier zip avec toutes les données de votre espace : stratégies, projets, planification, indicateurs, suivis, bénéficiaires, documents, plaintes, comptes, réglages et fichiers.")}
            </Text>
            {estAdmin && <Checkbox
              color="red"
              label={voc("Vider l'espace après le téléchargement")}
              description={voc("Toutes les données seront supprimées dès que le fichier sera téléchargé : stratégies, projets, bénéficiaires, documents, plaintes, partenaires et fichiers. Les comptes, les réglages, le logo, les zones et les listes de référence restent.")}
              checked={retirer}
              onChange={(e) => setRetirer(e.currentTarget.checked)}
            />}
          </Stack>
        ) : (
          <Stack gap="xs" mb="sm">
            <Text size="sm">
              {voc("Seulement les projets et les cadres stratégiques choisis, avec tout ce qui leur appartient (planification, indicateurs, suivis, documents, plaintes, bénéficiaires inscrits). Les zones, bailleurs, partenaires et comptes cités viennent avec ; les autres projets restent ici.")}
            </Text>
            <MultiSelect
              label={voc("1. Cadres stratégiques (avec leurs programmes)")}
              description={voc("Facultatif : laissez vide pour choisir des projets parmi tous ceux de l'espace.")}
              placeholder={voc("Choisir un ou plusieurs cadres")}
              data={cadres.map((c) => ({ value: String(c.id), label: c.nom }))}
              value={cadresChoisis}
              onChange={choisirCadres}
              searchable clearable maw={640}
            />
            <MultiSelect
              label={cadresChoisis.length > 0 ? voc("2. Projets de ces cadres") : voc("2. Projets")}
              description={cadresChoisis.length > 0
                ? voc("Tous les projets de ces cadres sont choisis : retirez ceux à ne pas emporter.")
                : undefined}
              placeholder={projetsProposes.length === 0 ? voc("Aucun projet rattaché à ces cadres") : voc("Choisir un ou plusieurs projets")}
              data={projetsProposes.map((p) => ({ value: String(p.id), label: `${p.code} — ${p.nom}` }))}
              value={projetsChoisis}
              onChange={setProjetsChoisis}
              searchable clearable maw={640}
            />
            <Text size="xs" c="dimmed">{voc("Un extrait se reprend toujours en mode « Ajouter » : il ne peut jamais effacer l'espace qui le reçoit. Les comptes cités y arrivent désactivés.")}</Text>
            {estAdmin && <Checkbox
              color="red"
              label={voc("Retirer de la plateforme ce qui est exporté (après le téléchargement)")}
              description={retraitPossible
                ? voc("Les projets et cadres choisis seront supprimés de cet espace dès que le fichier sera téléchargé. Les zones, comptes, bailleurs et bénéficiaires restent.")
                : voc`Impossible : ${projetsLaisses} projet(s) de ces cadres resteraient ici sans cadre. Gardez tous leurs projets dans la liste pour retirer les cadres.`}
              checked={retirer && retraitPossible}
              disabled={!retraitPossible}
              onChange={(e) => setRetirer(e.currentTarget.checked)}
            />}
          </Stack>
        )}
        <Alert color="orange" icon={<TriangleAlert size={16} />} mb="sm">
          {voc("Ce fichier contient des données personnelles en clair (bénéficiaires, plaignants, pièces jointes). Gardez-le en lieu sûr et ne l'envoyez jamais par courriel.")}
        </Alert>
        <Button
          leftSection={retirer && retraitPossible ? <Trash2 size={16} /> : <DatabaseBackup size={16} />}
          color={retirer && retraitPossible ? "red" : undefined}
          onClick={() => (retirer && retraitPossible ? setAvertissement(true) : exporter())}
          disabled={!peutExporter || selectionVide || exportEnCours} w="fit-content"
          {...(exportEnCours ? { leftSection: <Loader size={14} /> } : {})}
        >
          {exportEnCours ? voc("Veuillez patienter…") : etendue === "tout"
            ? retirer ? voc("Télécharger la sauvegarde et vider l'espace") : voc("Télécharger la sauvegarde complète")
            : retirer && retraitPossible ? voc("Télécharger l'extrait et le retirer") : voc("Télécharger l'extrait")}
        </Button>
        <Modal opened={avertissement} onClose={() => setAvertissement(false)}
          title={etendue === "tout" ? voc("Vider tout l'espace ?") : voc("Retirer de la plateforme ?")} centered>
          {etendue === "tout" ? (
            <Stack gap="sm">
              <Alert color="red" icon={<TriangleAlert size={16} />}>
                {voc("Après le téléchargement, TOUTES les données de cet espace seront supprimées définitivement : stratégies, projets, planification, indicateurs, suivis, bénéficiaires, documents, plaintes, partenaires et fichiers. Seul le fichier zip les gardera.")}
              </Alert>
              <Text size="sm">{voc("Restent : les comptes des utilisateurs, les réglages, le logo, les zones et les listes de référence.")}</Text>
              <Text size="sm">{voc("Si le téléchargement n'aboutit pas, rien n'est supprimé.")}</Text>
              <TextInput
                label={voc`Pour confirmer, tapez ${MOT_VIDER}`}
                value={motVider}
                onChange={(e) => setMotVider(e.currentTarget.value)}
                maw={260}
              />
              <Group justify="flex-end">
                <Button variant="default" onClick={() => setAvertissement(false)}>{voc("Annuler")}</Button>
                <Button color="red" leftSection={<Trash2 size={16} />} onClick={exporter} disabled={motVider.trim().toUpperCase() !== MOT_VIDER}>
                  {voc("Télécharger et vider l'espace")}
                </Button>
              </Group>
            </Stack>
          ) : (
          <Stack gap="sm">
            <Alert color="red" icon={<TriangleAlert size={16} />}>
              {voc("Après le téléchargement, ces éléments seront supprimés définitivement de cet espace, avec tout ce qui leur appartient (planification, indicateurs, suivis, documents, plaintes). Seul le fichier zip les gardera.")}
            </Alert>
            <List size="sm" spacing={2}>
              {projetsPartants.map((p) => <List.Item key={`p${p.id}`}>{voc("Projet")} {p.code} — {p.nom}</List.Item>)}
              {cadresPartants.map((c) => <List.Item key={`c${c.id}`}>{voc("Cadre stratégique")} {c.nom}</List.Item>)}
            </List>
            {cadresPartants.length > 0 && (
              <Text size="xs" c="dimmed">{voc("Les programmes de ces cadres sont aussi retirés.")}</Text>
            )}
            <Text size="sm">{voc("Si le téléchargement n'aboutit pas, rien n'est supprimé.")}</Text>
            <Group justify="flex-end">
              <Button variant="default" onClick={() => setAvertissement(false)}>{voc("Annuler")}</Button>
              <Button color="red" leftSection={<Trash2 size={16} />} onClick={exporter}>{voc("J'ai compris : télécharger et supprimer")}</Button>
            </Group>
          </Stack>
          )}
        </Modal>
        {exportEnCours && <Text size="xs" c="dimmed" mt={6}>{voc("Préparation du fichier : cela peut prendre quelques minutes.")}</Text>}
        {exportTermine && !exportEnCours && (
          <Alert color="teal" icon={<CircleCheck size={16} />} mt="sm" withCloseButton onClose={() => setExportTermine(null)}>
            {exportTermine}
          </Alert>
        )}
      </Card>

      <Card withBorder radius="md" padding="lg">
        <Group gap="xs" mb="xs"><Upload size={18} /><Title order={4}>{voc("Reprendre une sauvegarde")}</Title></Group>
        {!peutImporter && <Alert color="gray" mb="sm">{voc("L'import global est réservé à l'administrateur : demandez-lui l'autorisation.")}</Alert>}
        <Text size="sm" mb="xs">
          {voc("Pour retrouver, dans cet espace, tout ce que vous aviez dans un autre (sur cette plateforme ou une autre).")}
        </Text>
        <Radio.Group value={mode} onChange={(v) => { setMode(v as ModeReprise); setConfirmation(""); }} mb="sm">
          <Stack gap="xs">
            <Radio value="ajouter" label={voc("Ajouter à ce qui existe (recommandé)")}
              description={voc("Cet espace garde tout ce qu'il a ; les données de la sauvegarde s'y ajoutent. Ce qui existe déjà (zones, comptes, bailleurs, réglages…) n'est pas dupliqué ; un projet dont le code existe déjà est ajouté avec un code suffixé « -R1 ».")} />
            <Radio value="remplacer" label={voc("Remplacer tout le contenu")} disabled={!estAdmin || !!manifeste?.selection}
              description={voc("Tout le contenu actuel de cet espace est remplacé par celui de la sauvegarde. Ensuite, on se connecte avec les comptes de l'espace sauvegardé ; votre compte est gardé s'il n'y figure pas.")} />
          </Stack>
        </Radio.Group>
        <Text size="xs" c="dimmed" mb="sm">{voc("Le journal d'audit est conservé ; les événements de l'espace sauvegardé s'y ajoutent.")}</Text>
        <Group align="flex-end" mb="sm">
          <FileInput
            label={voc("Fichier de sauvegarde (.zip)")}
            accept=".zip,application/zip"
            value={fichier}
            onChange={(f) => { setFichier(f); setManifeste(null); setEnvoi(null); setIdentifiant(null); setConfirmation(""); }}
            disabled={!peutImporter}
            clearable
            w={340}
          />
          <Button variant="light" onClick={analyser} disabled={!peutImporter || !fichier || (envoi !== null && !manifeste)}>{voc("Envoyer et vérifier")}</Button>
        </Group>
        {envoi !== null && !manifeste && <Progress value={envoi * 100} mb="sm" animated />}
        {manifeste && (
          <Stack gap="xs">
            <Alert color="blue">
              {voc`Sauvegarde de « ${manifeste.organisation || voc("plateforme")} » du ${new Date(manifeste.date).toLocaleString(locale())} : ${manifeste.objets.toLocaleString(locale())} éléments.`}
            </Alert>
            {manifeste.selection && (
              <Text size="sm" c="dimmed">{voc("Ce fichier est un extrait (quelques projets ou cadres) : il s'ajoute à cet espace.")}</Text>
            )}
            {mode === "remplacer" && !manifeste.selection ? (
              <>
                <TextInput
                  label={voc`Pour confirmer, tapez ${MOT}`}
                  value={confirmation}
                  onChange={(e) => setConfirmation(e.currentTarget.value)}
                  w={340}
                />
                <Button color="red" onClick={reprendre} disabled={confirmation.trim() !== MOT || repriseEnCours} w="fit-content"
                  {...(repriseEnCours ? { leftSection: <Loader size={14} /> } : {})}>
                  {repriseEnCours ? voc("Veuillez patienter…") : voc("Remplacer le contenu de cet espace")}
                </Button>
              </>
            ) : (
              <Button onClick={reprendre} disabled={repriseEnCours} w="fit-content"
                {...(repriseEnCours ? { leftSection: <Loader size={14} /> } : {})}>
                {repriseEnCours ? voc("Veuillez patienter…") : voc("Ajouter ces données à la plateforme")}
              </Button>
            )}
            {repriseEnCours && (
              <Stack gap={4}>
                {avancement && (
                  <>
                    <Progress value={(100 * avancement.traites) / avancement.total} size="sm" animated />
                    <Text size="xs">{voc`${avancement.traites.toLocaleString(locale())} éléments traités sur ${avancement.total.toLocaleString(locale())}`}</Text>
                  </>
                )}
                <Text size="xs" c="dimmed">{voc("Import en cours : cela peut prendre plusieurs minutes. Ne fermez pas cette page.")}</Text>
              </Stack>
            )}
          </Stack>
        )}
        {repriseTerminee && (
          <Alert color="teal" icon={<CircleCheck size={16} />} mt="sm" withCloseButton onClose={() => setRepriseTerminee(null)}>
            {repriseTerminee}
          </Alert>
        )}
      </Card>
    </Stack>
  );
}
