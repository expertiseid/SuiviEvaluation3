import { useState } from "react";
import { useSearchParams } from "react-router-dom";
import {
  Alert, Badge, Button, Card, Group, Loader, SegmentedControl, Select, SimpleGrid, Stack, Table, Text, Title,
} from "@mantine/core";
import { notifications } from "@mantine/notifications";
import { CircleCheck, CreditCard, Database, HardDrive, PackageOpen, Plus } from "lucide-react";
import { type PageStockage, acheterStockage, useEtatPaiementStockage, usePageStockage } from "../../api/console";
import { JaugeStockage } from "../../components/common/EspaceStockage";
import { StatCard } from "../../components/common/StatCard";
import { TitreRubrique } from "../../components/common/TitreRubrique";
import { messageErreurApi } from "../../utils/erreurs";
import { langue, locale } from "../../utils/i18n";
import { volumeLisible } from "../../utils/stockage";
import { voc } from "../../utils/vocabulaire";

/** « 30000 » → « 30 000 FCFA ». */
const somme = (n: number, devise: string) => `${n.toLocaleString("fr-FR")} ${devise === "XOF" ? "FCFA" : devise === "USD" ? "$" : devise}`;

const libelleDuree = (mois: number) => (mois % 12 === 0 ? (mois === 12 ? voc("1 an") : voc`${mois / 12} ans`) : voc`${mois} mois`);

/** Retour de la page de paiement de CinetPay (?paiement=…) : en attente, puis agrandi ou échoué. */
function RetourPaiement({ reference, fermer }: { reference: string; fermer: () => void }) {
  const { data: etat } = useEtatPaiementStockage(reference);
  if (!etat || etat.statut === "EN_ATTENTE") {
    return <Alert color="blue" icon={<Loader size={16} />}>{voc("Paiement en cours de confirmation… Cette page se met à jour toute seule.")}</Alert>;
  }
  if (etat.statut === "PAYE") {
    return (
      <Alert color="teal" icon={<CircleCheck size={18} />} withCloseButton onClose={fermer}>
        {voc`Paiement reçu : votre espace a été agrandi de ${etat.tranches * 10} Go.`}
      </Alert>
    );
  }
  return <Alert color="red" withCloseButton onClose={fermer}>{voc("Le paiement n'a pas abouti : votre espace n'a pas changé. Vous pouvez réessayer.")}</Alert>;
}

/** Augmenter l'espace : tranches de 10 Go, durée, mobile money (payé en ligne) ou carte (avec Expertise-ID). */
function Augmenter({ tarifs }: { tarifs: NonNullable<PageStockage["tarifs"]> }) {
  const [tranches, setTranches] = useState("1");
  const [mois, setMois] = useState("12");
  const [moyen, setMoyen] = useState<"mobile" | "carte">("mobile");
  const [envoi, setEnvoi] = useState(false);
  const [carteEnvoyee, setCarteEnvoyee] = useState(false);
  const carte = moyen === "carte";
  const montant = Number(tranches) * Number(mois) * (carte ? tarifs.tranche_usd : tarifs.tranche);

  const payer = async () => {
    setEnvoi(true);
    try {
      const reponse = await acheterStockage({ tranches: Number(tranches), mois: Number(mois), moyen, langue: langue() });
      if (reponse.lien) { window.location.href = reponse.lien; return; }
      setCarteEnvoyee(true);
    } catch (error) {
      notifications.show({ color: "red", message: messageErreurApi(error, voc("Le paiement n'a pas pu être préparé. Réessayez dans un moment.")) });
    }
    setEnvoi(false);
  };

  return (
    <Card withBorder radius="md" padding="lg">
      <Stack gap="md">
        <Group gap="xs"><Plus size={18} /><Title order={4}>{voc("Augmenter mon stockage")}</Title></Group>
        <Text size="sm" c="dimmed">
          {voc`Par tranche de 10 Go : ${somme(tarifs.tranche, tarifs.devise)} (${tarifs.tranche_usd} $) HT par mois. Votre espace est agrandi dès que le paiement est confirmé.`}
        </Text>
        <SegmentedControl value={moyen} onChange={(v) => { setMoyen(v as "mobile" | "carte"); setCarteEnvoyee(false); }} data={[
          { value: "mobile", label: voc("Mobile money (FCFA)") }, { value: "carte", label: voc("Carte bancaire (dollars)") },
        ]} />
        <Group grow align="flex-start">
          <Select label={voc("Stockage à ajouter")} value={tranches} onChange={(v) => setTranches(v ?? "1")} allowDeselect={false}
            data={Array.from({ length: tarifs.tranches_max }, (_, i) => ({ value: String(i + 1), label: voc`+ ${(i + 1) * 10} Go` }))} />
          <Select label={voc("Durée")} value={mois} onChange={(v) => setMois(v ?? "12")} allowDeselect={false}
            data={tarifs.durees.map((d) => ({ value: String(d), label: libelleDuree(d) }))} />
        </Group>
        <Group justify="space-between" align="center">
          <Text>{voc("Montant à payer (HT) :")} <Text span fw={700} size="lg">{carte ? `${montant.toLocaleString("fr-FR")} $` : somme(montant, tarifs.devise)}</Text></Text>
          <Button leftSection={carte ? <CreditCard size={16} /> : <HardDrive size={16} />} loading={envoi}
            disabled={!carte && !tarifs.paiement} onClick={payer}>
            {carte ? voc("Continuer avec la carte bancaire") : voc("Payer et agrandir mon espace")}
          </Button>
        </Group>
        {!carte && !tarifs.paiement && <Alert color="gray">{voc("Le paiement en ligne n'est pas disponible : contactez Expertise-ID.")}</Alert>}
        {carteEnvoyee && (
          <Alert color="teal" icon={<CircleCheck size={18} />}>
            {voc("Demande envoyée : notre équipe vous contacte au plus vite pour le paiement par carte bancaire. Votre espace sera agrandi dès le paiement reçu.")}
          </Alert>
        )}
      </Stack>
    </Card>
  );
}

/** Stockage : espace alloué à l'organisation, occupé, restant, et achat de stockage supplémentaire. */
export function StockagePage() {
  const { data: page, isLoading } = usePageStockage();
  const [parametres, setParametres] = useSearchParams();
  const reference = parametres.get("paiement");

  if (isLoading || !page) return <Loader />;
  const limite = page.limite ?? 0;
  const utilise = page.utilise ?? 0;
  const ajoute = page.limite_go && page.offre_go ? page.limite_go - page.offre_go : 0;

  return (
    <Stack gap="md">
      <TitreRubrique route="/stockage" defaut={voc("Stockage")} />
      {reference && <RetourPaiement reference={reference} fermer={() => setParametres({}, { replace: true })} />}

      {!page.limite ? (
        <Alert color="gray">{voc`Votre organisation n'a pas de limite de stockage. Espace occupé : ${volumeLisible(utilise)}.`}</Alert>
      ) : (
        <>
          <SimpleGrid cols={{ base: 1, sm: 3 }}>
            <StatCard label={voc("Espace alloué")} value={voc`${page.limite_go} Go`} icon={<HardDrive size={18} />} />
            <StatCard label={voc("Espace utilisé")} value={volumeLisible(utilise)} icon={<Database size={18} />} color="blue" />
            <StatCard label={voc("Espace disponible")} value={volumeLisible(Math.max(0, limite - utilise))} icon={<PackageOpen size={18} />}
              color={limite - utilise < 0.1 * limite ? "red" : "green"} />
          </SimpleGrid>
          <Card withBorder radius="md" padding="lg">
            <Stack gap="sm">
              <JaugeStockage espace={page} taille="lg" />
              <Text size="sm" c="dimmed">
                {page.offre_go ? voc`${page.offre_go} Go inclus dans votre offre` : ""}
                {ajoute > 0 ? voc` · ${ajoute} Go ajoutés` : ""}
                {ajoute < 0 ? voc` · ${-ajoute} Go en moins` : ""}
              </Text>
              <Text size="xs" c="dimmed">
                {voc("Compte les documents, images et pièces jointes de votre organisation, ainsi que ses données.")}
              </Text>
              {limite - utilise < 0.1 * limite && (
                <Alert color="orange" variant="light">{voc("Votre espace est presque plein : supprimez des fichiers inutiles ou augmentez votre stockage.")}</Alert>
              )}
            </Stack>
          </Card>
        </>
      )}

      {page.peut_acheter && page.tarifs && page.limite ? <Augmenter tarifs={page.tarifs} /> : null}
      {!page.peut_acheter && page.limite ? (
        <Text size="sm" c="dimmed">{voc("Pour augmenter le stockage, adressez-vous à l'administrateur de votre organisation.")}</Text>
      ) : null}

      {!!page.achats?.length && (
        <Card withBorder radius="md" padding="lg">
          <Stack gap="sm">
            <Title order={5}>{voc("Stockage acheté")}</Title>
            <Table striped>
              <Table.Thead>
                <Table.Tr><Table.Th>{voc("Date")}</Table.Th><Table.Th>{voc("Stockage")}</Table.Th><Table.Th>{voc("Durée")}</Table.Th><Table.Th>{voc("Montant")}</Table.Th></Table.Tr>
              </Table.Thead>
              <Table.Tbody>
                {page.achats.map((a, i) => (
                  <Table.Tr key={i}>
                    <Table.Td>{new Date(a.date).toLocaleDateString(locale())}</Table.Td>
                    <Table.Td><Badge variant="light">{voc`+ ${a.tranches * 10} Go`}</Badge></Table.Td>
                    <Table.Td>{libelleDuree(a.mois)}</Table.Td>
                    <Table.Td>{somme(a.montant, a.devise)}</Table.Td>
                  </Table.Tr>
                ))}
              </Table.Tbody>
            </Table>
          </Stack>
        </Card>
      )}
    </Stack>
  );
}
