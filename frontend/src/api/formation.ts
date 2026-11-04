/** Cours en ligne (apps.formation) : sommaire, leçons, quiz, attestation. */
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiClient } from "./client";

export interface LeconResume { code: string; titre: string; duree: number; terminee: boolean }
export interface ModuleFormation {
  code: string;
  titre: string;
  description: string;
  icone: string;
  /** Liste des leçons (accès ouvert) ou leur nombre (démonstration). */
  lecons: LeconResume[] | number;
  quiz?: { questions: number; seuil: number; reussi: boolean; meilleur: number | null };
}
export interface SommaireFormation {
  acces: boolean;
  modules: ModuleFormation[];
  progression?: number;
  attestation?: { numero: string; date: string } | null;
  attestation_possible?: boolean;
}

export type Bloc =
  | { type: "texte" | "astuce" | "attention"; texte: string }
  | { type: "etapes" | "exercice"; items: string[] }
  | { type: "image"; src: string; legende: string }
  | { type: "video"; chapitre: string; debut: number; fin: number };

export interface Lecon {
  module: { code: string; titre: string };
  code: string;
  titre: string;
  duree: number;
  objectif: string;
  blocs: Bloc[];
  terminee: boolean;
  precedente: string | null;
  suivante: string | null;
}

export interface Quiz { module: { code: string; titre: string }; seuil: number; questions: { question: string; choix: string[] }[] }
export interface ResultatQuiz {
  score: number;
  total: number;
  reussi: boolean;
  seuil: number;
  corrections: { juste: boolean; bonne: number; explication: string }[];
}

export const useSommaireFormation = () =>
  useQuery({ queryKey: ["formation"], queryFn: async () => (await apiClient.get<SommaireFormation>("/formation/")).data });

export const useLecon = (module: string, code: string) =>
  useQuery({
    queryKey: ["formation", "lecon", module, code],
    queryFn: async () => (await apiClient.get<Lecon>(`/formation/modules/${module}/lecons/${code}/`)).data,
  });

export function useMarquerLecon(module: string, code: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (terminee: boolean) =>
      (await (terminee ? apiClient.post<Lecon>(`/formation/modules/${module}/lecons/${code}/`)
        : apiClient.delete<Lecon>(`/formation/modules/${module}/lecons/${code}/`))).data,
    onSuccess: (lecon) => {
      queryClient.setQueryData(["formation", "lecon", module, code], lecon);
      queryClient.invalidateQueries({ queryKey: ["formation"], exact: true });
    },
  });
}

export const useQuiz = (module: string) =>
  useQuery({ queryKey: ["formation", "quiz", module], queryFn: async () => (await apiClient.get<Quiz>(`/formation/modules/${module}/quiz/`)).data });

export function useRepondreQuiz(module: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (reponses: number[]) => (await apiClient.post<ResultatQuiz>(`/formation/modules/${module}/quiz/`, { reponses })).data,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["formation"], exact: true }),
  });
}

export async function telechargerAttestation() {
  const reponse = await apiClient.get("/formation/attestation/", { responseType: "blob" });
  const url = window.URL.createObjectURL(reponse.data);
  const lien = document.createElement("a");
  lien.href = url;
  lien.download = "attestation_formation.pdf";
  document.body.appendChild(lien);
  lien.click();
  lien.remove();
  window.URL.revokeObjectURL(url);
}
