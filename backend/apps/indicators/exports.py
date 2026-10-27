"""
Export avancé pour interopérabilité avec les outils de collecte (XLSForm,
pour KoboToolbox/ODK Collect).
"""
import io
import re

from openpyxl import Workbook

from apps.core.vocabulaire import v

from .services import indicateurs_pour_projet


def _slug(texte: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9_]", "_", texte.strip().lower())
    return re.sub(r"_+", "_", slug).strip("_")[:60]


def generer_xlsform(projet) -> bytes:
    """
    Génère un formulaire XLSForm (.xlsx) reprenant les indicateurs du projet,
    importable directement dans KoboToolbox/ODK Build pour la collecte
    mobile — sert de pont entre la plateforme et la collecte hors-ligne
    recommandée par le cahier des charges (KoboToolbox plutôt que du natif).
    """
    indicateurs = indicateurs_pour_projet(projet.id).order_by("libelle")

    wb = Workbook()
    survey = wb.active
    survey.title = "survey"
    survey.append(["type", "name", "label", "hint"])
    survey.append(["text", "periode", f"Période de collecte — {projet.nom}", ""])

    noms_utilises = set()
    for indicateur in indicateurs:
        nom = _slug(indicateur.libelle) or f"indicateur_{indicateur.id}"
        while nom in noms_utilises:
            nom = f"{nom}_{indicateur.id}"
        noms_utilises.add(nom)
        survey.append(["decimal", nom, indicateur.libelle, f"Unité : {indicateur.unite}"])

    choices = wb.create_sheet("choices")
    choices.append(["list_name", "name", "label"])

    settings_sheet = wb.create_sheet("settings")
    settings_sheet.append(["form_title", "form_id"])
    settings_sheet.append([f"{v('Suivi ')}{projet.nom}", f"suivi_{projet.code.lower()}"])

    buffer = io.BytesIO()
    wb.save(buffer)
    return buffer.getvalue()
