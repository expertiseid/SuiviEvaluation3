"""
Identifiant et carte des bénéficiaires.

Chaque bénéficiaire reçoit un identifiant unique (BEN-000123, voir Beneficiaire.save). Son QR
code contient le lien vers sa fiche (`<adresse de la plateforme>/beneficiaires/identifiant/BEN-…`) :
le scanner avec un téléphone ouvre directement la fiche (après connexion). Les cartes sont au
format carte de crédit (85 × 54 mm), 8 par page A4.
"""
import datetime

import segno
from django.utils.html import escape

from apps.core.vocabulaire import v


def lien_fiche(beneficiaire, origine: str) -> str:
    return f"{origine.rstrip('/')}/beneficiaires/identifiant/{beneficiaire.identifiant}"


def qr_svg(beneficiaire, origine: str, echelle: int = 4) -> str:
    """QR code du bénéficiaire, en SVG (sans déclaration XML : utilisable dans une page HTML)."""
    return segno.make(lien_fiche(beneficiaire, origine), error="m").svg_inline(scale=echelle, border=1, omitsize=True)


def _localite(zone):
    noms = []
    while zone is not None and len(noms) < 3:
        noms.append(zone.nom)
        zone = zone.parent
    return ", ".join(noms)


def _carte(b, origine):
    projets = sorted({p.projet.code for p in b.participations.all()})
    details = [
        {"F": "Femme", "M": "Homme"}.get(b.sexe, ""),
        b.date_naissance.strftime("né(e) le %d/%m/%Y") if b.date_naissance else "",
    ]
    return f"""
    <div class="carte">
      <div class="bandeau">{escape(v("Carte bénéficiaire"))}</div>
      <div class="corps">
        <div class="texte">
          <div class="nom">{escape(b.nom)} {escape(b.prenom)}</div>
          <div class="id">{escape(b.identifiant or "")}</div>
          <div class="ligne">{escape(" · ".join(d for d in details if d))}</div>
          <div class="ligne">{escape(_localite(b.zone))}</div>
          <div class="ligne">{escape(", ".join(projets))}</div>
        </div>
        <div class="qr">{qr_svg(b, origine, echelle=3)}</div>
      </div>
    </div>"""


CARTES_PAR_PAGE = 8  # 2 colonnes × 4 rangées


def cartes_pdf(beneficiaires, origine: str) -> bytes:
    """
    Cartes à imprimer, 8 par page A4. Chaque page est construite explicitement (tableau de
    2 × 4) : le moteur PDF ne coupe ainsi jamais une carte entre deux pages.
    """
    from weasyprint import HTML

    cartes = [_carte(b, origine) for b in beneficiaires]
    pages = []
    for debut in range(0, len(cartes), CARTES_PAR_PAGE):
        lot = cartes[debut : debut + CARTES_PAR_PAGE]
        rangees = "".join(
            "<tr>" + "".join(f"<td>{c}</td>" for c in lot[i : i + 2]) + "</tr>" for i in range(0, len(lot), 2)
        )
        pages.append(f'<table class="page">{rangees}</table>')
    html = f"""<html><head><meta charset="utf-8"><style>
      @page {{ size: A4; margin: 12mm 12mm 14mm;
              @bottom-left {{ content: "Imprimé le {datetime.date.today():%d/%m/%Y} — {len(beneficiaires)} carte(s)";
                              font-family: sans-serif; font-size: 7pt; color: #888; }}
              @bottom-right {{ content: "Page " counter(page) " / " counter(pages);
                               font-family: sans-serif; font-size: 7pt; color: #888; }} }}
      body {{ font-family: sans-serif; margin: 0; }}
      table.page {{ border-collapse: separate; border-spacing: 6mm 5mm; margin: -5mm -6mm; page-break-after: always; }}
      table.page:last-child {{ page-break-after: auto; }}
      td {{ padding: 0; vertical-align: top; }}
      .carte {{ width: 85mm; height: 54mm; border: 0.3mm solid #9aa; border-radius: 3mm; overflow: hidden;
               box-sizing: border-box; }}
      .bandeau {{ background: #0c8a5f; color: white; font-size: 8pt; font-weight: bold; padding: 1.5mm 3mm;
                  text-transform: uppercase; letter-spacing: 0.3mm; }}
      .corps {{ display: flex; padding: 2.5mm 3mm; gap: 2mm; }}
      .texte {{ flex: 1; min-width: 0; }}
      .nom {{ font-size: 10.5pt; font-weight: bold; }}
      .id {{ font-family: monospace; font-size: 10pt; color: #0c8a5f; margin: 1mm 0 1.5mm; }}
      .ligne {{ font-size: 7.5pt; color: #444; margin-bottom: 0.8mm; }}
      .qr svg {{ width: 26mm; height: 26mm; }}
    </style></head><body>{"".join(pages)}</body></html>"""
    return HTML(string=html).write_pdf()
