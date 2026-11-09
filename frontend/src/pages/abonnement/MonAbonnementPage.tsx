import { useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import {
  Alert, Badge, Box, Button, Card, Container, Divider, Group, Loader, SegmentedControl, Select, Stack, Table, Text, Title,
} from "@mantine/core";
import { notifications } from "@mantine/notifications";
import { ArrowLeft, CalendarClock, CircleCheck, CreditCard, LogOut, RefreshCw } from "lucide-react";
import {
  type PageAbonnement, type StatutAbonnement, payerAbonnement, useAbonnement, useDevisAbonnement, useEtatPaiementAbonnement,
} from "../../api/console";
import { useAuth } from "../../auth/useAuth";
import { LogoPlateforme, PiedDePage } from "../../components/common/Logos";
import { messageErreurApi } from "../../utils/erreurs";
import { langue, locale } from "../../utils/i18n";
import { voc } from "../../utils/vocabulaire";

const somme = (n: number, devise = "XOF") => `${n.toLocaleString("fr-FR")} ${devise === "XOF" ? "FCFA" : devise}`;
const jour = (d: string | null | undefined) => (d ? new Date(`${d}T12:00:00`).toLocaleDateString(locale(), { day: "numeric", month: "long", year: "numeric" }) : "—");
const libelleDuree = (mois: number) => (mois % 12 === 0 ? (mois === 12 ? voc("1 an") : voc`${mois / 12} ans`) : voc`${mois} mois`);

const STATUTS: Record<StatutAbonnement, { couleur: string; libelle: string }> = {
  ACTIF: { couleur: "teal", libelle: "Actif" },
  BIENTOT: { couleur: "yellow", libelle: "Se termine bientôt" },
  GRACE: { couleur: "orange", libelle: "Terminé : à renouveler" },
  BLOQUE: { couleur: "red", libelle: "Accès bloqué" },
  SANS_ECHEANCE: { couleur: "gray", libelle: "Sans échéance" },
};

/** Retour de la page de paiement de CinetPay (?paiement=…). */
function RetourPaiement({ reference, fermer }: { reference: string; fermer: () => void }) {
  const { data: etat } = useEtatPaiementAbonnement(reference);
  if (!etat || etat.statut === "EN_ATTENTE") {
    return <Alert color="blue" icon={<Loader size={16} />}>{voc("Paiement en cours de confirmation… Cette page se met à jour toute seule.")}</Alert>;
  }
  if (etat.statut === "PAYE") {
    return (
      <Alert color="teal" icon={<CircleCheck size={18} />} withCloseButton onClose={fermer}>
        {voc`Paiement reçu : votre abonnement court maintenant jusqu'au ${jour(etat.fin)}.`}
      </Alert>
    );
  }
  return <Alert color="red" withCloseButton onClose={fermer}>{voc("Le paiement n'a pas abouti : votre abonnement n'a pas changé. Vous pouvez réessayer.")}</Alert>;
}

function Etat({ page }: { page: PageAbonnement }) {
  const statut = STATUTS[page.statut];
  return (
    <Card withBorder radius="md" padding="lg">
      <Group justify="space-between" align="flex-start" mb="sm">
        <Box>
          <Text size="sm" c="dimmed">{voc("Votre offre")}</Text>
          <Title order={3}>{page.offre_libelle || "—"}</Title>
        </Box>
        <Badge size="lg" variant="light" color={statut.couleur}>{voc(statut.libelle)}</Badge>
      </Group>
      {page.fin && (
        <Group gap="xs" mb="sm">
          <CalendarClock size={18} />
          <Text>{page.statut === "GRACE" || page.statut === "BLOQUE" ? voc`Terminé le ${jour(page.fin)}` : voc`Payé jusqu'au ${jour(page.fin)}`}</Text>
          {page.statut === "ACTIF" || page.statut === "BIENTOT" ? <Text c="dimmed">{voc`(${page.jours_restants} jours restants)`}</Text> : null}
        </Group>
      )}
      {page.statut === "BIENTOT" && (
        <Alert color="yellow" variant="light">{voc`Votre abonnement se termine dans ${page.jours_restants} jours. Renouvelez-le pour continuer sans interruption.`}</Alert>
      )}
      {page.statut === "GRACE" && (
        <Alert color="orange" variant="light">
          {voc`Votre abonnement est terminé. Vous gardez l'accès jusqu'au ${jour(page.fin_grace)} : après cette date, l'accès sera bloqué jusqu'au renouvellement.`}
        </Alert>
      )}
      {page.statut === "BLOQUE" && (
        <Alert color="red" variant="light">
          {voc("L'accès à la plateforme est bloqué. Vos données sont conservées : l'accès est rétabli dès le paiement.")}
        </Alert>
      )}
      {page.statut === "SANS_ECHEANCE" && <Text size="sm" c="dimmed">{voc("Votre abonnement n'a pas de date de fin.")}</Text>}
    </Card>
  );
}

function Payer({ page }: { page: PageAbonnement }) {
  const offres = page.offres ?? [];
  const [offre, setOffre] = useState<string>(page.renouvelable && page.offre ? page.offre : offres[0]?.offre ?? "");
  const [mois, setMois] = useState("12");
  const [moyen, setMoyen] = useState<"mobile" | "carte">("mobile");
  const [envoi, setEnvoi] = useState(false);
  const [carteEnvoyee, setCarteEnvoyee] = useState(false);
  const { data: devis, isFetching } = useDevisAbonnement(offre || null, Number(mois));
  const carte = moyen === "carte";
  const choisie = offres.find((o) => o.offre === offre);
  const prixUsd = choisie ? choisie.prix_mois_usd * Number(mois) : 0;
  const deductionUsd = devis && devis.prix ? Math.round((prixUsd * devis.deduction) / devis.prix) : 0;

  const choixOffres = [
    ...(page.renouvelable && page.offre && !offres.some((o) => o.offre === page.offre)
      ? [{ value: page.offre, label: voc`${page.offre_libelle ?? ""} (offre actuelle)` }] : []),
    ...offres.map((o) => ({
      value: o.offre,
      label: o.offre === page.offre ? voc`${o.libelle} (offre actuelle)` : `${o.libelle} · ${carte ? `${o.prix_mois_usd} $` : somme(o.prix_mois, page.devise)} ${voc("par mois")}`,
    })),
  ];

  const payer = async () => {
    setEnvoi(true);
    try {
      const reponse = await payerAbonnement({ offre, mois: Number(mois), moyen, langue: langue() });
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
        <Group gap="xs"><RefreshCw size={18} /><Title order={4}>{voc("Renouveler ou changer d'offre")}</Title></Group>
        <Text size="sm" c="dimmed">
          {voc("Même offre : la nouvelle période s'ajoute à la fin de l'actuelle. Autre offre : elle commence aujourd'hui, et ce qui reste de votre abonnement actuel est déduit du prix.")}
        </Text>
        <SegmentedControl value={moyen} onChange={(v) => { setMoyen(v as "mobile" | "carte"); setCarteEnvoyee(false); }} data={[
          { value: "mobile", label: voc("Mobile money (FCFA)") }, { value: "carte", label: voc("Carte bancaire (dollars)") },
        ]} />
        <Group grow align="flex-start">
          <Select label={voc("Offre")} value={offre} onChange={(v) => setOffre(v ?? offre)} allowDeselect={false} data={choixOffres} />
          <Select label={voc("Durée")} value={mois} onChange={(v) => setMois(v ?? "12")} allowDeselect={false}
            data={(page.durees ?? [1, 3, 6, 12]).map((d) => ({ value: String(d), label: libelleDuree(d) }))} />
        </Group>
        {devis && (
          <Card bg="gray.0" radius="md" padding="md">
            <Stack gap={6}>
              <Group justify="space-between"><Text size="sm">{voc("Prix")}</Text><Text size="sm">{carte ? `${prixUsd} $` : somme(devis.prix, page.devise)}</Text></Group>
              {devis.deduction > 0 && (
                <Group justify="space-between">
                  <Text size="sm">{voc`Déduction : ce qui reste de votre abonnement (${devis.jours_restants} jours)`}</Text>
                  <Text size="sm" c="teal.8">− {carte ? `${deductionUsd} $` : somme(devis.deduction, page.devise)}</Text>
                </Group>
              )}
              <Divider />
              <Group justify="space-between">
                <Text fw={700}>{voc("À payer (HT)")}</Text>
                <Text fw={700} size="lg">{carte ? `${prixUsd - deductionUsd} $` : somme(devis.a_payer, page.devise)}</Text>
              </Group>
              <Text size="xs" c="dimmed">{voc`Nouvelle échéance : ${jour(devis.nouvelle_fin)}`}</Text>
            </Stack>
          </Card>
        )}
        {devis && !devis.possible && (
          <Alert color="yellow" variant="light">{voc("Ce qui reste de votre abonnement couvre déjà presque tout ce montant : choisissez une durée plus longue.")}</Alert>
        )}
        <Group justify="flex-end">
          <Button leftSection={carte ? <CreditCard size={16} /> : <RefreshCw size={16} />} loading={envoi || isFetching}
            disabled={!devis || !devis.possible || (!carte && !page.paiement)} onClick={payer}>
            {carte ? voc("Continuer avec la carte bancaire") : voc("Payer")}
          </Button>
        </Group>
        {!carte && !page.paiement && <Alert color="gray">{voc("Le paiement en ligne n'est pas disponible : contactez Expertise-ID.")}</Alert>}
        {carteEnvoyee && (
          <Alert color="teal" icon={<CircleCheck size={18} />}>
            {voc("Demande envoyée : notre équipe vous contacte au plus vite pour le paiement par carte bancaire. Votre abonnement sera prolongé dès le paiement reçu.")}
          </Alert>
        )}
      </Stack>
    </Card>
  );
}

/**
 * Abonnement de l'organisation : échéance, renouvellement, changement d'offre. Page à part (sans le menu) :
 * elle reste ouverte quand l'accès est bloqué, pour pouvoir payer.
 */
export function MonAbonnementPage() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const { data: page, isLoading } = useAbonnement();
  const [parametres, setParametres] = useSearchParams();
  const reference = parametres.get("paiement");

  return (
    <Box bg="gray.0" mih="100vh" style={{ display: "flex", flexDirection: "column" }}>
      <Box bg="teal.9" c="white">
        <Container size="md" py="sm">
          <Group justify="space-between" wrap="nowrap">
            <LogoPlateforme taille={30} clair />
            <Button size="xs" variant="subtle" color="gray.0" leftSection={<LogOut size={14} />} onClick={() => { logout(); navigate("/login"); }}>
              {voc("Déconnexion")}
            </Button>
          </Group>
        </Container>
      </Box>
      <Container size="md" py="lg" style={{ flex: 1, width: "100%" }}>
        <Stack gap="md">
          {page && page.statut !== "BLOQUE" && (
            <Box><Button component={Link} to="/" variant="subtle" leftSection={<ArrowLeft size={16} />} px={0}>{voc("Retour à la plateforme")}</Button></Box>
          )}
          <Title order={2}>{voc("Abonnement")}</Title>
          {reference && <RetourPaiement reference={reference} fermer={() => setParametres({}, { replace: true })} />}
          {isLoading || !page ? <Loader /> : (
            <>
              <Etat page={page} />
              {page.peut_payer ? (page.statut !== "SANS_ECHEANCE" || page.renouvelable) && <Payer page={page} /> : (
                <Alert color="gray">{voc`Seul l'administrateur de votre organisation peut renouveler l'abonnement. Compte connecté : ${user?.email ?? ""}.`}</Alert>
              )}
              {!!page.paiements?.length && (
                <Card withBorder radius="md" padding="lg">
                  <Title order={5} mb="sm">{voc("Paiements de l'abonnement")}</Title>
                  <Table.ScrollContainer minWidth={520}>
                    <Table striped>
                      <Table.Thead>
                        <Table.Tr><Table.Th>{voc("Date")}</Table.Th><Table.Th>{voc("Offre")}</Table.Th><Table.Th>{voc("Durée")}</Table.Th><Table.Th>{voc("Montant")}</Table.Th></Table.Tr>
                      </Table.Thead>
                      <Table.Tbody>
                        {page.paiements.map((p, i) => (
                          <Table.Tr key={i}>
                            <Table.Td>{p.date ? new Date(p.date).toLocaleDateString(locale()) : "—"}</Table.Td>
                            <Table.Td>{p.offre_libelle}</Table.Td>
                            <Table.Td>{libelleDuree(p.mois)}</Table.Td>
                            <Table.Td>
                              {somme(p.montant, p.devise)}
                              {p.deduction > 0 && <Text size="xs" c="dimmed">{voc`après déduction de ${somme(p.deduction, p.devise)}`}</Text>}
                            </Table.Td>
                          </Table.Tr>
                        ))}
                      </Table.Tbody>
                    </Table>
                  </Table.ScrollContainer>
                </Card>
              )}
            </>
          )}
        </Stack>
      </Container>
      <PiedDePage />
    </Box>
  );
}
