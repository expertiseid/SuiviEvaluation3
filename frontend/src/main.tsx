import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { createTheme, MantineProvider } from "@mantine/core";
import { Notifications } from "@mantine/notifications";
import { ModalsProvider } from "@mantine/modals";
import { DateInput, DatePickerInput, DatesProvider } from "@mantine/dates";
import dayjs from "dayjs";
import "dayjs/locale/fr";
import customParseFormat from "dayjs/plugin/customParseFormat";

import "@fontsource/inter/400.css";
import "@fontsource/inter/500.css";
import "@fontsource/inter/600.css";
import "@fontsource/inter/700.css";
import "@mantine/core/styles.css";
import "@mantine/notifications/styles.css";
import "@mantine/dates/styles.css";
import "./index.css";

import App from "./App";
import { AuthProvider } from "./auth/AuthContext";

// Dates en français partout : noms des mois et jours, semaine commençant le lundi,
// affichage et saisie au clavier au format JJ/MM/AAAA.
dayjs.extend(customParseFormat);
dayjs.locale("fr");

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
  },
});

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <MantineProvider theme={theme} defaultColorScheme="light">
      <DatesProvider settings={{ locale: "fr", firstDayOfWeek: 1 }}>
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
  </StrictMode>,
);
