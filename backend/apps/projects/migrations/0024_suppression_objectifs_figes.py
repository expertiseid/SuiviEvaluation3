"""
Fin du passage à une planification à niveaux libres : l'Objectif général et
les Objectifs spécifiques ayant été convertis en Activités
(0023_objectifs_vers_niveaux_libres), leurs modèles et le lien
Activite.objectif_specifique disparaissent ; chaque élément est rattaché
directement à son projet.
"""
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("projects", "0023_objectifs_vers_niveaux_libres"),
        ("indicators", "0013_rattachement_projet_ou_element"),
    ]

    operations = [
        migrations.RemoveField(model_name="activite", name="objectif_specifique"),
        migrations.RemoveField(model_name="historicalactivite", name="objectif_specifique"),
        migrations.AlterField(
            model_name="activite",
            name="projet",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT, related_name="activites", to="projects.projet"
            ),
        ),
        migrations.DeleteModel(name="HistoricalObjectifSpecifique"),
        migrations.DeleteModel(name="HistoricalObjectifGeneral"),
        migrations.DeleteModel(name="ObjectifSpecifique"),
        migrations.DeleteModel(name="ObjectifGeneral"),
    ]
