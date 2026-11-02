"""
Droits des personnes sur leurs données (lot 9) : accès, rectification, effacement, opposition.

Procédure tracée : chaque demande est enregistrée avec son échéance (un mois), puis traitée avec une
réponse motivée ; chaque étape va au journal d'audit, sans nom ni contenu. Réservé à l'Administrateur,
qui voit aussi les dossiers confidentiels. La plateforme ne modifie rien d'elle-même : la rectification
passe par « Modifier » (plaignant) sur la fiche du dossier, l'effacement par l'anonymisation.

Registre des traitements : export Excel décrivant le traitement (finalités, données, destinataires,
durées de conservation, mesures de sécurité) et la liste des demandes, sans donnée personnelle.
"""
import calendar
import io
from datetime import date

from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from apps.core.audit import A, auditer
from apps.core.vocabulaire import v

from .models import Categorie, DemandeDroits, Mecanisme, Prestataire

S = DemandeDroits.Statut


def un_mois_apres(jour: date) -> date:
    """Même jour le mois suivant (dernier jour du mois s'il n'existe pas : 31 janvier → 28 ou 29 février)."""
    annee, mois = (jour.year + 1, 1) if jour.month == 12 else (jour.year, jour.month + 1)
    return jour.replace(year=annee, month=mois, day=min(jour.day, calendar.monthrange(annee, mois)[1]))


def _date(valeur, champ):
    if not valeur:
        return timezone.localdate()
    try:
        jour = date.fromisoformat(str(valeur)[:10])
    except ValueError:
        raise ValidationError({champ: v("Date invalide.")})
    if jour > timezone.localdate():
        raise ValidationError({champ: v("La date ne peut pas être dans le futur.")})
    return jour


@transaction.atomic
def enregistrer(auteur, donnees):
    from .models import Dossier

    if donnees.get("type") not in DemandeDroits.Type.values:
        raise ValidationError({"type": v("Choisissez le droit exercé.")})
    demandeur = (donnees.get("demandeur") or "").strip()
    if not demandeur:
        raise ValidationError({"demandeur": v("Indiquez qui exerce ce droit.")})
    dossier = None
    numero = (donnees.get("numero_dossier") or "").strip()
    if numero:
        dossier = Dossier.objects.filter(numero__iexact=numero).first()
        if dossier is None:
            raise ValidationError({"numero_dossier": v("Aucun dossier ne porte ce numéro.")})
    reception = _date(donnees.get("date_reception"), "date_reception")
    demande = DemandeDroits.objects.create(
        type=donnees["type"], date_reception=reception, echeance=un_mois_apres(reception),
        demandeur=demandeur[:200], contact=(donnees.get("contact") or "").strip()[:255],
        description=(donnees.get("description") or "").strip(), dossier=dossier,
        numero_dossier=dossier.numero if dossier else "", enregistree_par=auteur,
    )
    auditer(auteur, A.DROITS_PERSONNES, f"Demande n° {demande.pk}", operation="enregistrement", type=demande.type,
            dossier=demande.numero_dossier)
    return demande


@transaction.atomic
def traiter(auteur, demande, donnees):
    """{statut, reponse} : en cours, satisfaite ou refusée ; une réponse est exigée pour conclure."""
    statut = donnees.get("statut")
    if statut not in (S.EN_COURS, S.SATISFAITE, S.REFUSEE):
        raise ValidationError({"statut": v("Choisissez l'état de la demande.")})
    reponse = (donnees.get("reponse") or "").strip()
    if statut != S.EN_COURS and not reponse:
        raise ValidationError({"reponse": v("Indiquez la réponse donnée à la personne (et le motif d'un refus).")})
    demande.statut = statut
    if reponse:
        demande.reponse = reponse
    demande.traitee_par = auteur
    demande.date_reponse = timezone.localdate() if statut != S.EN_COURS else None
    demande.save()
    auditer(auteur, A.DROITS_PERSONNES, f"Demande n° {demande.pk}", operation="traitement", statut=statut, type=demande.type)
    return demande


# --- Registre des traitements ----------------------------------------------------------------------

def _registre(mecanisme):
    from apps.accounts.models import User
    from apps.core.modules import MASQUE, acces_module

    from .habilitations import ids_habilites

    acces = sum(1 for u in User.objects.filter(is_active=True) if acces_module(u, "/plaintes") != MASQUE)
    sensibles = [c.nom for c in Categorie.objects.filter(actif=True) if c.sensible_effective]
    prestataires = Prestataire.objects.filter(actif=True).count()
    duree = lambda mois: f"{mois} mois après la clôture, puis anonymisation" if mois else "À fixer par l'organisation"  # noqa: E731
    return [
        ("Nom du traitement", mecanisme.nom),
        ("Responsable du traitement", mecanisme.responsable_traitement or "À compléter (Paramétrage › Mécanisme)"),
        ("Contact pour les données personnelles", mecanisme.contact_donnees or "À compléter (Paramétrage › Mécanisme)"),
        ("Finalités", "Recevoir, traiter et suivre les plaintes, retours et signalements des personnes concernées "
                      "par les projets ; répondre aux plaignants ; protéger les personnes (circuit confidentiel) ; "
                      "produire des statistiques anonymes de redevabilité."),
        ("Base légale", "Consentement du plaignant (recueilli au dépôt) ; obligations et intérêt légitime de "
                        "l'organisation pour les signalements de protection. À valider par l'organisation."),
        ("Personnes concernées", "Plaignants et auteurs de retours ; personnes mises en cause ; agents qui saisissent "
                                 "et traitent les dossiers."),
        ("Catégories de données", "Récit et lieu ; nom, téléphone, courriel, langue et mode de réponse (facultatifs, "
                                  "dépôt anonyme possible) ; personnes mises en cause ; pièces jointes ; décisions, "
                                  "notes et échanges ; journal des actions."),
        ("Données sensibles", f"Catégories confidentielles : {', '.join(sensibles)}" if sensibles else "Aucune catégorie confidentielle active"),
        ("Destinataires", f"{acces} compte(s) ayant accès au module ; dossiers confidentiels : {len(ids_habilites())} "
                          f"personne(s) habilitée(s) et les Administrateurs ; prestataires d'assistance ({prestataires}) "
                          "seulement avec le consentement de la personne."),
        ("Transferts hors du pays", "Aucun par la plateforme. À compléter selon le lieu d'hébergement du serveur."),
        ("Conservation des dossiers ordinaires", duree(mecanisme.conservation_ordinaire_mois)),
        ("Conservation des dossiers confidentiels", duree(mecanisme.conservation_sensible_mois)),
        ("Mesures de sécurité", "Récits, coordonnées, décisions, notes et pièces jointes chiffrés ; dossiers "
                                "confidentiels réservés aux personnes habilitées (double validation), personnes mises "
                                "en cause exclues ; métadonnées des pièces jointes effacées ; liens de téléchargement "
                                "de quelques minutes ; exports motivés et filigranés ; journal d'audit non modifiable ; "
                                "anonymisation à l'échéance de conservation."),
        ("Droits des personnes", "Accès, rectification, effacement et opposition : demandes enregistrées et suivies "
                                 "(réponse sous un mois), voir la feuille « Demandes »."),
        ("Mise à jour du registre", timezone.localdate().strftime("%d/%m/%Y")),
    ]


def registre_excel():
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font, PatternFill

    from apps.core.langues import traduire_classeur

    mecanisme = Mecanisme.courant()
    classeur = Workbook()
    feuille = classeur.active
    feuille.title = "Registre"
    feuille.append(["Registre des traitements — mécanisme de plaintes et retours"])
    feuille["A1"].font = Font(bold=True, size=13)
    feuille.append([])
    for rubrique, contenu in _registre(mecanisme):
        feuille.append([rubrique, contenu])
    for ligne in feuille.iter_rows(min_row=3):
        ligne[0].font = Font(bold=True)
        ligne[0].fill = PatternFill("solid", fgColor="E6F4F1")
        for cellule in ligne:
            cellule.alignment = Alignment(wrap_text=True, vertical="top")
    feuille.column_dimensions["A"].width = 34
    feuille.column_dimensions["B"].width = 100

    demandes = classeur.create_sheet("Demandes")
    demandes.append(["N°", "Droit exercé", "Reçue le", "Échéance", "État", "Réponse le", "Dossier lié"])
    for cellule in demandes[1]:
        cellule.font = Font(bold=True)
    for d in DemandeDroits.objects.order_by("date_reception", "id"):
        demandes.append([d.pk, d.get_type_display(), d.date_reception.strftime("%d/%m/%Y"), d.echeance.strftime("%d/%m/%Y"),
                         d.get_statut_display(), d.date_reponse.strftime("%d/%m/%Y") if d.date_reponse else "",
                         d.numero_dossier])
    for colonne, largeur in zip("ABCDEFG", (8, 26, 12, 12, 20, 12, 18)):
        demandes.column_dimensions[colonne].width = largeur
    # Le titre, les rubriques et les libellés se traduisent ; les valeurs saisies par l'organisation non.
    saisies = {3, 17} | ({4} if mecanisme.responsable_traitement else set()) | ({5} if mecanisme.contact_donnees else set())
    traduire_classeur(classeur, garder=lambda f, c: (f.title == "Registre" and c.column == 2 and c.row in saisies)
                      or (f.title == "Demandes" and c.row > 1 and c.column in (1, 3, 4, 6, 7)))
    sortie = io.BytesIO()
    classeur.save(sortie)
    return sortie.getvalue()
