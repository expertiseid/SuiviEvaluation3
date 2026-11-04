import { useContext } from "react";
import { AuthContext } from "./AuthContext";

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth doit être utilisé dans un AuthProvider");
  return ctx;
}

/** Visiteur de la démonstration : les enregistrements sont simulés (sans erreur hors connexion). */
export function useEstDemo() {
  return !!useContext(AuthContext)?.user?.est_demo;
}
