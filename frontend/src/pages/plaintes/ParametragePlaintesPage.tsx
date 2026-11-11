import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { CircleAlert, CircleCheck, Download, Power, PowerOff, Upload } from "lucide-react";
import {
  Alert,
  Badge,
  Button,
  Card,
  FileInput,
  Group,
  List,
  MultiSelect,
  NumberInput,
  SimpleGrid,
  Select,
  Stack,
  Switch,
  Tabs,
  Text,
  TextInput,
  Textarea,
  } from "@mantine/core";
import { modals } from "@mantine/modals";
import { notifications } from "@mantine/notifications";
import {
  type MecanismePlaintes,
  type RapportImportParametrage,
  telechargerCanevasParametrage,
  useActivationMecanisme,
  useAppliquerModele,
  useCategoriesPlainte,
  useCircuitsPlainte,
  useEnregistrerMecanisme,
  useImporterCanevasParametrage,
  useMecanisme,
  useModelesMecanisme,
} from "../../api/plaintes";
import { useProjets } from "../../api/projects";
import { useAuth } from "../../auth/useAuth";
import { DonneesPersonnellesPlaintes } from "./DonneesPersonnellesPlaintes";
import { HabilitationsPlaintes } from "./HabilitationsPlaintes";
import { messageErreurApi } from "../../utils/erreurs";
import { useAccesModules } from "../../utils/modules";
import { voc } from "../../utils/vocabulaire";
import { CalendrierPlaintes } from "./CalendrierPlaintes";
import { CircuitsPlaintes } from "./CircuitsPlaintes";
import { MessagesPlaintes } from "./MessagesPlaintes";
import { PrestatairesPlaintes } from "./PrestatairesPlaintes";
import { CategoriesPlainte, PrioritesPlainte, TypesRetour } from "./ListesPlaintes";
import { EnTetePlaintes } from "./EnTetePlaintes";

const LANGUES = [
  { value: "fr", label: "Français" },
  { value: "en", label: "English" },
  { value: "ar", label: "العربية" },
  { value: "es", label: "Español" },
  { value: "de", label: "Deutsch" },
  { value: "it", label: "Italiano" },
];

/** Point de départ : un modèle pré-rempli, ensuite entièrement modifiable. */
function ChoixModele() {
  const { data: modeles = [] } = useModelesMecanisme();
  const appliquer = useAppliquerModele();
  return (
    <Card withBorder>
      <Stack gap="sm">
        <Text fw={600}>{voc("Partir d'un modèle")}</Text>
        <Text size="sm" c="dimmed">
          {voc("Le modèle installe des types, priorités, catégories et circuits courants, que vous adaptez ensuite. Le circuit confidentiel est toujours ajouté.")}
        </Text>
        <SimpleGrid cols={{ base: 1, sm: modeles.length || 1 }}>
          {modeles.map((m) => (
            <Card key={m.code} withBorder padding="sm">
              <Stack gap="xs" h="100%" justify="space-between">
                <div>
                  <Text fw={600} size="sm">{m.libelle}</Text>
                  <Text size="xs" c="dimmed">{m.description}</Text>
                </div>
                <Button
                  size="xs"
                  variant="light"
                  loading={appliquer.isPending && appliquer.variables === m.code}
                  onClick={async () => {
                    try {
                      await appliquer.mutateAsync(m.code);
                      notifications.show({ message: voc("Modèle appliqué : complétez maintenant les réglages."), color: "teal" });
                    } catch (error) {
                      notifications.show({ message: messageErreurApi(error, voc("Erreur lors de l'enregistrement")), color: "red" });
                    }
                  }}
                >
                  {voc("Utiliser ce modèle")}
                </Button>
              </Stack>
            </Card>
          ))}
        </SimpleGrid>
      </Stack>
    </Card>
  );
}

/** Ce qui manque pour activer, ou « prêt », avec les boutons Activer / Désactiver. */
function Activation({ mecanisme, modifiable }: { mecanisme: MecanismePlaintes; modifiable: boolean }) {
  const activation = useActivationMecanisme();
  const basculer = (activer: boolean) =>
    modals.openConfirmModal({
      title: activer ? voc("Activer le mécanisme") : voc("Désactiver le mécanisme"),
      children: (
        <Text size="sm">
          {activer
            ? voc("Les retours pourront être reçus et traités selon ce paramétrage.")
            : voc("Plus aucun retour ne sera reçu ; les dossiers existants sont conservés.")}
        </Text>
      ),
      labels: { confirm: activer ? voc("Activer") : voc("Désactiver"), cancel: voc("Annuler") },
      confirmProps: { color: activer ? "teal" : "red" },
      onConfirm: async () => {
        try {
          await activation.mutateAsync(activer);
        } catch (error) {
          notifications.show({ message: messageErreurApi(error, voc("Activation impossible")), color: "red" });
        }
      },
    });

  if (mecanisme.actif) {
    return (
      <Alert color="teal" icon={<CircleCheck size={18} />} title={voc("Mécanisme actif")}>
        <Group justify="space-between">
          <Text size="sm">{voc("Le mécanisme reçoit les retours. Les réglages restent modifiables.")}</Text>
          {modifiable && (
            <Button size="xs" color="red" variant="light" leftSection={<PowerOff size={14} />} onClick={() => basculer(false)}>
              {voc("Désactiver")}
            </Button>
          )}
        </Group>
        {mecanisme.controles.length > 0 && (
          <List size="sm" mt="xs" c="orange.8">
            {mecanisme.controles.map((c) => <List.Item key={c}>{voc(c)}</List.Item>)}
          </List>
        )}
      </Alert>
    );
  }
  if (mecanisme.controles.length) {
    return (
      <Alert color="orange" icon={<CircleAlert size={18} />} title={voc("À compléter avant l'activation")}>
        <List size="sm">
          {mecanisme.controles.map((c) => <List.Item key={c}>{voc(c)}</List.Item>)}
        </List>
      </Alert>
    );
  }
  return (
    <Alert color="teal" icon={<CircleCheck size={18} />} title={voc("Prêt à être activé")}>
      <Group justify="space-between">
        <Text size="sm">{voc("Tous les contrôles sont satisfaits.")}</Text>
        {modifiable && (
          <Button size="xs" color="teal" leftSection={<Power size={14} />} onClick={() => basculer(true)}>
            {voc("Activer")}
          </Button>
        )}
      </Group>
    </Alert>
  );
}

/** Réglages généraux du mécanisme. */
function FormulaireMecanisme({ mecanisme, modifiable }: { mecanisme: MecanismePlaintes; modifiable: boolean }) {
  const enregistrer = useEnregistrerMecanisme();
  const { data: projets = [] } = useProjets();
  const { data: circuits = [] } = useCircuitsPlainte();
  const [valeurs, setValeurs] = useState(mecanisme);
  useEffect(() => setValeurs(mecanisme), [mecanisme]);
  const changer = <K extends keyof MecanismePlaintes>(champ: K, valeur: MecanismePlaintes[K]) =>
    setValeurs((v) => ({ ...v, [champ]: valeur }));

  const sauver = async () => {
    try {
      await enregistrer.mutateAsync({
        nom: valeurs.nom,
        anonymat_autorise: valeurs.anonymat_autorise,
        langues: valeurs.langues,
        texte_information: valeurs.texte_information,
        texte_consentement: valeurs.texte_consentement,
        anonymisation_automatique: valeurs.anonymisation_automatique,
        prefixe_numero: valeurs.prefixe_numero,
        jours_ouvres: valeurs.jours_ouvres,
        conservation_ordinaire_mois: valeurs.conservation_ordinaire_mois,
        conservation_sensible_mois: valeurs.conservation_sensible_mois,
        delai_defaut_jours: valeurs.delai_defaut_jours,
        rappel_jours_avant: valeurs.rappel_jours_avant,
        escalade_active: valeurs.escalade_active,
        notifications_courriel: valeurs.notifications_courriel,
        circuit_alternatif: valeurs.circuit_alternatif,
        seuil_masquage: valeurs.seuil_masquage,
        accuse_reception_auto: valeurs.accuse_reception_auto,
        signature_messages: valeurs.signature_messages,
        pieces_formulaire_public: valeurs.pieces_formulaire_public,
        responsable_traitement: valeurs.responsable_traitement,
        contact_donnees: valeurs.contact_donnees,
        taille_max_piece_mo: valeurs.taille_max_piece_mo,
        projets: valeurs.projets,
      });
      notifications.show({ message: voc("Réglages enregistrés"), color: "teal" });
    } catch (error) {
      notifications.show({ message: messageErreurApi(error, voc("Erreur lors de l'enregistrement")), color: "red" });
    }
  };

  return (
    <Card withBorder>
      <Stack gap="sm">
        <SimpleGrid cols={{ base: 1, sm: 2 }}>
          <TextInput label={voc("Nom du mécanisme")} value={valeurs.nom} disabled={!modifiable} onChange={(e) => changer("nom", e.currentTarget.value)} />
          <TextInput
            label={voc("Préfixe des numéros de dossier")}
            description={voc("Ex : MGP → MGP-2026-0001")}
            value={valeurs.prefixe_numero}
            disabled={!modifiable}
            onChange={(e) => changer("prefixe_numero", e.currentTarget.value)}
          />
          <MultiSelect label={voc("Langues de réception")} data={LANGUES} value={valeurs.langues} disabled={!modifiable} onChange={(v) => changer("langues", v)} />
          <MultiSelect
            label={voc("Projets couverts")}
            description={voc("Laisser vide pour couvrir tous les projets.")}
            data={projets.map((p) => ({ value: String(p.id), label: p.code ? `${p.code} — ${p.nom}` : p.nom }))}
            value={valeurs.projets.map(String)}
            disabled={!modifiable}
            searchable
            clearable
            onChange={(v) => changer("projets", v.map(Number))}
          />
          <NumberInput
            label={voc("Conservation des dossiers ordinaires (mois)")}
            description={voc("Exemple indicatif : 60 mois. À fixer selon les règles de l'organisation.")}
            min={1}
            value={valeurs.conservation_ordinaire_mois ?? ""}
            disabled={!modifiable}
            onChange={(v) => changer("conservation_ordinaire_mois", v === "" ? null : Number(v))}
          />
          <NumberInput
            label={voc("Conservation des dossiers sensibles (mois)")}
            description={voc("Exemple indicatif : 120 mois. À fixer selon les règles de l'organisation.")}
            min={1}
            value={valeurs.conservation_sensible_mois ?? ""}
            disabled={!modifiable}
            onChange={(v) => changer("conservation_sensible_mois", v === "" ? null : Number(v))}
          />
        </SimpleGrid>
        <Switch
          label={voc("Anonymiser automatiquement à l'échéance de conservation")}
          description={voc("Sinon, les dossiers arrivés à échéance apparaissent dans « À anonymiser » et sont confirmés un par un. Jamais pour un dossier sous suspension légale.")}
          checked={!!valeurs.anonymisation_automatique}
          disabled={!modifiable}
          onChange={(e) => changer("anonymisation_automatique", e.currentTarget.checked)}
        />
        <Select
          label={voc("Circuit alternatif (personne mise en cause)")}
          description={voc("Suivi quand une personne mise en cause fait partie du circuit confidentiel habituel : direction, siège, référent extérieur… Obligatoire pour l'activation.")}
          data={circuits.filter((c) => c.sensible).map((c) => ({ value: String(c.id), label: c.nom }))}
          value={valeurs.circuit_alternatif ? String(valeurs.circuit_alternatif) : null}
          disabled={!modifiable}
          onChange={(v) => changer("circuit_alternatif", v ? Number(v) : null)}
          clearable
        />
        <SimpleGrid cols={{ base: 1, sm: 2 }}>
          <NumberInput
            label={voc("Délai de traitement par défaut (jours)")}
            description={voc("Quand ni la catégorie ni la priorité ne fixent de délai.")}
            min={1}
            value={valeurs.delai_defaut_jours}
            disabled={!modifiable}
            onChange={(v) => changer("delai_defaut_jours", Number(v) || 1)}
          />
          <NumberInput
            label={voc("Seuil de masquage des petits effectifs confidentiels")}
            description={voc("Tableaux de bord : une case comptant moins de dossiers confidentiels est affichée « moins de N ». Jamais en dessous de 5.")}
            min={5}
            value={valeurs.seuil_masquage}
            disabled={!modifiable}
            onChange={(v) => changer("seuil_masquage", Math.max(5, Number(v) || 5))}
          />
          <NumberInput
            label={voc("Rappel avant l'échéance (jours)")}
            description={voc("Le gestionnaire est prévenu quand l'échéance approche.")}
            min={0}
            value={valeurs.rappel_jours_avant}
            disabled={!modifiable}
            onChange={(v) => changer("rappel_jours_avant", Number(v) || 0)}
          />
          <NumberInput
            label={voc("Taille maximale d'un fichier joint (Mo)")}
            description={voc`Pièces jointes des plaignants et de l'équipe. Plafond de la plateforme : ${valeurs.plafond_piece_mo} Mo.`}
            min={1}
            max={valeurs.plafond_piece_mo}
            value={valeurs.taille_max_piece_mo}
            disabled={!modifiable}
            onChange={(v) => changer("taille_max_piece_mo", Math.min(valeurs.plafond_piece_mo, Math.max(1, Number(v) || 1)))}
          />
        </SimpleGrid>
        <Group gap="xl">
          <Switch
            label={voc("Signaler les retards aux superviseurs (escalade)")}
            checked={valeurs.escalade_active}
            disabled={!modifiable}
            onChange={(e) => changer("escalade_active", e.currentTarget.checked)}
          />
          <Switch
            label={voc("Accusé de réception automatique au plaignant")}
            checked={valeurs.accuse_reception_auto}
            disabled={!modifiable}
            onChange={(e) => changer("accuse_reception_auto", e.currentTarget.checked)}
          />
          <Switch
            label={voc("Envoyer aussi les notifications par courriel")}
            checked={valeurs.notifications_courriel}
            disabled={!modifiable}
            onChange={(e) => changer("notifications_courriel", e.currentTarget.checked)}
          />
        </Group>
        <Group gap="xl">
          <Switch
            label={voc("Accepter les retours anonymes")}
            checked={valeurs.anonymat_autorise}
            disabled={!modifiable}
            onChange={(e) => changer("anonymat_autorise", e.currentTarget.checked)}
          />
          <Switch
            label={voc("Délais comptés en jours ouvrés")}
            checked={valeurs.jours_ouvres}
            disabled={!modifiable}
            onChange={(e) => changer("jours_ouvres", e.currentTarget.checked)}
          />
          <Switch
            label={voc("Les plaignants peuvent joindre des fichiers (formulaire public et complément)")}
            checked={valeurs.pieces_formulaire_public}
            disabled={!modifiable}
            onChange={(e) => changer("pieces_formulaire_public", e.currentTarget.checked)}
          />
        </Group>
        <SimpleGrid cols={{ base: 1, sm: 2 }}>
          <TextInput
            label={voc("Responsable du traitement des données")}
            description={voc("Organisation, adresse : figure dans le registre des traitements.")}
            value={valeurs.responsable_traitement}
            disabled={!modifiable}
            onChange={(e) => changer("responsable_traitement", e.currentTarget.value)}
          />
          <TextInput
            label={voc("Contact pour les données personnelles")}
            description={voc("Personne ou adresse à qui adresser les demandes d'accès, de rectification, d'effacement.")}
            value={valeurs.contact_donnees}
            disabled={!modifiable}
            onChange={(e) => changer("contact_donnees", e.currentTarget.value)}
          />
        </SimpleGrid>
        <TextInput
          label={voc("Signature des messages au plaignant")}
          description={voc("Remplace {signature} dans les messages (ex : « L'équipe du projet »). Vide : le nom du mécanisme.")}
          value={valeurs.signature_messages}
          disabled={!modifiable}
          onChange={(e) => changer("signature_messages", e.currentTarget.value)}
        />
        <Textarea
          label={voc("Texte d'information du public")}
          description={voc("Présenté aux personnes qui déposent un retour : à quoi sert le mécanisme, comment leurs données sont protégées.")}
          autosize
          minRows={3}
          value={valeurs.texte_information}
          disabled={!modifiable}
          onChange={(e) => changer("texte_information", e.currentTarget.value)}
        />
        <Textarea
          label={voc("Clause de consentement (RGPD)")}
          description={voc("Affichée sur le formulaire public juste avant la case d'accord ; le dossier garde le texte accepté et sa date. Vide : une phrase d'accord courte est utilisée.")}
          autosize
          minRows={3}
          value={valeurs.texte_consentement ?? ""}
          disabled={!modifiable}
          onChange={(e) => changer("texte_consentement", e.currentTarget.value)}
        />
        {modifiable && (
          <Group justify="flex-start" mt={-8}>
            <Button size="xs" variant="subtle" onClick={() => changer("texte_consentement", voc("Les informations que vous donnez dans ce formulaire servent uniquement à traiter votre retour et à vous répondre. Elles sont gardées de façon confidentielle, accessibles seulement aux personnes chargées de votre dossier, puis supprimées ou rendues anonymes à la fin de la durée de conservation. Vous pouvez à tout moment demander à consulter, corriger ou effacer vos informations, avec votre code de suivi ou en nous contactant."))}>
              {voc("Insérer le modèle de clause")}
            </Button>
          </Group>
        )}
        {modifiable && (
          <Group justify="flex-end">
            <Button onClick={sauver} loading={enregistrer.isPending}>{voc("Enregistrer")}</Button>
          </Group>
        )}
      </Stack>
    </Card>
  );
}

/** Tout le paramétrage dans un classeur Excel, à remplir hors ligne puis réimporter. */
function CanevasExcel({ modifiable }: { modifiable: boolean }) {
  const importer = useImporterCanevasParametrage();
  const [fichier, setFichier] = useState<File | null>(null);
  const [rapport, setRapport] = useState<RapportImportParametrage | null>(null);
  return (
    <Stack gap="sm">
      <Text size="sm" c="dimmed">
        {voc("Le canevas contient tout le paramétrage actuel (une feuille par rubrique). Modifiez-le ou complétez-le puis réimportez-le : les éléments sont retrouvés par leur nom, les étapes d'un circuit présent dans le fichier sont remplacées.")}
      </Text>
      <Group>
        <Button variant="light" leftSection={<Download size={14} />} onClick={() => telechargerCanevasParametrage()}>
          {voc("Télécharger le canevas")}
        </Button>
      </Group>
      {modifiable && (
        <Group align="flex-end">
          <FileInput w={320} label={voc("Fichier complété")} accept=".xlsx" value={fichier} onChange={setFichier} clearable />
          <Button
            leftSection={<Upload size={14} />}
            disabled={!fichier}
            loading={importer.isPending}
            onClick={async () => {
              if (!fichier) return;
              try {
                setRapport(await importer.mutateAsync(fichier));
                setFichier(null);
              } catch (error) {
                notifications.show({ message: messageErreurApi(error, voc("Import impossible")), color: "red" });
              }
            }}
          >
            {voc("Importer")}
          </Button>
        </Group>
      )}
      {rapport && (
        <Alert color={rapport.erreurs.length ? "orange" : "teal"} title={voc`${rapport.crees} créé(s), ${rapport.mis_a_jour} mis à jour`}>
          {rapport.erreurs.length > 0 && (
            <List size="sm">
              {rapport.erreurs.map((e, i) => (
                <List.Item key={i}>{voc`Ligne ${e.ligne} : ${e.message}`}</List.Item>
              ))}
            </List>
          )}
        </Alert>
      )}
    </Stack>
  );
}

/** Paramétrage du mécanisme de gestion des plaintes et retours (lot 1). */
export function ParametragePlaintesPage() {
  const { data: mecanisme } = useMecanisme();
  const { data: categories } = useCategoriesPlainte();
  const modifiable = useAccesModules().peutEcrire("/plaintes");
  const estAdmin = useAuth().user?.role === "ADMIN";
  const [params] = useSearchParams();
  if (!mecanisme) return null;
  const vide = categories !== undefined && categories.length === 0;

  return (
    <Stack>
      <EnTetePlaintes
        actions={mecanisme.actif ? (
          <Badge color="teal" size="lg" leftSection={<Power size={13} />}>{voc("Mécanisme actif")}</Badge>
        ) : (
          <Badge color="gray" size="lg" leftSection={<PowerOff size={13} />}>{voc("Mécanisme inactif")}</Badge>
        )}
      />
      <Tabs defaultValue={params.get("onglet") ?? "mecanisme"} keepMounted={false}>
        <Tabs.List>
          <Tabs.Tab value="mecanisme">{voc("Mécanisme")}</Tabs.Tab>
          <Tabs.Tab value="types">{voc("Types de retours")}</Tabs.Tab>
          <Tabs.Tab value="categories">{voc("Catégories")}</Tabs.Tab>
          <Tabs.Tab value="priorites">{voc("Priorités")}</Tabs.Tab>
          <Tabs.Tab value="circuits">{voc("Circuits de traitement")}</Tabs.Tab>
          <Tabs.Tab value="messages">{voc("Messages")}</Tabs.Tab>
          <Tabs.Tab value="calendrier">{voc("Calendrier")}</Tabs.Tab>
          <Tabs.Tab value="prestataires">{voc("Prestataires d'assistance")}</Tabs.Tab>
          <Tabs.Tab value="habilitations">{voc("Habilitations")}</Tabs.Tab>
          {estAdmin && <Tabs.Tab value="donnees">{voc("Données personnelles")}</Tabs.Tab>}
          <Tabs.Tab value="excel">{voc("Canevas Excel")}</Tabs.Tab>
        </Tabs.List>
        <Tabs.Panel value="mecanisme" pt="md">
          <Stack>
            <Activation mecanisme={mecanisme} modifiable={modifiable} />
            {vide && modifiable && <ChoixModele />}
            <FormulaireMecanisme mecanisme={mecanisme} modifiable={modifiable} />
          </Stack>
        </Tabs.Panel>
        <Tabs.Panel value="types" pt="md"><TypesRetour modifiable={modifiable} /></Tabs.Panel>
        <Tabs.Panel value="categories" pt="md"><CategoriesPlainte modifiable={modifiable} /></Tabs.Panel>
        <Tabs.Panel value="priorites" pt="md"><PrioritesPlainte modifiable={modifiable} /></Tabs.Panel>
        <Tabs.Panel value="circuits" pt="md"><CircuitsPlaintes modifiable={modifiable} /></Tabs.Panel>
        <Tabs.Panel value="messages" pt="md"><MessagesPlaintes modifiable={modifiable} /></Tabs.Panel>
        <Tabs.Panel value="calendrier" pt="md"><CalendrierPlaintes modifiable={modifiable} /></Tabs.Panel>
        <Tabs.Panel value="prestataires" pt="md"><PrestatairesPlaintes modifiable={modifiable} /></Tabs.Panel>
        <Tabs.Panel value="habilitations" pt="md"><HabilitationsPlaintes modifiable={modifiable} /></Tabs.Panel>
        {estAdmin && <Tabs.Panel value="donnees" pt="md"><DonneesPersonnellesPlaintes /></Tabs.Panel>}
        <Tabs.Panel value="excel" pt="md"><CanevasExcel modifiable={modifiable} /></Tabs.Panel>
      </Tabs>
    </Stack>
  );
}
