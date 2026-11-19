"""
Pilotage du mécanisme de plaintes (lot 6) — partie 9 du cahier des charges.

- Indicateurs de base (9.2), chacun avec sa définition, sa période, son numérateur et son
  dénominateur ; les définitions standard ne changent pas (comparaisons fiables).
- Tableaux de bord (9.3) : quatre vues par défaut (opérationnelle, pilotage, projet et S&E,
  confidentielle), composées à partir d'un catalogue d'éléments (chiffres clés, graphiques, listes) ;
  l'organisation règle la vue de chacun, chaque utilisateur peut s'en faire une copie.
- Statistiques ne valent pas accès : les totaux portent sur tous les dossiers (sauf ceux qui mettent
  en cause l'utilisateur), mais les dossiers confidentiels n'apparaissent que dans des totaux — les
  ventilations ne comptent que les dossiers ordinaires — et toute case comptant moins de
  `seuil_masquage` dossiers confidentiels est affichée « moins de N ». Les listes et le clic vers les
  dossiers passent par dossiers_visibles : un dossier interdit n'y apparaît jamais.
- La vue confidentielle est réservée aux personnes habilitées (Administrateur, points focaux d'un
  circuit confidentiel) et ne montre que des totaux, sans aucun détail individuel.
"""
from collections import OrderedDict
from datetime import date, timedelta
from statistics import mean, median

from django.db.models import Count, Min, Q
from django.utils import timezone

from apps.accounts.constants import ROLE_ADMIN
from apps.core.vocabulaire import v

from .models import (
    ActionCorrective, ActionDossier, Canal, Dossier, EtapeCircuit, IssueDossier, Mecanisme, Referencement,
    StatutDossier, TableauPlaintes,
)
from .reception import dossiers_visibles

CLOS = StatutDossier.CLOTURE


def habilite_confidentiel(user):
    return user.role == ROLE_ADMIN or EtapeCircuit.objects.filter(circuit__sensible=True, responsable=user).exists()


def _pct(numerateur, denominateur):
    return round(100 * numerateur / denominateur, 1) if denominateur else None


# --- Catalogue et vues par défaut ------------------------------------------------------------------

# code : (libellé, nature — chiffre / graphique / liste —, confidentiel)
CATALOGUE = OrderedDict([
    ("volume", ("Volume reçu", "chiffre", False)),
    ("ouverts", ("Dossiers ouverts", "chiffre", False)),
    ("clotures", ("Dossiers clôturés", "chiffre", False)),
    ("en_retard", ("Dossiers en retard", "chiffre", False)),
    ("dans_delais", ("Traitement dans les délais", "chiffre", False)),
    ("delai_moyen", ("Délai de traitement moyen", "chiffre", False)),
    ("delai_median", ("Délai de traitement médian", "chiffre", False)),
    ("accuses", ("Accusés de réception", "chiffre", False)),
    ("boucle", ("Boucle bouclée", "chiffre", False)),
    ("reouvertures_recours", ("Réouvertures et recours", "chiffre", False)),
    ("attente_affectation", ("En attente d'affectation", "chiffre", False)),
    ("satisfaction", ("Satisfaction", "chiffre", False)),
    ("mes_a_traiter", ("Mes dossiers à traiter", "chiffre", False)),
    ("echeances_7j", ("Échéances des 7 prochains jours", "chiffre", False)),
    ("actions_en_cours", ("Actions correctives en cours", "chiffre", False)),
    ("par_mois", ("Volume reçu dans le temps", "graphique", False)),
    ("tendance_12_mois", ("Tendance sur 12 mois", "graphique", False)),
    ("par_categorie", ("Répartition par catégorie", "graphique", False)),
    ("par_canal", ("Répartition par canal", "graphique", False)),
    ("par_type", ("Répartition par type de retour", "graphique", False)),
    ("par_priorite", ("Répartition par priorité", "graphique", False)),
    ("par_projet", ("Retours par projet", "graphique", False)),
    ("par_etape", ("Dossiers ouverts par étape", "graphique", False)),
    ("par_issue", ("Issue des dossiers clôturés", "graphique", False)),
    ("liste_echeances", ("Prochaines échéances", "liste", False)),
    ("liste_actions", ("Actions correctives en cours", "liste", False)),
    ("conf_recus", ("Dossiers confidentiels reçus", "chiffre", True)),
    ("conf_ouverts", ("Dossiers confidentiels ouverts", "chiffre", True)),
    ("conf_delai_moyen", ("Délai moyen (confidentiels)", "chiffre", True)),
    ("conf_dans_delais", ("Dans les délais (confidentiels)", "chiffre", True)),
    ("conf_referencements", ("Référencements effectués", "chiffre", True)),
    ("conf_par_etape", ("Confidentiels ouverts par étape", "graphique", True)),
    ("conf_par_categorie", ("Confidentiels par catégorie", "graphique", True)),
])

VUES = OrderedDict([
    ("operationnelle", ("Opérationnelle", ["mes_a_traiter", "echeances_7j", "en_retard", "attente_affectation",
                                          "liste_echeances", "par_etape"])),
    ("pilotage", ("Pilotage du mécanisme", ["volume", "clotures", "dans_delais", "delai_moyen", "delai_median", "boucle",
                                            "satisfaction", "reouvertures_recours", "par_mois", "par_categorie",
                                            "par_canal"])),
    ("projet", ("Projet et suivi-évaluation", ["volume", "boucle", "dans_delais", "actions_en_cours", "par_projet",
                                               "par_categorie", "tendance_12_mois", "liste_actions"])),
    ("confidentielle", ("Confidentielle", ["conf_recus", "conf_ouverts", "conf_delai_moyen", "conf_dans_delais",
                                           "conf_referencements", "conf_par_etape", "conf_par_categorie"])),
])

GRAPHIQUE_PAR_DEFAUT = {"par_mois": "courbes", "tendance_12_mois": "aires", "par_canal": "camembert",
                        "par_type": "camembert", "par_issue": "camembert"}


def elements_par_defaut(vue):
    return [{"code": c, "graphique": GRAPHIQUE_PAR_DEFAUT.get(c, "barres")} for c in VUES[vue][1]]


def configuration(vue, user):
    """Vue de l'utilisateur s'il s'en est fait une copie, sinon celle de l'organisation, sinon celle par défaut."""
    perso = TableauPlaintes.objects.filter(vue=vue, utilisateur=user).first()
    orga = TableauPlaintes.objects.filter(vue=vue, utilisateur=None).first()
    source = "utilisateur" if perso else "organisation" if orga else "defaut"
    elements = (perso or orga).elements if (perso or orga) else elements_par_defaut(vue)
    return {"elements": nettoyer(vue, elements), "source": source}


def nettoyer(vue, elements):
    """Garde les éléments connus ; les éléments confidentiels ne sortent jamais de la vue confidentielle."""
    propres = []
    for e in elements or []:
        code = e.get("code") if isinstance(e, dict) else None
        if code in CATALOGUE and (CATALOGUE[code][2] == (vue == "confidentielle")) and code not in [p["code"] for p in propres]:
            propres.append({"code": code, "graphique": str(e.get("graphique") or GRAPHIQUE_PAR_DEFAUT.get(code, "barres"))[:20]})
    return propres


# --- Calcul ------------------------------------------------------------------------------------------

class Calcul:
    """Calcule les éléments d'une vue pour un utilisateur, une période et un projet."""

    def __init__(self, user, du=None, au=None, projet=None):
        self.user = user
        self.aujourdhui = timezone.localdate()
        self.au = au or self.aujourdhui
        self.du = du or (self.au - timedelta(days=364))
        self.projet = projet
        self.mecanisme = Mecanisme.courant()
        self.seuil = max(5, self.mecanisme.seuil_masquage)
        # Statistiques : tous les dossiers, sauf ceux qui mettent l'utilisateur en cause.
        base = Dossier.objects.exclude(mis_en_cause_utilisateurs=user)
        visibles = dossiers_visibles(user)
        if projet:
            base, visibles = base.filter(projet_id=projet), visibles.filter(projet_id=projet)
        self.base, self.visibles = base, visibles

    # Outils
    def masquer(self, nombre):
        """« moins de N » pour un petit effectif confidentiel (0 reste 0)."""
        return v(f"moins de {self.seuil}") if 0 < nombre < self.seuil else nombre

    def lien(self, **params):
        base = {"date_du": self.du.isoformat(), "date_au": self.au.isoformat()}
        if self.projet:
            base["projet"] = str(self.projet)
        return {**base, **{k: str(x) for k, x in params.items() if x is not None}}

    @property
    def recus(self):
        return self.base.filter(date_reception__range=(self.du, self.au))

    @property
    def clotures(self):
        return self.base.filter(statut=CLOS, date_cloture__range=(self.du, self.au))

    def ouverts_maintenant(self, qs):
        return qs.exclude(statut=CLOS)

    def en_retard_qs(self, qs):
        return self.ouverts_maintenant(qs).filter(Q(echeance__lt=self.aujourdhui) | Q(echeance_etape__lt=self.aujourdhui))

    def chiffre(self, code, valeur, definition, numerateur=None, denominateur=None, unite="", lien=None, niveau="ok",
                periode=True):
        return {"code": code, "nature": "chiffre", "libelle": v(CATALOGUE[code][0]), "valeur": valeur, "unite": unite,
                "definition": v(definition), "numerateur": numerateur, "denominateur": denominateur, "niveau": niveau,
                "periode": {"du": self.du, "au": self.au} if periode else {"au": self.aujourdhui}, "lien": lien}

    def graphique(self, code, lignes, confidentiels=None):
        """lignes : [(libellé, valeur, lien)] ; confidentiels : total confidentiel du même périmètre (masqué)."""
        return {"code": code, "nature": "graphique", "libelle": v(CATALOGUE[code][0]),
                "categories": [l[0] for l in lignes], "valeurs": [l[1] for l in lignes], "liens": [l[2] for l in lignes],
                "confidentiels": None if confidentiels is None else self.masquer(confidentiels),
                "periode": {"du": self.du, "au": self.au}}

    def calculer(self, code):
        return getattr(self, f"_{code}")()

    # Indicateurs de base (9.2)
    def _volume(self):
        n = self.recus.count()
        return self.chiffre("volume", n, "Nombre de retours reçus sur la période, tous types et canaux confondus.",
                            lien=self.lien())

    def _ouverts(self):
        n = self.base.filter(date_reception__lte=self.au).filter(~Q(statut=CLOS) | Q(date_cloture__gt=self.au)).count()
        return self.chiffre("ouverts", n, "Dossiers non clôturés à la fin de la période.", lien=self.lien(statut="EN_COURS"))

    def _clotures(self):
        return self.chiffre("clotures", self.clotures.count(), "Dossiers clôturés pendant la période.",
                            lien=self.lien(statut=CLOS))

    def _en_retard(self):
        n = self.en_retard_qs(self.base).count()
        ouverts = self.ouverts_maintenant(self.base).count()
        return self.chiffre("en_retard", n, "Dossiers ouverts dont l'échéance (du dossier ou de l'étape) est dépassée "
                            "à la date du calcul.", n, ouverts, lien={"vue": "en_retard"},
                            niveau="alerte" if ouverts and n / ouverts > 0.25 else "attention" if n else "ok", periode=False)

    def _dans_delais(self):
        clos = self.clotures.exclude(echeance=None)
        dans = sum(1 for d in clos.only("date_cloture", "echeance") if d.date_cloture <= d.echeance)
        total = clos.count()
        pct = _pct(dans, total)
        return self.chiffre("dans_delais", pct, "Dossiers clôturés dans le délai ÷ dossiers clôturés sur la période.",
                            dans, total, "%", self.lien(statut=CLOS),
                            niveau="ok" if pct is None or pct >= 80 else "attention" if pct >= 60 else "alerte")

    def _durees(self, qs):
        return [(d.date_cloture - d.date_reception).days for d in qs.only("date_cloture", "date_reception")
                if d.date_cloture and d.date_reception]

    def _delai_moyen(self):
        d = self._durees(self.clotures)
        return self.chiffre("delai_moyen", round(mean(d), 1) if d else None,
                            "Moyenne, en jours, entre réception et clôture des dossiers clôturés sur la période.",
                            None, len(d), "j", self.lien(statut=CLOS))

    def _delai_median(self):
        d = self._durees(self.clotures)
        return self.chiffre("delai_median", median(d) if d else None,
                            "Médiane, en jours, entre réception et clôture des dossiers clôturés sur la période.",
                            None, len(d), "j", self.lien(statut=CLOS))

    def _joignables(self, qs):
        return qs.filter(anonyme=False).filter(~Q(telephone="") | ~Q(courriel=""))

    def _accuses(self):
        joignables = self._joignables(self.recus)
        accuses = joignables.filter(actions__type=ActionDossier.Type.COMMUNICATION, actions__sens="SORTANT",
                                    actions__objet="ACCUSE_RECEPTION").distinct().count()
        total = joignables.count()
        pct = _pct(accuses, total)
        return self.chiffre("accuses", pct, "Dossiers reçus avec un accusé de réception envoyé ÷ dossiers reçus avec un "
                            "moyen de contact.", accuses, total, "%", self.lien(),
                            niveau="ok" if pct is None or pct >= 80 else "attention" if pct >= 50 else "alerte")

    def _boucle(self):
        joignables = self._joignables(self.clotures)
        bouclés = joignables.filter(retour_donne=True).count()
        total = joignables.count()
        pct = _pct(bouclés, total)
        return self.chiffre("boucle", pct, "Dossiers clôturés avec retour donné au plaignant ÷ dossiers clôturés "
                            "joignables (non anonymes, avec un moyen de contact).", bouclés, total, "%",
                            self.lien(statut=CLOS),
                            niveau="ok" if pct is None or pct >= 80 else "attention" if pct >= 60 else "alerte")

    def _reouvertures_recours(self):
        clos = self.base.filter(actions__type=ActionDossier.Type.CLOTURE,
                                actions__date__date__range=(self.du, self.au)).distinct()
        contestes = clos.filter(actions__type__in=[ActionDossier.Type.REOUVERTURE, ActionDossier.Type.RECOURS]).distinct().count()
        total = clos.count()
        return self.chiffre("reouvertures_recours", contestes, "Dossiers clôturés pendant la période puis rouverts ou "
                            "contestés (recours) — nombre et part des dossiers clôturés.", contestes, total,
                            lien={"vue": "recours"},
                            niveau="attention" if total and contestes / total > 0.1 else "ok")

    def _attente_affectation(self):
        n = self.ouverts_maintenant(self.base).filter(responsable=None).count()
        return self.chiffre("attente_affectation", n, "Dossiers ouverts sans gestionnaire à la date du calcul.",
                            lien={"vue": "sans_responsable"}, niveau="attention" if n else "ok", periode=False)

    def _satisfaction(self):
        reponses = ActionDossier.objects.filter(
            dossier__in=self.base, type=ActionDossier.Type.COMMUNICATION, objet="SATISFACTION", sens="ENTRANT",
            date__date__range=(self.du, self.au), details__has_key="satisfait")
        total = reponses.count()
        satisfaits = reponses.filter(details__satisfait=True).count()
        pct = _pct(satisfaits, total) if total >= 10 else None
        return self.chiffre("satisfaction", pct, "Répondants satisfaits ÷ répondants à l'enquête de satisfaction "
                            "(affiché à partir de 10 réponses).", satisfaits, total, "%")

    # Opérationnel
    def _mes_a_traiter(self):
        n = self.ouverts_maintenant(self.visibles).filter(responsable=self.user).count()
        return self.chiffre("mes_a_traiter", n, "Dossiers ouverts dont vous êtes le gestionnaire.",
                            lien={"vue": "a_traiter"}, periode=False)

    def _echeances_7j(self):
        n = self.ouverts_maintenant(self.visibles).filter(
            echeance__range=(self.aujourdhui, self.aujourdhui + timedelta(days=7))).count()
        return self.chiffre("echeances_7j", n, "Dossiers ouverts dont l'échéance tombe dans les 7 prochains jours.",
                            niveau="attention" if n else "ok", periode=False)

    def _actions_en_cours(self):
        qs = ActionCorrective.objects.filter(statut__in=["A_FAIRE", "EN_COURS"])
        if self.projet:
            qs = qs.filter(projet_id=self.projet)
        retard = qs.filter(echeance__lt=self.aujourdhui).count()
        return self.chiffre("actions_en_cours", qs.count(), "Actions correctives à faire ou en cours (dont en retard : "
                            f"{retard}).", periode=False, niveau="attention" if retard else "ok")

    def _liste_echeances(self):
        qs = self.ouverts_maintenant(self.visibles).exclude(echeance=None).select_related("etape", "responsable").order_by("echeance")[:10]
        from .traitement import nom_personne

        return {"code": "liste_echeances", "nature": "liste", "libelle": v(CATALOGUE["liste_echeances"][0]),
                "colonnes": [v("Dossier"), v("Échéance"), v("Étape"), v("Gestionnaire")],
                "lignes": [{"id": d.id, "cellules": [d.numero, d.echeance, d.etape.nom if d.etape else "", nom_personne(d.responsable)],
                            "retard": d.echeance < self.aujourdhui} for d in qs]}

    def _liste_actions(self):
        from .traitement import nom_personne

        qs = ActionCorrective.objects.filter(statut__in=["A_FAIRE", "EN_COURS"]).select_related("responsable", "projet")
        if self.projet:
            qs = qs.filter(projet_id=self.projet)
        return {"code": "liste_actions", "nature": "liste", "libelle": v(CATALOGUE["liste_actions"][0]),
                "colonnes": [v("Action"), v("Projet"), v("Échéance"), v("Responsable"), v("Statut")],
                "lignes": [{"id": a.id, "cellules": [a.titre, a.projet.code if a.projet else "", a.echeance,
                                                       nom_personne(a.responsable), v(a.get_statut_display())],
                            "retard": bool(a.echeance and a.echeance < self.aujourdhui)} for a in qs.order_by("echeance")[:10]]}

    # Ventilations : dossiers ordinaires seulement, plus le total confidentiel masqué.
    def _ventiler(self, code, qs, cle, libelle, filtre):
        ordinaires = qs.filter(sensible=False)
        lignes = []
        for ligne in ordinaires.values(cle).annotate(n=Count("id", distinct=True)).order_by("-n"):
            valeur = ligne[cle]
            lignes.append((libelle(valeur), ligne["n"], self.lien(**{filtre: valeur}) if filtre and valeur else None))
        return self.graphique(code, lignes, qs.filter(sensible=True).count())

    def _par_mois(self, debut=None):
        debut = debut or self.du
        qs = self.base.filter(date_reception__range=(debut, self.au))
        mois = OrderedDict()
        curseur = date(debut.year, debut.month, 1)
        while curseur <= self.au:
            mois[curseur.strftime("%Y-%m")] = 0
            curseur = date(curseur.year + (curseur.month == 12), curseur.month % 12 + 1, 1)
        for d in qs.filter(sensible=False).values_list("date_reception", flat=True):
            mois[d.strftime("%Y-%m")] = mois.get(d.strftime("%Y-%m"), 0) + 1
        lignes = [(f"{m[5:]}/{m[:4]}", n, None) for m, n in mois.items()]
        return self.graphique("par_mois", lignes, qs.filter(sensible=True).count())

    def _tendance_12_mois(self):
        # Les 12 derniers mois, celui en cours compris.
        annee, mois = (self.au.year, self.au.month - 11) if self.au.month > 11 else (self.au.year - 1, self.au.month + 1)
        element = self._par_mois(date(annee, mois, 1))
        element.update(code="tendance_12_mois", libelle=v(CATALOGUE["tendance_12_mois"][0]))
        return element

    def _par_categorie(self):
        from .models import Categorie

        noms = {c.id: (c.parent_id or c.id) for c in Categorie.objects.all()}
        principales = {c.id: c.nom for c in Categorie.objects.filter(parent=None)}
        compte = OrderedDict()
        for cat in self.recus.filter(sensible=False).values_list("categorie_id", flat=True):
            cle = noms.get(cat)
            compte[cle] = compte.get(cle, 0) + 1
        lignes = sorted(((principales.get(c, v("À classer")), n, self.lien(categorie=c) if c else None)
                         for c, n in compte.items()), key=lambda x: -x[1])
        return self.graphique("par_categorie", lignes, self.recus.filter(sensible=True).count())

    def _par_canal(self):
        libelles = dict(Canal.choices)
        return self._ventiler("par_canal", self.recus, "canal", lambda c: v(libelles.get(c, c)), "canal")

    def _par_type(self):
        return self._ventiler("par_type", self.recus, "type_retour__nom", lambda x: x or "—", None)

    def _par_priorite(self):
        return self._ventiler("par_priorite", self.recus, "priorite__nom", lambda x: x or v("À évaluer"), None)

    def _par_projet(self):
        return self._ventiler("par_projet", self.recus, "projet__code", lambda x: x or v("Sans projet"), None)

    def _par_etape(self):
        qs = self.ouverts_maintenant(self.visibles)
        element = self._ventiler("par_etape", qs, "etape__nom", lambda x: x or "—", None)
        element["periode"] = {"au": self.aujourdhui}
        return element

    def _par_issue(self):
        libelles = dict(IssueDossier.choices)
        return self._ventiler("par_issue", self.clotures, "issue", lambda x: v(libelles.get(x, x or "—")), None)

    # Vue confidentielle : totaux seulement, petits effectifs masqués.
    @property
    def confidentiels(self):
        return self.visibles.filter(sensible=True)

    def _conf_recus(self):
        n = self.confidentiels.filter(date_reception__range=(self.du, self.au)).count()
        return self.chiffre("conf_recus", self.masquer(n), "Dossiers confidentiels reçus sur la période.")

    def _conf_ouverts(self):
        n = self.ouverts_maintenant(self.confidentiels).count()
        return self.chiffre("conf_ouverts", self.masquer(n), "Dossiers confidentiels non clôturés à la date du calcul.",
                            periode=False)

    def _conf_delai_moyen(self):
        d = self._durees(self.confidentiels.filter(statut=CLOS, date_cloture__range=(self.du, self.au)))
        return self.chiffre("conf_delai_moyen", round(mean(d), 1) if len(d) >= self.seuil else None,
                            "Moyenne, en jours, entre réception et clôture des dossiers confidentiels clôturés "
                            f"(affichée à partir de {self.seuil} dossiers).", None, self.masquer(len(d)), "j")

    def _conf_dans_delais(self):
        clos = self.confidentiels.filter(statut=CLOS, date_cloture__range=(self.du, self.au)).exclude(echeance=None)
        total = clos.count()
        dans = sum(1 for d in clos.only("date_cloture", "echeance") if d.date_cloture <= d.echeance)
        return self.chiffre("conf_dans_delais", _pct(dans, total) if total >= self.seuil else None,
                            "Dossiers confidentiels clôturés dans le délai ÷ clôturés sur la période "
                            f"(affiché à partir de {self.seuil} dossiers).", None, self.masquer(total), "%")

    def _conf_referencements(self):
        n = Referencement.objects.filter(dossier__in=self.confidentiels, date__range=(self.du, self.au)).count()
        return self.chiffre("conf_referencements", self.masquer(n), "Orientations vers une assistance (médicale, "
                            "psychosociale, juridique, sécurité) enregistrées sur la période, avec consentement.")

    def _ventiler_confidentiels(self, code, qs, cle, libelle):
        lignes = [(libelle(l[cle]), self.masquer(l["n"]), None)
                  for l in qs.values(cle).annotate(n=Count("id", distinct=True)).order_by("-n")]
        return self.graphique(code, lignes)

    def _conf_par_etape(self):
        element = self._ventiler_confidentiels("conf_par_etape", self.ouverts_maintenant(self.confidentiels), "etape__nom",
                                               lambda x: x or "—")
        element["periode"] = {"au": self.aujourdhui}
        return element

    def _conf_par_categorie(self):
        qs = self.confidentiels.filter(date_reception__range=(self.du, self.au))
        return self._ventiler_confidentiels("conf_par_categorie", qs, "categorie__nom", lambda x: x or v("À classer"))


def calculer_vue(vue, user, du=None, au=None, projet=None, elements=None):
    """Éléments calculés d'une vue (configuration de l'utilisateur, sinon de l'organisation, sinon par défaut)."""
    calcul = Calcul(user, du, au, projet)
    config = configuration(vue, user)
    resultat = []
    for element in elements or config["elements"]:
        donnees = calcul.calculer(element["code"])
        donnees["graphique"] = element.get("graphique")
        resultat.append(donnees)
    return {"vue": vue, "libelle": v(VUES[vue][0]), "source": config["source"], "du": calcul.du, "au": calcul.au,
            "seuil_masquage": calcul.seuil, "elements": resultat}


def retours_projet(projet_id, user):
    """Encart « Retours des communautés » de la fiche projet (agrégé, sans détail confidentiel)."""
    calcul = Calcul(user, projet=projet_id)
    codes = ["volume", "ouverts", "en_retard", "dans_delais", "boucle", "actions_en_cours", "par_categorie", "par_mois"]
    return {"projet": projet_id, "du": calcul.du, "au": calcul.au, "seuil_masquage": calcul.seuil,
            "elements": [{**calcul.calculer(c), "graphique": GRAPHIQUE_PAR_DEFAUT.get(c, "barres")} for c in codes]}


# --- Tableau de bord consolidé -----------------------------------------------------------------------

def plaintes_tableau_de_bord(projet_ids) -> dict:
    """
    Plaintes et retours des projets, pour le tableau de bord consolidé (qui peut être partagé par lien) :
    uniquement des totaux et des taux, jamais de dossier. Les dossiers confidentiels comptent dans les
    totaux, les ventilations (type, canal, catégorie) ne portent que sur les dossiers ordinaires.
    """
    aujourdhui = timezone.localdate()
    dossiers = Dossier.objects.filter(projet_id__in=projet_ids)
    ordinaires = dossiers.filter(sensible=False)
    clos = list(dossiers.filter(statut=CLOS).values("id", "date_reception", "date_cloture", "echeance", "issue"))
    ouverts = dossiers.exclude(statut=CLOS)
    en_retard = ouverts.filter(Q(echeance__lt=aujourdhui) | Q(echeance_etape__lt=aujourdhui)).count()

    def ventiler(champ):
        return [{"libelle": str(libelle or v("Non renseigné")), "nombre": n} for libelle, n in
                ordinaires.values_list(champ).annotate(n=Count("id")).order_by("-n")]

    # Par territoire : région (premier niveau administratif) de la zone de chaque dossier ordinaire.
    from apps.geo.models import Zone

    zones_dossiers = list(ordinaires.values_list("zone_id", flat=True))
    zones = {z["id"]: z for z in Zone.objects.filter(niveau_administratif__pays__in=Zone.objects.filter(
        id__in=[z for z in zones_dossiers if z]).values("niveau_administratif__pays")).values("id", "nom", "parent_id", "niveau_administratif__ordre")}

    def region(zid):
        while zid in zones and zones[zid]["niveau_administratif__ordre"] > 1 and zones[zid]["parent_id"]:
            zid = zones[zid]["parent_id"]
        return zones[zid]["nom"] if zid in zones else v("Zone non renseignée")

    territoires = {}
    for zid in zones_dossiers:
        nom = region(zid)
        territoires[nom] = territoires.get(nom, 0) + 1
    par_territoire = sorted(({"libelle": nom, "nombre": n} for nom, n in territoires.items()), key=lambda x: -x["nombre"])

    canaux = dict(Canal.choices)
    par_canal = [{"libelle": v(canaux.get(x["libelle"], x["libelle"])), "nombre": x["nombre"]} for x in ventiler("canal")]

    # Accusés de réception : part des dossiers joignables, et délai depuis la réception.
    joignables = dossiers.filter(anonyme=False).filter(~Q(telephone="") | ~Q(courriel=""))
    premiers_accuses = dict(ActionDossier.objects.filter(dossier__in=dossiers, type=ActionDossier.Type.COMMUNICATION, sens="SORTANT",
                                                         objet="ACCUSE_RECEPTION").values("dossier_id")
                            .annotate(premier=Min("date")).values_list("dossier_id", "premier"))
    receptions = dict(dossiers.filter(id__in=premiers_accuses).values_list("id", "date_reception"))
    delais_accuse = [max((premiers_accuses[d].date() - receptions[d]).days, 0) for d in receptions]
    accuses = joignables.filter(id__in=premiers_accuses).count()

    durees = [(d["date_cloture"] - d["date_reception"]).days for d in clos if d["date_cloture"] and d["date_reception"]]
    avec_echeance = [d for d in clos if d["echeance"] and d["date_cloture"]]
    contestes = dossiers.filter(statut=CLOS).filter(actions__type__in=[ActionDossier.Type.REOUVERTURE, ActionDossier.Type.RECOURS]) \
        .values("id").distinct().count() + dossiers.exclude(statut=CLOS).filter(actions__type=ActionDossier.Type.REOUVERTURE) \
        .values("id").distinct().count()
    deja_clos = dossiers.filter(actions__type=ActionDossier.Type.CLOTURE).values("id").distinct().count()
    reponses = ActionDossier.objects.filter(dossier__in=dossiers, type=ActionDossier.Type.COMMUNICATION, objet="SATISFACTION",
                                            sens="ENTRANT", details__has_key="satisfait")
    nb_reponses = reponses.count()

    # Mesures correctives : dossiers clôturés ayant donné lieu à une action, et actions réalisées.
    ids_clos = [d["id"] for d in clos]
    avec_mesure = Dossier.objects.filter(id__in=ids_clos, actions_correctives__isnull=False).distinct().count()
    actions = ActionCorrective.objects.filter(dossiers__in=dossiers).exclude(statut=ActionCorrective.Statut.ABANDONNEE).distinct()
    nb_actions = actions.count()

    return {
        "total": dossiers.count(),
        "par_type": ventiler("type_retour__nom"), "par_canal": par_canal, "par_categorie": ventiler("categorie__nom")[:10],
        "par_territoire": par_territoire,
        "ouverts": ouverts.count(), "clotures": len(clos), "en_retard": en_retard,
        "taux_resolution": _pct(sum(1 for d in clos if d["issue"] == IssueDossier.RESOLU), len(clos)),
        "taux_accuse": _pct(accuses, joignables.count()),
        "delai_accuse_moyen": round(mean(delais_accuse), 1) if delais_accuse else None,
        "delai_accuse_median": median(delais_accuse) if delais_accuse else None,
        "delai_moyen": round(mean(durees), 1) if durees else None, "delai_median": median(durees) if durees else None,
        "dans_delais": _pct(sum(1 for d in avec_echeance if d["date_cloture"] <= d["echeance"]), len(avec_echeance)),
        "taux_reouverture": _pct(contestes, deja_clos),
        "satisfaction": _pct(reponses.filter(details__satisfait=True).count(), nb_reponses) if nb_reponses >= 10 else None,
        "satisfaction_reponses": nb_reponses,
        "avec_mesure_corrective": _pct(avec_mesure, len(clos)),
        "actions_correctives": nb_actions,
        "mise_en_oeuvre_mesures": _pct(actions.filter(statut=ActionCorrective.Statut.REALISEE).count(), nb_actions),
    }
