import { Navigate, Route, Routes } from "react-router-dom";
import { AppLayout } from "./layouts/AppLayout";
import { RequireAuth } from "./auth/RequireAuth";
import { LoginPage } from "./auth/LoginPage";
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
import { LanguesPage } from "./pages/langues/LanguesPage";
import { ParametresAlertePage } from "./pages/parametres/ParametresAlertePage";
import { PagePartagee } from "./pages/partage/PagePartagee";
import { PlaintesPage } from "./pages/plaintes/PlaintesPage";

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      {/* Lien de partage public : hors connexion, en lecture seule. */}
      <Route path="/partage/:jeton" element={<PagePartagee />} />
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
        <Route path="/plaintes" element={<PlaintesPage />} />
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
