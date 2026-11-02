"""
Traitement d'un dossier (lot 3) : classification, affectation et récusation, étapes du circuit,
notes et actions correctives, communication avec le plaignant, décision, clôture motivée (dont
les sorties Référée et Hors périmètre), réouverture, recours, dossiers liés.

Toutes les règles sont vérifiées ici, côté serveur : une transition interdite est refusée quelle
que soit l'interface. Chaque action laisse une trace dans le journal du dossier (ActionDossier).
"""
from datetime import timedelta

from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from apps.accounts.constants import ROLE_ADMIN, ROLE_COORDO_GENERAL
from apps.core.vocabulaire import v

from .models import ActionDossier, Categorie, Circuit, IssueDossier, ModeReponse, Priorite, StatutDossier, TypeRetour
from .reception import circuit_pour

A = ActionDossier.Type
# Réouverture : exceptionnelle, réservée à ces rôles.
ROLES_REOUVERTURE = {ROLE_ADMIN, ROLE_COORDO_GENERAL}


def nom_personne(u):
    return (f"{u.first_name} {u.last_name}".strip() or u.username) if u else ""


def journaliser(dossier, type_, auteur, texte="", **champs):
    return ActionDossier.objects.create(dossier=dossier, type=type_, auteur=auteur, texte=texte, **champs)


def _texte(donnees, champ, message):
    valeur = (donnees.get(champ) or "").strip()
    if not valeur:
        raise ValidationError({champ: message})
    return valeur


def _ouvert(dossier):
    if dossier.statut == StatutDossier.CLOTURE:
        raise ValidationError({"detail": v("Ce dossier est clôturé : rouvrez-le d'abord.")})


def _en_cours(dossier):
    if dossier.statut == StatutDossier.RECU:
        dossier.statut = StatutDossier.EN_COURS


def etapes(dossier):
    return list(dossier.circuit.etapes.order_by("ordre", "id")) if dossier.circuit_id else []


def personnes_habilitees(dossier):
    """
    Personnes à qui le dossier peut être confié : pour un dossier confidentiel, les responsables des
    étapes de son circuit et les Administrateurs ; sinon, les utilisateurs qui ont accès au module.
    """
    from apps.accounts.models import User
    from apps.core.modules import MASQUE, acces_module

    if dossier.sensible:
        ids = set(dossier.circuit.etapes.exclude(responsable=None).values_list("responsable_id", flat=True)) if dossier.circuit_id else set()
        return User.objects.filter(is_active=True).filter(pk__in=ids) | User.objects.filter(is_active=True, role=ROLE_ADMIN)
    ids = [u.pk for u in User.objects.filter(is_active=True) if acces_module(u, "/plaintes") != MASQUE]
    return User.objects.filter(pk__in=ids)


def _objet(modele, valeur, champ):
    if valeur in (None, ""):
        return None
    objet = modele.objects.filter(pk=valeur).first() if str(valeur).isdigit() else None
    if objet is None or not getattr(objet, "actif", True):
        raise ValidationError({champ: v("Choisissez une valeur de la liste.")})
    return objet


@transaction.atomic
def classer(dossier, auteur, donnees):
    """Type, catégorie, priorité, projet. Une catégorie sensible fait passer le dossier au circuit confidentiel."""
    _ouvert(dossier)
    changements = {}
    for champ, modele in (("type_retour", TypeRetour), ("categorie", Categorie), ("priorite", Priorite)):
        if champ not in donnees:
            continue
        nouveau = _objet(modele, donnees[champ], champ)
        if champ == "type_retour" and nouveau is None:
            raise ValidationError({champ: v("Choisissez un type de retour.")})
        ancien = getattr(dossier, champ)
        if ancien != nouveau:
            changements[champ] = [str(ancien) if ancien else "", str(nouveau) if nouveau else ""]
            setattr(dossier, champ, nouveau)
    if "projet" in donnees:
        from apps.projects.models import Projet

        from .models import Mecanisme

        projet = None
        if donnees["projet"] not in (None, ""):
            projet = Projet.objects.filter(pk=donnees["projet"]).first() if str(donnees["projet"]).isdigit() else None
            couverts = set(Mecanisme.courant().projets.values_list("id", flat=True))
            if projet is None or (couverts and projet.id not in couverts):
                raise ValidationError({"projet": v("Ce projet n'est pas couvert par le mécanisme.")})
        if dossier.projet != projet:
            changements["projet"] = [dossier.projet.code if dossier.projet else "", projet.code if projet else ""]
            dossier.projet = projet
    if not changements:
        return dossier
    journaliser(dossier, A.CLASSIFICATION, auteur, details=changements)
    # Dans le doute, protéger : un dossier devenu sensible quitte aussitôt le circuit ordinaire. L'inverse
    # (lever la sensibilité) n'est jamais automatique.
    if not dossier.sensible and dossier.categorie and dossier.categorie.sensible_effective:
        _vers_confidentiel(dossier, auteur)
    dossier.save()
    return dossier


def _vers_confidentiel(dossier, auteur):
    circuit = circuit_pour(dossier.categorie, True) or Circuit.objects.filter(actif=True, sensible=True, par_defaut=True).first()
    dossier.sensible = True
    dossier.circuit = circuit
    dossier.etape = circuit.etapes.order_by("ordre", "id").first() if circuit else None
    if dossier.responsable_id and not personnes_habilitees(dossier).filter(pk=dossier.responsable_id).exists():
        dossier.responsable = None
    journaliser(dossier, A.SENSIBILITE, auteur, v("Dossier transmis au circuit confidentiel."))


@transaction.atomic
def affecter(dossier, auteur, responsable_id):
    _ouvert(dossier)
    from apps.accounts.models import User

    responsable = User.objects.filter(pk=responsable_id, is_active=True).first() if str(responsable_id or "").isdigit() else None
    if responsable is None:
        raise ValidationError({"responsable": v("Choisissez une personne de la liste.")})
    if not personnes_habilitees(dossier).filter(pk=responsable.pk).exists():
        raise ValidationError({"responsable": v("Cette personne ne peut pas recevoir ce dossier (accès au module ou au circuit confidentiel).")})
    if dossier.en_recours and responsable.pk == dossier.gestionnaire_initial_id:
        raise ValidationError({"responsable": v("Un recours est réexaminé par une autre personne que le premier gestionnaire.")})
    ancien = dossier.responsable
    dossier.responsable = responsable
    if dossier.gestionnaire_initial_id is None and not dossier.en_recours:
        dossier.gestionnaire_initial = responsable
    _en_cours(dossier)
    dossier.save()
    journaliser(dossier, A.AFFECTATION, auteur, details={"de": nom_personne(ancien), "a": nom_personne(responsable)})
    return dossier


@transaction.atomic
def recuser(dossier, auteur, donnees):
    """Le gestionnaire se retire du dossier (conflit d'intérêts…), avec un motif ; le dossier est à réaffecter."""
    _ouvert(dossier)
    if dossier.responsable_id != auteur.pk:
        raise ValidationError({"detail": v("Seul le gestionnaire du dossier peut se récuser.")})
    motif = _texte(donnees, "motif", v("Indiquez le motif de la récusation."))
    dossier.responsable = None
    dossier.save()
    journaliser(dossier, A.RECUSATION, auteur, motif)
    return dossier


@transaction.atomic
def changer_etape(dossier, auteur, donnees):
    _ouvert(dossier)
    liste = etapes(dossier)
    cible = next((e for e in liste if str(e.pk) == str(donnees.get("etape"))), None)
    if cible is None:
        raise ValidationError({"etape": v("Choisissez une étape du circuit du dossier.")})
    if cible.est_cloture:
        raise ValidationError({"etape": v("Pour terminer le dossier, utilisez « Clôturer » (motif, décision et retour au plaignant).")})
    ancienne = dossier.etape
    dossier.etape = cible
    _en_cours(dossier)
    dossier.save()
    journaliser(dossier, A.ETAPE, auteur, (donnees.get("commentaire") or "").strip(),
                details={"de": ancienne.nom if ancienne else "", "a": cible.nom})
    return dossier


@transaction.atomic
def noter(dossier, auteur, donnees):
    """Note interne, ou action corrective (« corrective » : vrai), possible même sur un dossier clôturé."""
    texte = _texte(donnees, "texte", v("Écrivez la note."))
    journaliser(dossier, A.ACTION_CORRECTIVE if donnees.get("corrective") else A.NOTE, auteur, texte)
    return dossier


@transaction.atomic
def communiquer(dossier, auteur, donnees):
    """Trace un échange avec le plaignant ; la communication de la décision passe le dossier à « Réponse donnée »."""
    sens = donnees.get("sens") or ActionDossier.Sens.SORTANT
    objet = donnees.get("objet") or ActionDossier.Objet.AUTRE
    canal = donnees.get("canal") or ""
    if sens not in ActionDossier.Sens.values:
        raise ValidationError({"sens": v("Choisissez le sens de l'échange.")})
    if objet not in ActionDossier.Objet.values:
        raise ValidationError({"objet": v("Choisissez l'objet de l'échange.")})
    if canal not in ModeReponse.values or canal == ModeReponse.AUCUN:
        raise ValidationError({"canal": v("Choisissez le moyen utilisé.")})
    texte = _texte(donnees, "texte", v("Résumez l'échange."))
    if sens == ActionDossier.Sens.SORTANT:
        if canal in (ModeReponse.TELEPHONE, ModeReponse.SMS) and not dossier.telephone:
            raise ValidationError({"canal": v("Aucun numéro de téléphone n'est enregistré pour ce plaignant.")})
        if canal == ModeReponse.COURRIEL and not dossier.courriel:
            raise ValidationError({"canal": v("Aucune adresse courriel n'est enregistrée pour ce plaignant.")})
    if objet == ActionDossier.Objet.DECISION and sens == ActionDossier.Sens.SORTANT:
        if not dossier.decision:
            raise ValidationError({"objet": v("Enregistrez d'abord la décision.")})
        if dossier.statut != StatutDossier.CLOTURE:
            dossier.statut = StatutDossier.REPONDU
        dossier.date_reponse = timezone.localdate()
        dossier.save()
    journaliser(dossier, A.COMMUNICATION, auteur, texte, sens=sens, canal=canal, objet=objet)
    return dossier


@transaction.atomic
def decider(dossier, auteur, donnees):
    _ouvert(dossier)
    decision = _texte(donnees, "decision", v("Écrivez la décision."))
    dossier.decision = decision
    dossier.date_decision = timezone.localdate()
    _en_cours(dossier)
    dossier.save()
    journaliser(dossier, A.DECISION, auteur, decision)
    return dossier


@transaction.atomic
def cloturer(dossier, auteur, donnees):
    """
    Clôture motivée : issue, motif, décision enregistrée et retour donné au plaignant (ou la raison
    pour laquelle il n'a pas pu l'être). Sortie « Référée » : acteur externe et consentement exigés.
    """
    _ouvert(dossier)
    erreurs = {}
    issue = donnees.get("issue")
    if issue not in IssueDossier.values:
        erreurs["issue"] = v("Choisissez l'issue du dossier.")
    motif = (donnees.get("motif") or "").strip()
    if not motif:
        erreurs["motif"] = v("Indiquez le motif de la clôture.")
    decision = (donnees.get("decision") or "").strip() or dossier.decision
    if not decision:
        erreurs["decision"] = v("Une décision doit être enregistrée avant la clôture.")
    retour = donnees.get("retour_donne")
    if retour not in (True, False):
        erreurs["retour_donne"] = v("Indiquez si le plaignant a été informé de la réponse.")
    raison = (donnees.get("raison_sans_retour") or "").strip()
    if retour is False and not raison:
        erreurs["raison_sans_retour"] = v("Expliquez pourquoi le plaignant n'a pas pu être informé.")
    oriente_vers = (donnees.get("oriente_vers") or "").strip()
    consentement = bool(donnees.get("consentement_reference"))
    if issue == IssueDossier.REFERE:
        if not oriente_vers:
            erreurs["oriente_vers"] = v("Indiquez vers qui le dossier est orienté.")
        if not consentement:
            erreurs["consentement_reference"] = v("L'orientation vers un acteur externe exige le consentement du plaignant.")
    if erreurs:
        raise ValidationError(erreurs)
    if decision != dossier.decision:
        dossier.decision = decision
        dossier.date_decision = timezone.localdate()
        journaliser(dossier, A.DECISION, auteur, decision)
    cloture = next((e for e in etapes(dossier) if e.est_cloture), None)
    dossier.etape = cloture or dossier.etape
    dossier.statut = StatutDossier.CLOTURE
    dossier.issue = issue
    dossier.motif_cloture = motif
    dossier.retour_donne = retour
    dossier.raison_sans_retour = "" if retour else raison
    dossier.oriente_vers = oriente_vers if issue == IssueDossier.REFERE else ""
    dossier.consentement_reference = consentement if issue == IssueDossier.REFERE else False
    dossier.date_cloture = timezone.localdate()
    dossier.en_recours = False
    dossier.save()
    journaliser(dossier, A.CLOTURE, auteur, motif, details={
        "issue": issue, "retour_donne": retour, "raison_sans_retour": dossier.raison_sans_retour,
        "oriente_vers": dossier.oriente_vers,
    })
    return dossier


def _rouvrir_sur(dossier, donnees):
    liste = [e for e in etapes(dossier) if not e.est_cloture]
    cible = next((e for e in liste if str(e.pk) == str(donnees.get("etape"))), None)
    if donnees.get("etape") and cible is None:
        raise ValidationError({"etape": v("Choisissez une étape du circuit du dossier.")})
    dossier.etape = cible or (liste[-1] if liste else dossier.etape)
    dossier.statut = StatutDossier.EN_COURS
    dossier.issue = ""
    dossier.motif_cloture = ""
    dossier.retour_donne = None
    dossier.raison_sans_retour = ""
    dossier.date_cloture = None


@transaction.atomic
def rouvrir(dossier, auteur, donnees):
    """Réouverture exceptionnelle et motivée, réservée aux rôles autorisés."""
    if dossier.statut != StatutDossier.CLOTURE:
        raise ValidationError({"detail": v("Seul un dossier clôturé peut être rouvert.")})
    if auteur.role not in ROLES_REOUVERTURE:
        raise ValidationError({"detail": v("La réouverture est réservée à l'Administrateur et au Coordonnateur général.")})
    motif = _texte(donnees, "motif", v("Indiquez le motif de la réouverture."))
    _rouvrir_sur(dossier, donnees)
    dossier.save()
    journaliser(dossier, A.REOUVERTURE, auteur, motif, details={"etape": dossier.etape.nom if dossier.etape else ""})
    return dossier


@transaction.atomic
def recours(dossier, auteur, donnees):
    """Le plaignant conteste la réponse : réexamen par une autre personne que le premier gestionnaire."""
    if dossier.statut not in (StatutDossier.REPONDU, StatutDossier.CLOTURE):
        raise ValidationError({"detail": v("Un recours porte sur une réponse déjà donnée.")})
    motif = _texte(donnees, "motif", v("Indiquez ce que le plaignant conteste."))
    dossier.gestionnaire_initial = dossier.gestionnaire_initial or dossier.responsable
    dossier.responsable = None
    dossier.en_recours = True
    _rouvrir_sur(dossier, donnees)
    dossier.save()
    journaliser(dossier, A.RECOURS, auteur, motif)
    return dossier


@transaction.atomic
def lier(dossier, auteur, autre, delier=False):
    if autre.pk == dossier.pk:
        raise ValidationError({"detail": v("Un dossier ne peut pas être lié à lui-même.")})
    if delier:
        dossier.dossiers_lies.remove(autre)
    else:
        dossier.dossiers_lies.add(autre)
    texte = (v("Lien retiré avec {0}.") if delier else v("Lié au dossier {0}.")).replace("{0}", autre.numero)
    journaliser(dossier, A.LIEN, auteur, texte)
    journaliser(autre, A.LIEN, auteur, texte.replace(autre.numero, dossier.numero))
    return dossier


def dossiers_possiblement_lies(dossier, visibles):
    """Même projet et même catégorie, reçus à moins de 30 jours d'écart — jamais fusionnés automatiquement."""
    if not (dossier.projet_id and dossier.categorie_id):
        return visibles.none()
    ecart = timedelta(days=30)
    return (
        visibles.filter(projet_id=dossier.projet_id, categorie_id=dossier.categorie_id,
                        date_reception__range=(dossier.date_reception - ecart, dossier.date_reception + ecart))
        .exclude(pk=dossier.pk)
        .exclude(pk__in=dossier.dossiers_lies.values("pk"))
        .order_by("date_reception")[:5]
    )
