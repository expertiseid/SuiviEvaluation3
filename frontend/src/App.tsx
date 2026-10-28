import { Route, Routes } from "react-router-dom";
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
import { CarteBeneficiairesPage } from "./pages/beneficiaires/CarteBeneficiairesPage";
import { ApprobationsPage } from "./pages/approbations/ApprobationsPage";
import { CadreStrategiqueDetailPage } from "./pages/strategie/CadreStrategiqueDetailPage";
import { ZonesAdministrativesPage } from "./pages/geo/ZonesAdministrativesPage";
import { PlanificationImportPage } from "./pages/planification/PlanificationImportPage";
import { DocumentsGlobauxPage } from "./pages/documents/DocumentsGlobauxPage";
import { ParametresAlertePage } from "./pages/parametres/ParametresAlertePage";

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
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
        <Route path="/beneficiaires/carte" element={<CarteBeneficiairesPage />} />
        <Route path="/beneficiaires/:id" element={<BeneficiaireDetailPage />} />
        <Route path="/doublons" element={<DoublonsPage />} />
        <Route path="/approbations" element={<ApprobationsPage />} />
        <Route path="/strategie" element={<CadresStrategiquesListPage />} />
        <Route path="/strategie/:id" element={<CadreStrategiqueDetailPage />} />
        <Route path="/zones-administratives" element={<ZonesAdministrativesPage />} />
        <Route path="/planification" element={<PlanificationImportPage />} />
        <Route path="/documents" element={<DocumentsGlobauxPage />} />
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
