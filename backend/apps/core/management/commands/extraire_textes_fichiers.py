"""
Relève les textes des fichiers produits par le serveur (rapports, exports, modèles d'import)
pour les traduire : écrit apps/core/i18n/sources.json et indique, pour chaque langue, les
textes encore sans traduction dans apps/core/i18n/{langue}.json.

Sont relevés, dans les modules listés dans MODULES : les chaînes du code (un morceau de texte
par balise pour le HTML ; les valeurs insérées des f-strings deviennent {0}, {1}…), ainsi que
les libellés des choix de tous les modèles (statuts, types…), affichés dans les fichiers.

Usage : docker compose exec backend python manage.py extraire_textes_fichiers
"""
import ast
import html
import json
import re
from pathlib import Path

from django.apps import apps as registre
from django.conf import settings
from django.core.management.base import BaseCommand

from apps.core.langues import DOSSIER_CATALOGUES, LANGUES_TRADUITES, normaliser
from apps.core.vocabulaire import libelles_des_modeles

MODULES = [
    "beneficiaries/services/carte.py",
    "beneficiaries/services/carte_officielle.py",
    "beneficiaries/services/export_excel.py",
    "beneficiaries/services/import_excel.py",
    "beneficiaries/services/variables.py",
    "indicators/exports.py",
    "indicators/import_excel.py",
    "planification/services.py",
    "projects/import_excel.py",
    "strategy/import_chaine.py",
    "projects/taux.py",
    "reports/cadre_logique.py",
    "reports/financier.py",
    "reports/risques.py",
    "reports/suivi_strategique.py",
    "strategy/services.py",
    "suivi/canevas.py",
    "suivi/export_excel.py",
    "suivi/export_pdf.py",
    "suivi/export_periode.py",
]

# Textes absents du code tels quels : valeurs que l'utilisateur tape dans un modèle (à reconnaître
# dans toutes les langues, voir vers_francais) et pied de page des rapports (dans leurs styles).
# Mots seuls en minuscules (« femmes ») ou en majuscules sans accent (« NOTE ») : écartés du relevé,
# qui les prend pour des clés ou des codes.
# Libellés de la carte imprimée définis dans apps/beneficiaries/views.py.
TEXTES_SUPPLEMENTAIRES = [
    # Préfixe des colonnes d'attributs et champs qu'un attribut peut remplir (apps.projects.attributs).
    "Attribut", "Description", "Sources de vérification", "Hypothèses",
    "Aucun", "Page", "femmes", "hommes", "Carte", "{0} par {1}", "SITUATION", "PROJECTION", "NOTE",
    "Projets", "Bénéficiaires", "Budget", "Exécution physique", "Exécution financière", "Bénéf.", "Physique", "Financier",
]

_BLOC_NON_TEXTE = re.compile(r"<(style|script)[^>]*>.*?</\1>", re.IGNORECASE | re.DOTALL)
_BALISE = re.compile(r"<[^>]*>")
_ATTRIBUT = re.compile(r'\s(?:title|alt)="([^"]*)"')


def _produit_du_html(expression) -> bool:
    """Valeur insérée qui contient elle-même des balises (« <br/>… », une barre de progression)."""
    return any(
        isinstance(n, ast.Constant) and isinstance(n.value, str) and "<" in n.value for n in ast.walk(expression)
    ) or any(isinstance(n, ast.Name) and n.id.startswith(("_barre", "badge", "html")) for n in ast.walk(expression))


def _modele(noeud) -> str:
    """
    Chaîne ou f-string → texte, les valeurs insérées devenant {0}, {1}… Une valeur qui produit
    du HTML coupe le texte comme une balise : le texte affiché s'arrête là.
    """
    if isinstance(noeud, ast.Constant):
        return noeud.value
    morceaux, n = [], 0
    for partie in noeud.values:
        if isinstance(partie, ast.Constant):
            morceaux.append(str(partie.value))
        elif _produit_du_html(partie.value):
            morceaux.append("<valeur/>")
        else:
            morceaux.append("{%d}" % n)
            n += 1
    return "".join(morceaux)


def _renumeroter(texte: str) -> str:
    """{3} … {5} → {0} … {1} : chaque morceau de texte est une clé à part entière."""
    ordre = {}
    return re.sub(r"\{\d+\}", lambda m: "{%d}" % ordre.setdefault(m.group(0), len(ordre)), texte)


def _est_un_texte(texte: str) -> bool:
    """Écarte ce qui n'est pas du texte affiché : codes, identifiants, styles, formats, adresses."""
    t = texte.strip()
    sans_reperes = re.sub(r"\{\d+\}", "", t).strip()
    if not re.search(r"[A-Za-zÀ-ÿ]{2,}", sans_reperes):
        return False
    if re.fullmatch(r"[a-z0-9_.\-/]+", sans_reperes) or re.fullmatch(r"[A-Z0-9_]+", sans_reperes):
        return False  # identifiant, clé, code (EN_COURS)
    if re.search(r"^[\w\-]+\s*:\s*[^:]+;", t) or re.search(r"[{}]\s*$", sans_reperes) or "%" in t and re.search(r"%[a-zA-Z]", t):
        return False  # CSS, format de date
    if re.match(r"^(https?:|/|#[0-9a-fA-F]{3,8}\b|\.|@)", t):
        return False
    if "\\" in t or "[^" in t or re.fullmatch(r"[\w-]+:\s*\{\d+\}", t) or t in ("User-Agent",):
        return False  # expression régulière, en-tête HTTP, code technique (EPSG:{0})
    if '="' in t or t in ("Arial", "Calibri", "DejaVu Sans", "Liberation Sans", "Agg", "Mn", "shapeName", "#texte"):
        return False  # attribut HTML, police, réglage technique
    return True


def _textes_du_module(chemin: Path) -> set:
    arbre = ast.parse(chemin.read_text(encoding="utf-8"))
    # Morceaux fixes d'une f-string : relevés avec la f-string entière, pas seuls.
    morceaux_de_fstring = {id(p) for n in ast.walk(arbre) if isinstance(n, ast.JoinedStr) for p in n.values}
    docstrings = {
        id(n.body[0].value)
        for n in ast.walk(arbre)
        if isinstance(n, (ast.Module, ast.FunctionDef, ast.ClassDef, ast.AsyncFunctionDef))
        and n.body and isinstance(n.body[0], ast.Expr) and isinstance(n.body[0].value, ast.Constant)
    }
    textes = set()
    for noeud in ast.walk(arbre):
        if id(noeud) in morceaux_de_fstring or id(noeud) in docstrings:
            continue
        if not (isinstance(noeud, ast.JoinedStr) or (isinstance(noeud, ast.Constant) and isinstance(noeud.value, str))):
            continue
        brut = _modele(noeud)
        if "<" in brut and ">" in brut:
            sans_blocs = _BLOC_NON_TEXTE.sub(" ", brut)
            candidats = [*_BALISE.split(sans_blocs), *_ATTRIBUT.findall(sans_blocs)]
            # Comme à la traduction (apps.core.langues.traduire_html) : espaces du HTML normalisés.
            candidats = [re.sub(r"\s+", " ", html.unescape(c)) for c in candidats]
        else:
            candidats = [brut]
        for candidat in candidats:
            propre = _renumeroter(candidat.strip())
            if _est_un_texte(propre):
                textes.add(propre)
    return textes


def _libelles_des_choix() -> set:
    libelles = set()
    for modele in registre.get_models():
        if modele._meta.app_label in ("admin", "auth", "contenttypes", "sessions") or modele.__name__.startswith("Historical"):
            continue
        for champ in modele._meta.get_fields():
            for _, libelle in getattr(champ, "choices", None) or []:
                if isinstance(libelle, str) and _est_un_texte(libelle):
                    libelles.add(libelle.strip())
    return libelles


class Command(BaseCommand):
    help = "Relève les textes des rapports, exports et modèles d'import à traduire."

    def handle(self, *args, **options):
        racine = Path(settings.BASE_DIR) / "apps"
        from apps.geo.services.synthese import COURTS

        # Libellés courts des indicateurs par zone : imprimés sur la carte (légende, tableau).
        textes = _libelles_des_choix() | set(TEXTES_SUPPLEMENTAIRES) | set(COURTS.values())
        for module in MODULES:
            textes |= _textes_du_module(racine / module)
        liste = sorted(textes)
        DOSSIER_CATALOGUES.mkdir(exist_ok=True)
        (DOSSIER_CATALOGUES / "sources.json").write_text(json.dumps(liste, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        self.stdout.write(f"{len(liste)} textes")
        for langue in LANGUES_TRADUITES:
            chemin = DOSSIER_CATALOGUES / f"{langue}.json"
            catalogue = json.loads(chemin.read_text(encoding="utf-8")) if chemin.exists() else {}
            manquants = [t for t in liste if t not in catalogue]
            self.stdout.write(f"{langue} : {len(liste) - len(manquants)} traduits, {len(manquants)} manquants")
            # Noms de feuilles et en-têtes des modèles : reconnus à l'import par leur traduction,
            # deux libellés différents ne doivent donc jamais se traduire pareil.
            vus = {}
            for libelle in sorted(libelles_des_modeles()):
                traduction = normaliser(catalogue.get(libelle, libelle))
                if traduction in vus and vus[traduction] != libelle:
                    self.stdout.write(f"  ⚠ même traduction pour « {vus[traduction]} » et « {libelle} »")
                vus.setdefault(traduction, libelle)
