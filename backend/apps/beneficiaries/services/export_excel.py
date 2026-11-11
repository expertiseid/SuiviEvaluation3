"""
Export Excel de la liste des bénéficiaires — d'un projet, ou de tous les
projets (feuille « Tous les bénéficiaires » + une feuille par projet + « Sans
projet »). Les premières colonnes reprennent exactement celles du modèle
d'import : un export peut être corrigé puis réimporté.
"""
import io
from collections import Counter

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

from apps.core.excel_utils import figer_entete, quadriller
from apps.core.langues import traduire_classeur, traduire_html
from apps.core.vocabulaire import v

from ..models import VariableBeneficiaire

from .import_excel import colonnes as colonnes_import
from .import_excel import niveaux_du_pays
from .variables import cellule

COULEUR_ENTETE = "1F4E78"
COLONNES_PARTICIPATION = ["Activité", "Sous-activité", "Date d'inscription", "Rôle dans le projet"]


def _niveaux_zone(zone):
    """Noms de la localisation par niveau administratif (ordre 1 = le plus haut)."""
    par_ordre = {}
    while zone is not None:
        par_ordre[zone.niveau_administratif.ordre] = zone.nom
        zone = zone.parent
    return par_ordre


def _localisation_ordonnee(zone, nb_niveaux):
    """Localisation sur nb_niveaux colonnes (Région, Province, Commune…), du plus haut au plus bas."""
    par_ordre = _niveaux_zone(zone)
    return [par_ordre.get(ordre, "") for ordre in range(1, nb_niveaux + 1)]


def _colonnes_beneficiaire(b, codes_projets, nb_niveaux):
    """Valeurs d'un bénéficiaire, dans l'ordre des colonnes du modèle d'import (réimportable)."""
    return [
        b.pays,
        *_localisation_ordonnee(b.zone, nb_niveaux),
        b.nom,
        b.prenom,
        b.sexe,
        b.date_naissance,
        b.telephone,
        b.numero_piece_identite,
        b.type_piece,
        "; ".join(s.libelle for s in b.statuts_particuliers.all()),
        "; ".join(t.libelle for t in b.types_activite.all()),
        float(b.latitude) if b.latitude is not None else None,
        float(b.longitude) if b.longitude is not None else None,
        "" if b.consentement is None else "Oui" if b.consentement else "Non",
        b.date_consentement,
        codes_projets,
    ]


def _feuille(wb, titre, colonnes, lignes, premiere=False):
    feuille = wb.active if premiere else wb.create_sheet()
    # Titre d'onglet Excel : 31 caractères max, sans []:*?/\
    feuille.title = "".join(c for c in titre if c not in "[]:*?/\\")[:31]
    # En-têtes au vocabulaire de l'organisation (réimportables : l'import les ramène aux noms par défaut).
    feuille.append([v(c) for c in colonnes])
    for cellule in feuille[1]:
        cellule.font = Font(bold=True, color="FFFFFF")
        cellule.fill = PatternFill("solid", fgColor=COULEUR_ENTETE)
        cellule.alignment = Alignment(vertical="center", wrap_text=True)
    for ligne in lignes:
        feuille.append(ligne)
    if "Date de naissance (AAAA-MM-JJ)" in colonnes:
        lettre = get_column_letter(colonnes.index("Date de naissance (AAAA-MM-JJ)") + 1)
        for cellule in feuille[lettre][1:]:
            cellule.number_format = "DD/MM/YYYY"
    quadriller(feuille, max_col=len(colonnes))
    figer_entete(feuille)
    feuille.auto_filter.ref = f"A1:{get_column_letter(len(colonnes))}{max(feuille.max_row, 1)}"
    for i, entete in enumerate(colonnes, start=1):
        feuille.column_dimensions[get_column_letter(i)].width = max(12, min(30, len(str(entete)) + 4))
    return feuille


def _lignes_projet(beneficiaires, projet, nb_niveaux, variables):
    lignes = []
    for b in beneficiaires:
        participations = [p for p in b.participations.all() if p.projet_id == projet.id]
        for p in participations or [None]:
            lignes.append(
                _colonnes_beneficiaire(b, projet.code, nb_niveaux)
                + [b.identifiant]
                + [
                    p.activite.libelle if p and p.activite else "",
                    p.sous_activite.libelle if p and p.sous_activite else "",
                    p.date_inscription if p else None,
                    p.role_dans_projet if p else "",
                ]
                + [cellule(variable, b, [projet.id]) for variable in variables]
            )
    return lignes


def _charger(queryset):
    return list(
        queryset.select_related("zone__niveau_administratif", "zone__parent__niveau_administratif")
        .prefetch_related(
            "statuts_particuliers",
            "types_activite",
            "participations__projet",
            "participations__activite",
            "participations__sous_activite",
        )
        .order_by("nom", "prenom")
    )


def _inscrits(beneficiaires, projet):
    return [b for b in beneficiaires if any(p.projet_id == projet.id for p in b.participations.all())]


def exporter_beneficiaires(queryset, projets, inclure_sans_projet=False) -> bytes:
    """
    `projets` : les projets à détailler, une feuille chacun. Un seul projet →
    une seule feuille ; plusieurs → liste complète (sans doublon) en tête,
    puis une feuille par projet. `inclure_sans_projet` : export de tous les
    bénéficiaires, y compris ceux qui ne sont inscrits à aucun projet.
    """
    beneficiaires = _charger(queryset)
    # Localisation aux niveaux du pays le plus représenté (Région, Province, Commune au Burkina Faso).
    pays_principal = Counter(b.pays for b in beneficiaires if b.pays).most_common(1)
    pays_principal = pays_principal[0][0] if pays_principal else "BF"
    nb_niveaux = len(niveaux_du_pays(pays_principal))
    colonnes = colonnes_import(pays_principal)
    # Variables personnalisées : une colonne chacune, « NA » si elle ne concerne pas le projet.
    variables = list(VariableBeneficiaire.objects.prefetch_related("projets"))
    noms_variables = [variable.libelle for variable in variables]
    colonnes_projet = colonnes + ["Identifiant"] + COLONNES_PARTICIPATION + noms_variables
    wb = Workbook()

    if len(projets) == 1 and not inclure_sans_projet:
        projet = projets[0]
        _feuille(wb, projet.code, colonnes_projet, _lignes_projet(beneficiaires, projet, nb_niveaux, variables), premiere=True)
    else:
        colonnes_global = colonnes[:-1] + [v('Projets (codes)'), v('Projets (noms)'), "Identifiant"] + noms_variables
        lignes = []
        for b in beneficiaires:
            projets_b = sorted({p.projet for p in b.participations.all()}, key=lambda p: p.code)
            lignes.append(
                _colonnes_beneficiaire(b, "", nb_niveaux)[:-1]
                + ["; ".join(p.code for p in projets_b), "; ".join(p.nom for p in projets_b), b.identifiant]
                + [cellule(variable, b, [p.id for p in projets_b]) for variable in variables]
            )
        _feuille(wb, v('Tous les bénéficiaires'), colonnes_global, lignes, premiere=True)
        for projet in projets:
            inscrits = _inscrits(beneficiaires, projet)
            if inscrits:
                _feuille(wb, projet.code, colonnes_projet, _lignes_projet(inscrits, projet, nb_niveaux, variables))
        sans_projet = [b for b in beneficiaires if not b.participations.all()] if inclure_sans_projet else []
        if sans_projet:
            _feuille(
                wb, v('Sans projet'), colonnes + ["Identifiant"] + noms_variables,
                [
                    _colonnes_beneficiaire(b, "", nb_niveaux) + [b.identifiant] + [cellule(variable, b, []) for variable in variables]
                    for b in sans_projet
                ],
            )

    buffer = io.BytesIO()
    # Export réimportable : seuls les en-têtes et noms de feuilles sont traduits, jamais les données
    # (un type d'activité « Maraîchage » doit être retrouvé tel quel à l'import).
    traduire_classeur(wb, garder=lambda feuille, cellule: cellule.row > 1)
    wb.save(buffer)
    return buffer.getvalue()


def exporter_beneficiaires_pdf(queryset, projets, inclure_sans_projet=False) -> bytes:
    """Même découpage que l'export Excel : un tableau par projet (et « Sans projet » si demandé)."""
    import datetime

    from django.utils.html import escape
    from weasyprint import HTML

    beneficiaires = _charger(queryset)
    cellule = 'style="padding:4px 6px;border-bottom:1px solid #e5e5e5;vertical-align:top;"'
    entetes = ["#", "Nom et prénom", "Sexe", "Naissance", "Téléphone", "Pièce d'identité", "Localité",
               "Statuts particuliers", "Activité / sous-activité", "Inscription"]

    def tableau(lignes):
        ths = "".join(f'<th style="padding:5px 6px;text-align:left;">{v(e)}</th>' for e in entetes)
        return (
            '<table style="width:100%;border-collapse:collapse;">'
            f'<thead><tr style="background:#1F4E78;color:white;font-size:10px;text-transform:uppercase;">{ths}</tr></thead>'
            f"<tbody>{''.join(lignes)}</tbody></table>"
        )

    def ligne(numero, b, participation):
        par_ordre = _niveaux_zone(b.zone)
        localite = ", ".join(par_ordre[o] for o in sorted(par_ordre, reverse=True))
        piece = " ".join(x for x in (b.type_piece, b.numero_piece_identite) if x)
        activite = ""
        if participation:
            activite = " / ".join(
                x.libelle for x in (participation.activite, participation.sous_activite) if x
            )
        valeurs = [
            numero,
            f"<strong>{escape(b.nom)}</strong> {escape(b.prenom)}",
            b.sexe,
            b.date_naissance.strftime("%d/%m/%Y") if b.date_naissance else "",
            escape(b.telephone),
            escape(piece),
            escape(localite),
            escape(", ".join(s.libelle for s in b.statuts_particuliers.all())),
            escape(activite),
            participation.date_inscription.strftime("%d/%m/%Y") if participation else "",
        ]
        return "<tr>" + "".join(f"<td {cellule}>{v}</td>" for v in valeurs) + "</tr>"

    sections = []
    for projet in projets:
        inscrits = _inscrits(beneficiaires, projet)
        if not inscrits:
            continue
        lignes = []
        for i, b in enumerate(inscrits, start=1):
            participation = next((p for p in b.participations.all() if p.projet_id == projet.id), None)
            lignes.append(ligne(i, b, participation))
        femmes = sum(1 for b in inscrits if b.sexe == "F")
        sections.append(
            f"<h3>{escape(projet.code)} — {escape(projet.nom)}</h3>"
            f'<div class="resume">{len(inscrits)} bénéficiaire(s) · {femmes} femme(s) · {len(inscrits) - femmes} homme(s)</div>'
            + tableau(lignes)
        )
    if inclure_sans_projet:
        sans_projet = [b for b in beneficiaires if not b.participations.all()]
        if sans_projet:
            sections.append(
                f'<h3>Sans projet</h3><div class="resume">{len(sans_projet)} bénéficiaire(s)</div>'
                + tableau([ligne(i, b, None) for i, b in enumerate(sans_projet, start=1)])
            )

    titre = (
        v('Bénéficiaires — tous les projets')
        if inclure_sans_projet
        else v('Bénéficiaires — ') + ", ".join(p.code for p in projets)
    )
    html_content = f"""
    <html><head><style>
      @page {{ size: A4 landscape; margin: 12mm 10mm; }}
      body {{ font-family: "Helvetica Neue", Arial, sans-serif; color: #222; font-size: 11px; }}
      h2 {{ margin-bottom: 2px; font-size: 20px; }}
      h3 {{ margin: 18px 0 4px; border-bottom: 2px solid #1F4E78; padding-bottom: 4px; color: #1F4E78; font-size: 15px; }}
      .resume {{ color: #666; margin-bottom: 6px; }}
      tr {{ page-break-inside: avoid; }}
    </style></head><body>
      <h2>{escape(titre)}</h2>
      <div class="resume">Généré le {datetime.date.today().strftime('%d/%m/%Y')} · {len(beneficiaires)} bénéficiaire(s) au total</div>
      {"".join(sections) or v('<p style="color:#888;">Aucun bénéficiaire.</p>')}
    </body></html>
    """
    return HTML(string=traduire_html(html_content)).write_pdf()
