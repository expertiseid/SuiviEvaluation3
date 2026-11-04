"""
Démonstration de la chaîne des documents : Stratégie (PNDES-II) → Programme → Projets, avec
contributions élément par élément. Le programme a sa fiche renseignée comme un projet (code,
budget et bailleurs, dates, statut, responsable, zones, cibles). Les projets éducation et santé
sont rattachés au programme, et un projet complet (PEQR-KOU-2025) y est créé. Rejouable : retire
aussi les anciens maillons de démonstration (« Pilier 1 » à « Pilier 3 »).

À lancer après seed_50_projets (il s'appuie sur le PNDES-II et ses projets) :
    docker compose exec backend python manage.py seed_chaine_documents
"""
from datetime import date
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction

from apps.accounts.models import User
from apps.geo.models import Zone
from apps.partners.models import Partenaire, PartiePrenante, StructureOrganisation
from apps.strategy.serializers import enregistrer_bailleurs

from apps.projects.models import Activite, Projet
from apps.strategy.models import CadreStrategique, ElementStrategique, TypeDocument, TypeNiveau
from apps.strategy.services import supprimer_cadre_strategique_cascade

MAILLONS = [("Programme", "Programmes", "Briefcase")]
# Anciens maillons de la démonstration, retirés à chaque exécution.
ANCIENS_MAILLONS = ["Pilier 1", "Pilier 2", "Pilier 3"]


def maillon(nom):
    """Maillon de la chaîne d'après son nom."""
    return TypeDocument.objects.get(nom=nom)


def document(nom, type_nom, description, parent=None, element_parent=None, niveaux=(), elements=()):
    """elements : (niveau, code, nom, code_parent, contribue_a element)."""
    doc = CadreStrategique.objects.create(nom=nom, description=description, type_document=maillon(type_nom),
                                          document_parent=parent, element_parent=element_parent)
    par_nom, precedent = {}, None
    for ordre, n in enumerate(niveaux, start=1):
        precedent = TypeNiveau.objects.create(cadre_strategique=doc, nom_niveau=n, ordre=ordre, niveau_parent=precedent)
        par_nom[n] = precedent
    par_code = {}
    for niveau, code, libelle, code_parent, contribue in elements:
        par_code[code] = ElementStrategique.objects.create(
            type_niveau=par_nom[niveau], code=code, nom=libelle, element_parent=par_code.get(code_parent), contribue_a=contribue,
        )
    return doc, par_code




# Fiches des documents (comme celles des projets), par code. Montants en FCFA ; bailleurs créés
# s'ils n'existent pas ; zones, partenaires, services et parties prenantes retrouvés par leur nom
# (ignorés s'ils n'existent pas dans la base).
FICHES = {
    "PNDCH": {
        "statut": "EN_COURS", "date_debut": date(2026, 1, 1), "date_fin": date(2030, 12, 31),
        "fonds_propres": 45_000_000_000, "responsable_nom": "Secrétariat permanent du PNDCH",
        "bailleurs": [("Banque mondiale", 60_000_000_000), ("Union européenne", 35_000_000_000), ("UNICEF", 12_000_000_000)],
        "partenaire": None, "consortium": [], "tout_le_pays": True, "zones": [],
        "cibles": (2_400_000, 1_150_000, 1_250_000, 900_000, 180_000),
        "services": ["Direction des programmes", "Direction du suivi-évaluation et de la capitalisation"],
        "parties": ["Ministère de l'Éducation nationale", "Ministère de la Santé"],
        "capitalisation": "Revue à mi-parcours prévue en 2028 : pilotage conjoint éducation-santé, "
                          "mutualisation des infrastructures sociales en zone rurale.",
    },
}


def remplir_fiche(doc, code):
    """Renseigne la fiche du document `doc` d'après FICHES[code] (bailleurs : budget recalculé)."""
    f = FICHES[code]
    doc.code, doc.statut = code, f["statut"]
    doc.date_debut, doc.date_fin = f["date_debut"], f["date_fin"]
    doc.fonds_propres = Decimal(f["fonds_propres"])
    doc.responsable_nom = f["responsable_nom"]
    doc.type_mise_en_oeuvre = f.get("type", "DIRECT")
    doc.partenaire_mise_en_oeuvre = Partenaire.objects.filter(nom=f["partenaire"]).first() if f["partenaire"] else None
    doc.pays, doc.tout_le_pays = ["BF"], f["tout_le_pays"]
    (doc.cible_totale, doc.cible_hommes, doc.cible_femmes, doc.cible_jeunes, doc.cible_pdi) = f["cibles"]
    doc.elements_capitalisation = f["capitalisation"]
    doc.save()
    doc.partenaires_consortium.set(Partenaire.objects.filter(nom__in=f["consortium"]))
    doc.zones.set(Zone.objects.filter(nom__in=f["zones"], parent__isnull=True))
    doc.structures.set(StructureOrganisation.objects.filter(nom__in=f["services"]))
    doc.parties_prenantes.set(PartiePrenante.objects.filter(nom__in=f["parties"]))
    doc.utilisateurs_affectes.set(User.objects.filter(role="ADMIN")[:1])
    enregistrer_bailleurs(doc, [{"nom": nom, "montant": Decimal(m)} for nom, m in f["bailleurs"]])


def creer_projet_dernier_maillon(sortie):
    """
    Projet complet (tous les onglets, comme ceux de seed_50_projets) rattaché au dernier maillon :
    le programme, résultat « Les capacités d'accueil scolaires sont étendues », toutes ses activités
    sur ce résultat — pour voir sa remontée jusqu'à la stratégie. Rejouable (le projet précédent est remplacé).
    """
    import random

    from apps.beneficiaries.models import StatutParticulier, TypeActiviteBeneficiaire
    from apps.geo.models import Zone
    from apps.partners.models import Bailleur, Partenaire, PartiePrenante, StructureOrganisation
    from apps.projects.models import Equipe
    from apps.projects.services import supprimer_projet_cascade
    from apps.projects.verrou import verrou_desactive

    from .seed_50_projets import SECTEURS, User, creer_projet

    random.seed(77)
    with transaction.atomic(), verrou_desactive():
        for ancien in Projet.objects.filter(code="PEQR-KOU-2025"):
            # Son équipe (créée sous le code provisoire de creer_projet) part avec lui.
            equipes = list(Equipe.objects.filter(activites__projet=ancien).distinct())
            supprimer_projet_cascade(ancien)
            for equipe in equipes:
                if not equipe.activites.exists():
                    equipe.delete()
        Equipe.objects.filter(nom="Équipe projet PEQR-KOU-2025").delete()
        sigle = {s.sigle: s for s in StructureOrganisation.objects.all()}
        admin = User.objects.filter(role="ADMIN").order_by("id").first()
        ref = {
            "structure_secteur": {"EDU": sigle["SESE"]}, "dsec": sigle["DSEC"], "dp": sigle["DP"],
            "parties_prenantes": list(PartiePrenante.objects.all()),
            "bailleurs": list(Bailleur.objects.all()),
            "partenaires_bailleur": {p.nom: p for p in Partenaire.objects.filter(type="BAILLEUR")},
            "partenaires_meo": list(Partenaire.objects.filter(type="MISE_EN_OEUVRE").order_by("id")),
            "statuts": {s.code: s for s in StatutParticulier.objects.all()},
            "types_activite": {t.libelle: t for t in TypeActiviteBeneficiaire.objects.all()},
            "admin": admin, "utilisateurs": list(User.objects.exclude(pk=admin.pk)),
        }
        pndes = CadreStrategique.objects.get(nom__startswith="Plan national de développement économique")
        els = {e.nom: e for e in ElementStrategique.objects.filter(type_niveau__cadre_strategique=pndes)}
        # Éléments du PNDES-II correspondant au secteur éducation (planification créée par creer_projet).
        elements = {("EDU", "axe"): els["Développer le capital humain"]}
        for t, (theme, _, resultats) in enumerate(SECTEURS["EDU"]["themes"]):
            elements[("EDU", t)] = els[theme]
            for r, (resultat, _, _) in enumerate(resultats):
                elements[("EDU", t, r)] = els[resultat]
        region = Zone.objects.get(nom="Koulse", niveau_administratif__ordre=1)
        provinces = list(Zone.objects.filter(parent=region, niveau_administratif__ordre=2))[:3]
        projet = creer_projet(5, "EDU", ref, {"A": pndes}, elements, region, provinces, set())  # 5 : projet en cours

        programme = CadreStrategique.objects.get(type_document__nom="Programme", nom__startswith="Programme national de développement du capital")
        ecoles = ElementStrategique.objects.get(type_niveau__cadre_strategique=programme, code="RP1.1")
        Projet.objects.filter(id=projet.id).update(
            nom="Projet d'écoles de qualité dans la région Koulsé", code="PEQR-KOU-2025",
            cadre_strategique=programme, element_strategique=ecoles, elements_capitalisation="",
        )
        projet.elements_strategiques_secondaires.clear()
        Equipe.objects.filter(activites__projet=projet).distinct().update(nom="Équipe projet PEQR-KOU-2025")
        Activite.objects.filter(projet=projet).update(axe_strategique=ecoles)
    sortie.write(f"Projet au dernier maillon : PEQR-KOU-2025 (id {projet.id})")


class Command(BaseCommand):
    help = "Crée la démonstration de la chaîne des documents (stratégie → programme) et y rattache des projets."

    def handle(self, *args, **options):
        self.creer_chaine()
        creer_projet_dernier_maillon(self.stdout)

    def creer_chaine(self):
        with transaction.atomic():
            premier = TypeDocument.objects.order_by("ordre").first()
            premier.nom, premier.nom_pluriel, premier.icone = "Stratégie", "Stratégies", "Target"
            premier.save()
            for i, (nom, pluriel, icone) in enumerate(MAILLONS, start=2):
                TypeDocument.objects.update_or_create(nom=nom, defaults={"nom_pluriel": pluriel, "ordre": i, "icone": icone})
            # Rejouable : on retire la démonstration précédente (projets remis sur le PNDES-II).
            pndes = CadreStrategique.objects.get(nom__startswith="Plan national de développement économique")
            noms = [m[0] for m in MAILLONS] + ANCIENS_MAILLONS
            anciens = list(CadreStrategique.objects.filter(type_document__nom__in=noms).order_by("-type_document__ordre"))
            Projet.objects.filter(cadre_strategique__in=anciens).update(cadre_strategique=pndes, element_strategique=None)
            for d in anciens:
                CadreStrategique.objects.filter(document_parent=d).update(document_parent=None, element_parent=None)
                ElementStrategique.objects.filter(contribue_a__type_niveau__cadre_strategique=d).update(contribue_a=None)
                supprimer_cadre_strategique_cascade(d)
            TypeDocument.objects.filter(nom__in=ANCIENS_MAILLONS).delete()

            os = {e.nom: e for e in ElementStrategique.objects.filter(type_niveau__cadre_strategique=pndes)}
            axe1 = ElementStrategique.objects.get(type_niveau__cadre_strategique=pndes, code="AXE1")
            os_edu = os["Améliorer l'accès à une éducation de base de qualité"]
            os_sante = os["Améliorer l'accès aux soins de santé primaires"]

            programme, p = document(
                "Programme national de développement du capital humain (PNDCH) 2026-2030", "Programme",
                "Programme de mise en œuvre de l'axe 1 du PNDES-II : éducation de base et santé primaire.",
                pndes, axe1, ["Objectif du programme", "Résultat du programme"],
                [("Objectif du programme", "OP1", "Généraliser l'accès à une éducation de base de qualité", None, os_edu),
                 ("Résultat du programme", "RP1.1", "Les capacités d'accueil scolaires sont étendues", "OP1", None),
                 ("Résultat du programme", "RP1.2", "Les enfants hors école sont scolarisés", "OP1", None),
                 ("Objectif du programme", "OP2", "Rapprocher les soins de santé primaires des populations", None, os_sante),
                 ("Résultat du programme", "RP2.1", "Les formations sanitaires de proximité sont fonctionnelles", "OP2", None)],
            )
            # Projets éducation et santé : rattachés au programme (leurs activités suivent le rattachement du projet).
            edu = list(Projet.objects.filter(cadre_strategique=pndes, nom__iregex=r"(éducation|école|scolaris|cantines)").order_by("code"))
            sante = list(Projet.objects.filter(cadre_strategique=pndes, nom__iregex=r"(santé|paludisme|mère)").order_by("code"))
            for i, projet in enumerate(edu):
                element = p["RP1.1"] if i % 2 == 0 else p["RP1.2"]
                Projet.objects.filter(id=projet.id).update(cadre_strategique=programme, element_strategique=element)
                Activite.objects.filter(projet=projet).update(axe_strategique=None)
            for projet in sante:
                Projet.objects.filter(id=projet.id).update(cadre_strategique=programme, element_strategique=p["RP2.1"])
                Activite.objects.filter(projet=projet).update(axe_strategique=None)

            remplir_fiche(programme, "PNDCH")

        self.stdout.write(f"Maillons : {', '.join(TypeDocument.objects.order_by('ordre').values_list('nom', flat=True))}")
        self.stdout.write(f"Document créé : {programme}")
        self.stdout.write(f"Projets rattachés au programme : {', '.join(p.code for p in edu + sante)}")

