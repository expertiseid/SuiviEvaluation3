import type { ReactNode } from "react";
import { Navigate, useLocation } from "react-router-dom";
import { Center, Loader } from "@mantine/core";
import { useIdentiteOrganisation } from "../api/identite";
import { useAuth } from "./useAuth";
import type { Role } from "../types";

export function RequireAuth({ children, roles }: { children: ReactNode; roles?: Role[] }) {
  const { user, loading } = useAuth();
  const { pathname } = useLocation();
  const { data: plateforme, isLoading: chargementPlateforme } = useIdentiteOrganisation();

  if (loading || chargementPlateforme) {
    return (
      <Center h="100vh">
        <Loader />
      </Center>
    );
  }

  if (!user) {
    // Page d'accueil à l'adresse de la plateforme ; la console renvoie à la connexion Expertise-ID.
    if (pathname === "/console") return <Navigate to="/expertise-id" replace />;
    return <Navigate to={pathname === "/" ? "/accueil" : "/login"} replace />;
  }

  // Plateforme multi-organisations : les opérateurs Expertise-ID n'ont que la console ; les comptes
  // des organisations n'y ont pas accès.
  if (plateforme?.multi_organisations) {
    if (user.est_operateur && pathname !== "/console") return <Navigate to="/console" replace />;
    if (!user.est_operateur && pathname === "/console") return <Navigate to="/" replace />;
  }

  if (roles && !roles.includes(user.role)) {
    return <Navigate to="/" replace />;
  }

  return <>{children}</>;
}
