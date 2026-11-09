# Offres du 4 nov. 2026 : Standard et Standard + stockage. Les demandes faites avec les anciennes
# offres (Essentiel, Institution) passent à Standard ; Expertise-ID confirme l'offre avec l'organisation.

from django.db import migrations, models


def anciennes_offres(apps, schema_editor):
    DemandeInscription = apps.get_model("accounts", "DemandeInscription")
    DemandeInscription.objects.filter(offre__in=["ESSENTIEL", "INSTITUTION"]).update(offre="STANDARD")


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0012_sous_domaine_inscription'),
    ]

    operations = [
        migrations.AlterField(
            model_name='demandeinscription',
            name='offre',
            field=models.CharField(blank=True, choices=[('STANDARD', 'Standard'), ('STOCKAGE_PLUS', 'Standard + stockage')], max_length=20),
        ),
        migrations.RunPython(anciennes_offres, migrations.RunPython.noop),
    ]
