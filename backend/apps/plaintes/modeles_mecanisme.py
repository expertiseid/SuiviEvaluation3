"""
Modèles prêts à l'emploi du mécanisme de plaintes : une organisation démarre en choisissant un
modèle, puis l'adapte. Appliquer un modèle COPIE ses éléments dans la configuration (ajout de ce
qui manque, par nom, sans rien supprimer ni écraser) : modifier ce fichier ne change jamais une
configuration déjà en place.

- « standard » : mécanisme de plaintes et retours des projets auprès des communautés, aligné sur
  l'engagement 5 de la Norme humanitaire fondamentale ;
- « personnel » : réclamations internes du personnel ;
- le circuit des plaintes sensibles (exploitation, abus et harcèlement sexuels, fraude,
  corruption, mise en cause d'un membre du personnel…) et le circuit alternatif (quand une personne
  mise en cause en est destinataire) sont toujours ajoutés, quel que soit le modèle : leurs étapes
  sont à confier à des personnes nommément désignées (points focaux), ce que l'activation vérifie.
"""
from django.db import transaction

from apps.accounts.constants import ROLE_ANIMATEUR_TERRAIN, ROLE_CHARGE_SE, ROLE_CHEF_PROJET, ROLE_COORDO_GENERAL

TYPES = [
    ("Plainte", "Mécontentement sur un service, une distribution, un comportement…"),
    ("Suggestion", "Proposition d'amélioration"),
    ("Question", "Demande d'information"),
    ("Remerciement", "Retour positif"),
    ("Signalement", "Fait grave porté à la connaissance de l'organisation"),
]
PRIORITES = [("Normale", False, 30), ("Élevée", False, 15), ("Urgente", True, 3)]

# Circuit standard (un modèle, pas une règle) : (étape, délai en jours, rôle responsable, clôture).
ETAPES_STANDARD = [
    ("Réception", 1, ROLE_ANIMATEUR_TERRAIN, False),
    ("Enregistrement", 1, ROLE_CHARGE_SE, False),
    ("Classification", 2, ROLE_CHARGE_SE, False),
    ("Affectation", 2, ROLE_COORDO_GENERAL, False),
    ("Traitement", 14, ROLE_CHEF_PROJET, False),
    ("Décision", 5, ROLE_COORDO_GENERAL, False),
    ("Retour au plaignant", 3, ROLE_CHARGE_SE, False),
    ("Clôture", 2, ROLE_CHARGE_SE, True),
]
# Circuit confidentiel : responsables à désigner nommément (aucun rôle entier).
ETAPES_SENSIBLES = [
    ("Réception confidentielle", 1, None, False),
    ("Évaluation des risques", 1, None, False),
    ("Assistance et référencement", 3, None, False),
    ("Traitement selon le protocole de l'organisation", 30, None, False),
    ("Décision", 7, None, False),
    ("Retour au plaignant", 3, None, False),
    ("Clôture", 2, None, True),
]

# Catégories sensibles toujours présentes ; les deux premières sont verrouillées.
CATEGORIES_SENSIBLES = [
    ("Exploitation et abus sexuels", True),
    ("Harcèlement sexuel", True),
    ("Violence ou atteinte à la protection (dont enfants)", False),
    ("Fraude et corruption", False),
    ("Menaces et représailles", False),
    ("Comportement d'un membre du personnel ou d'un partenaire", False),
    ("Incident menaçant la sécurité d'une personne", False),
]

MODELES = {
    "standard": {
        "libelle": "Mécanisme standard auprès des communautés",
        "description": "Plaintes et retours des communautés et bénéficiaires d'un projet (engagement 5 de la "
        "Norme humanitaire fondamentale).",
        "nom": "Mécanisme de plaintes et retours des communautés",
        "circuit": "Circuit standard",
        "categories": [
            ("Ciblage et sélection des bénéficiaires", ["Critères de sélection", "Exclusion d'un ménage"]),
            ("Distribution et assistance", ["Quantité ou qualité", "Retard", "Lieu ou horaires"]),
            ("Comportement du personnel", []),
            ("Information et communication", []),
            ("Accès aux services", []),
            ("Suggestion d'amélioration", []),
            ("Autre", []),
        ],
        "texte": "Ce mécanisme vous permet de faire part d'une plainte, d'une suggestion, d'une question ou "
        "d'un remerciement concernant nos projets. Votre retour sera enregistré, traité dans les délais annoncés "
        "et vous recevrez une réponse si vous le souhaitez. Vous pouvez rester anonyme. Vos données sont "
        "protégées et ne sont partagées qu'avec les personnes chargées de traiter votre dossier. Ce service "
        "est gratuit.",
    },
    "personnel": {
        "libelle": "Réclamations internes du personnel",
        "description": "Réclamations et signalements des employés, stagiaires et volontaires de l'organisation.",
        "nom": "Mécanisme de réclamations du personnel",
        "circuit": "Circuit des réclamations du personnel",
        "categories": [
            ("Conditions de travail", ["Horaires", "Sécurité au travail", "Matériel"]),
            ("Rémunération et avantages", []),
            ("Relations de travail", ["Conflit avec un collègue", "Conflit avec un responsable"]),
            ("Discrimination", []),
            ("Suggestion", []),
            ("Autre", []),
        ],
        "texte": "Ce mécanisme permet à chaque membre du personnel de faire une réclamation ou un signalement "
        "en toute confiance. Votre demande sera traitée de façon confidentielle et dans les délais annoncés. "
        "Aucune mesure de représailles ne sera tolérée.",
    },
}


def liste_modeles() -> list:
    return [{"code": code, "libelle": m["libelle"], "description": m["description"]} for code, m in MODELES.items()]


@transaction.atomic
def appliquer_modele(code: str) -> dict:
    """
    Copie le modèle dans la configuration (ajoute ce qui manque, par nom) et ajoute toujours le
    circuit et les catégories sensibles. Renvoie le nombre d'éléments ajoutés par nature.
    """
    from apps.accounts.models import Role

    from .models import Categorie, Circuit, EtapeCircuit, Mecanisme, Priorite, TypeRetour

    modele = MODELES[code]
    roles = {r.code: r for r in Role.objects.all()}
    ajouts = {"types": 0, "priorites": 0, "categories": 0, "circuits": 0}

    for ordre, (nom, description) in enumerate(TYPES, start=1):
        _, cree = TypeRetour.objects.get_or_create(nom=nom, defaults={"description": description, "ordre": ordre})
        ajouts["types"] += cree
    for ordre, (nom, urgente, delai) in enumerate(PRIORITES, start=1):
        _, cree = Priorite.objects.get_or_create(nom=nom, defaults={"urgente": urgente, "delai_jours": delai, "ordre": ordre})
        ajouts["priorites"] += cree

    def circuit(nom, sensible, etapes, description):
        objet, cree = Circuit.objects.get_or_create(nom=nom, defaults={"sensible": sensible, "description": description})
        if cree:
            ajouts["circuits"] += 1
            for ordre, (etape, delai, role, cloture) in enumerate(etapes, start=1):
                EtapeCircuit.objects.create(circuit=objet, nom=etape, ordre=ordre, delai_jours=delai,
                                            role=roles.get(role) if role else None, est_cloture=cloture)
        # Un circuit par défaut pour chaque nature (ordinaire / sensible), s'il n'y en a pas encore.
        if not Circuit.objects.filter(sensible=sensible, par_defaut=True).exists():
            Circuit.objects.filter(pk=objet.pk).update(par_defaut=True)
        return objet

    circuit(modele["circuit"], False, ETAPES_STANDARD, modele["description"])
    circuit("Circuit confidentiel", True, ETAPES_SENSIBLES,
            "Plaintes sensibles : seules les personnes désignées à chaque étape y ont accès.")
    # Circuit alternatif (obligatoire) : quand une personne mise en cause est destinataire du circuit
    # confidentiel habituel — direction générale, siège, conseil d'administration, référent extérieur…
    alternatif = circuit("Circuit confidentiel alternatif", True, ETAPES_SENSIBLES,
                         "Plaintes mettant en cause une personne du circuit confidentiel habituel.")

    for ordre, (nom, sous) in enumerate(modele["categories"], start=1):
        parent, cree = Categorie.objects.get_or_create(parent=None, nom=nom, defaults={"ordre": ordre})
        ajouts["categories"] += cree
        for sous_ordre, sous_nom in enumerate(sous, start=1):
            _, cree = Categorie.objects.get_or_create(parent=parent, nom=sous_nom, defaults={"ordre": sous_ordre})
            ajouts["categories"] += cree
    for ordre, (nom, verrouillee) in enumerate(CATEGORIES_SENSIBLES, start=100):
        objet, cree = Categorie.objects.get_or_create(
            parent=None, nom=nom, defaults={"ordre": ordre, "sensible": True, "verrouillee": verrouillee},
        )
        ajouts["categories"] += cree
        if not cree and (verrouillee or not objet.sensible):
            Categorie.objects.filter(pk=objet.pk).update(sensible=True, verrouillee=objet.verrouillee or verrouillee)

    mecanisme = Mecanisme.courant()
    mecanisme.modele = code
    if mecanisme.circuit_alternatif_id is None:
        mecanisme.circuit_alternatif = alternatif
    if not mecanisme.texte_information:
        mecanisme.texte_information = modele["texte"]
    if mecanisme.nom == Mecanisme._meta.get_field("nom").default:
        mecanisme.nom = modele["nom"]
    if not mecanisme.langues:
        mecanisme.langues = ["fr"]
    mecanisme.save()
    return ajouts
