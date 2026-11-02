"""
Réception d'un retour — interface d'entrée commune à tous les canaux (formulaire public, saisie
par un agent ; plus tard courriel, SMS, import, KoboToolbox…). Chaque canal ne fait que rassembler
les données : les mêmes règles s'appliquent ici à tous (contrôles, sensibilité, circuit, numéro,
code de suivi).
"""
import hashlib
import secrets

from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from apps.core.vocabulaire import v

from .models import (
    Canal,
    Categorie,
    Circuit,
    CompteurDossiers,
    Dossier,
    Mecanisme,
    ModeReponse,
    Priorite,
    TypeRetour,
)

# Sans lettres ni chiffres qui se confondent (0/O, 1/I/L) : le code se dicte au téléphone.
ALPHABET_CODE = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"


def nouveau_code_suivi() -> str:
    brut = "".join(secrets.choice(ALPHABET_CODE) for _ in range(12))
    return f"{brut[:4]}-{brut[4:8]}-{brut[8:]}"


def empreinte_code(code: str) -> str:
    """Le code n'est jamais conservé en clair : on garde son empreinte (tirets, espaces et casse ignorés)."""
    normalise = "".join(c for c in (code or "").upper() if c.isalnum())
    return hashlib.sha256(normalise.encode()).hexdigest()


def _numero(mecanisme, annee: int) -> str:
    compteur, _ = CompteurDossiers.objects.select_for_update().get_or_create(annee=annee)
    compteur.dernier += 1
    compteur.save(update_fields=["dernier"])
    return f"{mecanisme.prefixe_numero}-{annee}-{compteur.dernier:05d}"


def circuit_pour(categorie, sensible: bool):
    """Circuit propre à la catégorie s'il convient, sinon le circuit par défaut de la nature du dossier."""
    if categorie is not None and categorie.circuit_id and categorie.circuit.actif and categorie.circuit.sensible == sensible:
        return categorie.circuit
    return Circuit.objects.filter(actif=True, sensible=sensible, par_defaut=True).first()


def _objet(modele, valeur, champ, message):
    if valeur in (None, ""):
        return None
    if isinstance(valeur, modele):
        objet = valeur
    else:
        objet = modele.objects.filter(pk=valeur).first() if str(valeur).isdigit() else None
    if objet is None or not getattr(objet, "actif", True):
        raise ValidationError({champ: message})
    return objet


@transaction.atomic
def recevoir(donnees: dict, canal: str, saisi_par=None, public: bool = False):
    """
    Crée le dossier et renvoie (dossier, code de suivi en clair — à remettre au plaignant, il
    n'est plus jamais affiché ensuite).

    `public` : formulaire public (consentement exigé ; nom exigé si l'anonymat n'est pas autorisé).
    Un agent n'est jamais obligé de saisir une information qu'il n'a pas.
    """
    mecanisme = Mecanisme.courant()
    if not mecanisme.actif:
        raise ValidationError({"detail": "Le mécanisme de plaintes et retours n'est pas ouvert."})
    if canal not in Canal.values:
        raise ValidationError({"canal": "Canal de réception inconnu."})

    erreurs = {}
    type_retour = _objet(TypeRetour, donnees.get("type_retour"), "type_retour", v("Choisissez un type de retour de la liste."))
    if type_retour is None:
        erreurs["type_retour"] = v("Choisissez un type de retour.")
    categorie = _objet(Categorie, donnees.get("categorie"), "categorie", v("Choisissez une catégorie de la liste."))
    priorite = None if public else _objet(Priorite, donnees.get("priorite"), "priorite", v("Choisissez une priorité de la liste."))
    description = (donnees.get("description") or "").strip()
    if not description:
        erreurs["description"] = v("Décrivez votre retour.")

    projet = None
    if donnees.get("projet") not in (None, ""):
        from apps.projects.models import Projet

        projet = Projet.objects.filter(pk=donnees["projet"]).first() if str(donnees["projet"]).isdigit() else None
        couverts = set(mecanisme.projets.values_list("id", flat=True))
        if projet is None or (couverts and projet.id not in couverts):
            erreurs["projet"] = v("Ce projet n'est pas couvert par le mécanisme.")

    anonyme = bool(donnees.get("anonyme"))
    if anonyme and not mecanisme.anonymat_autorise:
        erreurs["anonyme"] = v("Les retours anonymes ne sont pas acceptés par ce mécanisme.")
    nom = "" if anonyme else (donnees.get("nom") or "").strip()[:200]
    telephone = "" if anonyme else (donnees.get("telephone") or "").strip()[:40]
    courriel = "" if anonyme else (donnees.get("courriel") or "").strip()[:254]
    mode_reponse = ModeReponse.AUCUN if anonyme else (donnees.get("mode_reponse") or ModeReponse.AUCUN)
    if mode_reponse not in ModeReponse.values:
        erreurs["mode_reponse"] = v("Mode de réponse inconnu.")
    elif mode_reponse in (ModeReponse.TELEPHONE, ModeReponse.SMS) and not telephone:
        erreurs["telephone"] = v("Indiquez un numéro de téléphone pour recevoir la réponse, ou choisissez un autre mode.")
    elif mode_reponse == ModeReponse.COURRIEL and not courriel:
        erreurs["courriel"] = v("Indiquez une adresse courriel pour recevoir la réponse, ou choisissez un autre mode.")
    if courriel and ("@" not in courriel or "." not in courriel.split("@")[-1]):
        erreurs["courriel"] = v("Adresse courriel invalide.")
    if public and not anonyme and not mecanisme.anonymat_autorise and not nom:
        erreurs["nom"] = v("Indiquez votre nom.")
    consentement = bool(donnees.get("consentement"))
    if public and not consentement:
        erreurs["consentement"] = v("Votre accord est nécessaire pour que votre retour soit traité.")

    date_reception = timezone.localdate()
    if not public and donnees.get("date_reception"):
        from datetime import date

        try:
            date_reception = date.fromisoformat(str(donnees["date_reception"])[:10])
        except ValueError:
            erreurs["date_reception"] = v("Date de réception invalide.")
        else:
            if date_reception > timezone.localdate():
                erreurs["date_reception"] = v("La date de réception ne peut pas être dans le futur.")
    if erreurs:
        raise ValidationError(erreurs)

    # Sensibilité (penche vers la protection) : catégorie sensible, ou retour visant le personnel.
    concerne_personnel = donnees.get("concerne_personnel")
    concerne_personnel = None if concerne_personnel in (None, "") else concerne_personnel in (True, "true", "oui", "1", 1)
    sensible = bool(categorie and categorie.sensible_effective) or concerne_personnel is True
    circuit = circuit_pour(categorie, sensible)
    etape = circuit.etapes.order_by("ordre", "id").first() if circuit else None

    code = nouveau_code_suivi()
    dossier = Dossier.objects.create(
        numero=_numero(mecanisme, date_reception.year),
        empreinte_code_suivi=empreinte_code(code),
        canal=canal,
        date_reception=date_reception,
        recueilli_directement=None if public else donnees.get("recueilli_directement"),
        type_retour=type_retour,
        categorie=categorie,
        priorite=priorite,
        projet=projet,
        lieu=(donnees.get("lieu") or "").strip()[:255],
        description=description,
        concerne_personnel=concerne_personnel,
        sensible=sensible,
        circuit=circuit,
        etape=etape,
        anonyme=anonyme,
        nom=nom,
        telephone=telephone,
        courriel=courriel,
        mode_reponse=mode_reponse,
        consentement=consentement,
        langue=(donnees.get("langue") or "")[:5],
        saisi_par=saisi_par,
    )
    from .models import ActionDossier

    ActionDossier.objects.create(
        dossier=dossier, type=ActionDossier.Type.RECEPTION, auteur=saisi_par,
        details={"canal": canal, "circuit": circuit.nom if circuit else "", "sensible": sensible},
    )
    from . import delais

    delais.recalculer(dossier, entree_etape=date_reception)
    transaction.on_commit(lambda: delais.notifier_reception(dossier))
    return dossier, code


def dossiers_visibles(user):
    """
    Dossiers que l'utilisateur peut voir : l'Administrateur voit tout (choix de l'organisation) ;
    les autres voient les dossiers ordinaires, et les dossiers sensibles seulement s'ils sont
    responsables d'une étape de leur circuit. Un dossier interdit n'apparaît ni dans les listes ni
    dans les compteurs.
    """
    from django.db.models import Exists, OuterRef

    from apps.accounts.constants import ROLE_ADMIN

    from .models import EtapeCircuit

    if user.role == ROLE_ADMIN:
        return Dossier.objects.all()

    habilite = EtapeCircuit.objects.filter(circuit=OuterRef("circuit"), responsable=user)
    return Dossier.objects.filter(sensible=False) | Dossier.objects.filter(sensible=True).filter(Exists(habilite))
