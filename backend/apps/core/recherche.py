"""
Recherche dans toute la plateforme (barre de recherche du menu) : projets, activités, indicateurs, bénéficiaires,
documents stratégiques et leurs éléments, documents, dossiers de plaintes, zones.

Chaque catégorie part de la liste que l'utilisateur verrait dans son onglet (get_queryset de la vue, qui applique
projets visibles, éléments masqués, habilitations des plaintes…) ; un onglet masqué pour lui n'est pas cherché.
"""
from django.db.models import CharField, Func, Q, Value
from django.db.models.functions import Cast, Lower
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .modules import MASQUE, acces_module

PAR_CATEGORIE = 6
LONGUEUR_MIN = 2


def _liste(classe, request):
    """Ce que l'utilisateur verrait dans la liste de cette vue (mêmes règles de visibilité)."""
    vue = classe()
    vue.request, vue.action, vue.kwargs, vue.format_kwarg = request, "list", {}, None
    return vue.get_queryset()


# Sans l'extension « unaccent » : les accents sont retirés des deux côtés (base et texte cherché).
AVEC_ACCENTS = "àâäáãåçéèêëíìîïñóòôöõúùûüýÿœæ"
SANS_ACCENTS = "aaaaaaceeeeiiiinooooouuuuyyoa"


def _sans_accents(texte: str) -> str:
    return texte.lower().translate(str.maketrans(AVEC_ACCENTS, SANS_ACCENTS))


def _cherche(queryset, champs, mots):
    """Chaque mot cherché doit se trouver dans l'un des champs (ordre libre, sans accents ni majuscules)."""
    alias = {f"_r{i}": Func(Lower(Cast(champ, CharField())), Value(AVEC_ACCENTS), Value(SANS_ACCENTS), function="translate")
             for i, champ in enumerate(champs)}
    queryset = queryset.alias(**alias)
    for mot in mots:
        filtre = Q()
        for nom in alias:
            filtre |= Q(**{f"{nom}__contains": _sans_accents(mot)})
        queryset = queryset.filter(filtre)
    return queryset


def _categories():
    from apps.beneficiaries.views import BeneficiaireViewSet
    from apps.documents.views import DocumentViewSet
    from apps.geo.views import ZoneViewSet
    from apps.indicators.views import IndicateurViewSet
    from apps.plaintes.views import DossierViewSet
    from apps.projects.views import ActiviteViewSet, ProjetViewSet
    from apps.strategy.views import CadreStrategiqueViewSet, ElementStrategiqueViewSet

    return [
        # (clé, module, vue, champs cherchés, ligne de résultat)
        ("projets", "/projets", ProjetViewSet, ("nom", "code"),
         lambda p: {"titre": p.nom, "detail": p.code, "lien": f"/projets/{p.id}"}),
        ("activites", "/projets", ActiviteViewSet, ("libelle", "code_activite"),
         lambda a: {"titre": a.libelle, "detail": " · ".join(filter(None, [a.code_activite, a.projet.nom])),
                    "lien": f"/projets/{a.projet_id}"}),
        ("indicateurs", "/indicateurs", IndicateurViewSet, ("libelle",),
         lambda i: {"titre": i.libelle, "detail": i.unite, "lien": f"/indicateurs/{i.id}"}),
        ("beneficiaires", "/beneficiaires", BeneficiaireViewSet, ("nom", "prenom", "identifiant", "telephone"),
         lambda b: {"titre": f"{b.nom} {b.prenom}".strip(), "detail": " · ".join(filter(None, [b.identifiant, b.telephone])),
                    "lien": f"/beneficiaires/{b.id}"}),
        ("strategies", "/strategie", CadreStrategiqueViewSet, ("nom", "code"),
         lambda c: {"titre": c.nom, "detail": c.code, "document": c.id, "type_document": c.type_document_id}),
        ("elements", "/strategie", ElementStrategiqueViewSet, ("nom", "code"),
         lambda e: {"titre": e.nom, "detail": " · ".join(filter(None, [e.type_niveau.nom_niveau, e.code])),
                    "document": e.type_niveau.cadre_strategique_id,
                    "type_document": e.type_niveau.cadre_strategique.type_document_id}),
        ("documents", "/documents", DocumentViewSet, ("nom", "description"),
         lambda d: {"titre": d.nom, "detail": d.type_document, "lien": f"/projets/{d.projet_id}" if d.projet_id else "/documents"}),
        ("plaintes", "/plaintes", DossierViewSet, ("numero",),
         lambda d: {"titre": d.numero, "detail": d.get_statut_display(), "lien": f"/plaintes/dossiers/{d.id}"}),
        ("zones", "/zones-administratives", ZoneViewSet, ("nom", "code"),
         lambda z: {"titre": z.nom, "detail": z.niveau_administratif.nom_niveau if z.niveau_administratif_id else "",
                    "lien": "/zones-administratives"}),
    ]


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def rechercher(request):
    """?q=texte : jusqu'à 6 résultats par catégorie, insensibles aux accents et à la casse."""
    texte = (request.query_params.get("q") or "").strip()[:100]
    mots = [m for m in texte.split() if m]
    if len(texte) < LONGUEUR_MIN:
        return Response({"groupes": []})
    groupes = []
    for cle, module, vue, champs, ligne in _categories():
        if acces_module(request.user, module) == MASQUE:
            continue
        objets = list(_cherche(_liste(vue, request), champs, mots).distinct()[:PAR_CATEGORIE])
        if objets:
            groupes.append({"cle": cle, "resultats": [{"id": o.pk, **ligne(o)} for o in objets]})
    return Response({"groupes": groupes})
