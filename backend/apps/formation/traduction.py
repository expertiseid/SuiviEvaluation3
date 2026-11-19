"""
Traduction du contenu du cours (apps.formation.contenu) dans la langue de l'utilisateur : un catalogue par
langue (apps/formation/i18n/{langue}.json, texte français → traduction), appliqué à tout ce qui est envoyé à
l'écran. Les codes, icônes, images et réglages techniques ne sont pas traduits ; un texte absent du catalogue
reste en français (jamais vide).

Après une modification de contenu.py : `python -m apps.formation.traduction` liste les textes à traduire
(le test test_traductions_completes le vérifie aussi).
"""
import json
from functools import lru_cache
from pathlib import Path

DOSSIER = Path(__file__).resolve().parent / "i18n"
# Clés techniques, jamais affichées telles quelles.
NON_TRADUITS = {"code", "icone", "src", "type", "chapitre", "bonne", "duree", "debut", "fin"}


@lru_cache(maxsize=None)
def catalogue(langue: str) -> dict:
    chemin = DOSSIER / f"{langue}.json"
    return json.loads(chemin.read_text(encoding="utf-8")) if chemin.exists() else {}


def textes(objet, cle=None):
    """Tous les textes affichés d'un contenu (modules, leçons, blocs, quiz…)."""
    if isinstance(objet, dict):
        for k, valeur in objet.items():
            if k not in NON_TRADUITS:
                yield from textes(valeur, k)
    elif isinstance(objet, (list, tuple)):
        for valeur in objet:
            yield from textes(valeur, cle)
    elif isinstance(objet, str) and objet.strip():
        yield objet


def traduire_contenu(objet, langue: str | None = None):
    """Copie du contenu dans la langue active (ou `langue`)."""
    from apps.core.langues import langue_active

    langue = langue or langue_active()
    if langue == "fr":
        return objet
    cat = catalogue(langue)

    def traduire(o, cle=None):
        if isinstance(o, dict):
            return {k: (valeur if k in NON_TRADUITS else traduire(valeur, k)) for k, valeur in o.items()}
        if isinstance(o, (list, tuple)):
            return [traduire(valeur, cle) for valeur in o]
        if isinstance(o, str):
            return cat.get(o) or o
        return o

    return traduire(objet)


def manquants(langue: str) -> list[str]:
    from .contenu import MODULES

    cat = catalogue(langue)
    return sorted({t for t in textes(MODULES) if not cat.get(t)})


if __name__ == "__main__":
    from apps.core.langues import LANGUES_TRADUITES

    for langue in LANGUES_TRADUITES:
        print(langue, len(manquants(langue)), "texte(s) à traduire")
