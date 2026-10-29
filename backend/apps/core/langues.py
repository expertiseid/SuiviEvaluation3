"""
Langue des fichiers produits par le serveur : rapports (PDF, Word), exports Excel et modèles
d'import. Le texte est écrit en français dans le code ; il est traduit au moment où le fichier
est produit, dans la langue de l'interface de la personne qui le télécharge.

- Les vues qui produisent un fichier sont décorées par @dans_la_langue_demandee : la langue
  (en-tête Accept-Language envoyé par l'interface, ou ?langue=) est active le temps de la vue.
  Ailleurs (imports, messages d'erreur), la langue reste le français : l'interface traduit
  elle-même les messages du serveur.
- Les textes sont traduits par le catalogue apps/core/i18n/{langue}.json (clé = texte
  français exact ; les valeurs insérées y sont des {0}, {1}…), complété par les corrections
  de l'Administrateur (écran Langues). Mise à jour : manage.py extraire_textes_fichiers.
- À l'import, un fichier rempli dans une autre langue est ramené au français par
  apps.core.vocabulaire.ramener_classeur, à l'aide des mêmes catalogues.
"""
import functools
import html
import json
import re
import time
import unicodedata
from contextlib import contextmanager
from contextvars import ContextVar
from pathlib import Path

LANGUES_TRADUITES = ("en", "ar", "es", "de")
DOSSIER_CATALOGUES = Path(__file__).parent / "i18n"

_langue = ContextVar("langue_fichiers", default="fr")
# Textes déjà traduits dans le code (par v()) pendant la production d'un fichier : la traduction
# du document entier les laisse tels quels. Sinon « Prénom » → « Nombre » (espagnol) serait
# retraduit comme le mot français « Nombre » → « Número ».
_deja_traduits = ContextVar("deja_traduits", default=None)


def langue_active() -> str:
    return _langue.get()


@contextmanager
def en_langue(code):
    """Active une langue le temps d'un bloc (français si le code est inconnu)."""
    jeton = _langue.set(code if code in LANGUES_TRADUITES else "fr")
    jeton_deja = _deja_traduits.set(set())
    try:
        yield
    finally:
        _deja_traduits.reset(jeton_deja)
        _langue.reset(jeton)


def langue_demandee(request) -> str:
    """?langue=xx, sinon la première langue de l'en-tête Accept-Language, sinon le français."""
    params = getattr(request, "query_params", None) or getattr(request, "GET", {})
    code = (params.get("langue") or "").strip().lower()
    if not code:
        entete = request.META.get("HTTP_ACCEPT_LANGUAGE", "")
        code = entete.split(",")[0].split(";")[0].split("-")[0].strip().lower()
    return code if code in LANGUES_TRADUITES else "fr"


def dans_la_langue_demandee(vue):
    """Décorateur d'une vue (fonction ou méthode) qui produit un fichier."""

    @functools.wraps(vue)
    def envelopper(*args, **kwargs):
        request = next((a for a in args if hasattr(a, "META")), None)
        with en_langue(langue_demandee(request) if request is not None else "fr"):
            return vue(*args, **kwargs)

    return envelopper


# --- Catalogues --------------------------------------------------------------------------

_catalogues: dict = {}
_corrections = {"valeurs": {}, "instant": 0.0, "fusionnes": {}}
DUREE_CACHE_SECONDES = 10


def _catalogue_livre(langue) -> dict:
    if langue not in _catalogues:
        chemin = DOSSIER_CATALOGUES / f"{langue}.json"
        _catalogues[langue] = json.loads(chemin.read_text(encoding="utf-8")) if chemin.exists() else {}
    return _catalogues[langue]


def _corrections_admin(langue) -> dict:
    """
    Corrections de l'Administrateur (écran Langues), avec un court cache : une correction
    s'applique aux fichiers au plus tard DUREE_CACHE_SECONDES après, dans chaque processus.
    """
    if time.monotonic() - _corrections["instant"] > DUREE_CACHE_SECONDES:
        from .models import TraductionCorrigee

        valeurs = {}
        for code, source, traduction in TraductionCorrigee.objects.values_list("langue", "source", "traduction"):
            valeurs.setdefault(code, {})[source] = traduction
        _corrections.update(valeurs=valeurs, instant=time.monotonic(), fusionnes={})
    return _corrections["valeurs"].get(langue, {})


def catalogue(langue) -> dict:
    """Catalogue livré, complété par les corrections de l'Administrateur."""
    corrections = _corrections_admin(langue)
    if not corrections:
        return _catalogue_livre(langue)
    fusionnes = _corrections["fusionnes"]
    if langue not in fusionnes:
        fusionnes[langue] = {**_catalogue_livre(langue), **corrections}
    return fusionnes[langue]


# --- Traduction --------------------------------------------------------------------------

_modeles: dict = {}


def _modele_assez_precis(fixe: str) -> bool:
    if re.search(r"\S+\s+\S+", fixe.strip()) and len(fixe) >= 10:
        return True
    return bool(re.search(r"[^\W\d_]{3,}", fixe)) and bool(re.search(r"[:—(]|\b(et|au)\b", fixe))


def _modeles_de(langue):
    """
    Clés à valeurs insérées (« Généré le {0} ») compilées en expressions. Pour ne pas capturer
    une donnée quelconque (« Projet {0} » transformerait « Projet Eau potable »), il faut assez de
    texte fixe : deux mots et dix caractères (règle de traduireSelonModele, frontend), ou un mot
    accompagné d'une ponctuation ou d'une tournure qui ne se trouve pas dans un nom
    (« Unité : {0} », « du {0} au {1} », « {0} et plus »).
    """
    if langue not in _modeles:
        modeles = []
        for cle in _catalogue_livre(langue):
            if not re.search(r"\{\d+\}", cle) or not _modele_assez_precis(re.sub(r"\{\d+\}", "", cle)):
                continue
            ordre, morceaux = [], []
            for morceau in re.split(r"(\{\d+\})", cle):
                repere = re.fullmatch(r"\{(\d+)\}", morceau)
                if repere:
                    ordre.append(int(repere.group(1)))
                    morceaux.append(r"([\s\S]+?)")
                else:
                    morceaux.append(re.escape(morceau))
            modeles.append((re.compile("^" + "".join(morceaux) + "$"), ordre, cle))
        # Les plus longs (donc les plus précis) d'abord.
        modeles.sort(key=lambda m: -len(m[2]))
        _modeles[langue] = modeles
    return _modeles[langue]


def _completer(modele: str, valeurs: dict) -> str:
    return re.sub(r"\{(\d+)\}", lambda m: valeurs.get(int(m.group(1)), ""), modele)


def traduire(texte, langue=None):
    """Texte français → langue active (ou `langue`) ; inchangé s'il est absent du catalogue."""
    langue = langue or langue_active()
    if langue == "fr" or not isinstance(texte, str) or not texte.strip():
        return texte
    cat = catalogue(langue)
    if texte in cat:
        return cat[texte]
    # Espaces autour du texte (morceaux de phrases dans le HTML) : gardés tels quels.
    debut = texte[: len(texte) - len(texte.lstrip())]
    fin = texte[len(texte.rstrip()):]
    coeur = texte.strip()
    if coeur in cat:
        return debut + cat[coeur] + fin
    for motif, ordre, cle in _modeles_de(langue):
        m = motif.match(coeur)
        if m:
            valeurs = {n: m.group(i + 1) for i, n in enumerate(ordre)}
            return debut + _completer(cat.get(cle, cle), valeurs) + fin
    return texte


def traduire_texte_fixe(texte):
    """Traduction d'un texte du code (v()), notée pour ne pas être retraduite avec le document."""
    traduit = traduire(texte)
    deja = _deja_traduits.get()
    if deja is not None and isinstance(traduit, str) and traduit != texte:
        deja.add(traduit.strip())
    return traduit


def _a_traduire(texte) -> bool:
    deja = _deja_traduits.get()
    return isinstance(texte, str) and not (deja and texte.strip() in deja)


def traduire_modele(modele: str, *valeurs) -> str:
    """Texte à valeurs insérées (« Par {0} ») : traduit, puis complété avec les valeurs."""
    return _completer(traduire(modele), {i: str(x) for i, x in enumerate(valeurs)})


def formes(texte: str) -> set:
    """Le texte français et ses traductions dans toutes les langues (pour reconnaître une saisie)."""
    return {texte} | {catalogue(langue).get(texte, texte) for langue in LANGUES_TRADUITES}


def normaliser(texte) -> str:
    """Comparaison tolérante : sans accents ni casse, tirets = espaces, espaces simples."""
    sans_accents = "".join(c for c in unicodedata.normalize("NFD", str(texte)) if unicodedata.category(c) != "Mn")
    return " ".join(sans_accents.replace("-", " ").replace("’", "'").lower().split())


_inverse = {"index": None, "instant": None}


def vers_francais(saisie):
    """
    Saisie d'une cellule dans une autre langue (« In progress », « Ja ») → texte français du
    catalogue (« En cours », « Oui ») ; inchangée si elle n'y figure pas. Comparaison tolérante
    (accents, casse, espaces).
    """
    if not isinstance(saisie, str) or not saisie.strip():
        return saisie
    for langue in LANGUES_TRADUITES:
        catalogue(langue)  # rafraîchit les corrections si besoin
    if _inverse["index"] is None or _inverse["instant"] != _corrections["instant"]:
        index = {}
        for langue in LANGUES_TRADUITES:
            for source, traduction in catalogue(langue).items():
                index.setdefault(normaliser(traduction), source)
        _inverse.update(index=index, instant=_corrections["instant"])
    return _inverse["index"].get(normaliser(saisie), saisie)


# --- Fichiers ----------------------------------------------------------------------------

_BALISE = re.compile(r"(<[^>]*>)")
_BLOC_NON_TEXTE = re.compile(r"(<style[^>]*>.*?</style>|<script[^>]*>.*?</script>)", re.IGNORECASE | re.DOTALL)


def traduire_html(contenu: str) -> str:
    """
    Traduit le texte visible d'un document HTML (rapport PDF ou Word) : chaque morceau de texte
    entre deux balises, et les attributs title/alt. En arabe, le document s'écrit de droite à gauche.
    """
    langue = langue_active()
    if langue == "fr" or not contenu:
        return contenu

    def texte(morceau):
        brut = html.unescape(morceau)
        if not _a_traduire(brut):
            return morceau
        # Espaces et retours à la ligne du code HTML : sans effet à l'affichage, normalisés
        # comme à l'extraction des textes (le catalogue n'en a pas).
        coeur = re.sub(r"\s+", " ", brut.strip())
        traduit = traduire(coeur)
        if traduit == coeur:
            return morceau
        debut, fin = brut[: len(brut) - len(brut.lstrip())], brut[len(brut.rstrip()):]
        return debut + html.escape(traduit, quote=False) + fin

    def balise(b):
        return re.sub(
            r'(\s(?:title|alt)=")([^"]*)(")',
            lambda m: m.group(1) + html.escape(traduire(html.unescape(m.group(2)))) + m.group(3),
            b,
        )

    def style(bloc):
        # Seul texte des styles : le pied de page des rapports (« Page 3 / 5 »).
        return bloc.replace('content: "Page "', f'content: "{traduire("Page")} "')

    # Blocs <style> et <script> : rangs impairs du découpage.
    blocs = _BLOC_NON_TEXTE.split(contenu)
    traduit = "".join(
        style(bloc) if i % 2 else "".join(balise(p) if p.startswith("<") else texte(p) for p in _BALISE.split(bloc) if p)
        for i, bloc in enumerate(blocs)
    )
    if langue == "ar":
        if re.search(r"<html[\s>]", traduit, re.IGNORECASE):
            traduit = re.sub(r"<html(?=[\s>])", '<html dir="rtl" lang="ar"', traduit, count=1, flags=re.IGNORECASE)
        else:
            traduit = f'<div dir="rtl">{traduit}</div>'
    return traduit


def titre_feuille(titre: str) -> str:
    """Nom de feuille accepté par Excel : sans [ ] : * ? / \\, 31 caractères au plus."""
    return re.sub(r"[\[\]:*?/\\]", " ", titre)[:31]


def traduire_figure(figure):
    """
    Traduit les textes posés sur une figure matplotlib (carte imprimée). En arabe, les lettres
    sont liées et le texte remis dans l'ordre d'affichage, ce que matplotlib ne fait pas ; sans
    les bibliothèques nécessaires, la carte reste en français plutôt qu'illisible.
    """
    from matplotlib.text import Text

    langue = langue_active()
    if langue == "fr":
        return figure
    preparer = str
    if langue == "ar":
        try:
            import arabic_reshaper
            from bidi import get_display
        except ImportError:
            return figure

        def preparer(texte):
            return "\n".join(get_display(arabic_reshaper.reshape(ligne)) for ligne in texte.split("\n"))

    for objet in figure.findobj(Text):
        contenu = objet.get_text()
        if not contenu.strip() or not _a_traduire(contenu):
            continue
        traduit = traduire(contenu)
        if traduit == contenu and "\n" in contenu:
            traduit = "\n".join(traduire(ligne) for ligne in contenu.split("\n"))
        objet.set_text(preparer(traduit))
    return figure


def traduire_classeur(wb, feuilles=None, garder=None):
    """
    Traduit les textes d'un classeur Excel : noms de feuilles, cellules, commentaires et listes
    déroulantes. En arabe, les feuilles s'affichent de droite à gauche. `feuilles` limite aux
    feuilles nommées ; `garder(feuille, cellule)` désigne les cellules à laisser telles quelles.
    """
    langue = langue_active()
    if langue == "fr":
        return wb
    for feuille in list(wb.worksheets):
        if feuilles is not None and feuille.title not in feuilles:
            continue
        for ligne in feuille.iter_rows():
            for cellule in ligne:
                if garder is not None and garder(feuille, cellule):
                    continue
                if isinstance(cellule.value, str) and not cellule.value.startswith("=") and _a_traduire(cellule.value):
                    cellule.value = traduire(cellule.value)
                if cellule.comment is not None:
                    cellule.comment.text = traduire(cellule.comment.text)
        for validation in feuille.data_validations.dataValidation:
            formule = validation.formula1 or ""
            if validation.type == "list" and formule.startswith('"') and formule.endswith('"'):
                choix = [traduire(c) for c in formule[1:-1].split(",")]
                validation.formula1 = '"' + ",".join(c.replace(",", " ") for c in choix) + '"'
        titre = traduire(feuille.title) if _a_traduire(feuille.title) else feuille.title
        if titre != feuille.title:
            feuille.title = titre_feuille(titre)
        if langue == "ar":
            feuille.sheet_view.rightToLeft = True
    return wb
