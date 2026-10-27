"""
Planification entièrement libre sous le projet : l'Objectif général et les
Objectifs spécifiques, jusqu'ici deux niveaux figés, deviennent des Activités
ordinaires (niveaux de profondeur 0 et 1, nommés « Objectif général » et
« Objectif spécifique » dans NiveauActivite) — chaque projet existant garde
exactement la même arborescence et le même affichage, mais tous ses niveaux
sont désormais renommables, supprimables, et on peut en ajouter autant qu'on
veut.

Les indicateurs rattachés à un objectif sont rattachés à l'Activité qui le
remplace.
"""
from django.db import migrations


def convertir(apps, schema_editor):
    Projet = apps.get_model("projects", "Projet")
    ObjectifGeneral = apps.get_model("projects", "ObjectifGeneral")
    Activite = apps.get_model("projects", "Activite")
    NiveauActivite = apps.get_model("projects", "NiveauActivite")
    Indicateur = apps.get_model("indicators", "Indicateur")

    for og in ObjectifGeneral.objects.select_related("projet").order_by("id"):
        projet = og.projet

        # Les noms de niveaux existants descendent de deux crans (ordre décroissant
        # pour ne jamais heurter la contrainte d'unicité projet+profondeur).
        for niveau in NiveauActivite.objects.filter(projet=projet).order_by("-profondeur"):
            niveau.profondeur += 2
            niveau.save(update_fields=["profondeur"])
        NiveauActivite.objects.create(projet=projet, profondeur=0, nom_niveau="Objectif général")
        NiveauActivite.objects.create(projet=projet, profondeur=1, nom_niveau="Objectif spécifique")

        noeud_og = Activite.objects.create(
            projet=projet, libelle=og.libelle, description=og.description, activite_parent=None
        )
        Indicateur.objects.filter(objectif_general=og).update(objectif_general=None, activite=noeud_og)

        for os_ in og.objectifs_specifiques.order_by("id"):
            noeud_os = Activite.objects.create(
                projet=projet, libelle=os_.libelle, description=os_.description, activite_parent=noeud_og
            )
            Indicateur.objects.filter(objectif_specifique=os_).update(objectif_specifique=None, activite=noeud_os)
            Activite.objects.filter(objectif_specifique=os_).update(projet=projet)
            Activite.objects.filter(objectif_specifique=os_, activite_parent__isnull=True).update(
                activite_parent=noeud_os
            )

    restantes = Activite.objects.filter(projet__isnull=True).count()
    if restantes:
        raise RuntimeError(f"{restantes} activité(s) sans projet après conversion.")


class Migration(migrations.Migration):
    dependencies = [
        ("projects", "0022_planification_flexible_etape1"),
        ("indicators", "0012_alter_historicalindicateur_libelle_and_more"),
    ]

    operations = [migrations.RunPython(convertir, migrations.RunPython.noop)]
