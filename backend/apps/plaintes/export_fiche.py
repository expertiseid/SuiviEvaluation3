"""
Fiche d'un dossier en PDF (lot 5). Chaque page porte en filigrane le nom de la personne qui exporte
et la date ; pour un dossier confidentiel, la mention « Confidentiel ». L'export est tracé au journal
(voir views.DossierViewSet.exporter) ; pour un dossier confidentiel, il exige un motif.
"""
import html

from django.utils import timezone

from apps.core.vocabulaire import v

from .models import ActionDossier, Canal, IssueDossier, ModeReponse, StatutDossier
from .traitement import nom_personne


def _e(texte):
    return html.escape(str(texte or "")).replace("\n", "<br/>")


def _date(d):
    return d.strftime("%d/%m/%Y") if d else "—"


def fiche_pdf(dossier, auteur):
    from weasyprint import HTML

    maintenant = timezone.localtime()
    filigrane = v(f"Exporté par {nom_personne(auteur)} le {maintenant:%d/%m/%Y à %H:%M}")
    if dossier.sensible:
        filigrane = v("Confidentiel") + " — " + filigrane
    choix = lambda enum, valeur: v(dict(enum.choices).get(valeur, valeur or "—"))  # noqa: E731
    lignes = [
        (v("Statut"), choix(StatutDossier, dossier.statut)),
        (v("Reçu le"), _date(dossier.date_reception)),
        (v("Canal de réception"), choix(Canal, dossier.canal)),
        (v("Type de retour"), dossier.type_retour.nom),
        (v("Catégorie"), dossier.categorie.nom if dossier.categorie_id else v("À classer")),
        (v("Priorité"), dossier.priorite.nom if dossier.priorite_id else "—"),
        (v("Projet"), f"{dossier.projet.code} — {dossier.projet.nom}" if dossier.projet_id else "—"),
        (v("Lieu"), dossier.lieu or "—"),
        (v("Circuit et étape"), " › ".join(x for x in (dossier.circuit.nom if dossier.circuit_id else "",
                                                       dossier.etape.nom if dossier.etape_id else "") if x)),
        (v("Gestionnaire"), nom_personne(dossier.responsable) or "—"),
        (v("Échéance"), _date(dossier.echeance)),
    ]
    plaignant = [(v("Anonyme"), v("Oui"))] if dossier.anonyme else [
        (v("Nom"), dossier.nom or "—"), (v("Téléphone"), dossier.telephone or "—"),
        (v("Courriel"), dossier.courriel or "—"), (v("Réponse souhaitée"), choix(ModeReponse, dossier.mode_reponse)),
    ]
    issue = [
        (v("Décision"), dossier.decision or "—"),
        (v("Issue"), choix(IssueDossier, dossier.issue) if dossier.issue else "—"),
        (v("Motif de la clôture"), dossier.motif_cloture or "—"),
        (v("Clôturé le"), _date(dossier.date_cloture)),
    ]
    mis_en_cause = [nom_personne(u) for u in dossier.mis_en_cause_utilisateurs.all()]
    if dossier.mis_en_cause_libre:
        mis_en_cause.append(dossier.mis_en_cause_libre)
    actions = "".join(
        f"<tr><td>{timezone.localtime(a.date):%d/%m/%Y %H:%M}</td><td>{_e(v(a.get_type_display()))}</td>"
        f"<td>{_e(nom_personne(a.auteur))}</td><td>{_e(a.texte)}</td></tr>"
        for a in dossier.actions.select_related("auteur").order_by("date") if a.type != ActionDossier.Type.EXPORT
    )

    def tableau(paires):
        return "<table class='fiche'>" + "".join(f"<tr><th>{_e(c)}</th><td>{_e(val)}</td></tr>" for c, val in paires) + "</table>"

    contenu = f"""
    <html><head><meta charset="utf-8"><style>
      @page {{ size: A4; margin: 18mm 15mm; @bottom-right {{ content: counter(page) " / " counter(pages); font-size: 8pt; color: #666; }} }}
      body {{ font-family: 'DejaVu Sans', sans-serif; font-size: 9.5pt; color: #222; }}
      h1 {{ font-size: 15pt; color: #087f5b; margin: 0 0 4mm; }}
      h2 {{ font-size: 11pt; color: #087f5b; margin: 6mm 0 2mm; border-bottom: 1px solid #cde; }}
      table {{ width: 100%; border-collapse: collapse; }}
      table.fiche th {{ width: 32%; text-align: left; color: #555; font-weight: normal; padding: 1.5mm 2mm; vertical-align: top; }}
      table.fiche td {{ padding: 1.5mm 2mm; }}
      table.journal th, table.journal td {{ border: 1px solid #ccd; padding: 1.2mm 1.5mm; font-size: 8.5pt; vertical-align: top; text-align: left; }}
      table.journal th {{ background: #e6f4ef; }}
      .filigrane {{ position: fixed; top: 45%; left: -10%; width: 120%; text-align: center; transform: rotate(-30deg);
                    font-size: 22pt; color: rgba(200, 30, 30, 0.13); font-weight: bold; }}
      .bandeau {{ background: {"#f3e5f5" if dossier.sensible else "#e6f4ef"}; padding: 2mm 3mm; font-size: 8.5pt; margin-bottom: 4mm; }}
    </style></head><body>
      <div class="filigrane">{_e(filigrane)}</div>
      <h1>{_e(v("Dossier"))} {_e(dossier.numero)}</h1>
      <div class="bandeau">{_e(filigrane)}</div>
      {tableau(lignes)}
      <h2>{_e(v("Description"))}</h2><p>{_e(dossier.description)}</p>
      <h2>{_e(v("Plaignant"))}</h2>{tableau(plaignant)}
      {f"<h2>{_e(v('Personnes mises en cause'))}</h2><p>{_e(', '.join(mis_en_cause))}</p>" if mis_en_cause else ""}
      <h2>{_e(v("Décision et clôture"))}</h2>{tableau(issue)}
      <h2>{_e(v("Journal du dossier"))}</h2>
      <table class="journal"><tr><th>{_e(v("Date"))}</th><th>{_e(v("Action"))}</th><th>{_e(v("Auteur"))}</th><th>{_e(v("Détail"))}</th></tr>{actions}</table>
    </body></html>"""
    return HTML(string=contenu).write_pdf()
