import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { createTheme, DirectionProvider, MantineProvider, Table } from "@mantine/core";
import { Notifications } from "@mantine/notifications";
import { z } from "zod";
import { ModalsProvider } from "@mantine/modals";
import { DateInput, DatePickerInput, DatesProvider } from "@mantine/dates";
import dayjs from "dayjs";
import "dayjs/locale/fr";
import "dayjs/locale/en-gb";
import "dayjs/locale/ar";
import "dayjs/locale/es";
import "dayjs/locale/de";
import customParseFormat from "dayjs/plugin/customParseFormat";

import "@fontsource/inter/400.css";
import "@fontsource/inter/500.css";
import "@fontsource/inter/600.css";
import "@fontsource/inter/700.css";
import "@mantine/core/styles.css";
import "@mantine/notifications/styles.css";
import "@mantine/dates/styles.css";
import "./index.css";

import { AuthProvider } from "./auth/AuthContext";
import { demarrerLangue, estRtl, langue } from "./utils/i18n";

// Dates dans la langue de l'interface (noms des mois et jours), semaine commençant le lundi,
// affichage et saisie au clavier au format JJ/MM/AAAA.
dayjs.extend(customParseFormat);
const LOCALES_DAYJS = { fr: "fr", en: "en-gb", ar: "ar", es: "es", de: "de" } as const;

function lireDateSaisie(texte: string): string | null {
  const date = dayjs(texte.trim(), ["DD/MM/YYYY", "D/M/YYYY", "DD-MM-YYYY", "YYYY-MM-DD"], true);
  return date.isValid() ? date.format("YYYY-MM-DD") : null;
}

const queryClient = new QueryClient({
  defaultOptions: { queries: { retry: 1, refetchOnWindowFocus: false } },
});

const theme = createTheme({
  primaryColor: "teal",
  primaryShade: { light: 7, dark: 5 },
  defaultRadius: "md",
  fontFamily: "Inter, system-ui, sans-serif",
  fontFamilyMonospace: "ui-monospace, Consolas, monospace",
  headings: { fontFamily: "Inter, system-ui, sans-serif", fontWeight: "600" },
  // Légèrement agrandies (ancien barème : 0.75 / 0.85 / 0.9 / 1 / 1.15) ; le
  // suivi d'un projet, déjà agrandi au cas par cas, garde l'ancien barème
  // (classe .bareme-police-suivi, index.css).
  fontSizes: { xs: "0.8rem", sm: "0.9rem", md: "0.97rem", lg: "1.07rem", xl: "1.22rem" },
  spacing: { xs: "0.5rem", sm: "0.75rem", md: "1rem", lg: "1.5rem", xl: "2rem" },
  shadows: { sm: "0 2px 8px rgba(16, 24, 32, 0.06)", md: "0 8px 20px rgba(16, 24, 32, 0.1)" },
  components: {
    Card: { defaultProps: { padding: "md", radius: "md" } },
    Button: { defaultProps: { radius: "md" } },
    DateInput: DateInput.extend({ defaultProps: { valueFormat: "DD/MM/YYYY", dateParser: lireDateSaisie } }),
    DatePickerInput: DatePickerInput.extend({ defaultProps: { valueFormat: "DD/MM/YYYY" } }),
    // Lignes des tableaux bien visibles (par défaut : gris très clair).
    Table: Table.extend({ vars: () => ({ table: { "--table-border-color": "var(--mantine-color-gray-5)" } }) }),
  },
});

// Politique de sécurité du contenu (CSP) : les styles que Mantine ajoute à la page portent le jeton
// (nonce) donné par le serveur dans <meta property="csp-nonce"> (vite.config.ts, deploiement/).
const jetonStyles = () => document.querySelector<HTMLMetaElement>('meta[property="csp-nonce"]')?.nonce ?? "";
// Fenêtres (Modal) : le blocage du défilement ajoute aussi un style à la page (react-remove-scroll) ;
// il prend son jeton dans __webpack_nonce__ (paquet get-nonce).
(globalThis as { __webpack_nonce__?: string }).__webpack_nonce__ = jetonStyles();
// Validation des formulaires (zod) : sans le mode « jitless », zod essaie de compiler du code
// (new Function), ce que la politique de contenu interdit.
z.config({ jitless: true });

// La langue est connue avant l'affichage : l'application (et ses textes) est chargée ensuite.
async function demarrer() {
  await demarrerLangue();
  dayjs.locale(LOCALES_DAYJS[langue()]);
  const { default: App } = await import("./App");
  createRoot(document.getElementById("root")!).render(
    <StrictMode>
      <DirectionProvider initialDirection={estRtl() ? "rtl" : "ltr"} detectDirection={false}>
        <MantineProvider theme={theme} defaultColorScheme="light" getStyleNonce={jetonStyles}>
          <DatesProvider settings={{ locale: LOCALES_DAYJS[langue()], firstDayOfWeek: 1 }}>
            <Notifications />
            <ModalsProvider>
              <QueryClientProvider client={queryClient}>
                <BrowserRouter>
                  <AuthProvider>
                    <App />
                  </AuthProvider>
                </BrowserRouter>
              </QueryClientProvider>
            </ModalsProvider>
          </DatesProvider>
        </MantineProvider>
      </DirectionProvider>
    </StrictMode>,
  );
}

void demarrer();
