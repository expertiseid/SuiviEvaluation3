"""
Un indicateur se rattache désormais au projet OU à un élément de sa
planification (Activite, à n'importe quel niveau) — les rattachements à
l'Objectif général / spécifique ont été convertis par
projects.0023_objectifs_vers_niveaux_libres.
"""
from django.db import migrations, models
from django.db.models import Q


class Migration(migrations.Migration):
    dependencies = [
        ("indicators", "0012_alter_historicalindicateur_libelle_and_more"),
        ("projects", "0023_objectifs_vers_niveaux_libres"),
    ]

    operations = [
        migrations.RemoveConstraint(model_name="indicateur", name="indicateur_rattachement_au_plus_un"),
        migrations.RemoveField(model_name="indicateur", name="objectif_general"),
        migrations.RemoveField(model_name="indicateur", name="objectif_specifique"),
        migrations.RemoveField(model_name="historicalindicateur", name="objectif_general"),
        migrations.RemoveField(model_name="historicalindicateur", name="objectif_specifique"),
        migrations.AddConstraint(
            model_name="indicateur",
            constraint=models.CheckConstraint(
                check=~Q(projet__isnull=False, activite__isnull=False),
                name="indicateur_rattachement_au_plus_un",
            ),
        ),
    ]
