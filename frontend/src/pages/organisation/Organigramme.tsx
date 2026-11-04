import { useState } from "react";
import { Link } from "react-router-dom";
import { ActionIcon, Avatar, Badge, Button, Card, Drawer, Group, Menu, ScrollArea, Stack, Tabs, Text, TextInput, Tooltip, UnstyledButton } from "@mantine/core";
import { Building2, ChevronDown, ChevronUp, Ellipsis, FolderKanban, Link2, Network, Pencil, Plus, Search, Trash2, Users } from "lucide-react";
import type { StructureOrganisation } from "../../types";
import { libelleStructure } from "../../utils/organisation";
import { voc } from "../../utils/vocabulaire";
import classes from "./Organigramme.module.css";

// Couleur du liseré de la boîte selon le niveau : organisation, direction, service, puis au-delà.
const COULEURS = ["teal", "indigo", "blue", "cyan", "gray"];

interface Actions {
  onEditer: (s: Partial<StructureOrganisation>) => void;
  onAffecter: (s: StructureOrganisation) => void;
  onSupprimer: (s: StructureOrganisation) => void;
}

function MenuActions({ structure, racine, onEditer, onAffecter, onSupprimer }: Actions & { structure: StructureOrganisation; racine: boolean }) {
  return (
    <Menu position="bottom-end" withinPortal>
      <Menu.Target>
        <ActionIcon size="sm" variant="subtle" color="gray" aria-label={voc("Actions")} onClick={(e) => e.stopPropagation()}>
          <Ellipsis size={16} />
        </ActionIcon>
      </Menu.Target>
      <Menu.Dropdown onClick={(e) => e.stopPropagation()}>
        <Menu.Item leftSection={<Plus size={14} />} onClick={() => onEditer({ parent: structure.id, type: "Service" })}>
          {racine ? voc("Ajouter un service") : voc("Sous-service")}
        </Menu.Item>
        <Menu.Item leftSection={<Link2 size={14} />} onClick={() => onAffecter(structure)}>{voc("Projets et membres")}</Menu.Item>
        <Menu.Item leftSection={<Pencil size={14} />} onClick={() => onEditer(structure)}>{voc("Modifier")}</Menu.Item>
        <Menu.Divider />
        <Menu.Item leftSection={<Trash2 size={14} />} color="red" onClick={() => onSupprimer(structure)}>{voc("Supprimer")}</Menu.Item>
      </Menu.Dropdown>
    </Menu>
  );
}

function Boite({ structure, niveau, nbEnfants, replie, basculer, ouvrir, actions }: {
  structure: StructureOrganisation;
  niveau: number;
  nbEnfants: number;
  replie: boolean;
  basculer: () => void;
  ouvrir: () => void;
  actions: Actions;
}) {
  const couleur = COULEURS[Math.min(niveau, COULEURS.length - 1)];
  const Icone = niveau === 0 ? Building2 : Network;
  return (
    <Stack gap={4} align="center">
      <Card withBorder padding="sm" radius="md" shadow="xs" className={classes.boite} onClick={ouvrir}
        style={{ borderTop: `4px solid var(--mantine-color-${couleur}-6)` }}>
        <Stack gap={6}>
          <Group justify="space-between" wrap="nowrap" gap={4} align="flex-start">
            <Group gap={6} wrap="nowrap" style={{ minWidth: 0 }}>
              <Icone size={16} color={`var(--mantine-color-${couleur}-7)`} style={{ flexShrink: 0 }} />
              <Text fw={700} size="sm" truncate>{structure.code || structure.nom}</Text>
            </Group>
            <MenuActions structure={structure} racine={niveau === 0} {...actions} />
          </Group>
          {structure.code && <Text size="sm" lineClamp={2} lh={1.3}>{structure.nom}</Text>}
          {structure.responsable && <Text size="xs" c="dimmed" lineClamp={1}>{structure.responsable}</Text>}
          <Group gap={6} justify="space-between" wrap="nowrap">
            {structure.type ? <Badge variant="light" color={couleur} size="xs">{structure.type}</Badge> : <span />}
            <Group gap={8} wrap="nowrap">
              <Tooltip label={voc("Projets")}>
                <Group gap={3} wrap="nowrap"><FolderKanban size={13} color="var(--mantine-color-dimmed)" /><Text size="xs">{structure.projets_resume.length}</Text></Group>
              </Tooltip>
              <Tooltip label={voc("Membres")}>
                <Group gap={3} wrap="nowrap"><Users size={13} color="var(--mantine-color-dimmed)" /><Text size="xs">{structure.utilisateurs_resume.length}</Text></Group>
              </Tooltip>
            </Group>
          </Group>
        </Stack>
      </Card>
      {nbEnfants > 0 && (
        <UnstyledButton onClick={basculer} aria-label={replie ? voc("Déplier") : voc("Replier")}>
          <Badge size="xs" variant="default" leftSection={replie ? <ChevronDown size={11} /> : <ChevronUp size={11} />}>
            {replie ? voc`${nbEnfants} service(s)` : voc("Replier")}
          </Badge>
        </UnstyledButton>
      )}
    </Stack>
  );
}

/** Volet de détail d'une structure : projets et membres (onglets, recherche), actions. */
function Detail({ structure, onClose, actions, racine }: { structure: StructureOrganisation | null; onClose: () => void; actions: Actions; racine: boolean }) {
  const [recherche, setRecherche] = useState("");
  const agir = (f: () => void) => { onClose(); f(); };
  const fermer = () => { setRecherche(""); onClose(); };
  const terme = recherche.trim().toLowerCase();
  const projets = (structure?.projets_resume ?? []).filter((p) => !terme || `${p.code} ${p.nom}`.toLowerCase().includes(terme));
  const membres = (structure?.utilisateurs_resume ?? []).filter((u) => !terme || u.nom.toLowerCase().includes(terme));
  return (
    <Drawer opened={!!structure} onClose={fermer} position="right" size="xl" padding="lg"
      title={structure ? (
        <Stack gap={4}>
          <Text fw={700} size="lg" lh={1.3}>{libelleStructure(structure)}</Text>
          <Group gap="xs">
            {structure.type && <Badge variant="light">{structure.type}</Badge>}
            {structure.responsable && <Text size="sm" c="dimmed">{voc("Responsable :")} {structure.responsable}</Text>}
          </Group>
        </Stack>
      ) : null}>
      {structure && (
        <Stack gap="md">
          <Group gap="xs">
            <Button size="xs" variant="light" leftSection={<Plus size={13} />} onClick={() => agir(() => actions.onEditer({ parent: structure.id, type: "Service" }))}>
              {racine ? voc("Ajouter un service") : voc("Sous-service")}
            </Button>
            <Button size="xs" variant="light" color="indigo" leftSection={<Link2 size={13} />} onClick={() => agir(() => actions.onAffecter(structure))}>
              {voc("Projets et membres")}
            </Button>
            <Button size="xs" variant="default" leftSection={<Pencil size={13} />} onClick={() => agir(() => actions.onEditer(structure))}>{voc("Modifier")}</Button>
          </Group>
          <Tabs defaultValue="projets" keepMounted={false}>
            <Tabs.List>
              <Tabs.Tab value="projets" leftSection={<FolderKanban size={14} />}>
                {voc("Projets")} <Badge size="xs" variant="light" ml={4}>{structure.projets_resume.length}</Badge>
              </Tabs.Tab>
              <Tabs.Tab value="membres" leftSection={<Users size={14} />}>
                {voc("Membres")} <Badge size="xs" variant="light" ml={4}>{structure.utilisateurs_resume.length}</Badge>
              </Tabs.Tab>
            </Tabs.List>
            {(structure.projets_resume.length > 8 || structure.utilisateurs_resume.length > 8) && (
              <TextInput mt="sm" placeholder={voc("Rechercher (code ou nom)")} leftSection={<Search size={14} />}
                value={recherche} onChange={(e) => setRecherche(e.currentTarget.value)} />
            )}
            <Tabs.Panel value="projets" pt="sm">
              {projets.length ? (
                <Stack gap={0}>
                  {projets.map((p, i) => (
                    <UnstyledButton key={p.id} component={Link} to={`/projets/${p.id}`} py={8} px={6}
                      style={{ borderTop: i ? "1px solid var(--mantine-color-gray-2)" : undefined, borderRadius: 4 }}
                      className={classes.ligne}>
                      <Text size="xs" fw={700} c="teal.8" ff="monospace">{p.code}</Text>
                      <Text size="sm" lh={1.35}>{p.nom}</Text>
                    </UnstyledButton>
                  ))}
                </Stack>
              ) : <Text size="sm" c="dimmed">{terme ? voc("Aucun résultat.") : voc("Aucun projet affecté.")}</Text>}
            </Tabs.Panel>
            <Tabs.Panel value="membres" pt="sm">
              {membres.length ? (
                <Stack gap={6}>
                  {membres.map((u) => (
                    <Group key={u.id} gap="xs"><Avatar size={26} radius="xl" color="teal">{u.nom[0]}</Avatar><Text size="sm">{u.nom}</Text></Group>
                  ))}
                </Stack>
              ) : <Text size="sm" c="dimmed">{terme ? voc("Aucun résultat.") : voc("Aucun membre affecté.")}</Text>}
            </Tabs.Panel>
          </Tabs>
        </Stack>
      )}
    </Drawer>
  );
}

/** Organigramme : l'organisation en haut, ses services en dessous, reliés par des traits. */
export function Organigramme({ structures, ...actions }: Actions & { structures: StructureOrganisation[] }) {
  const [replies, setReplies] = useState<Set<number>>(new Set());
  const [ouverte, setOuverte] = useState<StructureOrganisation | null>(null);
  const enfantsDe = (id: number | null) => structures.filter((s) => s.parent === id);
  const niveauDe = (s: StructureOrganisation) => {
    let n = 0;
    for (let p = s.parent; p !== null; p = structures.find((x) => x.id === p)?.parent ?? null) n += 1;
    return n;
  };
  const basculer = (id: number) => setReplies((r) => {
    const suivant = new Set(r);
    if (suivant.has(id)) suivant.delete(id);
    else suivant.add(id);
    return suivant;
  });

  const noeud = (s: StructureOrganisation, niveau: number): React.ReactNode => {
    const enfants = enfantsDe(s.id);
    const replie = replies.has(s.id);
    return (
      <li key={s.id}>
        <Boite structure={s} niveau={niveau} nbEnfants={enfants.length} replie={replie} basculer={() => basculer(s.id)}
          ouvrir={() => setOuverte(s)} actions={actions} />
        {enfants.length > 0 && !replie && <ul>{enfants.map((e) => noeud(e, niveau + 1))}</ul>}
      </li>
    );
  };

  return (
    <>
      <ScrollArea type="auto" offsetScrollbars>
        <Stack gap="xl" className={classes.conteneur}>
          {enfantsDe(null).map((racine) => <ul key={racine.id} className={classes.arbre}>{noeud(racine, 0)}</ul>)}
        </Stack>
      </ScrollArea>
      <Detail structure={ouverte ? structures.find((s) => s.id === ouverte.id) ?? null : null} onClose={() => setOuverte(null)}
        actions={actions} racine={ouverte ? niveauDe(ouverte) === 0 : false} />
    </>
  );
}
