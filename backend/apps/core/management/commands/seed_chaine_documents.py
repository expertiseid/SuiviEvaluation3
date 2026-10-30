"""
Démonstration de la chaîne des documents : PNDES-II (cadre stratégique) → Programme → Pilier 1 →
Pilier 2 → Pilier 3, avec contributions élément par élément ; un Pilier 3 saute le Pilier 2
(avertissement). Les projets éducation et santé sont rattachés aux Piliers 3, et un projet
complet (PEQR-KOU-2025) est créé au dernier maillon. Rejouable.

À lancer après seed_50_projets (il s'appuie sur le PNDES-II et ses projets) :
    docker compose exec backend python manage.py seed_chaine_documents
"""
from django.core.management.base import BaseCommand
from django.db import transaction

from apps.projects.models import Activite, Projet
from apps.strategy.models import CadreStrategique, ElementStrategique, TypeDocument, TypeNiveau
from apps.strategy.services import supprimer_cadre_strategique_cascade

MAILLONS = [("Programme", "Programmes", "Briefcase"), ("Pilier 1", "Piliers 1", "Layers"),
            ("Pilier 2", "Piliers 2", "Layers"), ("Pilier 3", "Piliers 3", "Layers")]


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




def creer_projet_dernier_maillon(sortie):
    """
    Projet complet (tous les onglets, comme ceux de seed_50_projets) rattaché au dernier maillon :
    Pilier 3 Koulsé-Sirba, axe « Écoles de la région », toutes ses activités sur cet axe — pour
    voir sa remontée jusqu'au cadre stratégique. Rejouable (le projet précédent est remplacé).
    """
    import random

    from apps.beneficiaries.models import StatutParticulier, TypeActiviteBeneficiaire
    from apps.geo.models import Zone
    from apps.partners.models import Bailleur, Partenaire, PartiePrenante, StructureOrganisation
    from apps.projects.services import supprimer_projet_cascade
    from apps.projects.verrou import verrou_desactive

    from .seed_50_projets import SECTEURS, User, creer_projet

    random.seed(77)
    with transaction.atomic(), verrou_desactive():
        for ancien in Projet.objects.filter(code="PEQR-KOU-2025"):
            supprimer_projet_cascade(ancien)
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

        pilier3 = CadreStrategique.objects.get(nom__startswith="Pilier 3 — Plan régional d'investissement Koulsé")
        ecoles = ElementStrategique.objects.get(type_niveau__cadre_strategique=pilier3, code="P3-K1")
        Projet.objects.filter(id=projet.id).update(
            nom="Projet d'écoles de qualité dans la région Koulsé", code="PEQR-KOU-2025",
            cadre_strategique=pilier3, element_strategique=ecoles, elements_capitalisation="",
        )
        projet.elements_strategiques_secondaires.clear()
        Activite.objects.filter(projet=projet).update(axe_strategique=ecoles)
    sortie.write(f"Projet au dernier maillon : PEQR-KOU-2025 (id {projet.id})")


class Command(BaseCommand):
    help = "Crée la démonstration de la chaîne des documents (programme, piliers 1 à 3) et y rattache des projets."

    def handle(self, *args, **options):
        self.creer_chaine()
        creer_projet_dernier_maillon(self.stdout)

    def creer_chaine(self):
        with transaction.atomic():
            premier = TypeDocument.objects.order_by("ordre").first()
            premier.nom, premier.nom_pluriel, premier.icone = "Cadre stratégique", "Cadres stratégiques", "Target"
            premier.save()
            for i, (nom, pluriel, icone) in enumerate(MAILLONS, start=2):
                TypeDocument.objects.update_or_create(nom=nom, defaults={"nom_pluriel": pluriel, "ordre": i, "icone": icone})
            # Rejouable : on retire la démonstration précédente (projets remis sur le PNDES-II).
            pndes = CadreStrategique.objects.get(nom__startswith="Plan national de développement économique")
            anciens = list(CadreStrategique.objects.filter(type_document__nom__in=[m[0] for m in MAILLONS]).order_by("-type_document__ordre"))
            Projet.objects.filter(cadre_strategique__in=anciens).update(cadre_strategique=pndes, element_strategique=None)
            for d in anciens:
                CadreStrategique.objects.filter(document_parent=d).update(document_parent=None, element_parent=None)
                ElementStrategique.objects.filter(contribue_a__type_niveau__cadre_strategique=d).update(contribue_a=None)
                supprimer_cadre_strategique_cascade(d)

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
            pilier1, a = document(
                "Pilier 1 — Accès aux services sociaux de base", "Pilier 1",
                "Premier pilier du PNDCH : accès physique aux écoles et aux centres de santé.",
                programme, None, ["Axe du pilier"],
                [("Axe du pilier", "P1-A1", "Accès à l'école", None, p["RP1.1"]),
                 ("Axe du pilier", "P1-A2", "Scolarisation des enfants hors école", None, p["RP1.2"]),
                 ("Axe du pilier", "P1-A3", "Accès aux soins de proximité", None, p["RP2.1"])],
            )
            pilier2, b = document(
                "Pilier 2 — Infrastructures scolaires et sanitaires", "Pilier 2",
                "Construction, réhabilitation et équipement des infrastructures sociales.",
                pilier1, None, ["Domaine", "Sous-domaine"],
                [("Domaine", "P2-D1", "Infrastructures scolaires", None, a["P1-A1"]),
                 ("Sous-domaine", "P2-D1.1", "Salles de classe et équipements", "P2-D1", None),
                 ("Domaine", "P2-D2", "Infrastructures sanitaires", None, a["P1-A3"]),
                 ("Sous-domaine", "P2-D2.1", "Centres de santé et maternités", "P2-D2", None)],
            )
            centre_nord, c = document(
                "Pilier 3 — Plan régional d'investissement Koulsé-Sirba", "Pilier 3",
                "Déclinaison régionale du pilier 2.",
                pilier2, None, ["Action régionale"],
                [("Action régionale", "P3-K1", "Écoles de la région", None, b["P2-D1.1"]),
                 ("Action régionale", "P3-K2", "Santé de la région", None, b["P2-D2.1"])],
            )
            # Saut de maillon : rattaché directement au Pilier 1 (le Pilier 2 est sauté).
            est, e = document(
                "Pilier 3 — Plan régional d'investissement Est", "Pilier 3",
                "Déclinaison régionale rattachée directement au pilier 1.",
                pilier1, None, ["Action régionale"],
                [("Action régionale", "P3-E1", "Retour à l'école des enfants déplacés", None, a["P1-A2"]),
                 ("Action régionale", "P3-E2", "Soins de proximité", None, a["P1-A3"])],
            )

            # Projets éducation et santé : rattachés aux Piliers 3 (leurs activités suivent le rattachement du projet).
            edu = list(Projet.objects.filter(cadre_strategique=pndes, nom__iregex=r"(éducation|école|scolaris|cantines)").order_by("code"))
            sante = list(Projet.objects.filter(cadre_strategique=pndes, nom__iregex=r"(santé|paludisme|mère)").order_by("code"))
            for i, projet in enumerate(edu):
                pilier, element = (centre_nord, c["P3-K1"]) if i % 2 == 0 else (est, e["P3-E1"])
                Projet.objects.filter(id=projet.id).update(cadre_strategique=pilier, element_strategique=element)
                Activite.objects.filter(projet=projet).update(axe_strategique=None)
            for i, projet in enumerate(sante):
                pilier, element = (centre_nord, c["P3-K2"]) if i % 2 == 0 else (est, e["P3-E2"])
                Projet.objects.filter(id=projet.id).update(cadre_strategique=pilier, element_strategique=element)
                Activite.objects.filter(projet=projet).update(axe_strategique=None)

        self.stdout.write(f"Maillons : {', '.join(TypeDocument.objects.order_by('ordre').values_list('nom', flat=True))}")
        self.stdout.write(f"Documents créés : {programme}, {pilier1}, {pilier2}, {centre_nord}, {est}")
        self.stdout.write(f"Projets rattachés aux piliers 3 : {', '.join(p.code for p in edu + sante)}")

