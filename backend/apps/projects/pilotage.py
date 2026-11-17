"""
Rapports, risques et apprentissage (tableau de bord) : rapports attendus, reçus, validés et remis à temps ;
risques actifs par niveau, mesures d'atténuation prévues et suivies, revues en retard ; recommandations et
leur mise en œuvre ; leçons apprises, bonnes pratiques et décisions documentées. Quelques requêtes.
"""
import datetime
from collections import Counter

# Un risque est « suivi » s'il a été réévalué depuis moins de ce nombre de jours.
SUIVI_RISQUE_JOURS = 90
EXEMPLES_MAX = 15


def _pourcent(partie, total):
    return round(partie / total * 100, 1) if total else None


def pilotage(projet_ids, aujourd_hui=None) -> dict:
    from django.db.models import Max

    from .models import Apprentissage, Projet, RapportProjet, Recommandation, Risque

    aujourd_hui = aujourd_hui or datetime.date.today()
    codes = dict(Projet.objects.filter(id__in=projet_ids).values_list("id", "code"))

    # Rapports : attendus à ce jour (échéance passée), reçus, validés, remis à temps.
    rapports = list(RapportProjet.objects.filter(projet_id__in=projet_ids).values(
        "projet_id", "libelle", "echeance", "date_remise", "statut"))
    echus = [r for r in rapports if r["echeance"] <= aujourd_hui]
    recus = [r for r in rapports if r["statut"] != RapportProjet.Statut.ATTENDU]
    a_temps = [r for r in recus if r["date_remise"] and r["date_remise"] <= r["echeance"]]
    en_retard = sorted((r for r in echus if r["statut"] == RapportProjet.Statut.ATTENDU), key=lambda r: r["echeance"])
    delais = [(r["date_remise"] - r["echeance"]).days for r in recus if r["date_remise"]]

    # Risques : actifs (ou survenus) par niveau, mesures prévues et suivies, revues en retard.
    risques = list(Risque.objects.filter(projet_id__in=projet_ids).annotate(derniere=Max("evaluations__date")).values(
        "projet_id", "code", "libelle", "probabilite", "impact", "statut", "mesures_attenuation", "date_prochaine_revue", "derniere"))
    ouverts = [r for r in risques if r["statut"] in (Risque.Statut.ACTIF, Risque.Statut.SURVENU)]
    niveaux = Counter(Risque.niveau_pour(r["probabilite"] * r["impact"]) for r in ouverts)
    limite_suivi = aujourd_hui - datetime.timedelta(days=SUIVI_RISQUE_JOURS)
    revue_en_retard = [r for r in ouverts if r["date_prochaine_revue"] and r["date_prochaine_revue"] < aujourd_hui]
    graves = sorted((r for r in ouverts if r["probabilite"] * r["impact"] >= 10), key=lambda r: -r["probabilite"] * r["impact"])

    # Recommandations et leur mise en œuvre.
    recommandations = list(Recommandation.objects.filter(projet_id__in=projet_ids).values(
        "projet_id", "code", "libelle", "echeance", "statut", "priorite"))
    retenues = [r for r in recommandations if r["statut"] != Recommandation.Statut.ABANDONNEE]
    realisees = [r for r in retenues if r["statut"] == Recommandation.Statut.REALISEE]
    rec_en_retard = sorted((r for r in retenues if r["statut"] != Recommandation.Statut.REALISEE
                            and r["echeance"] and r["echeance"] < aujourd_hui), key=lambda r: r["echeance"])

    apprentissages = Counter(Apprentissage.objects.filter(projet_id__in=projet_ids).values_list("type", flat=True))

    return {
        "rapports": {
            "total": len(rapports), "attendus_a_date": len(echus), "recus": len(recus),
            "valides": sum(1 for r in rapports if r["statut"] == RapportProjet.Statut.VALIDE),
            "a_revoir": sum(1 for r in rapports if r["statut"] == RapportProjet.Statut.A_REVOIR),
            "en_retard": len(en_retard), "taux_remis": _pourcent(len([r for r in echus if r["statut"] != RapportProjet.Statut.ATTENDU]), len(echus)),
            "taux_a_temps": _pourcent(len(a_temps), len(recus)),
            "retard_moyen_jours": round(sum(max(d, 0) for d in delais) / len(delais), 1) if delais else None,
            "en_retard_exemples": [{"projet": codes.get(r["projet_id"], ""), "libelle": r["libelle"], "echeance": r["echeance"],
                                    "jours": (aujourd_hui - r["echeance"]).days} for r in en_retard[:EXEMPLES_MAX]],
        },
        "risques": {
            "total": len(risques), "ouverts": len(ouverts), "survenus": sum(1 for r in ouverts if r["statut"] == Risque.Statut.SURVENU),
            "par_niveau": {n: niveaux.get(n, 0) for n in ("CRITIQUE", "ELEVE", "MOYEN", "FAIBLE")},
            "avec_mesures": _pourcent(sum(1 for r in ouverts if r["mesures_attenuation"].strip()), len(ouverts)),
            "suivis": _pourcent(sum(1 for r in ouverts if r["derniere"] and r["derniere"] >= limite_suivi), len(ouverts)),
            "revue_en_retard": len(revue_en_retard),
            "graves_exemples": [{"projet": codes.get(r["projet_id"], ""), "code": r["code"], "libelle": r["libelle"],
                                 "criticite": r["probabilite"] * r["impact"], "niveau": Risque.niveau_pour(r["probabilite"] * r["impact"]),
                                 "mesures": bool(r["mesures_attenuation"].strip()), "derniere_revue": r["derniere"]}
                                for r in graves[:EXEMPLES_MAX]],
        },
        "recommandations": {
            "total": len(recommandations), "retenues": len(retenues), "realisees": len(realisees),
            "en_cours": sum(1 for r in retenues if r["statut"] == Recommandation.Statut.EN_COURS),
            "taux_mise_en_oeuvre": _pourcent(len(realisees), len(retenues)), "en_retard": len(rec_en_retard),
            "en_retard_exemples": [{"projet": codes.get(r["projet_id"], ""), "code": r["code"], "libelle": r["libelle"],
                                    "echeance": r["echeance"], "priorite": r["priorite"]} for r in rec_en_retard[:EXEMPLES_MAX]],
        },
        "apprentissage": {
            "lecons": apprentissages.get(Apprentissage.Type.LECON, 0),
            "bonnes_pratiques": apprentissages.get(Apprentissage.Type.BONNE_PRATIQUE, 0),
            "decisions": apprentissages.get(Apprentissage.Type.DECISION, 0),
        },
    }
