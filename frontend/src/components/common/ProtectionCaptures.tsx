import { useEffect, useMemo, useState } from "react";
import { Box, Stack, Text } from "@mantine/core";
import { notifications } from "@mantine/notifications";
import { EyeOff } from "lucide-react";
import { useIdentiteOrganisation } from "../../api/identite";
import { useAuth } from "../../auth/useAuth";
import { voc } from "../../utils/vocabulaire";

/**
 * Protection de l'écran contre les captures : réglage de l'organisation (Organisation › Identité et logo), ou
 * propre à l'utilisateur (sa fiche : bloquées ou permises). Jamais pour l'Administrateur.
 *
 * Un navigateur ne peut pas interdire une capture faite par le système (ou une photo de l'écran) : on la rend
 * inutile ou traçable. Filigrane au nom de la personne sur toute la page ; écran masqué quand la fenêtre perd
 * la main (outil de capture, autre application) et à la touche « Impr. écran » ; impression, enregistrement
 * de la page, copie et menu du clic droit bloqués.
 */
export function ProtectionCaptures() {
  const { user } = useAuth();
  const { data: identite } = useIdentiteOrganisation();
  const reglage = user?.captures ?? "ORGANISATION";
  const actif = !!user && user.role !== "ADMIN"
    && (reglage === "BLOQUEES" || (reglage === "ORGANISATION" && !!identite?.bloquer_captures));
  const [masque, setMasque] = useState(false);

  useEffect(() => {
    if (!actif) return;
    const avertir = () => notifications.show({
      id: "capture-bloquee", color: "orange",
      message: voc("Captures, impression et copie sont désactivées sur cette plateforme par l'administrateur."),
    });
    // Un clic dans un aperçu de document (cadre intégré) fait aussi perdre la main à la page : pas masqué.
    const perteDeMain = () => { if (!(document.activeElement instanceof HTMLIFrameElement)) setMasque(true); };
    const retour = () => setMasque(false);
    const visibilite = () => setMasque(document.visibilityState !== "visible");
    // Raccourcis de capture du système (⌘ + Maj + 3/4/5 sur Mac, Windows + Maj + S) : le système garde la
    // touche finale pour lui, mais la page voit ⌘/Windows + Maj d'abord. L'écran est masqué dès ce moment, et
    // jusqu'au prochain clic (la sélection de la zone à capturer ne passe pas par la page) ou 10 secondes.
    let minuterie = 0;
    const enGarde = () => {
      setMasque(true);
      window.clearTimeout(minuterie);
      minuterie = window.setTimeout(retour, 10000);
    };
    const clic = () => { window.clearTimeout(minuterie); setMasque(false); };
    const touche = (e: KeyboardEvent) => {
      const cle = e.key.toLowerCase();
      if (e.type === "keydown" && e.metaKey && e.shiftKey) {
        enGarde();
        return;
      }
      if (e.key === "PrintScreen" || ((e.metaKey || e.ctrlKey) && e.shiftKey && ["3", "4", "5", "s"].includes(cle))) {
        setMasque(true);
        navigator.clipboard?.writeText("").catch(() => undefined);
        avertir();
        window.setTimeout(retour, 2000);
      } else if ((e.metaKey || e.ctrlKey) && ["p", "s"].includes(cle)) {
        e.preventDefault();
        avertir();
      }
    };
    const horsSaisie = (cible: EventTarget | null) =>
      !(cible instanceof HTMLElement && cible.closest("input, textarea, [contenteditable='true']"));
    const copie = (e: ClipboardEvent) => { if (horsSaisie(e.target)) { e.preventDefault(); avertir(); } };
    const menu = (e: MouseEvent) => { if (horsSaisie(e.target)) e.preventDefault(); };
    const impression = () => avertir();

    document.body.classList.add("protection-captures");
    window.addEventListener("blur", perteDeMain);
    window.addEventListener("focus", retour);
    document.addEventListener("visibilitychange", visibilite);
    window.addEventListener("keydown", touche, true);
    window.addEventListener("keyup", touche, true);  // « Impr. écran » n'arrive qu'au relâchement sous Windows
    document.addEventListener("copy", copie, true);
    document.addEventListener("cut", copie, true);
    document.addEventListener("contextmenu", menu, true);
    window.addEventListener("beforeprint", impression);
    window.addEventListener("mousedown", clic, true);
    return () => {
      window.clearTimeout(minuterie);
      window.removeEventListener("mousedown", clic, true);
      document.body.classList.remove("protection-captures");
      window.removeEventListener("blur", perteDeMain);
      window.removeEventListener("focus", retour);
      document.removeEventListener("visibilitychange", visibilite);
      window.removeEventListener("keydown", touche, true);
      window.removeEventListener("keyup", touche, true);
      document.removeEventListener("copy", copie, true);
      document.removeEventListener("cut", copie, true);
      document.removeEventListener("contextmenu", menu, true);
      window.removeEventListener("beforeprint", impression);
    };
  }, [actif]);

  // Filigrane : nom, identifiant et date, répétés en biais sur toute la page.
  const filigrane = useMemo(() => {
    if (!actif || !user) return "";
    const nom = [user.first_name, user.last_name].filter(Boolean).join(" ") || user.username;
    const texte = `${nom} · ${user.email || user.username} · ${new Date().toLocaleDateString()}`
      .replace(/&/g, "&amp;").replace(/</g, "&lt;");
    const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="420" height="220"><text x="20" y="130" transform="rotate(-24 210 110)" `
      + `font-family="sans-serif" font-size="15" fill="rgba(60,60,60,0.13)">${texte}</text></svg>`;
    return `url("data:image/svg+xml;charset=utf-8,${encodeURIComponent(svg)}")`;
  }, [actif, user]);

  if (!actif) return null;
  return (
    <>
      <style>{`
        @media print { body { display: none !important; } }
        body.protection-captures { -webkit-user-select: none; user-select: none; }
        body.protection-captures :is(input, textarea, [contenteditable='true']) { -webkit-user-select: text; user-select: text; }
      `}</style>
      <Box aria-hidden style={{ position: "fixed", inset: 0, zIndex: 9999, pointerEvents: "none", backgroundImage: filigrane }} />
      {masque && (
        <Box style={{ position: "fixed", inset: 0, zIndex: 10000, background: "var(--mantine-color-body)", display: "flex",
          alignItems: "center", justifyContent: "center" }}>
          <Stack align="center" gap="xs">
            <EyeOff size={36} />
            <Text fw={600}>{voc("Contenu masqué")}</Text>
            <Text size="sm" c="dimmed">{voc("Revenez sur la fenêtre de la plateforme pour l'afficher.")}</Text>
            <Text size="sm" c="dimmed">{voc("Cliquez pour l'afficher de nouveau.")}</Text>
          </Stack>
        </Box>
      )}
    </>
  );
}
