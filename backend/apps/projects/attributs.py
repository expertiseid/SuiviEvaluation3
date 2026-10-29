"""
Attributs libres des éléments de la planification et des sous-activités (« Responsable »,
« Lieu »…) : Activite.attributs et SousActivite.attributs, {nom: texte}.

Dans la feuille « Planification » d'un modèle d'import, une colonne dont l'en-tête commence par
« Attribut : » (dans n'importe quelle langue de l'interface) n'est jamais un niveau : sa valeur
s'applique à l'élément ou à la sous-activité de la même ligne, où que soit placée la colonne.
Un attribut qui porte le nom d'un champ existant (Description, Sources de vérification,
Hypothèses) remplit ce champ.
"""
from rest_framework import serializers

from apps.core.langues import formes, normaliser, vers_francais

PREFIXE = "Attribut"
LONGUEUR_MAX_NOM = 100
LONGUEUR_MAX_VALEUR = 2000
# Attribut au nom d'un champ de l'élément : c'est ce champ qui est renseigné.
CHAMPS_CONNUS = {"Description": "description", "Sources de vérification": "sources_verification", "Hypothèses": "hypotheses"}


def nom_de_colonne(entete) -> str | None:
    """« Attribut : Responsable » (ou « Attribute: Responsable »…) → « Responsable » ; None sinon."""
    texte = str(entete or "")
    if ":" not in texte:
        return None
    avant, apres = texte.split(":", 1)
    if normaliser(avant) not in {normaliser(f) for f in formes(PREFIXE)}:
        return None
    return apres.strip() or None


def champ_connu(nom: str) -> str | None:
    """Nom d'attribut qui désigne un champ de l'élément (dans n'importe quelle langue)."""
    francais = vers_francais(nom)
    return next((champ for libelle, champ in CHAMPS_CONNUS.items() if normaliser(francais) == normaliser(libelle)), None)


def nettoyer(attributs) -> dict:
    """Attributs saisis → {nom: texte} sans valeur vide ; ValidationError si la forme est fausse."""
    if attributs in (None, ""):
        return {}
    if not isinstance(attributs, dict):
        raise serializers.ValidationError("Attendu : un objet {nom: texte}.")
    propres = {}
    for nom, valeur in attributs.items():
        nom = str(nom).strip()
        valeur = "" if valeur is None else str(valeur).strip()
        if not nom or not valeur:
            continue
        if len(nom) > LONGUEUR_MAX_NOM or len(valeur) > LONGUEUR_MAX_VALEUR:
            raise serializers.ValidationError(
                f"« {nom[:40]} » : {LONGUEUR_MAX_NOM} caractères au plus pour le nom, {LONGUEUR_MAX_VALEUR} pour la valeur."
            )
        propres[nom] = valeur
    return propres


def retenir_ordre(projet, noms):
    """Ajoute à l'ordre des attributs du projet les noms qu'il ne connaît pas encore, à la fin."""
    nouveaux = [nom for nom in dict.fromkeys(noms) if nom not in (projet.ordre_attributs or [])]
    if nouveaux:
        projet.ordre_attributs = [*(projet.ordre_attributs or []), *nouveaux]
        projet.save(update_fields=["ordre_attributs"])


def ordonner(noms, ordre) -> list[str]:
    """Noms d'attributs dans l'ordre du projet (fichier importé) ; les inconnus à la fin, par nom."""
    rang = {nom: i for i, nom in enumerate(ordre or [])}
    return sorted(dict.fromkeys(noms), key=lambda nom: (rang.get(nom, len(rang)), nom))
