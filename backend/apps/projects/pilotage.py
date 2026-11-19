"""
Rapports, risques et apprentissage (tableau de bord) : rapports attendus, reçus, validés et remis à temps ;
risques actifs par niveau, mesures d'atténuation prévues et suivies, revues en retard ; recommandations et
leur mise en œuvre ; leçons apprises, bonnes pratiques et décisions documentées. Quelques requêtes.
"""
import datetime
from collections import Counter

from apps.core.vocabulaire import v

# Un risque est « suivi » s'il a été réévalué depuis moins de ce nombre de jours.
SUIVI_RISQUE_JOURS = 90
EXEMPLES_MAX = 15


def _pourcent(partie, total):
    return round(partie / total * 100, 1) if total else None


def pilotage(projet_ids, aujourd_hui=None) -> dict:
    from django.db.models import Max, Q, Sum

    from apps.reports.models import LienPartage

    from .models import (
        Apprentissage, DocumentObligatoire, EvaluationRisque, MesureRisque, Projet, RapportProjet, Recommandation, Risque,
    )

    aujourd_hui = aujourd_hui or datetime.date.today()
    codes = dict(Projet.objects.filter(id__in=projet_ids).values_list("id", "code"))

    # Rapports : attendus à ce jour (échéance passée), reçus, validés, remis à temps.
    rapports = list(RapportProjet.objects.filter(projet_id__in=projet_ids).values(
        "id", "projet_id", "libelle", "echeance", "date_remise", "date_validation", "statut"))
    echus = [r for r in rapports if r["echeance"] <= aujourd_hui]
    recus = [r for r in rapports if r["statut"] != RapportProjet.Statut.ATTENDU]
    a_temps = [r for r in recus if r["date_remise"] and r["date_remise"] <= r["echeance"]]
    en_retard = sorted((r for r in echus if r["statut"] == RapportProjet.Statut.ATTENDU), key=lambda r: r["echeance"])
    delais = [(r["date_remise"] - r["echeance"]).days for r in recus if r["date_remise"]]
    validations = [(r["date_validation"] - r["date_remise"]).days for r in rapports
                   if r["statut"] == RapportProjet.Statut.VALIDE and r["date_validation"] and r["date_remise"]]
    # Acceptés dès la première soumission : validés sans être jamais passés par « à revoir » (historique).
    valides_ids = [r["id"] for r in rapports if r["statut"] == RapportProjet.Statut.VALIDE]
    revus = set(RapportProjet.history.filter(id__in=valides_ids, statut=RapportProjet.Statut.A_REVOIR).values_list("id", flat=True))

    # Risques : actifs (ou survenus) par niveau, mesures prévues et suivies, revues en retard.
    risques = list(Risque.objects.filter(projet_id__in=projet_ids).annotate(derniere=Max("evaluations__date")).values(
        "projet_id", "code", "libelle", "probabilite", "impact", "statut", "mesures_attenuation", "date_prochaine_revue", "derniere"))
    ouverts = [r for r in risques if r["statut"] in (Risque.Statut.ACTIF, Risque.Statut.SURVENU)]
    niveaux = Counter(Risque.niveau_pour(r["probabilite"] * r["impact"]) for r in ouverts)
    limite_suivi = aujourd_hui - datetime.timedelta(days=SUIVI_RISQUE_JOURS)
    revue_en_retard = [r for r in ouverts if r["date_prochaine_revue"] and r["date_prochaine_revue"] < aujourd_hui]
    graves = sorted((r for r in ouverts if r["probabilite"] * r["impact"] >= 10), key=lambda r: -r["probabilite"] * r["impact"])

    # Problèmes survenus puis maîtrisés ou clos : délai entre la première réévaluation « survenu » et la suivante
    # qui le dit maîtrisé ou clos.
    resolutions = []
    survenu_le = {}
    for risque_id, date, statut in (EvaluationRisque.objects.filter(risque__projet_id__in=projet_ids)
                                    .order_by("risque_id", "date", "id").values_list("risque_id", "date", "statut")):
        if statut == Risque.Statut.SURVENU:
            survenu_le.setdefault(risque_id, date)
        elif statut in (Risque.Statut.MAITRISE, Risque.Statut.CLOS) and risque_id in survenu_le:
            resolutions.append((date - survenu_le.pop(risque_id)).days)

    # Mesures d'atténuation suivies : réalisées parmi celles retenues, en retard.
    mesures = list(MesureRisque.objects.filter(risque__projet_id__in=projet_ids).exclude(statut=MesureRisque.Statut.ABANDONNEE)
                   .values("statut", "echeance"))
    mesures_realisees = sum(1 for m in mesures if m["statut"] == MesureRisque.Statut.REALISEE)
    mesures_en_retard = sum(1 for m in mesures if m["statut"] != MesureRisque.Statut.REALISEE and m["echeance"] and m["echeance"] < aujourd_hui)

    # Recommandations et leur mise en œuvre.
    recommandations = list(Recommandation.objects.filter(projet_id__in=projet_ids).values(
        "projet_id", "code", "libelle", "echeance", "statut", "priorite", "origine"))
    retenues = [r for r in recommandations if r["statut"] != Recommandation.Statut.ABANDONNEE]
    realisees = [r for r in retenues if r["statut"] == Recommandation.Statut.REALISEE]
    rec_en_retard = sorted((r for r in retenues if r["statut"] != Recommandation.Statut.REALISEE
                            and r["echeance"] and r["echeance"] < aujourd_hui), key=lambda r: r["echeance"])

    liens = LienPartage.objects.filter(Q(projet_id__in=projet_ids) | Q(projet__isnull=True), actif=True)
    partages = {"liens": liens.count(), "consultations": liens.aggregate(n=Sum("nombre_consultations"))["n"] or 0}

    origines = dict(Recommandation.Origine.choices)
    par_origine = []
    for code, libelle in [*Recommandation.Origine.choices, ("", "Origine non précisée")]:
        retenues_origine = [r for r in retenues if r["origine"] == code]
        if retenues_origine:
            faites = sum(1 for r in retenues_origine if r["statut"] == Recommandation.Statut.REALISEE)
            par_origine.append({"origine": code, "libelle": v(origines.get(code, libelle)), "retenues": len(retenues_origine),
                                "realisees": faites, "taux_mise_en_oeuvre": _pourcent(faites, len(retenues_origine))})

    lecons = list(Apprentissage.objects.filter(projet_id__in=projet_ids, type__in=[Apprentissage.Type.LECON, Apprentissage.Type.BONNE_PRATIQUE])
                  .values_list("adaptation", flat=True))

    # Documents obligatoires : disponibles (un document de la GED leur est associé), manquants à l'échéance.
    obligatoires = list(DocumentObligatoire.objects.filter(projet_id__in=projet_ids).values("projet_id", "libelle", "echeance", "document_id"))
    manquants = sorted((d for d in obligatoires if d["document_id"] is None and d["echeance"] and d["echeance"] < aujourd_hui),
                       key=lambda d: d["echeance"])

    apprentissages = Counter(Apprentissage.objects.filter(projet_id__in=projet_ids).values_list("type", flat=True))

    return {
        "rapports": {
            "total": len(rapports), "attendus_a_date": len(echus), "recus": len(recus),
            "valides": sum(1 for r in rapports if r["statut"] == RapportProjet.Statut.VALIDE),
            "a_revoir": sum(1 for r in rapports if r["statut"] == RapportProjet.Statut.A_REVOIR),
            "en_retard": len(en_retard), "taux_remis": _pourcent(len([r for r in echus if r["statut"] != RapportProjet.Statut.ATTENDU]), len(echus)),
            "taux_a_temps": _pourcent(len(a_temps), len(recus)),
            "delai_validation_jours": round(sum(validations) / len(validations), 1) if validations else None,
            "acceptes_premiere_soumission": _pourcent(len(set(valides_ids) - revus), len(valides_ids)),
            "retard_moyen_jours": round(sum(max(d, 0) for d in delais) / len(delais), 1) if delais else None,
            "en_retard_exemples": [{"projet": codes.get(r["projet_id"], ""), "libelle": r["libelle"], "echeance": r["echeance"],
                                    "jours": (aujourd_hui - r["echeance"]).days} for r in en_retard[:EXEMPLES_MAX]],
        },
        "risques": {
            "total": len(risques), "ouverts": len(ouverts),
            "clos": sum(1 for r in risques if r["statut"] in (Risque.Statut.MAITRISE, Risque.Statut.CLOS)),
            "graves": len(graves), "graves_avec_mesures": _pourcent(sum(1 for r in graves if r["mesures_attenuation"].strip()), len(graves)),
            "problemes_resolus": len(resolutions),
            "delai_resolution_jours": round(sum(resolutions) / len(resolutions), 1) if resolutions else None,
            "mesures": len(mesures), "mesures_realisees": mesures_realisees, "mesures_en_retard": mesures_en_retard,
            "taux_execution_mesures": _pourcent(mesures_realisees, len(mesures)), "survenus": sum(1 for r in ouverts if r["statut"] == Risque.Statut.SURVENU),
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
            "par_origine": par_origine,
            "en_retard_exemples": [{"projet": codes.get(r["projet_id"], ""), "code": r["code"], "libelle": r["libelle"],
                                    "echeance": r["echeance"], "priorite": r["priorite"]} for r in rec_en_retard[:EXEMPLES_MAX]],
        },
        "documents_obligatoires": {
            "total": len(obligatoires), "disponibles": sum(1 for d in obligatoires if d["document_id"]),
            "taux_disponibilite": _pourcent(sum(1 for d in obligatoires if d["document_id"]), len(obligatoires)),
            "manquants_echus": len(manquants),
            "manquants_exemples": [{"projet": codes.get(d["projet_id"], ""), "libelle": d["libelle"], "echeance": d["echeance"]}
                                   for d in manquants[:EXEMPLES_MAX]],
        },
        # Analyses partagées par lien (tableau de bord, suivi des projets) et leurs consultations.
        "partages": partages,
        "apprentissage": {
            "lecons": apprentissages.get(Apprentissage.Type.LECON, 0),
            "bonnes_pratiques": apprentissages.get(Apprentissage.Type.BONNE_PRATIQUE, 0),
            "decisions": apprentissages.get(Apprentissage.Type.DECISION, 0),
            "lecons_adaptees": sum(lecons), "part_lecons_adaptees": _pourcent(sum(lecons), len(lecons)),
        },
    }
