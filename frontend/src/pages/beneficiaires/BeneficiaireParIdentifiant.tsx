import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { Alert, Text } from "@mantine/core";
import { rechercherBeneficiaireParIdentifiant } from "../../api/beneficiaries";
import { messageErreurApi } from "../../utils/erreurs";
import { voc } from "../../utils/vocabulaire";

/** Lien du QR code d'une carte bénéficiaire : retrouve la fiche par son identifiant et l'ouvre. */
export function BeneficiaireParIdentifiant() {
  const { identifiant = "" } = useParams();
  const navigate = useNavigate();
  const [erreur, setErreur] = useState<string | null>(null);

  useEffect(() => {
    rechercherBeneficiaireParIdentifiant(identifiant)
      .then((id) => navigate(`/beneficiaires/${id}`, { replace: true }))
      .catch((e) => setErreur(messageErreurApi(e, voc("Bénéficiaire introuvable."))));
  }, [identifiant, navigate]);

  return erreur ? (
    <Alert color="orange" title={identifiant}>{erreur}</Alert>
  ) : (
    <Text>{voc("Recherche de")} {identifiant}…</Text>
  );
}
