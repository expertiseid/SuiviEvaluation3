"""
Circuit confidentiel complet (lot 5) — partie 8 du cahier des charges.

- Marquage manuel : tout utilisateur qui voit un dossier peut le signaler comme sensible ; effet
  immédiat, il en perd l'accès s'il n'est pas habilité. Levée : seulement par une personne habilitée
  (point focal du circuit, Administrateur), avec un motif inscrit au journal.
- Personnes mises en cause : exclues du dossier (même Administrateur), de ses notifications et de son
  traitement. Si l'une d'elles est destinataire du circuit confidentiel habituel, le dossier part vers
  le circuit alternatif défini par l'organisation.
- Assistance et référencement : orientation vers un prestataire de l'annuaire, avec consentement ; on
  enregistre consentement, date et prestataire, jamais le contenu des échanges.
- Conservation : à l'échéance de conservation, le dossier est proposé à l'anonymisation ; une personne
  confirme. La suspension légale (procédure en cours) l'empêche. Les données utiles aux statistiques
  (numéro, dates, type, catégorie, canal, statut, issue) sont conservées.
"""
from datetime import date

from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from apps.accounts.constants import ROLE_ADMIN
from apps.core.vocabulaire import v

from .models import ActionDossier, Circuit, Dossier, Mecanisme, Prestataire, Referencement, StatutDossier

A = ActionDossier.Type


def ids_mis_en_cause(dossier):
    return set(dossier.mis_en_cause_utilisateurs.values_list("pk", flat=True)) if dossier.pk else set()


def circuit_confidentiel_pour(dossier, categorie_circuit=None):
    """
    Circuit confidentiel du dossier : celui de sa catégorie ou le circuit par défaut — sauf si une
    personne mise en cause en est destinataire : alors le circuit alternatif.
    """
    mecanisme = Mecanisme.courant()
    circuit = categorie_circuit or Circuit.objects.filter(actif=True, sensible=True, par_defaut=True).first()
    vises = ids_mis_en_cause(dossier)
    if circuit and vises and circuit.etapes.filter(responsable_id__in=vises).exists():
        alternatif = mecanisme.circuit_alternatif
        if alternatif and alternatif.actif:
            return alternatif
    return circuit


def est_habilite(dossier, user):
    """Point focal habilité du circuit confidentiel du dossier, ou Administrateur — jamais une personne mise en cause."""
    from . import habilitations

    if user.pk in ids_mis_en_cause(dossier):
        return False
    if user.role == ROLE_ADMIN:
        return True
    return habilitations.est_habilite(user) and bool(dossier.circuit_id and dossier.circuit.etapes.filter(responsable=user).exists())


def _passer_au_confidentiel(dossier, auteur, texte):
    from .reception import circuit_pour
    from .traitement import personnes_habilitees

    categorie_circuit = circuit_pour(dossier.categorie, True) if dossier.categorie_id else None
    circuit = circuit_confidentiel_pour(dossier, categorie_circuit if categorie_circuit and categorie_circuit.sensible else None)
    changement = (not dossier.sensible) or circuit != dossier.circuit
    dossier.sensible = True
    if circuit != dossier.circuit:
        dossier.circuit = circuit
        dossier.etape = circuit.etapes.order_by("ordre", "id").first() if circuit else None
    if dossier.responsable_id and not personnes_habilitees(dossier).filter(pk=dossier.responsable_id).exists():
        dossier.responsable = None
    dossier.save()
    if changement:
        ActionDossier.objects.create(dossier=dossier, type=A.SENSIBILITE, auteur=auteur, texte=texte,
                                     details={"circuit": circuit.nom if circuit else ""})
        from . import delais

        delais.recalculer(dossier, entree_etape=timezone.localdate())


@transaction.atomic
def signaler_sensible(dossier, auteur, donnees):
    """Marquage manuel : effet immédiat ; dans le doute, la protection l'emporte."""
    if dossier.sensible:
        raise ValidationError({"detail": v("Ce dossier est déjà traité dans le circuit confidentiel.")})
    motif = (donnees.get("motif") or "").strip()
    _passer_au_confidentiel(dossier, auteur, motif or v("Dossier signalé comme sensible."))
    return dossier


@transaction.atomic
def lever_sensibilite(dossier, auteur, donnees):
    """Levée motivée, par une personne habilitée ; impossible tant qu'une raison de protection demeure."""
    from .reception import circuit_pour

    if not dossier.sensible:
        raise ValidationError({"detail": v("Ce dossier n'est pas sensible.")})
    if not est_habilite(dossier, auteur):
        raise ValidationError({"detail": v("Seule une personne habilitée du circuit confidentiel peut lever la sensibilité.")})
    motif = (donnees.get("motif") or "").strip()
    if not motif:
        raise ValidationError({"motif": v("Indiquez le motif de la levée.")})
    if dossier.categorie_id and dossier.categorie.sensible_effective:
        raise ValidationError({"detail": v("La catégorie du dossier est sensible : reclassez-le d'abord dans une catégorie ordinaire.")})
    if ids_mis_en_cause(dossier) or dossier.mis_en_cause_libre:
        raise ValidationError({"detail": v("Des personnes sont mises en cause : le dossier reste confidentiel.")})
    if dossier.concerne_personnel:
        raise ValidationError({"detail": v("Le retour vise le personnel ou un partenaire : il reste confidentiel.")})
    circuit = circuit_pour(dossier.categorie, False)
    dossier.sensible = False
    dossier.circuit = circuit
    dossier.etape = circuit.etapes.order_by("ordre", "id").first() if circuit else None
    dossier.save()
    ActionDossier.objects.create(dossier=dossier, type=A.SENSIBILITE, auteur=auteur, texte=motif,
                                 details={"leve": True, "circuit": circuit.nom if circuit else ""})
    from . import delais

    delais.recalculer(dossier, entree_etape=timezone.localdate())
    return dossier


@transaction.atomic
def mettre_en_cause(dossier, auteur, donnees):
    """Personnes mises en cause (comptes et noms libres) : remplace la liste ; le dossier devient confidentiel."""
    from apps.accounts.models import User

    if dossier.statut == StatutDossier.CLOTURE:
        raise ValidationError({"detail": v("Ce dossier est clôturé : rouvrez-le d'abord.")})
    ids = [int(i) for i in donnees.get("utilisateurs") or [] if str(i).isdigit()]
    if auteur.pk in ids:
        raise ValidationError({"utilisateurs": v("Vous ne pouvez pas vous désigner vous-même.")})
    utilisateurs = list(User.objects.filter(pk__in=ids))
    libre = (donnees.get("libre") or "").strip()
    dossier.mis_en_cause_utilisateurs.set(utilisateurs)
    dossier.mis_en_cause_libre = libre
    dossier.save(update_fields=["mis_en_cause_libre", "updated_at"])
    ActionDossier.objects.create(dossier=dossier, type=A.MISE_EN_CAUSE, auteur=auteur,
                                 details={"comptes": len(utilisateurs), "noms_libres": bool(libre)})
    if utilisateurs or libre:
        _passer_au_confidentiel(dossier, auteur, v("Des personnes sont mises en cause : traitement confidentiel."))
    return dossier


@transaction.atomic
def orienter_assistance(dossier, auteur, donnees):
    prestataire = Prestataire.objects.filter(pk=donnees.get("prestataire"), actif=True).first() if str(donnees.get("prestataire") or "").isdigit() else None
    erreurs = {}
    if prestataire is None:
        erreurs["prestataire"] = v("Choisissez un prestataire de l'annuaire.")
    if donnees.get("consentement") is not True:
        erreurs["consentement"] = v("L'orientation exige le consentement de la personne.")
    try:
        jour = date.fromisoformat(str(donnees.get("date") or timezone.localdate())[:10])
    except ValueError:
        erreurs["date"] = v("Date invalide.")
    if erreurs:
        raise ValidationError(erreurs)
    Referencement.objects.create(dossier=dossier, prestataire=prestataire, type=prestataire.type, consentement=True,
                                 date=jour, auteur=auteur)
    ActionDossier.objects.create(dossier=dossier, type=A.ASSISTANCE, auteur=auteur,
                                 details={"prestataire": prestataire.nom, "type": prestataire.type, "date": jour.isoformat()})
    return dossier


def _reserve_admin(auteur, message):
    if auteur.role != ROLE_ADMIN:
        raise ValidationError({"detail": message})


@transaction.atomic
def suspendre(dossier, auteur, donnees):
    """Suspension légale (procédure en cours) : le dossier ne peut pas être anonymisé ; levée motivée."""
    _reserve_admin(auteur, v("La suspension légale est réservée à l'Administrateur."))
    motif = (donnees.get("motif") or "").strip()
    if not motif:
        raise ValidationError({"motif": v("Indiquez le motif.")})
    actif = bool(donnees.get("suspendre", True))
    dossier.suspension_legale = actif
    dossier.motif_suspension = motif if actif else ""
    dossier.save(update_fields=["suspension_legale", "motif_suspension", "updated_at"])
    ActionDossier.objects.create(dossier=dossier, type=A.SUSPENSION, auteur=auteur, texte=motif, details={"active": actif})
    return dossier


def fin_de_conservation(dossier, mecanisme=None):
    """Date à partir de laquelle le contenu d'un dossier clôturé peut être supprimé."""
    mecanisme = mecanisme or Mecanisme.courant()
    mois = mecanisme.conservation_sensible_mois if dossier.sensible else mecanisme.conservation_ordinaire_mois
    if not (dossier.date_cloture and mois):
        return None
    annee, reste = divmod(dossier.date_cloture.month - 1 + mois, 12)
    try:
        return dossier.date_cloture.replace(year=dossier.date_cloture.year + annee, month=reste + 1)
    except ValueError:  # 31 → fin du mois
        return dossier.date_cloture.replace(year=dossier.date_cloture.year + annee, month=reste + 1, day=28)


def a_anonymiser(queryset=None, aujourdhui=None):
    """Dossiers clôturés dont la durée de conservation est écoulée, non suspendus, pas encore anonymisés."""
    aujourdhui = aujourdhui or timezone.localdate()
    mecanisme = Mecanisme.courant()
    qs = (queryset if queryset is not None else Dossier.objects.all()).filter(
        statut=StatutDossier.CLOTURE, anonymise=False, suspension_legale=False).exclude(date_cloture=None)
    return [d for d in qs if (fin := fin_de_conservation(d, mecanisme)) and fin <= aujourdhui]


@transaction.atomic
def anonymiser(dossier, auteur, donnees):
    """
    Supprime le contenu et l'identité (récit, coordonnées, personnes mises en cause, notes, décision, pièces jointes,
    historique détaillé), garde ce qui sert aux statistiques. Irréversible : confirmation exigée.
    """
    _reserve_admin(auteur, v("L'anonymisation est réservée à l'Administrateur."))
    if dossier.suspension_legale:
        raise ValidationError({"detail": v("Suspension légale en cours : ce dossier ne peut pas être anonymisé.")})
    if dossier.statut != StatutDossier.CLOTURE:
        raise ValidationError({"detail": v("Seul un dossier clôturé peut être anonymisé.")})
    if donnees.get("confirmation") is not True:
        raise ValidationError({"confirmation": v("Confirmez l'anonymisation : elle est irréversible.")})
    efface = v("[contenu supprimé à l'échéance de conservation]")
    for champ in ("lieu", "nom", "telephone", "courriel", "mis_en_cause_libre", "decision", "motif_cloture",
                  "raison_sans_retour", "motif_suspension"):
        setattr(dossier, champ, "")
    dossier.description = efface
    dossier.anonyme = True
    dossier.mode_reponse = "AUCUN"
    dossier.anonymise = True
    dossier.date_anonymisation = timezone.localdate()
    dossier.save()
    dossier.mis_en_cause_utilisateurs.clear()
    from .pieces import supprimer_toutes

    supprimer_toutes(dossier)  # pièces jointes et leurs fichiers
    ActionDossier.objects.filter(dossier=dossier).update(texte="", details={})
    dossier.history.all().delete()  # copies de l'historique : le contenu ne doit survivre nulle part
    ActionDossier.objects.create(dossier=dossier, type=A.ANONYMISATION, auteur=auteur)
    return dossier
