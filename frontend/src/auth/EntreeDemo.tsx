import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Alert, Center, Loader, Stack, Text } from "@mantine/core";
import { connexionDemo } from "../api/identite";
import { messageErreurApi } from "../utils/erreurs";
import { voc } from "../utils/vocabulaire";
import { useAuth } from "./useAuth";

/**
 * Installation de démonstration (demo_directe) : on n'y voit jamais de page de connexion. Le visiteur
 * entre directement dans la démo, sur la page demandée (`destination`).
 */
export function EntreeDemo({ destination }: { destination: string }) {
  const { ouvrirSession } = useAuth();
  const navigate = useNavigate();
  const [erreur, setErreur] = useState("");
  const lancee = useRef(false);

  useEffect(() => {
    if (lancee.current) return;
    lancee.current = true;
    connexionDemo()
      .then((jetons) => ouvrirSession(jetons, destination))
      .then(() => navigate(destination, { replace: true }))
      .catch((error) => setErreur(messageErreurApi(error, voc("La démonstration n'est pas disponible pour le moment."))));
  }, [destination, navigate, ouvrirSession]);

  return (
    <Center h="100vh">
      {erreur ? (
        <Alert color="red" maw={420}>{erreur}</Alert>
      ) : (
        <Stack align="center" gap="xs">
          <Loader />
          <Text size="sm" c="dimmed">{voc("Ouverture de la démonstration…")}</Text>
        </Stack>
      )}
    </Center>
  );
}
