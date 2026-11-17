"""
Qualité des données (tableau de bord) : complétude des activités, indicateurs et bénéficiaires ; saisies
faites dans les délais ; valeurs atypiques ; doublons non traités ; saisies en attente d'approbation ; et un
score de qualité dont le calcul est affiché (moyenne pondérée de ses composantes connues).
"""
import datetime
from statistics import median

from apps.indicators.services import DELAI_SAISIE_JOURS

# Composantes du score et leur poids (sur 100).
POIDS = {"completude": 40, "ponctualite": 30, "plausibilite": 15, "doublons": 15}
# Valeur atypique : écart robuste (médiane et écart absolu médian) au-delà de ce seuil.
SEUIL_ATYPIQUE = 3.5
# Quantité réalisée au-delà de ce multiple de la quantité prévue : à vérifier.
MULTIPLE_QUANTITE = 2
VALEURS_MINIMUM = 4
EXEMPLES_MAX = 15


def _pourcent(partie, total):
    return round(partie / total * 100, 1) if total else None


def atypiques(valeurs):
    """Indices des valeurs atypiques (score robuste |0,6745 × (x − médiane) / écart absolu médian| > seuil)."""
    if len(valeurs) < VALEURS_MINIMUM:
        return []
    m = median(valeurs)
    ecart = median(abs(x - m) for x in valeurs)
    if not ecart:
        return []
    return [i for i, x in enumerate(valeurs) if abs(0.6745 * (x - m) / ecart) > SEUIL_ATYPIQUE]


def qualite(projet_ids) -> dict:
    from django.db.models import Count, Q

    from apps.beneficiaries.models import Beneficiaire, SignalementDoublon
    from apps.core.models import EtatApprobation
    from apps.indicators.models import Indicateur, ValeurIndicateur
    from apps.projects.models import Activite, Projet, TauxManuel
    from apps.suivi.models import PointSuivi

    codes = dict(Projet.objects.filter(id__in=projet_ids).values_list("id", "code"))

    # Complétude : part des informations essentielles renseignées.
    activites = list(Activite.objects.filter(projet_id__in=projet_ids, enfants__isnull=True)
                     .annotate(nb_responsables=Count("responsables", distinct=True))
                     .values("responsable_id", "equipe_responsable_id", "nb_responsables", "date_debut", "date_fin",
                             "budget_alloue", "quantite_prevue"))
    champs_activites = {
        "responsable": sum(1 for a in activites if a["responsable_id"] or a["equipe_responsable_id"] or a["nb_responsables"]),
        "dates": sum(1 for a in activites if a["date_debut"] and a["date_fin"]),
        "budget": sum(1 for a in activites if a["budget_alloue"]),
        "quantite_prevue": sum(1 for a in activites if a["quantite_prevue"]),
    }
    filtre_indicateurs = Q(projet_id__in=projet_ids) | Q(activite__projet_id__in=projet_ids)
    indicateurs = list(Indicateur.objects.filter(filtre_indicateurs).annotate(nb_valeurs=Count("valeurs"))
                       .values("valeur_reference", "nb_valeurs"))
    champs_indicateurs = {
        "reference": sum(1 for i in indicateurs if i["valeur_reference"] is not None),
        "valeurs": sum(1 for i in indicateurs if i["nb_valeurs"]),
    }
    beneficiaires = list(Beneficiaire.objects.filter(participations__projet_id__in=projet_ids).distinct()
                         .values("date_naissance", "zone_id", "telephone", "numero_piece_identite", "consentement"))
    champs_beneficiaires = {
        "date_naissance": sum(1 for b in beneficiaires if b["date_naissance"]),
        "localite": sum(1 for b in beneficiaires if b["zone_id"]),
        "contact": sum(1 for b in beneficiaires if b["telephone"] or b["numero_piece_identite"]),
        "consentement": sum(1 for b in beneficiaires if b["consentement"] is not None),
    }

    def famille(champs, total):
        return {"total": total, "champs": {c: _pourcent(n, total) for c, n in champs.items()},
                "completude": _pourcent(sum(champs.values()), total * len(champs))}

    completude = {"activites": famille(champs_activites, len(activites)),
                  "indicateurs": famille(champs_indicateurs, len(indicateurs)),
                  "beneficiaires": famille(champs_beneficiaires, len(beneficiaires))}
    taux_familles = [f["completude"] for f in completude.values() if f["completude"] is not None]

    # Ponctualité : saisies faites au plus tard DELAI_SAISIE_JOURS après la fin de la période.
    delai = datetime.timedelta(days=DELAI_SAISIE_JOURS)
    valeurs = list(ValeurIndicateur.objects.filter(indicateur__in=Indicateur.objects.filter(filtre_indicateurs))
                   .values("indicateur_id", "indicateur__libelle", "indicateur__unite", "periode_fin", "date_saisie",
                           "valeur_realisee", "indicateur__projet_id", "indicateur__activite__projet_id"))
    points = list(PointSuivi.objects.filter(Q(activite__projet_id__in=projet_ids) | Q(sous_activite__activite__projet_id__in=projet_ids))
                  .values("periode_fin", "date_saisie"))
    saisies = [(v["periode_fin"], v["date_saisie"]) for v in valeurs] + [(p["periode_fin"], p["date_saisie"]) for p in points]
    a_temps = sum(1 for fin, saisie in saisies if saisie.date() <= fin + delai)

    # Valeurs atypiques : par indicateur, et quantités réalisées très au-delà du prévu.
    par_indicateur = {}
    for v in valeurs:
        par_indicateur.setdefault(v["indicateur_id"], []).append(v)
    signales, verifiees = [], 0
    for liste in par_indicateur.values():
        if len(liste) < VALEURS_MINIMUM:
            continue
        verifiees += len(liste)
        for i in atypiques([float(v["valeur_realisee"]) for v in liste]):
            v = liste[i]
            signales.append({"projet": codes.get(v["indicateur__projet_id"] or v["indicateur__activite__projet_id"], ""),
                             "libelle": v["indicateur__libelle"][:200], "valeur": float(v["valeur_realisee"]),
                             "unite": v["indicateur__unite"], "periode_fin": v["periode_fin"], "motif": "indicateur"})
    quantites = list(Activite.objects.filter(projet_id__in=projet_ids, enfants__isnull=True, quantite_prevue__gt=0,
                                             quantite_realisee__isnull=False)
                     .values("projet_id", "code_activite", "libelle", "quantite_prevue", "quantite_realisee", "unite_quantite"))
    verifiees += len(quantites)
    for a in quantites:
        if a["quantite_realisee"] > MULTIPLE_QUANTITE * a["quantite_prevue"]:
            signales.append({"projet": codes.get(a["projet_id"], ""), "libelle": f"{a['code_activite']} {a['libelle']}".strip()[:200],
                             "valeur": float(a["quantite_realisee"]), "unite": a["unite_quantite"],
                             "prevu": float(a["quantite_prevue"]), "motif": "quantite"})

    # Doublons et approbations.
    doublons = SignalementDoublon.objects.aggregate(
        total=Count("id"), non_traites=Count("id", filter=Q(statut=SignalementDoublon.Statut.SIGNALE)))
    approbations = {"en_attente": 0, "rejetees": 0}
    for qs in (ValeurIndicateur.tous.filter(indicateur__in=Indicateur.objects.filter(filtre_indicateurs)),
               PointSuivi.tous.filter(Q(activite__projet_id__in=projet_ids) | Q(sous_activite__activite__projet_id__in=projet_ids)),
               TauxManuel.tous.filter(activite__projet_id__in=projet_ids)):
        compte = qs.aggregate(en_attente=Count("id", filter=Q(etat_approbation=EtatApprobation.EN_ATTENTE)),
                              rejetees=Count("id", filter=Q(etat_approbation=EtatApprobation.REJETEE)))
        approbations = {c: approbations[c] + compte[c] for c in approbations}

    # Score : moyenne pondérée des composantes connues (une composante sans donnée est ignorée).
    composantes = {
        "completude": round(sum(taux_familles) / len(taux_familles), 1) if taux_familles else None,
        "ponctualite": _pourcent(a_temps, len(saisies)),
        "plausibilite": round(100 - len(signales) / verifiees * 100, 1) if verifiees else None,
        "doublons": round(100 - doublons["non_traites"] / doublons["total"] * 100, 1) if doublons["total"] else None,
    }
    connues = {c: x for c, x in composantes.items() if x is not None}
    poids = sum(POIDS[c] for c in connues)
    score = round(sum(x * POIDS[c] for c, x in connues.items()) / poids, 1) if poids else None

    return {
        "score": score, "composantes": composantes, "poids": POIDS,
        "completude": completude,
        "saisies": len(saisies), "saisies_a_temps": a_temps, "delai_jours": DELAI_SAISIE_JOURS,
        "valeurs_verifiees": verifiees, "atypiques": len(signales), "atypiques_exemples": signales[:EXEMPLES_MAX],
        "doublons_signales": doublons["total"], "doublons_non_traites": doublons["non_traites"],
        "approbations_en_attente": approbations["en_attente"], "saisies_rejetees": approbations["rejetees"],
    }
