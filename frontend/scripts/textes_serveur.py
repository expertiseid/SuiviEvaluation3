"""Relève les messages du serveur à traduire dans l'interface.

Parcourt le code Python du backend (hors tests et commandes) et garde les textes passés
aux erreurs, réponses et avertissements. Les f-strings deviennent des modèles où chaque
valeur insérée est remplacée par {0}, {1}… — l'interface les reconnaît puis remet les valeurs.

Usage (depuis la racine du dépôt) :
    docker compose exec -T backend python - < frontend/scripts/textes_serveur.py > frontend/src/i18n/serveur.json
"""

import ast
import json
import re
from pathlib import Path

RACINE = Path("/app/apps")
APPELS = {
    "v", "ValidationError", "PermissionDenied", "NotFound", "ProjetClotureError", "SaisieFermeeError",
    "ImportSigImpossible", "ImportImpossible", "append", "ajouter",
}
CLES = {"detail", "message", "erreur"}
# Rapports, exports et cartes imprimées restent en français pour l'instant : on ne les relève pas.
EXCLUS = re.compile(r"(^export|^exports\.py$|^carte_officielle\.py$|^word\.py$|^cadre_logique\.py$|^financier\.py$|^risques\.py$|^suivi_strategique\.py$)")
FRANCAIS = re.compile(r"[éèêàùçôîâû]|\b(le|la|les|des|du|de|un|une|est|sont|pas|aucun|aucune)\b", re.I)


def modele(noeud):
    """Texte (ou modèle {0}, {1}… pour une f-string) d'un nœud chaîne, sinon None."""
    if isinstance(noeud, ast.Constant) and isinstance(noeud.value, str):
        return noeud.value
    if isinstance(noeud, ast.JoinedStr):
        morceaux, n = [], 0
        for partie in noeud.values:
            if isinstance(partie, ast.Constant):
                morceaux.append(str(partie.value))
            else:
                morceaux.append("{%d}" % n)
                n += 1
        return "".join(morceaux)
    return None


def candidats(noeud):
    """Chaînes portées par un appel ou un dict (y compris imbriquées dans un dict)."""
    if isinstance(noeud, ast.Dict):
        for cle, valeur in zip(noeud.keys, noeud.values):
            yield from candidats(valeur)
    elif isinstance(noeud, (ast.List, ast.Tuple)):
        for element in noeud.elts:
            yield from candidats(element)
    else:
        texte = modele(noeud)
        if texte is not None:
            yield texte


def nom_appel(appel):
    f = appel.func
    return f.attr if isinstance(f, ast.Attribute) else f.id if isinstance(f, ast.Name) else ""


textes = set()
for fichier in RACINE.rglob("*.py"):
    if "test" in fichier.name or "management" in fichier.parts or "migrations" in fichier.parts or EXCLUS.search(fichier.name):
        continue
    arbre = ast.parse(fichier.read_text(encoding="utf-8"))
    for noeud in ast.walk(arbre):
        trouves = []
        if isinstance(noeud, ast.Call) and nom_appel(noeud) in APPELS:
            for argument in noeud.args:
                trouves += candidats(argument)
        elif isinstance(noeud, ast.Dict):
            for cle, valeur in zip(noeud.keys, noeud.values):
                if isinstance(cle, ast.Constant) and cle.value in CLES:
                    trouves += candidats(valeur)
        for texte in trouves:
            # Un modèle fait uniquement de valeurs ({0}) ou trop court n'a rien à traduire.
            lettres = re.sub(r"\{\d+\}", "", texte)
            # Balises HTML et notes de modèles Excel (« - … ») relèvent des exports.
            if "<" in texte or texte[:1] in "- \n":
                continue
            if " " in lettres.strip() and re.search(r"[A-Za-zÀ-ÿ]{3,}", lettres) and FRANCAIS.search(lettres):
                textes.add(texte)

print(json.dumps(sorted(textes), ensure_ascii=False, indent=1))
