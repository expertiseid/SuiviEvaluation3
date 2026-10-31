import { useEffect, useState } from "react";
import { CornerDownRight, Lock, Plus, ShieldAlert, Siren, Trash2 } from "lucide-react";
import {
  ActionIcon,
  Badge,
  Button,
  Checkbox,
  Group,
  NumberInput,
  Select,
  Stack,
  Switch,
  Table,
  Text,
  TextInput,
  Tooltip,
} from "@mantine/core";
import { notifications } from "@mantine/notifications";
import {
  type CategoriePlainte,
  type PrioritePlainte,
  type TypeRetour,
  useCategoriesPlainte,
  useCircuitsPlainte,
  useEnregistrerCategorie,
  useEnregistrerPriorite,
  useEnregistrerTypeRetour,
  usePrioritesPlainte,
  useSupprimerCategorie,
  useSupprimerPriorite,
  useSupprimerTypeRetour,
  useTypesRetour,
} from "../../api/plaintes";
import { confirmerSuppression } from "../../components/common/confirmerSuppression";
import { messageErreurApi } from "../../utils/erreurs";
import { voc } from "../../utils/vocabulaire";

const VERROU = voc("Ce réglage protège les personnes et ne peut pas être modifié.");

/** Enregistre un champ et affiche l'erreur en clair si le serveur refuse. */
function useSauver<T>(mutation: { mutateAsync: (p: T) => Promise<unknown> }) {
  return async (payload: T) => {
    try {
      await mutation.mutateAsync(payload);
    } catch (error) {
      notifications.show({ message: messageErreurApi(error, voc("Erreur lors de l'enregistrement")), color: "red" });
    }
  };
}

/** Texte enregistré en quittant le champ. */
function ChampTexte({ valeur, onSauver, modifiable, placeholder }: { valeur: string; onSauver: (v: string) => void; modifiable: boolean; placeholder?: string }) {
  const [texte, setTexte] = useState(valeur);
  useEffect(() => setTexte(valeur), [valeur]);
  if (!modifiable) return <Text size="sm">{valeur || "—"}</Text>;
  return (
    <TextInput
      size="xs"
      style={{ flex: 1 }}
      value={texte}
      placeholder={placeholder}
      onChange={(e) => setTexte(e.currentTarget.value)}
      onBlur={() => texte !== valeur && onSauver(texte.trim())}
    />
  );
}

function BoutonSupprimer({ libelle, onConfirmer }: { libelle: string; onConfirmer: () => Promise<unknown> }) {
  return (
    <ActionIcon
      size="sm"
      variant="subtle"
      color="red"
      aria-label={voc("Supprimer")}
      onClick={() =>
        confirmerSuppression({
          message: voc`Supprimer « ${libelle} » ?`,
          onConfirm: async () => {
            try {
              await onConfirmer();
            } catch (error) {
              notifications.show({ message: messageErreurApi(error, voc("Suppression impossible")), color: "red" });
            }
          },
        })
      }
    >
      <Trash2 size={13} />
    </ActionIcon>
  );
}

/** Ajout d'un élément par son nom. */
function Ajout({ placeholder, libelle, onAjouter }: { placeholder: string; libelle: string; onAjouter: (nom: string) => Promise<void> }) {
  const [nom, setNom] = useState("");
  const ajouter = async () => {
    if (!nom.trim()) return;
    await onAjouter(nom.trim());
    setNom("");
  };
  return (
    <Group gap="xs">
      <TextInput size="xs" placeholder={placeholder} value={nom} onChange={(e) => setNom(e.currentTarget.value)} onKeyDown={(e) => e.key === "Enter" && ajouter()} />
      <Button size="xs" variant="light" leftSection={<Plus size={13} />} onClick={ajouter}>{libelle}</Button>
    </Group>
  );
}

/** Types de retours : plainte, suggestion, question… (liste libre). */
export function TypesRetour({ modifiable }: { modifiable: boolean }) {
  const { data: types = [] } = useTypesRetour();
  const sauver = useSauver<Partial<TypeRetour> & { id?: number }>(useEnregistrerTypeRetour());
  const supprimer = useSupprimerTypeRetour();
  return (
    <Stack gap="sm">
      <Text size="sm" c="dimmed">{voc("Les types de retours que l'organisation accepte. Un type désactivé n'est plus proposé, sans rien effacer.")}</Text>
      <Table withTableBorder verticalSpacing={4}>
        <Table.Thead>
          <Table.Tr>
            <Table.Th>{voc("Type")}</Table.Th>
            <Table.Th>{voc("Description")}</Table.Th>
            <Table.Th w={80}>{voc("Actif")}</Table.Th>
            {modifiable && <Table.Th w={50} />}
          </Table.Tr>
        </Table.Thead>
        <Table.Tbody>
          {types.map((t) => (
            <Table.Tr key={t.id}>
              <Table.Td><ChampTexte valeur={t.nom} modifiable={modifiable} onSauver={(nom) => sauver({ id: t.id, nom })} /></Table.Td>
              <Table.Td><ChampTexte valeur={t.description} modifiable={modifiable} onSauver={(description) => sauver({ id: t.id, description })} /></Table.Td>
              <Table.Td><Switch size="xs" checked={t.actif} disabled={!modifiable} aria-label={voc("Actif")} onChange={(e) => sauver({ id: t.id, actif: e.currentTarget.checked })} /></Table.Td>
              {modifiable && <Table.Td><BoutonSupprimer libelle={t.nom} onConfirmer={() => supprimer.mutateAsync(t.id)} /></Table.Td>}
            </Table.Tr>
          ))}
        </Table.Tbody>
      </Table>
      {modifiable && <Ajout placeholder={voc("Ex : Réclamation")} libelle={voc("Ajouter un type")} onAjouter={(nom) => sauver({ nom, ordre: types.length + 1 })} />}
    </Stack>
  );
}

/** Priorités et délais de traitement ; au moins une priorité urgente reste active. */
export function PrioritesPlainte({ modifiable }: { modifiable: boolean }) {
  const { data: priorites = [] } = usePrioritesPlainte();
  const sauver = useSauver<Partial<PrioritePlainte> & { id?: number }>(useEnregistrerPriorite());
  const supprimer = useSupprimerPriorite();
  return (
    <Stack gap="sm">
      <Text size="sm" c="dimmed">{voc("Une priorité urgente déclenche une notification immédiate et un traitement accéléré. Il en reste toujours au moins une.")}</Text>
      <Table withTableBorder verticalSpacing={4}>
        <Table.Thead>
          <Table.Tr>
            <Table.Th>{voc("Priorité")}</Table.Th>
            <Table.Th w={110}>{voc("Urgente")}</Table.Th>
            <Table.Th w={160}>{voc("Délai de traitement (jours)")}</Table.Th>
            <Table.Th w={80}>{voc("Active")}</Table.Th>
            {modifiable && <Table.Th w={50} />}
          </Table.Tr>
        </Table.Thead>
        <Table.Tbody>
          {priorites.map((p) => (
            <Table.Tr key={p.id}>
              <Table.Td>
                <Group gap={6} wrap="nowrap" w="100%">
                  {p.urgente && <Siren size={14} color="var(--mantine-color-red-7)" aria-hidden />}
                  <ChampTexte valeur={p.nom} modifiable={modifiable} onSauver={(nom) => sauver({ id: p.id, nom })} />
                </Group>
              </Table.Td>
              <Table.Td><Checkbox checked={p.urgente} disabled={!modifiable} label={p.urgente ? voc("Urgente") : undefined} onChange={(e) => sauver({ id: p.id, urgente: e.currentTarget.checked })} /></Table.Td>
              <Table.Td>
                {modifiable ? (
                  <NumberInput size="xs" min={0} value={p.delai_jours ?? ""} placeholder="—" onChange={(v) => sauver({ id: p.id, delai_jours: v === "" ? null : Number(v) })} />
                ) : p.delai_jours ?? "—"}
              </Table.Td>
              <Table.Td><Switch size="xs" checked={p.actif} disabled={!modifiable} aria-label={voc("Active")} onChange={(e) => sauver({ id: p.id, actif: e.currentTarget.checked })} /></Table.Td>
              {modifiable && <Table.Td><BoutonSupprimer libelle={p.nom} onConfirmer={() => supprimer.mutateAsync(p.id)} /></Table.Td>}
            </Table.Tr>
          ))}
        </Table.Tbody>
      </Table>
      {modifiable && <Ajout placeholder={voc("Ex : Basse")} libelle={voc("Ajouter une priorité")} onAjouter={(nom) => sauver({ nom, ordre: priorites.length + 1 })} />}
    </Stack>
  );
}

/** Ligne d'une catégorie ou d'une sous-catégorie. */
function LigneCategorie({ categorie, modifiable, onAjouterSous }: { categorie: CategoriePlainte; modifiable: boolean; onAjouterSous?: () => void }) {
  const sauver = useSauver<Partial<CategoriePlainte> & { id?: number }>(useEnregistrerCategorie());
  const supprimer = useSupprimerCategorie();
  const { data: circuits = [] } = useCircuitsPlainte();
  const sous = categorie.parent !== null;
  // Une catégorie sensible ne peut utiliser qu'un circuit confidentiel.
  const circuitsPossibles = circuits.filter((c) => !categorie.sensible_effective || c.sensible);
  return (
    <Table.Tr>
      <Table.Td>
        <Group gap={6} wrap="nowrap" pl={sous ? "lg" : 0} w="100%">
          {sous && <CornerDownRight size={13} color="var(--mantine-color-dimmed)" />}
          <ChampTexte valeur={categorie.nom} modifiable={modifiable} onSauver={(nom) => sauver({ id: categorie.id, nom })} />
        </Group>
      </Table.Td>
      <Table.Td w={150}>
        {categorie.verrouillee ? (
          <Tooltip label={VERROU} multiline w={240}>
            <Badge color="grape" variant="light" leftSection={<Lock size={11} />}>{voc("Sensible")}</Badge>
          </Tooltip>
        ) : sous && categorie.sensible_effective && !categorie.sensible ? (
          <Badge color="grape" variant="outline" leftSection={<ShieldAlert size={11} />}>{voc("Sensible (héritée)")}</Badge>
        ) : (
          <Checkbox
            checked={categorie.sensible}
            disabled={!modifiable}
            label={categorie.sensible ? voc("Sensible") : undefined}
            onChange={(e) => sauver({ id: categorie.id, sensible: e.currentTarget.checked })}
          />
        )}
      </Table.Td>
      <Table.Td w={230}>
        <Select
          size="xs"
          data={circuitsPossibles.map((c) => ({ value: String(c.id), label: c.nom }))}
          value={categorie.circuit ? String(categorie.circuit) : null}
          placeholder={voc("Circuit par défaut")}
          disabled={!modifiable}
          onChange={(v) => sauver({ id: categorie.id, circuit: v ? Number(v) : null })}
          clearable
        />
      </Table.Td>
      <Table.Td w={110}>
        {modifiable ? (
          <NumberInput size="xs" min={0} value={categorie.delai_jours ?? ""} placeholder="—" onChange={(v) => sauver({ id: categorie.id, delai_jours: v === "" ? null : Number(v) })} />
        ) : categorie.delai_jours ?? "—"}
      </Table.Td>
      <Table.Td w={70}>
        {categorie.verrouillee ? (
          <Tooltip label={VERROU} multiline w={240}><Lock size={14} aria-label={VERROU} /></Tooltip>
        ) : (
          <Switch size="xs" checked={categorie.actif} disabled={!modifiable} aria-label={voc("Active")} onChange={(e) => sauver({ id: categorie.id, actif: e.currentTarget.checked })} />
        )}
      </Table.Td>
      {modifiable && (
        <Table.Td w={70}>
          <Group gap={2} wrap="nowrap">
            {onAjouterSous && (
              <Tooltip label={voc("Ajouter une sous-catégorie")}>
                <ActionIcon size="sm" variant="subtle" onClick={onAjouterSous} aria-label={voc("Ajouter une sous-catégorie")}><Plus size={13} /></ActionIcon>
              </Tooltip>
            )}
            {!categorie.verrouillee && <BoutonSupprimer libelle={categorie.nom} onConfirmer={() => supprimer.mutateAsync(categorie.id)} />}
          </Group>
        </Table.Td>
      )}
    </Table.Tr>
  );
}

/** Catégories sur deux niveaux ; les catégories sensibles font passer le dossier dans le circuit confidentiel. */
export function CategoriesPlainte({ modifiable }: { modifiable: boolean }) {
  const { data: categories = [] } = useCategoriesPlainte();
  const enregistrer = useEnregistrerCategorie();
  const sauver = useSauver<Partial<CategoriePlainte> & { id?: number }>(enregistrer);
  const [sousDe, setSousDe] = useState<CategoriePlainte | null>(null);
  const principales = categories.filter((c) => c.parent === null);

  return (
    <Stack gap="sm">
      <Text size="sm" c="dimmed">
        {voc("Une catégorie sensible (abus, fraude, plainte visant le personnel…) fait passer le dossier dans le circuit confidentiel : seules les personnes désignées y ont accès. Les catégories liées à l'exploitation et aux abus sexuels restent toujours sensibles.")}
      </Text>
      <Table withTableBorder verticalSpacing={4}>
        <Table.Thead>
          <Table.Tr>
            <Table.Th>{voc("Catégorie")}</Table.Th>
            <Table.Th>{voc("Sensibilité")}</Table.Th>
            <Table.Th>{voc("Circuit")}</Table.Th>
            <Table.Th>{voc("Délai (jours)")}</Table.Th>
            <Table.Th>{voc("Active")}</Table.Th>
            {modifiable && <Table.Th />}
          </Table.Tr>
        </Table.Thead>
        <Table.Tbody>
          {principales.flatMap((p) => [
            <LigneCategorie key={p.id} categorie={p} modifiable={modifiable} onAjouterSous={() => setSousDe(p)} />,
            ...categories.filter((s) => s.parent === p.id).map((s) => <LigneCategorie key={s.id} categorie={s} modifiable={modifiable} />),
          ])}
        </Table.Tbody>
      </Table>
      {modifiable && (
        <Group gap="md" align="center">
          {sousDe ? (
            <Group gap="xs">
              <Text size="sm">{voc`Sous-catégorie de « ${sousDe.nom} » :`}</Text>
              <Ajout
                placeholder={voc("Nom de la sous-catégorie")}
                libelle={voc("Ajouter")}
                onAjouter={async (nom) => {
                  await sauver({ nom, parent: sousDe.id });
                  setSousDe(null);
                }}
              />
              <Button size="xs" variant="subtle" onClick={() => setSousDe(null)}>{voc("Annuler")}</Button>
            </Group>
          ) : (
            <Ajout placeholder={voc("Ex : Accès à l'eau")} libelle={voc("Ajouter une catégorie")} onAjouter={(nom) => sauver({ nom, ordre: principales.length + 1 })} />
          )}
        </Group>
      )}
    </Stack>
  );
}
