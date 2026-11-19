import { useEffect, useMemo, useState, type ReactNode } from "react";
import { useNavigate } from "react-router-dom";
import { Badge, Group, Kbd, Loader, Modal, ScrollArea, Stack, Text, TextInput, UnstyledButton } from "@mantine/core";
import { useDebouncedValue, useHotkeys } from "@mantine/hooks";
import { useQuery } from "@tanstack/react-query";
import {
  Activity, FileText, FolderKanban, Gauge, Layers, MapPin, MessagesSquare, Search, Target, Users, type LucideIcon,
} from "lucide-react";
import { apiClient } from "../../api/client";
import { useTypesDocuments } from "../../api/strategy";
import { lienDocument } from "../../utils/chaineDocuments";
import { correspond } from "../../utils/recherche";
import { voc } from "../../utils/vocabulaire";

type Onglet = { to: string; label: string; icon: LucideIcon };
interface Resultat { id: number; titre: string; detail?: string; lien?: string; document?: number; type_document?: number | null }
interface Groupe { cle: string; resultats: Resultat[] }

const GROUPES: Record<string, { titre: string; icone: LucideIcon }> = {
  projets: { titre: "Projets", icone: FolderKanban },
  activites: { titre: "Activités", icone: Activity },
  indicateurs: { titre: "Indicateurs", icone: Gauge },
  beneficiaires: { titre: "Bénéficiaires", icone: Users },
  strategies: { titre: "Documents stratégiques", icone: Target },
  elements: { titre: "Éléments stratégiques", icone: Layers },
  documents: { titre: "Documents", icone: FileText },
  plaintes: { titre: "Plaintes et retours", icone: MessagesSquare },
  zones: { titre: "Zones administratives", icone: MapPin },
};

/**
 * Recherche dans toute la plateforme (haut du menu, ou Ctrl/⌘ + K) : les onglets du menu d'abord, puis les
 * projets, activités, indicateurs, bénéficiaires, stratégies, documents… que l'utilisateur a le droit de voir
 * (GET /recherche/).
 */
export function RechercheGlobale({ onglets, auChoix }: { onglets: Onglet[]; auChoix?: () => void }) {
  const navigate = useNavigate();
  const [ouvert, setOuvert] = useState(false);
  const [texte, setTexte] = useState("");
  const [actif, setActif] = useState(0);
  const [cherche] = useDebouncedValue(texte.trim(), 250);
  const { data: maillons = [] } = useTypesDocuments();
  useHotkeys([["mod+K", () => setOuvert(true)]], []);

  const { data, isFetching } = useQuery({
    queryKey: ["recherche-globale", cherche],
    queryFn: async () => (await apiClient.get<{ groupes: Groupe[] }>("/recherche/", { params: { q: cherche } })).data,
    enabled: ouvert && cherche.length >= 2,
    staleTime: 30 * 1000,
  });

  // Une seule liste (onglets puis résultats) pour la navigation au clavier.
  const lignes = useMemo(() => {
    const tous: { cle: string; groupe: string; icone: LucideIcon; titre: string; detail?: string; lien: string }[] = [];
    if (texte.trim()) {
      onglets.filter((o) => correspond(o.label, texte.trim())).slice(0, 6)
        .forEach((o) => tous.push({ cle: `onglet-${o.to}`, groupe: voc("Onglets"), icone: o.icon, titre: o.label, lien: o.to }));
    }
    if (cherche.length >= 2) {
      (data?.groupes ?? []).forEach((g) => {
        const infos = GROUPES[g.cle] ?? { titre: g.cle, icone: Search };
        g.resultats.forEach((r) => tous.push({
          cle: `${g.cle}-${r.id}`, groupe: voc(infos.titre), icone: infos.icone, titre: r.titre, detail: r.detail,
          lien: r.lien ?? (r.document ? lienDocument({ id: r.document, type_document: r.type_document ?? null }, maillons) : "/"),
        }));
      });
    }
    return tous;
  }, [texte, cherche, onglets, data, maillons]);

  useEffect(() => { setActif(0); }, [lignes.length, texte]);

  const fermer = () => { setOuvert(false); setTexte(""); };
  const aller = (lien: string) => { fermer(); navigate(lien); auChoix?.(); };

  const clavier = (e: React.KeyboardEvent) => {
    if (e.key === "ArrowDown") { e.preventDefault(); setActif((a) => Math.min(a + 1, lignes.length - 1)); }
    else if (e.key === "ArrowUp") { e.preventDefault(); setActif((a) => Math.max(a - 1, 0)); }
    else if (e.key === "Enter" && lignes[actif]) { e.preventDefault(); aller(lignes[actif].lien); }
  };

  let groupePrecedent = "";
  const contenu: ReactNode[] = lignes.map((l, i) => {
    const Icone = l.icone;
    const titreGroupe = l.groupe !== groupePrecedent ? l.groupe : null;
    groupePrecedent = l.groupe;
    return (
      <div key={l.cle}>
        {titreGroupe && <Text size="xs" fw={700} c="dimmed" tt="uppercase" mt={i ? "sm" : 0} mb={4}>{titreGroupe}</Text>}
        <UnstyledButton onClick={() => aller(l.lien)} onMouseEnter={() => setActif(i)} w="100%" px="sm" py={6}
          style={{ borderRadius: 6, background: i === actif ? "var(--mantine-color-teal-0)" : undefined }}>
          <Group gap="sm" wrap="nowrap">
            <Icone size={16} color="var(--mantine-color-teal-7)" style={{ flexShrink: 0 }} />
            <div style={{ minWidth: 0 }}>
              <Text size="sm" lineClamp={1}>{l.titre}</Text>
              {l.detail && <Text size="xs" c="dimmed" lineClamp={1}>{l.detail}</Text>}
            </div>
          </Group>
        </UnstyledButton>
      </div>
    );
  });

  return (
    <>
      <UnstyledButton onClick={() => setOuvert(true)} w="100%" mb={6} px="sm" py={10} aria-label={voc("Rechercher…")}
        style={{ border: "1.5px solid var(--mantine-color-teal-4)", borderRadius: 8, background: "var(--mantine-color-white)" }}>
        <Group gap="xs" wrap="nowrap" justify="space-between">
          <Group gap="xs" wrap="nowrap">
            <Search size={17} color="var(--mantine-color-teal-7)" />
            <Text size="sm" c="dimmed">{voc("Rechercher…")}</Text>
          </Group>
          <Badge variant="default" size="sm" radius="sm" visibleFrom="sm">Ctrl K</Badge>
        </Group>
      </UnstyledButton>

      <Modal opened={ouvert} onClose={fermer} withCloseButton={false} size="xl" yOffset="8vh" padding="md">
        <Stack gap="sm">
          <TextInput size="lg" data-autofocus placeholder={voc("Rechercher un onglet, un projet, un indicateur, un bénéficiaire, un document…")}
            leftSection={<Search size={20} />} rightSection={isFetching ? <Loader size={16} /> : null}
            value={texte} onChange={(e) => setTexte(e.currentTarget.value)} onKeyDown={clavier} />
          <ScrollArea.Autosize mah="60vh">
            {!texte.trim() ? (
              <Text size="sm" c="dimmed" ta="center" py="md">
                {voc("Tapez un mot : nom d'onglet, de projet, d'activité, d'indicateur, de bénéficiaire, de document, numéro de dossier…")}
              </Text>
            ) : lignes.length === 0 && !isFetching && (cherche.length >= 2 || texte.trim().length < 2) ? (
              <Text size="sm" c="dimmed" ta="center" py="md">
                {texte.trim().length < 2 ? voc("Tapez au moins 2 caractères.") : voc("Aucun résultat.")}
              </Text>
            ) : contenu}
          </ScrollArea.Autosize>
          <Group gap="md" justify="flex-end">
            <Text size="xs" c="dimmed"><Kbd size="xs">↑</Kbd> <Kbd size="xs">↓</Kbd> {voc("pour choisir")}</Text>
            <Text size="xs" c="dimmed"><Kbd size="xs">{voc("Entrée")}</Kbd> {voc("pour ouvrir")}</Text>
          </Group>
        </Stack>
      </Modal>
    </>
  );
}
