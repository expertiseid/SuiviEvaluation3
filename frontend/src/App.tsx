import { Suspense } from "react";
import { Center, Loader } from "@mantine/core";
import { Navigate, Route, Routes } from "react-router-dom";
import { RequireAuth } from "./auth/RequireAuth";
import { ACCUEIL_APP } from "./utils/accueil";
import { aLaDemande } from "./utils/aLaDemande";

// Pages chargées à la demande : une page (lien partagé, formulaire public…) ne télécharge que son propre code.
const AppLayout = aLaDemande(() => import("./layouts/AppLayout").then((m) => ({ default: m.AppLayout })));
const LoginPage = aLaDemande(() => import("./auth/LoginPage").then((m) => ({ default: m.LoginPage })));
const NouveauMotDePassePage = aLaDemande(() => import("./auth/NouveauMotDePassePage").then((m) => ({ default: m.NouveauMotDePassePage })));
const AbonnementPage = aLaDemande(() => import("./pages/accueil/AbonnementPage").then((m) => ({ default: m.AbonnementPage })));
const MonAbonnementPage = aLaDemande(() => import("./pages/abonnement/MonAbonnementPage").then((m) => ({ default: m.MonAbonnementPage })));
const AccueilPage = aLaDemande(() => import("./pages/accueil/AccueilPage").then((m) => ({ default: m.AccueilPage })));
const AProposPage = aLaDemande(() => import("./pages/accueil/AProposPage").then((m) => ({ default: m.AProposPage })));
const InscriptionPage = aLaDemande(() => import("./pages/accueil/InscriptionPage").then((m) => ({ default: m.InscriptionPage })));
const ConsolePage = aLaDemande(() => import("./pages/console/ConsolePage").then((m) => ({ default: m.ConsolePage })));
const DashboardConsolidePage = aLaDemande(() => import("./pages/DashboardConsolidePage").then((m) => ({ default: m.DashboardConsolidePage })));
const ProjetsListPage = aLaDemande(() => import("./pages/projets/ProjetsListPage").then((m) => ({ default: m.ProjetsListPage })));
const ProjetDetailPage = aLaDemande(() => import("./pages/projets/ProjetDetailPage").then((m) => ({ default: m.ProjetDetailPage })));
const IndicateursListPage = aLaDemande(() => import("./pages/indicateurs/IndicateursListPage").then((m) => ({ default: m.IndicateursListPage })));
const EnquetesPage = aLaDemande(() => import("./pages/indicateurs/EnquetesPage").then((m) => ({ default: m.EnquetesPage })));
const IndicateurDetailPage = aLaDemande(() => import("./pages/indicateurs/IndicateurDetailPage").then((m) => ({ default: m.IndicateurDetailPage })));
const SuiviPage = aLaDemande(() => import("./pages/suivi/SuiviPage").then((m) => ({ default: m.SuiviPage })));
const SuiviProjetDashboard = aLaDemande(() => import("./pages/suivi/SuiviProjetDashboard").then((m) => ({ default: m.SuiviProjetDashboard })));
const BeneficiairesListPage = aLaDemande(() => import("./pages/beneficiaires/BeneficiairesListPage").then((m) => ({ default: m.BeneficiairesListPage })));
const BeneficiaireDetailPage = aLaDemande(() => import("./pages/beneficiaires/BeneficiaireDetailPage").then((m) => ({ default: m.BeneficiaireDetailPage })));
const DoublonsPage = aLaDemande(() => import("./pages/beneficiaires/DoublonsPage").then((m) => ({ default: m.DoublonsPage })));
const UtilisateursPage = aLaDemande(() => import("./pages/utilisateurs/UtilisateursPage").then((m) => ({ default: m.UtilisateursPage })));
const CadresStrategiquesListPage = aLaDemande(() => import("./pages/strategie/CadresStrategiquesListPage").then((m) => ({ default: m.CadresStrategiquesListPage })));
const OrganisationPage = aLaDemande(() => import("./pages/organisation/OrganisationPage").then((m) => ({ default: m.OrganisationPage })));
const BeneficiaireParIdentifiant = aLaDemande(() => import("./pages/beneficiaires/BeneficiaireParIdentifiant").then((m) => ({ default: m.BeneficiaireParIdentifiant })));
const CartePage = aLaDemande(() => import("./pages/carte/CartePage").then((m) => ({ default: m.CartePage })));
const ApprobationsPage = aLaDemande(() => import("./pages/approbations/ApprobationsPage").then((m) => ({ default: m.ApprobationsPage })));
const CadreStrategiqueDetailPage = aLaDemande(() => import("./pages/strategie/CadreStrategiqueDetailPage").then((m) => ({ default: m.CadreStrategiqueDetailPage })));
const ZonesAdministrativesPage = aLaDemande(() => import("./pages/geo/ZonesAdministrativesPage").then((m) => ({ default: m.ZonesAdministrativesPage })));
const PlanificationImportPage = aLaDemande(() => import("./pages/planification/PlanificationImportPage").then((m) => ({ default: m.PlanificationImportPage })));
const DocumentsGlobauxPage = aLaDemande(() => import("./pages/documents/DocumentsGlobauxPage").then((m) => ({ default: m.DocumentsGlobauxPage })));
const CorbeillePage = aLaDemande(() => import("./pages/documents/CorbeillePage").then((m) => ({ default: m.CorbeillePage })));
const LanguesPage = aLaDemande(() => import("./pages/langues/LanguesPage").then((m) => ({ default: m.LanguesPage })));
const StockagePage = aLaDemande(() => import("./pages/stockage/StockagePage").then((m) => ({ default: m.StockagePage })));
const JournalAuditPage = aLaDemande(() => import("./pages/journal-audit/JournalAuditPage").then((m) => ({ default: m.JournalAuditPage })));
const ParametresAlertePage = aLaDemande(() => import("./pages/parametres/ParametresAlertePage").then((m) => ({ default: m.ParametresAlertePage })));
const PagePartagee = aLaDemande(() => import("./pages/partage/PagePartagee").then((m) => ({ default: m.PagePartagee })));
const DocumentPartagePage = aLaDemande(() => import("./pages/documents/DocumentPartagePage").then((m) => ({ default: m.DocumentPartagePage })));
const FormationPage = aLaDemande(() => import("./pages/formation/FormationPage").then((m) => ({ default: m.FormationPage })));
const LeconPage = aLaDemande(() => import("./pages/formation/FormationPage").then((m) => ({ default: m.LeconPage })));
const QuizPage = aLaDemande(() => import("./pages/formation/FormationPage").then((m) => ({ default: m.QuizPage })));
const ActionsCorrectivesPage = aLaDemande(() => import("./pages/plaintes/ActionsCorrectivesPage").then((m) => ({ default: m.ActionsCorrectivesPage })));
const DossierPlaintePage = aLaDemande(() => import("./pages/plaintes/DossierPlaintePage").then((m) => ({ default: m.DossierPlaintePage })));
const DossiersPlaintesPage = aLaDemande(() => import("./pages/plaintes/DossiersPlaintesPage").then((m) => ({ default: m.DossiersPlaintesPage })));
const ParametragePlaintesPage = aLaDemande(() => import("./pages/plaintes/ParametragePlaintesPage").then((m) => ({ default: m.ParametragePlaintesPage })));
const FormulairePublicPage = aLaDemande(() => import("./pages/plaintes/public/FormulairePublicPage").then((m) => ({ default: m.FormulairePublicPage })));
const SuiviPublicPage = aLaDemande(() => import("./pages/plaintes/public/SuiviPublicPage").then((m) => ({ default: m.SuiviPublicPage })));
const TableauPlaintesPage = aLaDemande(() => import("./pages/plaintes/TableauPlaintesPage").then((m) => ({ default: m.TableauPlaintesPage })));

export default function App() {
  return (
    <Suspense fallback={<Center h="60vh"><Loader /></Center>}>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route path="/nouveau-mot-de-passe" element={<NouveauMotDePassePage />} />
        {/* Connexion à part des opérateurs Expertise-ID (console de la plateforme multi-organisations). */}
        <Route path="/expertise-id" element={<LoginPage operateur />} />
        {/* Vitrine publique : accueil, création du profil d'une organisation, abonnement, à propos. */}
        <Route path="/accueil" element={<AccueilPage />} />
        <Route path="/inscription" element={<InscriptionPage />} />
        <Route path="/abonnement" element={<AbonnementPage />} />
        {/* Abonnement de l'organisation : hors du menu, pour rester ouvert quand l'accès est bloqué. */}
        <Route path="/mon-abonnement" element={<RequireAuth><MonAbonnementPage /></RequireAuth>} />
        <Route path="/a-propos" element={<AProposPage />} />
        {/* Console Expertise-ID (plateforme multi-organisations). */}
        <Route path="/console" element={<RequireAuth><ConsolePage /></RequireAuth>} />
        {/* Lien de partage public : hors connexion, en lecture seule. */}
        <Route path="/partage/:jeton" element={<PagePartagee />} />
        {/* Document partagé par lien : sans compte, jusqu'à l'expiration du lien. */}
        <Route path="/document/:jeton" element={<DocumentPartagePage />} />
        {/* Formulaire public des plaintes et suivi par code : sans compte. */}
        <Route path="/plainte" element={<FormulairePublicPage />} />
        <Route path="/plainte/suivi" element={<SuiviPublicPage />} />
        <Route
          element={
            <RequireAuth>
              <AppLayout />
            </RequireAuth>
          }
        >
          <Route path="/" element={<Navigate to={ACCUEIL_APP} replace />} />
          <Route path={ACCUEIL_APP} element={<DashboardConsolidePage />} />
          <Route path="/projets" element={<ProjetsListPage />} />
          <Route path="/projets/:id" element={<ProjetDetailPage />} />
          <Route path="/indicateurs" element={<IndicateursListPage />} />
          <Route path="/indicateurs/enquetes" element={<EnquetesPage />} />
          <Route path="/indicateurs/:id" element={<IndicateurDetailPage />} />
          <Route path="/suivi" element={<SuiviPage />} />
          <Route path="/suivi/:id" element={<SuiviProjetDashboard />} />
          <Route path="/beneficiaires" element={<BeneficiairesListPage />} />
          <Route path="/beneficiaires/identifiant/:identifiant" element={<BeneficiaireParIdentifiant />} />
          <Route path="/carte" element={<CartePage />} />
          <Route path="/beneficiaires/carte" element={<Navigate to="/carte" replace />} />
          <Route path="/beneficiaires/:id" element={<BeneficiaireDetailPage />} />
          <Route path="/doublons" element={<DoublonsPage />} />
          <Route path="/approbations" element={<ApprobationsPage />} />
          <Route path="/strategie" element={<CadresStrategiquesListPage />} />
          <Route path="/strategie/:id" element={<CadreStrategiqueDetailPage />} />
          <Route path="/strategie/type/:typeId" element={<CadresStrategiquesListPage />} />
          <Route path="/strategie/type/:typeId/:id" element={<CadreStrategiqueDetailPage />} />
          <Route path="/zones-administratives" element={<ZonesAdministrativesPage />} />
          <Route path="/planification" element={<PlanificationImportPage />} />
          <Route path="/documents" element={<DocumentsGlobauxPage />} />
          <Route path="/formation" element={<FormationPage />} />
          <Route path="/formation/:module/quiz" element={<QuizPage />} />
          <Route path="/formation/:module/:lecon" element={<LeconPage />} />
          <Route path="/corbeille" element={<CorbeillePage />} />
          <Route path="/plaintes" element={<DossiersPlaintesPage />} />
          <Route path="/plaintes/parametrage" element={<ParametragePlaintesPage />} />
          <Route path="/plaintes/dossiers/:id" element={<DossierPlaintePage />} />
          <Route path="/plaintes/tableau-de-bord" element={<TableauPlaintesPage />} />
          <Route path="/plaintes/actions-correctives" element={<ActionsCorrectivesPage />} />
          <Route
            path="/organisation"
            element={
              <RequireAuth roles={["ADMIN"]}>
                <OrganisationPage />
              </RequireAuth>
            }
          />
          <Route
            path="/utilisateurs"
            element={
              <RequireAuth roles={["ADMIN"]}>
                <UtilisateursPage />
              </RequireAuth>
            }
          />
          <Route
            path="/journal-audit"
            element={
              <RequireAuth roles={["ADMIN"]}>
                <JournalAuditPage />
              </RequireAuth>
            }
          />
          <Route
            path="/stockage"
            element={
              <RequireAuth roles={["ADMIN"]}>
                <StockagePage />
              </RequireAuth>
            }
          />
          <Route
            path="/langues"
            element={
              <RequireAuth roles={["ADMIN"]}>
                <LanguesPage />
              </RequireAuth>
            }
          />
          <Route
            path="/parametres-alerte"
            element={
              <RequireAuth roles={["ADMIN"]}>
                <ParametresAlertePage />
              </RequireAuth>
            }
          />
        </Route>
      </Routes>
    </Suspense>
  );
}
