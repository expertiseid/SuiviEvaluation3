import { useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import {
  Alert, Anchor, Badge, Button, Card, Group, Loader, Progress, Radio, RingProgress, SimpleGrid, Stack, Text, ThemeIcon, Title,
} from "@mantine/core";
import { notifications } from "@mantine/notifications";
import {
  ArrowLeft, ArrowRight, Award, CircleCheck, ClipboardList, Compass, FolderOpen, Gauge, GraduationCap, Lightbulb, ListTree, Lock,
  MapPinned, MessagesSquare, PlayCircle, Settings, Target, TriangleAlert, type LucideIcon,
} from "lucide-react";
import {
  type Bloc, type LeconResume, type ResultatQuiz, telechargerAttestation, useLecon, useMarquerLecon, useQuiz, useRepondreQuiz,
  useSommaireFormation,
} from "../../api/formation";
import { messageErreurApi } from "../../utils/erreurs";
import { locale } from "../../utils/i18n";
import { voc } from "../../utils/vocabulaire";

const ICONES: Record<string, LucideIcon> = { Compass, Target, ListTree, Gauge, MapPinned, FolderOpen, MessagesSquare, Settings };

/** Texte avec **gras**. */
function Riche({ texte }: { texte: string }) {
  return <>{texte.split(/(\*\*[^*]+\*\*)/).filter(Boolean).map((m, i) => (m.startsWith("**") ? <b key={i}>{m.slice(2, -2)}</b> : m))}</>;
}

/** Cours en ligne : modules, progression et attestation ; réservé aux organisations abonnées. */
export function FormationPage() {
  const { data, isLoading } = useSommaireFormation();
  const [telechargement, setTelechargement] = useState(false);
  if (isLoading || !data) return <Loader />;

  if (!data.acces) {
    return (
      <Stack gap="md">
        <Title order={2}>{voc("Formation")}</Title>
        <Alert color="orange" icon={<Lock size={20} />} title={voc("Réservé aux organisations abonnées")}>
          <Text size="sm">{voc("Le cours en ligne complet (leçons pas à pas, vidéos, exercices, quiz et attestation) s'ouvre dès que l'abonnement de votre organisation est activé.")}</Text>
          <Button mt="sm" component={Link} to="/inscription" size="xs">{voc("S'abonner")}</Button>
        </Alert>
        <SimpleGrid cols={{ base: 1, sm: 2, lg: 4 }}>
          {data.modules.map((m) => {
            const Icone = ICONES[m.icone] ?? GraduationCap;
            return (
              <Card key={m.code} withBorder radius="md" padding="md" opacity={0.75}>
                <Group gap="xs" mb={6}><ThemeIcon variant="light" color="gray"><Icone size={16} /></ThemeIcon><Lock size={14} /></Group>
                <Text fw={600} size="sm">{voc(m.titre)}</Text>
                <Text size="xs" c="dimmed">{voc(m.description)}</Text>
              </Card>
            );
          })}
        </SimpleGrid>
      </Stack>
    );
  }

  const telecharger = async () => {
    setTelechargement(true);
    try {
      await telechargerAttestation();
    } catch (error) {
      notifications.show({ color: "red", message: messageErreurApi(error, voc("L'attestation n'a pas pu être téléchargée.")) });
    } finally {
      setTelechargement(false);
    }
  };

  return (
    <Stack gap="md">
      <Group justify="space-between" align="flex-start">
        <div>
          <Title order={2}>{voc("Formation")}</Title>
          <Text c="dimmed" size="sm">{voc("Le cours en ligne d'Expertise-ID Monitora : des leçons pas à pas, des exercices dans votre espace et un quiz par module.")}</Text>
        </div>
        <Group gap="md">
          <RingProgress size={74} thickness={7} roundCaps sections={[{ value: data.progression ?? 0, color: "teal" }]}
            label={<Text ta="center" fw={700} size="sm">{data.progression}%</Text>} />
          {(data.attestation || data.attestation_possible) && (
            <Button leftSection={<Award size={16} />} onClick={telecharger} loading={telechargement} color="yellow" c="dark">
              {voc("Mon attestation")}
            </Button>
          )}
        </Group>
      </Group>
      {data.attestation && (
        <Alert color="teal" icon={<Award size={18} />}>
          {voc`Attestation n° ${data.attestation.numero}, délivrée le ${new Date(data.attestation.date).toLocaleDateString(locale())}.`}
        </Alert>
      )}
      <SimpleGrid cols={{ base: 1, md: 2 }}>
        {data.modules.map((m, n) => {
          const lecons = m.lecons as LeconResume[];
          const faites = lecons.filter((l) => l.terminee).length;
          const Icone = ICONES[m.icone] ?? GraduationCap;
          return (
            <Card key={m.code} withBorder radius="md" padding="lg">
              <Stack gap="sm">
                <Group justify="space-between" wrap="nowrap" align="flex-start">
                  <Group gap="sm" wrap="nowrap">
                    <ThemeIcon size={40} radius="md" variant="light" color="teal"><Icone size={22} /></ThemeIcon>
                    <div>
                      <Text size="xs" c="dimmed">{voc`Module ${n + 1}`}</Text>
                      <Text fw={700}>{voc(m.titre)}</Text>
                    </div>
                  </Group>
                  {m.quiz?.reussi && <Badge color="teal" leftSection={<CircleCheck size={12} />}>{voc("Réussi")}</Badge>}
                </Group>
                <Text size="sm" c="dimmed">{voc(m.description)}</Text>
                <Progress value={(100 * faites) / lecons.length} size="sm" color="teal" />
                <Stack gap={4}>
                  {lecons.map((l) => (
                    <Anchor key={l.code} component={Link} to={`/formation/${m.code}/${l.code}`} size="sm" c={l.terminee ? "teal.8" : undefined}>
                      <Group gap={6} wrap="nowrap">
                        {l.terminee ? <CircleCheck size={15} /> : <PlayCircle size={15} />}
                        <span>{voc(l.titre)}</span>
                        <Text span size="xs" c="dimmed">· {voc`${l.duree} min`}</Text>
                      </Group>
                    </Anchor>
                  ))}
                </Stack>
                <Group justify="space-between">
                  <Text size="xs" c="dimmed">
                    {m.quiz?.meilleur != null ? voc`Meilleur score au quiz : ${m.quiz.meilleur} / ${m.quiz.questions}` : voc("Quiz pas encore tenté")}
                  </Text>
                  <Button size="xs" variant={m.quiz?.reussi ? "light" : "filled"} component={Link} to={`/formation/${m.code}/quiz`}
                    leftSection={<ClipboardList size={14} />}>
                    {m.quiz?.reussi ? voc("Refaire le quiz") : voc("Passer le quiz")}
                  </Button>
                </Group>
              </Stack>
            </Card>
          );
        })}
      </SimpleGrid>
    </Stack>
  );
}

function BlocLecon({ bloc }: { bloc: Bloc }) {
  switch (bloc.type) {
    case "texte":
      return <Text><Riche texte={voc(bloc.texte)} /></Text>;
    case "etapes":
      return (
        <Stack gap={8}>
          {bloc.items.map((item, i) => (
            <Group key={i} gap="sm" wrap="nowrap" align="flex-start">
              <ThemeIcon size={24} radius="xl" color="teal" variant="light"><Text size="xs" fw={700}>{i + 1}</Text></ThemeIcon>
              <Text size="sm" style={{ flex: 1 }}><Riche texte={voc(item)} /></Text>
            </Group>
          ))}
        </Stack>
      );
    case "image":
      return (
        <figure style={{ margin: 0 }}>
          <img src={`/formation/${bloc.src}`} alt={voc(bloc.legende)} loading="lazy"
            style={{ width: "100%", borderRadius: 10, border: "1px solid var(--mantine-color-gray-3)" }} />
          <Text component="figcaption" size="xs" c="dimmed" mt={4}>{voc(bloc.legende)}</Text>
        </figure>
      );
    case "video":
      return (
        <Stack gap={4}>
          <video src={`/formation/presentation.webm#t=${bloc.debut},${bloc.fin}`} controls preload="metadata"
            style={{ width: "100%", borderRadius: 10, background: "#0c1622" }} />
          <Text size="xs" c="dimmed">{voc("Extrait de la vidéo de présentation.")}</Text>
        </Stack>
      );
    case "astuce":
    case "attention":
      return (
        <Alert color={bloc.type === "astuce" ? "blue" : "orange"} icon={bloc.type === "astuce" ? <Lightbulb size={18} /> : <TriangleAlert size={18} />}>
          <Riche texte={voc(bloc.texte)} />
        </Alert>
      );
    case "exercice":
      return (
        <Card withBorder radius="md" padding="md" bg="teal.0" style={{ borderColor: "var(--mantine-color-teal-3)" }}>
          <Text fw={700} size="sm" mb={6}>{voc("À vous : exercice dans votre espace")}</Text>
          <Stack gap={4}>
            {bloc.items.map((item, i) => <Text key={i} size="sm">☐ <Riche texte={voc(item)} /></Text>)}
          </Stack>
        </Card>
      );
  }
}

export function LeconPage() {
  const { module = "", lecon: code = "" } = useParams();
  const navigate = useNavigate();
  const { data: lecon, isLoading, error } = useLecon(module, code);
  const marquer = useMarquerLecon(module, code);
  if (isLoading) return <Loader />;
  if (error || !lecon) return <Alert color="red">{messageErreurApi(error, voc("Leçon introuvable."))}</Alert>;

  const terminerEtContinuer = async () => {
    if (!lecon.terminee) await marquer.mutateAsync(true);
    navigate(lecon.suivante ? `/formation/${module}/${lecon.suivante}` : `/formation/${module}/quiz`);
  };

  return (
    <Stack gap="md" maw={860}>
      <Anchor component={Link} to="/formation" size="sm"><Group gap={4}><ArrowLeft size={14} />{voc("Formation")}</Group></Anchor>
      <div>
        <Text size="sm" c="dimmed">{voc(lecon.module.titre)} · {voc`${lecon.duree} min`}</Text>
        <Title order={2}>{voc(lecon.titre)}</Title>
      </div>
      <Alert color="teal" variant="light" title={voc("Objectif")}>{voc(lecon.objectif)}</Alert>
      {lecon.blocs.map((b, i) => <BlocLecon key={i} bloc={b} />)}
      <Group justify="space-between" mt="md">
        {lecon.precedente ? (
          <Button variant="default" component={Link} to={`/formation/${module}/${lecon.precedente}`} leftSection={<ArrowLeft size={16} />}>
            {voc("Leçon précédente")}
          </Button>
        ) : <span />}
        <Group gap="sm">
          {lecon.terminee && <Badge color="teal" leftSection={<CircleCheck size={12} />}>{voc("Leçon terminée")}</Badge>}
          <Button onClick={terminerEtContinuer} loading={marquer.isPending} rightSection={<ArrowRight size={16} />}>
            {lecon.suivante ? voc("Terminer et continuer") : voc("Terminer et passer au quiz")}
          </Button>
        </Group>
      </Group>
    </Stack>
  );
}

export function QuizPage() {
  const { module = "" } = useParams();
  const { data: quiz, isLoading, error } = useQuiz(module);
  const repondre = useRepondreQuiz(module);
  const [reponses, setReponses] = useState<(number | null)[]>([]);
  const [resultat, setResultat] = useState<ResultatQuiz | null>(null);
  if (isLoading) return <Loader />;
  if (error || !quiz) return <Alert color="red">{messageErreurApi(error, voc("Quiz introuvable."))}</Alert>;

  const complet = quiz.questions.every((_, i) => reponses[i] != null);
  const valider = async () => {
    try {
      setResultat(await repondre.mutateAsync(reponses as number[]));
      window.scrollTo({ top: 0, behavior: "smooth" });
    } catch (e) {
      notifications.show({ color: "red", message: messageErreurApi(e, voc("Erreur")) });
    }
  };
  const recommencer = () => { setResultat(null); setReponses([]); };

  return (
    <Stack gap="md" maw={760}>
      <Anchor component={Link} to="/formation" size="sm"><Group gap={4}><ArrowLeft size={14} />{voc("Formation")}</Group></Anchor>
      <div>
        <Text size="sm" c="dimmed">{voc("Quiz")}</Text>
        <Title order={2}>{voc(quiz.module.titre)}</Title>
        <Text size="sm" c="dimmed">{voc`${quiz.seuil} bonnes réponses sur ${quiz.questions.length} pour réussir.`}</Text>
      </div>
      {resultat && (
        <Alert color={resultat.reussi ? "teal" : "orange"} icon={resultat.reussi ? <Award size={20} /> : <TriangleAlert size={20} />}
          title={resultat.reussi ? voc("Module réussi !") : voc("Pas encore : relisez les leçons et réessayez")}>
          {voc`Score : ${resultat.score} / ${resultat.total}.`}
          <Group mt="sm" gap="sm">
            <Button size="xs" component={Link} to="/formation">{voc("Retour à la formation")}</Button>
            <Button size="xs" variant="default" onClick={recommencer}>{voc("Recommencer")}</Button>
          </Group>
        </Alert>
      )}
      {quiz.questions.map((q, i) => {
        const correction = resultat?.corrections[i];
        return (
          <Card key={i} withBorder radius="md" padding="md"
            style={correction ? { borderColor: `var(--mantine-color-${correction.juste ? "teal" : "red"}-4)` } : undefined}>
            <Text fw={600} size="sm" mb="xs">{i + 1}. {voc(q.question)}</Text>
            <Radio.Group value={reponses[i] != null ? String(reponses[i]) : null}
              onChange={(v) => !resultat && setReponses((r) => { const s = [...r]; s[i] = Number(v); return s; })}>
              <Stack gap={6}>
                {q.choix.map((c, j) => (
                  <Radio key={j} value={String(j)} disabled={!!resultat}
                    label={correction && j === correction.bonne ? <Text span size="sm" fw={700} c="teal.8">{voc(c)} ✓</Text> : voc(c)}
                    color={correction ? (j === correction.bonne ? "teal" : "red") : undefined} />
                ))}
              </Stack>
            </Radio.Group>
            {correction && (
              <Text size="xs" mt="xs" c={correction.juste ? "teal.8" : "red.8"}>
                {correction.juste ? voc("Juste.") : voc`Bonne réponse : ${voc(q.choix[correction.bonne])}.`} {voc(correction.explication)}
              </Text>
            )}
          </Card>
        );
      })}
      {!resultat && (
        <Group justify="flex-end">
          <Button onClick={valider} disabled={!complet} loading={repondre.isPending}>{voc("Valider mes réponses")}</Button>
        </Group>
      )}
    </Stack>
  );
}
