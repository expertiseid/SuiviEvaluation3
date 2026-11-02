"""Chiffre les données protégées déjà enregistrées en clair (lecture tolérante, réécriture chiffrée)."""
from django.db import migrations

CHAMPS_DOSSIER = ["lieu", "description", "nom", "telephone", "courriel", "decision", "motif_cloture",
                  "raison_sans_retour"]


def chiffrer(apps, schema_editor):
    for nom_modele, champs in (("Dossier", CHAMPS_DOSSIER), ("HistoricalDossier", CHAMPS_DOSSIER),
                               ("ActionDossier", ["texte"])):
        modele = apps.get_model("plaintes", nom_modele)
        for objet in modele.objects.all().iterator():
            # Lecture : déchiffre ou renvoie le texte en clair ; écriture : chiffre.
            modele.objects.filter(pk=objet.pk).update(**{c: getattr(objet, c) for c in champs})


class Migration(migrations.Migration):
    dependencies = [("plaintes", "0005_circuit_confidentiel")]

    operations = [migrations.RunPython(chiffrer, migrations.RunPython.noop)]
