from django.db import migrations


def renommer(apps, schema_editor):
    """Premier maillon par défaut : « Stratégie » (chaîne Stratégie → Programme → Projet)."""
    TypeDocument = apps.get_model("strategy", "TypeDocument")
    TypeDocument.objects.filter(nom="Cadre stratégique", nom_pluriel="Cadres stratégiques").update(
        nom="Stratégie", nom_pluriel="Stratégies")


class Migration(migrations.Migration):

    dependencies = [
        ("strategy", "0013_elements_parents_secondaires"),
    ]

    operations = [migrations.RunPython(renommer, migrations.RunPython.noop)]
