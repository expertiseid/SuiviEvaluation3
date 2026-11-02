"""
Exports du pilotage (lot 6) : vue du tableau de bord en Excel et en PDF (synthèse), liste des
dossiers en Excel. Dans la langue de l'utilisateur (dans_la_langue_demandee).

La liste des dossiers n'inclut jamais les dossiers confidentiels (chacun s'exporte à part, avec
motif : voir export_fiche) ; les coordonnées n'y figurent que pour l'Administrateur qui les demande ;
chaque dossier exporté est inscrit à son journal.
"""
import html
import io

from django.utils import timezone
from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill

from apps.core.vocabulaire import v

from .models import ActionDossier, Canal, IssueDossier, StatutDossier
from .traitement import nom_personne

ENTETE = PatternFill("solid", fgColor="087F5B")


def _valeur(element):
    valeur = element.get("valeur")
    if valeur is None:
        return "—"
    return f"{valeur} {element.get('unite') or ''}".strip()


def _periode(element):
    p = element.get("periode") or {}
    if p.get("du"):
        return f"{p['du']:%d/%m/%Y} – {p['au']:%d/%m/%Y}"
    return v("au") + f" {p['au']:%d/%m/%Y}" if p.get("au") else ""


def _entete(feuille, colonnes, largeurs):
    feuille.append(colonnes)
    for i, cellule in enumerate(feuille[feuille.max_row], start=1):
        cellule.font = Font(bold=True, color="FFFFFF")
        cellule.fill = ENTETE
        feuille.column_dimensions[cellule.column_letter].width = largeurs[i - 1]


def vue_excel(resultat):
    wb = Workbook()
    ws = wb.active
    ws.title = v("Indicateurs")[:31]
    ws.append([f"{v('Plaintes et retours')} — {resultat['libelle']}"])
    ws["A1"].font = Font(bold=True, size=13)
    ws.append([v("Période"), f"{resultat['du']:%d/%m/%Y} – {resultat['au']:%d/%m/%Y}"])
    ws.append([v("Une hausse du nombre de plaintes peut traduire une meilleure accessibilité du mécanisme, pas une "
                 "dégradation du projet.")])
    ws.append([])
    _entete(ws, [v("Indicateur"), v("Valeur"), v("Numérateur"), v("Dénominateur"), v("Période"), v("Définition")],
            [34, 14, 13, 14, 24, 80])
    for e in resultat["elements"]:
        if e["nature"] == "chiffre":
            ws.append([e["libelle"], _valeur(e), e.get("numerateur"), e.get("denominateur"), _periode(e), e["definition"]])
            ws.cell(ws.max_row, 6).alignment = Alignment(wrap_text=True)
    for e in resultat["elements"]:
        if e["nature"] == "graphique":
            feuille = wb.create_sheet(e["libelle"][:31].replace("/", "-"))
            _entete(feuille, [e["libelle"], v("Nombre")], [44, 14])
            for c, n in zip(e["categories"], e["valeurs"]):
                feuille.append([c, n])
            if e.get("confidentiels") is not None:
                feuille.append([v("Dossiers confidentiels (total)"), e["confidentiels"]])
        elif e["nature"] == "liste":
            feuille = wb.create_sheet(e["libelle"][:31].replace("/", "-"))
            _entete(feuille, e["colonnes"], [22] * len(e["colonnes"]))
            for ligne in e["lignes"]:
                feuille.append([c.strftime("%d/%m/%Y") if hasattr(c, "strftime") else c for c in ligne["cellules"]])
    sortie = io.BytesIO()
    wb.save(sortie)
    return sortie.getvalue()


def vue_pdf(resultat, auteur):
    from weasyprint import HTML

    e_ = lambda t: html.escape(str(t if t is not None else "—"))  # noqa: E731
    chiffres = "".join(
        f"<tr><td><b>{e_(e['libelle'])}</b><br/><span class='def'>{e_(e['definition'])}</span></td>"
        f"<td class='val'>{e_(_valeur(e))}</td><td>{e_(e.get('numerateur'))} / {e_(e.get('denominateur'))}</td>"
        f"<td>{e_(_periode(e))}</td></tr>"
        for e in resultat["elements"] if e["nature"] == "chiffre")
    blocs = []
    for e in resultat["elements"]:
        if e["nature"] == "graphique":
            lignes = "".join(f"<tr><td>{e_(c)}</td><td class='val'>{e_(n)}</td></tr>" for c, n in zip(e["categories"], e["valeurs"]))
            if e.get("confidentiels") is not None:
                lignes += f"<tr><td><i>{e_(v('Dossiers confidentiels (total)'))}</i></td><td class='val'>{e_(e['confidentiels'])}</td></tr>"
            blocs.append(f"<h2>{e_(e['libelle'])}</h2><table class='t'>{lignes}</table>")
        elif e["nature"] == "liste":
            entete = "".join(f"<th>{e_(c)}</th>" for c in e["colonnes"])
            lignes = "".join("<tr>" + "".join(
                f"<td>{e_(c.strftime('%d/%m/%Y') if hasattr(c, 'strftime') else c)}</td>" for c in l["cellules"]) + "</tr>"
                for l in e["lignes"])
            blocs.append(f"<h2>{e_(e['libelle'])}</h2><table class='t'><tr>{entete}</tr>{lignes}</table>")
    contenu = f"""<html><head><meta charset="utf-8"><style>
      @page {{ size: A4; margin: 15mm; @bottom-right {{ content: counter(page) " / " counter(pages); font-size: 8pt; }} }}
      body {{ font-family: 'DejaVu Sans', sans-serif; font-size: 9pt; color: #222; }}
      h1 {{ color: #087f5b; font-size: 15pt; margin: 0; }} h2 {{ color: #087f5b; font-size: 11pt; margin: 6mm 0 2mm; }}
      table {{ width: 100%; border-collapse: collapse; }} td, th {{ border: 1px solid #ccd; padding: 1.5mm; vertical-align: top; }}
      th {{ background: #e6f4ef; text-align: left; }} .val {{ text-align: right; font-weight: bold; white-space: nowrap; }}
      .def {{ color: #666; font-size: 7.5pt; }} .note {{ background: #fff4e6; padding: 2mm; font-size: 8pt; margin: 3mm 0; }}
    </style></head><body>
      <h1>{e_(v('Plaintes et retours'))} — {e_(resultat['libelle'])}</h1>
      <p>{e_(v('Période'))} : {resultat['du']:%d/%m/%Y} – {resultat['au']:%d/%m/%Y} · {e_(v('Édité par'))} {e_(nom_personne(auteur))},
         {timezone.localtime():%d/%m/%Y %H:%M}</p>
      <div class="note">{e_(v("Une hausse du nombre de plaintes peut traduire une meilleure accessibilité du mécanisme, pas une dégradation du projet."))}
        {e_(v(f"Les dossiers confidentiels ne figurent que dans des totaux ; un effectif inférieur à {resultat['seuil_masquage']} est masqué."))}</div>
      <table><tr><th>{e_(v('Indicateur'))}</th><th>{e_(v('Valeur'))}</th><th>{e_(v('Numérateur / dénominateur'))}</th><th>{e_(v('Période'))}</th></tr>{chiffres}</table>
      {''.join(blocs)}
    </body></html>"""
    return HTML(string=contenu).write_pdf()


def liste_dossiers_excel(dossiers, auteur, avec_coordonnees=False):
    """Dossiers ordinaires seulement ; coordonnées sur demande de l'Administrateur ; export inscrit au journal."""
    dossiers = [d for d in dossiers if not d.sensible]
    canaux, statuts, issues = dict(Canal.choices), dict(StatutDossier.choices), dict(IssueDossier.choices)
    wb = Workbook()
    ws = wb.active
    ws.title = v("Dossiers")[:31]
    colonnes = [v("Numéro"), v("Reçu le"), v("Canal"), v("Type de retour"), v("Catégorie"), v("Priorité"), v("Projet"),
                v("Lieu"), v("Statut"), v("Étape"), v("Gestionnaire"), v("Échéance"), v("Issue"), v("Clôturé le"),
                v("Description")]
    if avec_coordonnees:
        colonnes += [v("Nom"), v("Téléphone"), v("Courriel")]
    _entete(ws, colonnes, [16, 11, 18, 16, 26, 11, 16, 20, 18, 22, 20, 11, 20, 11, 60] + [22, 16, 24][:3 * avec_coordonnees])
    for d in dossiers:
        ligne = [d.numero, d.date_reception, v(canaux.get(d.canal, d.canal)), d.type_retour.nom,
                 d.categorie.nom if d.categorie_id else v("À classer"), d.priorite.nom if d.priorite_id else "",
                 d.projet.code if d.projet_id else "", d.lieu, v(statuts.get(d.statut, d.statut)),
                 d.etape.nom if d.etape_id else "", nom_personne(d.responsable), d.echeance,
                 v(issues.get(d.issue, "")) if d.issue else "", d.date_cloture, d.description]
        if avec_coordonnees:
            ligne += ["" if d.anonyme else d.nom, "" if d.anonyme else d.telephone, "" if d.anonyme else d.courriel]
        ws.append(ligne)
        for colonne in (2, 12, 14):
            ws.cell(ws.max_row, colonne).number_format = "DD/MM/YYYY"
    ActionDossier.objects.bulk_create([
        ActionDossier(dossier=d, type=ActionDossier.Type.EXPORT, auteur=auteur,
                      details={"liste": True, "coordonnees": avec_coordonnees}) for d in dossiers])
    sortie = io.BytesIO()
    wb.save(sortie)
    return sortie.getvalue(), len(dossiers)
