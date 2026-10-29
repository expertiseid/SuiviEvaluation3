"""
Contrôle des fichiers traduits : produit chaque rapport, export et modèle d'import dans une
langue, avec les données présentes en base, et liste les textes restés en français (texte des
PDF et Word, cellules et noms de feuilles des classeurs). Les données saisies (noms de projets,
d'activités…) restent normalement en français : à distinguer à la lecture.

Usage : docker compose exec backend python manage.py verifier_traductions_fichiers en
"""
import html
import io
import re
from unittest import mock

from django.core.management.base import BaseCommand
from openpyxl import load_workbook
from rest_framework.test import APIClient

FRANCAIS = re.compile(
    r"[éèêàùçôîâûœ]|\b(le|la|les|des|du|une|est|sont|aucun|aucune|projet|période|réalisé|généré|"
    r"bénéficiaire|activité|budget alloué|taux|prévu|total général|dont|par|sur|avec)\b",
    re.IGNORECASE,
)


class Command(BaseCommand):
    help = "Produit tous les fichiers dans une langue et liste les textes restés en français."

    def add_arguments(self, parser):
        parser.add_argument("langue")
        parser.add_argument("--projet", type=int)
        parser.add_argument("--cadre", type=int)

    def handle(self, *args, langue, projet=None, cadre=None, **options):
        from apps.accounts.models import User
        from apps.projects.models import Projet
        from apps.strategy.models import CadreStrategique
        from apps.suivi.models import PeriodePlanification

        projet = Projet.objects.get(id=projet) if projet else Projet.objects.order_by("id").first()
        cadre = CadreStrategique.objects.get(id=cadre) if cadre else CadreStrategique.objects.order_by("id").first()
        periode = PeriodePlanification.objects.filter(projet=projet).order_by("id").first()
        client = APIClient(SERVER_NAME="localhost", HTTP_ACCEPT_LANGUAGE=langue)
        client.force_authenticate(User.objects.filter(role="ADMIN").first())

        adresses = [
            "/projets/modele-import/",
            "/indicateurs/modele-import/",
            "/beneficiaires/modele-import/?pays=BF",
            "/planification/modele-import/",
            f"/elements-strategiques/modele-import/?cadre_strategique={cadre.id}",
            f"/suivi/projets/{projet.id}/canevas/",
            f"/suivi/projets/{projet.id}/exporter/excel/",
            f"/suivi/projets/{projet.id}/exporter/pdf/",
            f"/rapports/financier/{projet.id}/?fichier=xlsx",
            f"/rapports/financier/{projet.id}/?fichier=pdf",
            f"/rapports/cadre-logique/{projet.id}/?fichier=pdf",
            f"/rapports/risques/{projet.id}/?fichier=pdf",
            f"/rapports/suivi-strategique/{cadre.id}/?fichier=pdf",
            f"/beneficiaires/exporter/?fichier=excel&projets={projet.id}",
            f"/beneficiaires/exporter/?fichier=pdf&projets={projet.id}",
            f"/beneficiaires/cartes/?projet={projet.id}&origine=http://localhost",
        ]
        if periode:
            adresses += [
                f"/periodes-planification/{periode.id}/exporter/excel/",
                f"/periodes-planification/{periode.id}/exporter/pdf/",
                f"/periodes-planification/{periode.id}/exporter-suivi/excel/",
                f"/periodes-planification/{periode.id}/exporter-suivi/pdf/",
            ]

        documents = []

        class HTMLCapture:
            """Remplace weasyprint.HTML : garde le HTML qui aurait été mis en page."""

            def __init__(self, string=None, **kwargs):
                documents.append(string)

            def write_pdf(self, *args, **kwargs):
                return b"%PDF"

        modules = [
            "apps.reports.views", "apps.suivi.export_pdf", "apps.suivi.export_periode",
            "apps.beneficiaries.services.export_excel", "apps.beneficiaries.services.carte",
        ]
        with mock.patch.multiple("weasyprint", HTML=HTMLCapture), _remplacer(modules, HTMLCapture):
            for adresse in adresses:
                documents.clear()
                reponse = client.get("/api/v1" + adresse)
                restes = []
                if reponse.status_code != 200:
                    self.stdout.write(f"\n### {adresse} → HTTP {reponse.status_code}")
                    continue
                if documents:
                    for document in documents:
                        restes += _textes_html(document)
                elif reponse.content[:2] == b"PK":
                    restes += _textes_classeur(reponse.content)
                francais = sorted({t for t in restes if FRANCAIS.search(t)})
                self.stdout.write(f"\n### {adresse} — {len(francais)} texte(s) en français")
                for texte in francais:
                    self.stdout.write("   " + texte[:160].replace("\n", " ⏎ "))


class _remplacer:
    def __init__(self, modules, remplacant):
        import importlib

        self.cibles = [importlib.import_module(m) for m in modules]
        self.remplacant = remplacant

    def __enter__(self):
        self.anciens = [getattr(m, "HTML", None) for m in self.cibles]
        for m in self.cibles:
            if hasattr(m, "HTML"):
                m.HTML = self.remplacant

    def __exit__(self, *exc):
        for m, ancien in zip(self.cibles, self.anciens):
            if ancien is not None:
                m.HTML = ancien


def _textes_html(document):
    sans_blocs = re.sub(r"<(style|script)[^>]*>.*?</\1>", " ", document, flags=re.S | re.I)
    return [html.unescape(t).strip() for t in re.split(r"<[^>]*>", sans_blocs) if t.strip()]


def _textes_classeur(contenu):
    wb = load_workbook(io.BytesIO(contenu))
    textes = []
    for feuille in wb.worksheets:
        textes.append(f"[feuille] {feuille.title}")
        for ligne in feuille.iter_rows():
            for cellule in ligne:
                if isinstance(cellule.value, str) and cellule.value.strip():
                    textes.append(cellule.value.strip())
    return textes
