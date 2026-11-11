import { Navigate, Route, Routes } from "react-router-dom";
import { AppLayout } from "./layouts/AppLayout";
import { RequireAuth } from "./auth/RequireAuth";
import { LoginPage } from "./auth/LoginPage";
import { NouveauMotDePassePage } from "./auth/NouveauMotDePassePage";
import { AbonnementPage } from "./pages/accueil/AbonnementPage";
import { MonAbonnementPage } from "./pages/abonnement/MonAbonnementPage";
import { AccueilPage } from "./pages/accueil/AccueilPage";
import { AProposPage } from "./pages/accueil/AProposPage";
import { InscriptionPage } from "./pages/accueil/InscriptionPage";
import { ConsolePage } from "./pages/console/ConsolePage";
import { DashboardConsolidePage } from "./pages/DashboardConsolidePage";
import { ProjetsListPage } from "./pages/projets/ProjetsListPage";
import { ProjetDetailPage } from "./pages/projets/ProjetDetailPage";
import { IndicateursListPage } from "./pages/indicateurs/IndicateursListPage";
import { IndicateurDetailPage } from "./pages/indicateurs/IndicateurDetailPage";
import { SuiviPage } from "./pages/suivi/SuiviPage";
import { SuiviProjetDashboard } from "./pages/suivi/SuiviProjetDashboard";
import { BeneficiairesListPage } from "./pages/beneficiaires/BeneficiairesListPage";
import { BeneficiaireDetailPage } from "./pages/beneficiaires/BeneficiaireDetailPage";
import { DoublonsPage } from "./pages/beneficiaires/DoublonsPage";
import { UtilisateursPage } from "./pages/utilisateurs/UtilisateursPage";
import { CadresStrategiquesListPage } from "./pages/strategie/CadresStrategiquesListPage";
import { OrganisationPage } from "./pages/organisation/OrganisationPage";
import { BeneficiaireParIdentifiant } from "./pages/beneficiaires/BeneficiaireParIdentifiant";
import { CartePage } from "./pages/carte/CartePage";
import { ApprobationsPage } from "./pages/approbations/ApprobationsPage";
import { CadreStrategiqueDetailPage } from "./pages/strategie/CadreStrategiqueDetailPage";
import { ZonesAdministrativesPage } from "./pages/geo/ZonesAdministrativesPage";
import { PlanificationImportPage } from "./pages/planification/PlanificationImportPage";
import { DocumentsGlobauxPage } from "./pages/documents/DocumentsGlobauxPage";
import { CorbeillePage } from "./pages/documents/CorbeillePage";
import { LanguesPage } from "./pages/langues/LanguesPage";
import { StockagePage } from "./pages/stockage/StockagePage";
import { JournalAuditPage } from "./pages/journal-audit/JournalAuditPage";
import { ParametresAlertePage } from "./pages/parametres/ParametresAlertePage";
import { PagePartagee } from "./pages/partage/PagePartagee";
import { DocumentPartagePage } from "./pages/documents/DocumentPartagePage";
import { FormationPage, LeconPage, QuizPage } from "./pages/formation/FormationPage";
import { ActionsCorrectivesPage } from "./pages/plaintes/ActionsCorrectivesPage";
import { DossierPlaintePage } from "./pages/plaintes/DossierPlaintePage";
import { DossiersPlaintesPage } from "./pages/plaintes/DossiersPlaintesPage";
import { ParametragePlaintesPage } from "./pages/plaintes/ParametragePlaintesPage";
import { FormulairePublicPage } from "./pages/plaintes/public/FormulairePublicPage";
import { SuiviPublicPage } from "./pages/plaintes/public/SuiviPublicPage";
import { TableauPlaintesPage } from "./pages/plaintes/TableauPlaintesPage";

export default function App() {
  return (
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
        <Route path="/" element={<DashboardConsolidePage />} />
        <Route path="/projets" element={<ProjetsListPage />} />
        <Route path="/projets/:id" element={<ProjetDetailPage />} />
        <Route path="/indicateurs" element={<IndicateursListPage />} />
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
  );
}
