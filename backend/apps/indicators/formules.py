"""
Indicateurs calculés par formule, sans programmer : l'organisation choisit des mesures dans un catalogue
(bénéficiaires, activités, dépenses, plaintes, un autre indicateur…), les restreint par des filtres (sexe,
âge, zone, période…), puis les combine dans une expression simple (A ÷ B × 100).

Formule enregistrée (Indicateur.formule, JSON) :
    {"termes": [{"code": "A", "mesure": "depenses", "filtres": {}},
                {"code": "B", "mesure": "beneficiaires", "filtres": {"sexe": "F"}}],
     "expression": "A / B"}

Garde-fous : l'expression n'accepte que les termes, des nombres, + − × ÷ et des parenthèses (lue par l'analyseur
de Python, jamais exécutée) ; on n'additionne ni ne soustrait des grandeurs de nature différente (des FCFA et
des personnes) ; une division par zéro donne « non calculable » ; les données sont celles du projet de
l'indicateur (ou de toute l'organisation pour un indicateur stratégique). Chaque terme coûte une ou deux requêtes.
"""
import ast
import datetime
from decimal import Decimal, InvalidOperation

from apps.core.vocabulaire import v

CODES = "ABCDEFGH"
LONGUEUR_MAX = 200

# Mesure → libellé, nature (pour le contrôle des additions) et filtres acceptés.
MESURES = {
    "beneficiaires": {"libelle": "Bénéficiaires uniques", "nature": "personnes",
                      "filtres": ("sexe", "age_min", "age_max", "statut_particulier", "zone", "statut_participation", "periode")},
    "menages": {"libelle": "Personnes des ménages des bénéficiaires", "nature": "personnes",
                "filtres": ("sexe", "zone", "periode")},
    "activites": {"libelle": "Activités de terrain", "nature": "activités", "filtres": ("statut_activite", "delai", "periode")},
    "depenses": {"libelle": "Dépenses (FCFA)", "nature": "FCFA", "filtres": ()},
    "budget": {"libelle": "Budget révisé (FCFA)", "nature": "FCFA", "filtres": ()},
    "engage": {"libelle": "Montant engagé (FCFA)", "nature": "FCFA", "filtres": ()},
    "plaintes": {"libelle": "Plaintes et retours enregistrés", "nature": "dossiers", "filtres": ("periode",)},
    "indicateur": {"libelle": "Valeur d'un autre indicateur", "nature": "indicateur", "filtres": ("indicateur", "variante")},
    "enquete": {"libelle": "Résultat d'une enquête", "nature": "indicateur",
                "filtres": ("enquete", "calcul_enquete", "colonne", "valeurs", "sous_groupe_colonne", "sous_groupe_valeur")},
}
CALCULS_ENQUETE = {"proportion": "Proportion (%)", "moyenne": "Moyenne", "total": "Total estimé"}
PERIODES = {"tout": "Depuis le début", "annee": "Cette année", "trimestre": "Ce trimestre", "12_mois": "12 derniers mois"}
VARIANTES = {"actuelle": "Valeur retenue", "derniere": "Dernière valeur saisie", "precedente": "Valeur saisie précédente"}
STATUTS_PARTICIPATION = {"EN_COURS": "En cours", "TERMINE": "A tout reçu", "ABANDON": "Abandon"}
STATUTS_ACTIVITE = {"NON_REALISEE": "Non réalisée", "EN_COURS": "En cours", "REALISEE": "Réalisée", "SUSPENDUE": "Suspendue",
                    "ANNULEE": "Annulée"}
DELAIS = {"en_retard": "En retard", "a_temps": "Terminées dans les délais"}

# Modèles prêts à copier.
MODELES = [
    {"titre": "Coût par bénéficiaire", "unite": "FCFA", "sens": "BAISSE",
     "formule": {"termes": [{"code": "A", "mesure": "depenses", "filtres": {}}, {"code": "B", "mesure": "beneficiaires", "filtres": {}}],
                 "expression": "A / B"}},
    {"titre": "Part de femmes parmi les bénéficiaires", "unite": "%", "sens": "HAUSSE",
     "formule": {"termes": [{"code": "A", "mesure": "beneficiaires", "filtres": {"sexe": "F"}},
                            {"code": "B", "mesure": "beneficiaires", "filtres": {}}], "expression": "A / B * 100"}},
    {"titre": "Activités terminées dans les délais", "unite": "%", "sens": "HAUSSE",
     "formule": {"termes": [{"code": "A", "mesure": "activites", "filtres": {"delai": "a_temps"}},
                            {"code": "B", "mesure": "activites", "filtres": {"statut_activite": "REALISEE"}}], "expression": "A / B * 100"}},
    {"titre": "Plaintes pour 1 000 bénéficiaires", "unite": "plaintes", "sens": "BAISSE",
     "formule": {"termes": [{"code": "A", "mesure": "plaintes", "filtres": {}}, {"code": "B", "mesure": "beneficiaires", "filtres": {}}],
                 "expression": "A / B * 1000"}},
    {"titre": "Taux d'abandon des bénéficiaires", "unite": "%", "sens": "BAISSE",
     "formule": {"termes": [{"code": "A", "mesure": "beneficiaires", "filtres": {"statut_participation": "ABANDON"}},
                            {"code": "B", "mesure": "beneficiaires", "filtres": {}}], "expression": "A / B * 100"}},
    {"titre": "Progression d'une période à l'autre", "unite": "%", "sens": "HAUSSE",
     "formule": {"termes": [{"code": "A", "mesure": "indicateur", "filtres": {"variante": "derniere"}},
                            {"code": "B", "mesure": "indicateur", "filtres": {"variante": "precedente"}}], "expression": "(A - B) / B * 100"}},
]


class FormuleInvalide(ValueError):
    pass


# --- Contrôle ----------------------------------------------------------------------------------------


def _arbre(expression):
    if not isinstance(expression, str) or not expression.strip():
        raise FormuleInvalide(v("Écrivez le calcul (ex : A / B * 100)."))
    if len(expression) > LONGUEUR_MAX:
        raise FormuleInvalide(v("Le calcul est trop long."))
    texte = expression.replace("×", "*").replace("÷", "/").replace("−", "-").replace(",", ".")
    try:
        return ast.parse(texte, mode="eval").body
    except SyntaxError:
        raise FormuleInvalide(v("Le calcul est mal écrit : vérifiez les opérations et les parenthèses."))


def _nature(noeud, natures):
    """Nature du résultat d'un nœud (None : simple nombre) ; refuse ce qui n'est pas autorisé."""
    if isinstance(noeud, ast.Constant) and isinstance(noeud.value, (int, float)) and not isinstance(noeud.value, bool):
        return None
    if isinstance(noeud, ast.Name):
        if noeud.id not in natures:
            raise FormuleInvalide(v("« {0} » n'est pas un terme de la formule.").format(noeud.id))
        return natures[noeud.id]
    if isinstance(noeud, ast.UnaryOp) and isinstance(noeud.op, (ast.USub, ast.UAdd)):
        return _nature(noeud.operand, natures)
    if isinstance(noeud, ast.BinOp) and isinstance(noeud.op, (ast.Add, ast.Sub, ast.Mult, ast.Div)):
        gauche, droite = _nature(noeud.left, natures), _nature(noeud.right, natures)
        if isinstance(noeud.op, (ast.Add, ast.Sub)):
            if gauche and droite and gauche != droite and "indicateur" not in (gauche, droite):
                raise FormuleInvalide(v("On ne peut pas additionner ou soustraire des {0} et des {1}.").format(v(gauche), v(droite)))
            return gauche or droite
        return "ratio" if gauche or droite else None
    raise FormuleInvalide(v("Seuls les termes, les nombres, + − × ÷ et les parenthèses sont permis."))


def valider(formule) -> dict:
    """Formule nettoyée, ou FormuleInvalide avec un message clair."""
    from .models import Indicateur

    if not isinstance(formule, dict) or not isinstance(formule.get("termes"), list) or not formule["termes"]:
        raise FormuleInvalide(v("Ajoutez au moins un terme."))
    if len(formule["termes"]) > len(CODES):
        raise FormuleInvalide(v("{0} termes au plus.").format(len(CODES)))
    termes, natures = [], {}
    for code, terme in zip(CODES, formule["termes"]):
        mesure = (terme or {}).get("mesure")
        if mesure not in MESURES:
            raise FormuleInvalide(v("Terme {0} : choisissez ce qu'il mesure.").format(code))
        filtres = {}
        for cle, valeur in ((terme.get("filtres") or {}).items()):
            if cle not in MESURES[mesure]["filtres"] or valeur in (None, "", []):
                continue
            filtres[cle] = valeur
        if mesure == "enquete":
            from .models import Enquete

            enquete = Enquete.objects.filter(pk=filtres.get("enquete") or 0).defer("donnees").first()
            if enquete is None or not filtres.get("colonne") or filtres.get("calcul_enquete") not in CALCULS_ENQUETE:
                raise FormuleInvalide(v("Terme {0} : choisissez l'enquête, le calcul et la colonne.").format(code))
            if filtres["colonne"] not in [c["nom"] for c in enquete.colonnes]:
                raise FormuleInvalide(v("Terme {0} : colonne inconnue dans cette enquête.").format(code))
            if isinstance(filtres.get("valeurs"), str):
                filtres["valeurs"] = [x.strip() for x in filtres["valeurs"].split(";") if x.strip()]
        if mesure == "indicateur":
            if not Indicateur.objects.filter(pk=filtres.get("indicateur") or 0, formule__isnull=True).exists():
                raise FormuleInvalide(v("Terme {0} : choisissez un indicateur à valeurs saisies.").format(code))
        for cle in ("age_min", "age_max"):
            if cle in filtres:
                try:
                    filtres[cle] = int(filtres[cle])
                except (TypeError, ValueError):
                    raise FormuleInvalide(v("Terme {0} : âge non valide.").format(code))
        termes.append({"code": code, "mesure": mesure, "filtres": filtres})
        natures[code] = MESURES[mesure]["nature"]
    _nature(_arbre(formule.get("expression")), natures)
    return {"termes": termes, "expression": formule["expression"].strip()}


# --- Calcul ------------------------------------------------------------------------------------------


def _debut_periode(periode, aujourd_hui):
    if periode == "annee":
        return aujourd_hui.replace(month=1, day=1)
    if periode == "trimestre":
        return aujourd_hui.replace(month=(aujourd_hui.month - 1) // 3 * 3 + 1, day=1)
    if periode == "12_mois":
        return aujourd_hui - datetime.timedelta(days=365)
    return None


def _il_y_a(aujourd_hui, ans):
    """La même date, `ans` années plus tôt (le 29 février devient le 28)."""
    try:
        return aujourd_hui.replace(year=aujourd_hui.year - ans)
    except ValueError:
        return aujourd_hui.replace(year=aujourd_hui.year - ans, day=28)


def _zones_dans(zone_id):
    from apps.geo.models import Zone

    resultat, a_voir = {int(zone_id)}, [int(zone_id)]
    while a_voir:
        a_voir = list(Zone.objects.filter(parent_id__in=a_voir).values_list("id", flat=True))
        resultat.update(a_voir)
    return resultat


def _mesurer(terme, projet_ids, aujourd_hui, cache):
    from apps.beneficiaries.models import ParticipationProjet
    from apps.plaintes.models import Dossier
    from apps.projects.models import Activite

    mesure, f = terme["mesure"], terme["filtres"]
    debut = _debut_periode(f.get("periode"), aujourd_hui)
    if mesure in ("beneficiaires", "menages"):
        qs = ParticipationProjet.objects.filter(projet_id__in=projet_ids)
        if f.get("sexe"):
            qs = qs.filter(beneficiaire__sexe=f["sexe"])
        if f.get("statut_participation"):
            qs = qs.filter(statut=f["statut_participation"])
        if f.get("statut_particulier"):
            qs = qs.filter(beneficiaire__statuts_particuliers=f["statut_particulier"])
        if f.get("zone"):
            qs = qs.filter(beneficiaire__zone_id__in=_zones_dans(f["zone"]))
        if debut:
            qs = qs.filter(date_inscription__gte=debut)
        if f.get("age_min") is not None:  # né au plus tard il y a age_min ans
            qs = qs.filter(beneficiaire__date_naissance__lte=_il_y_a(aujourd_hui, f["age_min"]))
        if f.get("age_max") is not None:  # pas encore age_max + 1 ans
            qs = qs.filter(beneficiaire__date_naissance__gt=_il_y_a(aujourd_hui, f["age_max"] + 1))
        if mesure == "beneficiaires":
            return Decimal(qs.values("beneficiaire_id").distinct().count())
        tailles = dict(qs.values_list("beneficiaire_id", "beneficiaire__taille_menage"))
        return Decimal(sum(t or 0 for t in tailles.values()))
    if mesure == "activites":
        qs = Activite.objects.filter(projet_id__in=projet_ids, enfants__isnull=True)
        if f.get("statut_activite"):
            qs = qs.filter(statut=f["statut_activite"])
        if f.get("delai") == "a_temps":
            qs = qs.filter(statut=Activite.Statut.REALISEE, date_fin_reelle__isnull=False, date_fin__isnull=False)
            return Decimal(sum(1 for fin, reelle in qs.values_list("date_fin", "date_fin_reelle") if reelle <= fin))
        if f.get("delai") == "en_retard":
            qs = qs.filter(date_fin__lt=aujourd_hui).exclude(statut=Activite.Statut.REALISEE)
        if debut:
            qs = qs.filter(date_fin__gte=debut, date_fin__lte=aujourd_hui)
        return Decimal(qs.count())
    if mesure in ("depenses", "budget", "engage"):
        if "finances" not in cache:
            from apps.projects.finances import finances

            cache["finances"] = finances(projet_ids, aujourd_hui=aujourd_hui)
        return Decimal(cache["finances"][{"depenses": "depense", "budget": "budget_revise", "engage": "engage"}[mesure]])
    if mesure == "plaintes":
        qs = Dossier.objects.filter(projet_id__in=projet_ids)
        if debut:
            qs = qs.filter(date_reception__gte=debut)
        return Decimal(qs.count())
    if mesure == "enquete":
        from .enquetes import EnqueteInvalide, estimer
        from .models import Enquete

        enquete = Enquete.objects.get(pk=f["enquete"])
        domaine = (f["sous_groupe_colonne"], f["sous_groupe_valeur"]) if f.get("sous_groupe_colonne") and f.get("sous_groupe_valeur") else None
        try:
            resultats = estimer(enquete, f["calcul_enquete"], f["colonne"], f.get("valeurs"), domaine=domaine)["resultats"]
        except EnqueteInvalide:
            return None
        if not resultats:
            return None
        cache.setdefault("marges", {})[terme["code"]] = resultats[0]["marge"]
        return Decimal(str(resultats[0]["estimation"]))
    if mesure == "indicateur":
        from .models import Indicateur
        from .services import valeur_actuelle

        indicateur = Indicateur.objects.get(pk=f["indicateur"])
        variante = f.get("variante", "actuelle")
        if variante == "actuelle":
            return valeur_actuelle(indicateur)
        valeurs = list(indicateur.valeurs.order_by("-periode_fin", "-id").values_list("valeur_realisee", flat=True)[:2])
        rang = 0 if variante == "derniere" else 1
        return valeurs[rang] if len(valeurs) > rang else None
    return None


class _NonCalculable(Exception):
    pass


def _calculer(noeud, valeurs):
    if isinstance(noeud, ast.Constant):
        return Decimal(str(noeud.value))
    if isinstance(noeud, ast.Name):
        valeur = valeurs[noeud.id]
        if valeur is None:
            raise _NonCalculable(v("{0} n'a pas de valeur").format(noeud.id))
        return Decimal(valeur)
    if isinstance(noeud, ast.UnaryOp):
        x = _calculer(noeud.operand, valeurs)
        return -x if isinstance(noeud.op, ast.USub) else x
    gauche, droite = _calculer(noeud.left, valeurs), _calculer(noeud.right, valeurs)
    if isinstance(noeud.op, ast.Add):
        return gauche + droite
    if isinstance(noeud.op, ast.Sub):
        return gauche - droite
    if isinstance(noeud.op, ast.Mult):
        return gauche * droite
    if not droite:
        raise _NonCalculable(v("division par zéro"))
    return gauche / droite


def projets_de(indicateur, projet_ids_visibles=None):
    """Projets dont les données alimentent la formule : celui de l'indicateur, sinon toute l'organisation."""
    from apps.projects.models import Projet

    projet = indicateur.projet_rattache if indicateur is not None else None
    if projet is not None:
        return [projet.id]
    ids = Projet.objects.values_list("id", flat=True)
    return list(ids.filter(id__in=projet_ids_visibles) if projet_ids_visibles is not None else ids)


def evaluer(formule, projet_ids, aujourd_hui=None) -> dict:
    """{"valeur": Decimal | None, "termes": {code: valeur}, "non_calculable": raison | None}."""
    aujourd_hui = aujourd_hui or datetime.date.today()
    formule = valider(formule)
    cache = {}
    valeurs = {t["code"]: _mesurer(t, projet_ids, aujourd_hui, cache) for t in formule["termes"]}
    try:
        resultat = _calculer(_arbre(formule["expression"]), valeurs)
        valeur, raison = resultat.quantize(Decimal("0.01")), None
    except _NonCalculable as exc:
        valeur, raison = None, str(exc)
    except InvalidOperation:
        valeur, raison = None, v("résultat trop grand")
    return {"valeur": valeur, "termes": valeurs, "non_calculable": raison, "marges": cache.get("marges", {})}


def explication(formule) -> list[str]:
    """La formule en français : une ligne par terme, puis le calcul."""
    from apps.beneficiaries.models import StatutParticulier
    from apps.geo.models import Zone

    from .models import Indicateur

    lignes = []
    for t in formule.get("termes", []):
        f = t.get("filtres") or {}
        precisions = []
        if f.get("sexe"):
            precisions.append(v("femmes") if f["sexe"] == "F" else v("hommes"))
        if f.get("age_min") is not None or f.get("age_max") is not None:
            if f.get("age_max") is None:
                precisions.append(v("{0} ans et plus").format(f["age_min"]))
            elif f.get("age_min") is None:
                precisions.append(v("jusqu'à {0} ans").format(f["age_max"]))
            else:
                precisions.append(v("de {0} à {1} ans").format(f["age_min"], f["age_max"]))
        if f.get("statut_particulier"):
            precisions.append(str(StatutParticulier.objects.filter(pk=f["statut_particulier"]).first() or ""))
        if f.get("zone"):
            precisions.append(v("zone : {0}").format(Zone.objects.filter(pk=f["zone"]).values_list("nom", flat=True).first() or "?"))
        for cle, dico in (("statut_participation", STATUTS_PARTICIPATION), ("statut_activite", STATUTS_ACTIVITE),
                          ("delai", DELAIS), ("variante", VARIANTES)):
            if f.get(cle) in dico:
                precisions.append(v(dico[f[cle]]).lower())
        if f.get("enquete"):
            from .models import Enquete

            titre = Enquete.objects.filter(pk=f["enquete"]).values_list("titre", flat=True).first() or "?"
            detail = v(CALCULS_ENQUETE.get(f.get("calcul_enquete"), "")).lower()
            reponses = f" = {' ou '.join(f.get('valeurs') or [])}" if f.get("valeurs") else ""
            precisions.append(f"{titre} : {detail} de « {f.get('colonne')} »{reponses}")
            if f.get("sous_groupe_colonne") and f.get("sous_groupe_valeur"):
                precisions.append(f"{f['sous_groupe_colonne']} = {f['sous_groupe_valeur']}")
        if f.get("indicateur"):
            precisions.append(str(Indicateur.objects.filter(pk=f["indicateur"]).values_list("libelle", flat=True).first() or "?")[:120])
        if f.get("periode") and f["periode"] != "tout":
            precisions.append(v(PERIODES[f["periode"]]).lower())
        libelle = v(MESURES.get(t.get("mesure"), {}).get("libelle", "?"))
        lignes.append(f"{t.get('code')} = {libelle}" + (f" ({' ; '.join(p for p in precisions if p)})" if precisions else ""))
    lignes.append(v("Calcul : {0}").format(formule.get("expression", "").replace("*", "×").replace("/", "÷")))
    return lignes


def catalogue() -> dict:
    """Ce que l'éditeur propose : mesures et leurs filtres, choix possibles, modèles."""
    from apps.beneficiaries.models import StatutParticulier

    return {
        "mesures": [{"cle": cle, "libelle": v(m["libelle"]), "nature": m["nature"], "filtres": list(m["filtres"])} for cle, m in MESURES.items()],
        "periodes": [{"value": k, "label": v(x)} for k, x in PERIODES.items()],
        "variantes": [{"value": k, "label": v(x)} for k, x in VARIANTES.items()],
        "statuts_participation": [{"value": k, "label": v(x)} for k, x in STATUTS_PARTICIPATION.items()],
        "statuts_activite": [{"value": k, "label": v(x)} for k, x in STATUTS_ACTIVITE.items()],
        "delais": [{"value": k, "label": v(x)} for k, x in DELAIS.items()],
        "calculs_enquete": [{"value": k, "label": v(x)} for k, x in CALCULS_ENQUETE.items()],
        "statuts_particuliers": [{"value": str(s.id), "label": s.libelle} for s in StatutParticulier.objects.all()],
        "modeles": [{**m, "titre": v(m["titre"])} for m in MODELES],
    }
