import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Alert, Button, Center, Paper, PasswordInput, Stack, Text, TextInput, Title } from "@mantine/core";
import { useAuth } from "./useAuth";
import { voc } from "../utils/vocabulaire";
import { ChoixLangue } from "../components/common/ChoixLangue";

export function LoginPage() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      await login(username, password);
      navigate("/");
    } catch {
      setError("Identifiants invalides.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <Center h="100vh" bg="teal.9">
      <Paper shadow="md" radius="md" p="xl" w={380} withBorder pos="relative">
        <div style={{ position: "absolute", top: 8, insetInlineEnd: 8 }}>
          <ChoixLangue connecte={false} couleur="gray" />
        </div>
        <Stack gap="md">
          <div>
            <Title order={3}>{voc("Plateforme de Suivi-Évaluation")}</Title>
            <Text size="sm" c="dimmed">{voc("Connectez-vous pour accéder à vos projets")}</Text>
          </div>
          {error && <Alert color="red">{error}</Alert>}
          <form onSubmit={handleSubmit}>
            <Stack gap="sm">
              <TextInput
                label={voc("Identifiant")}
                value={username}
                onChange={(e) => setUsername(e.currentTarget.value)}
                required
              />
              <PasswordInput
                label={voc("Mot de passe")}
                value={password}
                onChange={(e) => setPassword(e.currentTarget.value)}
                required
              />
              <Button type="submit" loading={submitting} fullWidth mt="sm">
                {voc("Se connecter")}
              </Button>
            </Stack>
          </form>
        </Stack>
      </Paper>
    </Center>
  );
}
