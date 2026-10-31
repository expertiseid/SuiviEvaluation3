import { useEffect, useState } from "react";
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
  useEnregistrerMecanisme,
  useImporterCanevasParametrage,
  useMecanisme,
  useModelesMecanisme,
} from "../../api/plaintes";
import { useProjets } from "../../api/projects";
import { TitreRubrique } from "../../components/common/TitreRubrique";
import { messageErreurApi } from "../../utils/erreurs";
import { useAccesModules } from "../../utils/modules";
import { voc } from "../../utils/vocabulaire";
import { CircuitsPlaintes } from "./CircuitsPlaintes";
import { CategoriesPlainte, PrioritesPlainte, TypesRetour } from "./ListesPlaintes";

const LANGUES = [
  { value: "fr", label: "Français" },
  { value: "en", label: "English" },
  { value: "ar", label: "العربية" },
  { value: "es", label: "Español" },
  { value: "de", label: "Deutsch" },
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
        prefixe_numero: valeurs.prefixe_numero,
        jours_ouvres: valeurs.jours_ouvres,
        conservation_ordinaire_mois: valeurs.conservation_ordinaire_mois,
        conservation_sensible_mois: valeurs.conservation_sensible_mois,
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
        </Group>
        <Textarea
          label={voc("Texte d'information du public")}
          description={voc("Présenté aux personnes qui déposent un retour : à quoi sert le mécanisme, comment leurs données sont protégées.")}
          autosize
          minRows={3}
          value={valeurs.texte_information}
          disabled={!modifiable}
          onChange={(e) => changer("texte_information", e.currentTarget.value)}
        />
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

/** Mécanisme de gestion des plaintes et retours — lot 1 : paramétrage. */
export function PlaintesPage() {
  const { data: mecanisme } = useMecanisme();
  const { data: categories } = useCategoriesPlainte();
  const modifiable = useAccesModules().peutEcrire("/plaintes");
  if (!mecanisme) return null;
  const vide = categories !== undefined && categories.length === 0;

  return (
    <Stack>
      <Group justify="space-between">
        <TitreRubrique route="/plaintes" defaut={voc("Plaintes et retours")} />
        {mecanisme.actif ? (
          <Badge color="teal" size="lg" leftSection={<Power size={13} />}>{voc("Actif")}</Badge>
        ) : (
          <Badge color="gray" size="lg" leftSection={<PowerOff size={13} />}>{voc("Inactif")}</Badge>
        )}
      </Group>
      <Tabs defaultValue="mecanisme" keepMounted={false}>
        <Tabs.List>
          <Tabs.Tab value="mecanisme">{voc("Mécanisme")}</Tabs.Tab>
          <Tabs.Tab value="types">{voc("Types de retours")}</Tabs.Tab>
          <Tabs.Tab value="categories">{voc("Catégories")}</Tabs.Tab>
          <Tabs.Tab value="priorites">{voc("Priorités")}</Tabs.Tab>
          <Tabs.Tab value="circuits">{voc("Circuits de traitement")}</Tabs.Tab>
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
        <Tabs.Panel value="excel" pt="md"><CanevasExcel modifiable={modifiable} /></Tabs.Panel>
      </Tabs>
    </Stack>
  );
}
