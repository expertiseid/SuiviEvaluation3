"""
Détection des doublons d'enregistrement : jamais de fusion automatique, seulement un
signalement à examiner (écran « Doublons d'enregistrement »).

Pour ne signaler que les vrais doublons :
1. Même numéro de pièce d'identité (espaces, tirets et casse ignorés) : doublon quasi certain.
2. Sinon, nom ET prénom très proches (accents et casse ignorés, nom et prénom éventuellement
   inversés) ET au moins une confirmation : même téléphone, même date de naissance ou même
   localité.
3. Jamais signalés : sexe différent, année de naissance différente, ou deux numéros de pièce
   d'identité renseignés et différents.

Chaque résultat porte ses motifs (« Même téléphone »…), affichés avec le signalement.
"""
import re
import unicodedata
from difflib import SequenceMatcher

from django.contrib.postgres.search import TrigramSimilarity
from django.db.models import Q

# Présélection en base (similarité trigram du nom et du prénom, chacun de 0 à 1) ; le contrôle
# fin qui suit est plus strict.
SEUIL_PRESELECTION = 0.4
# Ressemblance minimale du nom et du prénom après normalisation (1 = identiques).
SEUIL_NOM = 0.8


def normaliser_texte(texte: str) -> str:
    sans_accents = unicodedata.normalize("NFKD", texte or "").encode("ascii", "ignore").decode()
    return " ".join(sans_accents.lower().split())


def normaliser_piece(numero: str) -> str:
    return re.sub(r"[^0-9A-Za-z]", "", numero or "").upper()


def normaliser_telephone(numero: str) -> str:
    chiffres = re.sub(r"\D", "", numero or "")
    return chiffres[-8:] if len(chiffres) >= 8 else chiffres  # sans indicatif pays


def _ancetres(zone):
    ids = set()
    while zone is not None:
        ids.add(zone.id)
        zone = zone.parent
    return ids


def _zones_proches(a, b):
    """Même localité : même zone, ou l'une contient l'autre (village dans sa commune…)."""
    if not a.zone_id or not b.zone_id:
        return False
    return a.zone_id == b.zone_id or a.zone_id in _ancetres(b.zone) or b.zone_id in _ancetres(a.zone)


def _contradiction(a, b) -> bool:
    if a.sexe and b.sexe and a.sexe != b.sexe:
        return True
    if a.date_naissance and b.date_naissance and a.date_naissance.year != b.date_naissance.year:
        return True
    pa, pb = normaliser_piece(a.numero_piece_identite), normaliser_piece(b.numero_piece_identite)
    return bool(pa and pb and pa != pb)


def _confirmations(a, b) -> list[str]:
    motifs = []
    ta, tb = normaliser_telephone(a.telephone), normaliser_telephone(b.telephone)
    if ta and ta == tb:
        motifs.append("Même téléphone")
    if a.date_naissance and a.date_naissance == b.date_naissance:
        motifs.append("Même date de naissance")
    if _zones_proches(a, b):
        motifs.append("Même localité")
    return motifs


def _ressemblance(x, y):
    return SequenceMatcher(None, normaliser_texte(x), normaliser_texte(y)).ratio()


def rechercher_doublons(beneficiaire):
    """Liste de {candidat, score, methode, motifs} pour un bénéficiaire donné."""
    from ..models import Beneficiaire

    resultats = []
    autres = Beneficiaire.objects.exclude(pk=beneficiaire.pk).select_related("zone__parent__parent__parent")

    piece = normaliser_piece(beneficiaire.numero_piece_identite)
    if piece:
        for candidat in autres.exclude(numero_piece_identite=""):
            if normaliser_piece(candidat.numero_piece_identite) == piece:
                resultats.append({
                    "candidat": candidat, "score": 1.0, "methode": "PIECE_IDENTITE",
                    "motifs": ["Même pièce d'identité"],
                })
    deja = {r["candidat"].pk for r in resultats}

    nom, prenom = beneficiaire.nom, beneficiaire.prenom
    candidats = autres.exclude(pk__in=deja).annotate(
        sim_nom=TrigramSimilarity("nom", nom),
        sim_prenom=TrigramSimilarity("prenom", prenom),
        sim_nom_inverse=TrigramSimilarity("nom", prenom),
        sim_prenom_inverse=TrigramSimilarity("prenom", nom),
    ).filter(
        Q(sim_nom__gte=SEUIL_PRESELECTION, sim_prenom__gte=SEUIL_PRESELECTION)
        | Q(sim_nom_inverse__gte=SEUIL_PRESELECTION, sim_prenom_inverse__gte=SEUIL_PRESELECTION)
    )[:200]

    for candidat in candidats:
        if _contradiction(beneficiaire, candidat):
            continue
        direct = min(_ressemblance(nom, candidat.nom), _ressemblance(prenom, candidat.prenom))
        inverse = min(_ressemblance(nom, candidat.prenom), _ressemblance(prenom, candidat.nom))
        similarite = max(direct, inverse)
        if similarite < SEUIL_NOM:
            continue
        confirmations = _confirmations(beneficiaire, candidat)
        if not confirmations:
            continue
        motifs = ["Nom et prénom identiques" if similarite == 1 else "Nom et prénom très proches"]
        if inverse > direct:
            motifs.append("Nom et prénom inversés")
        motifs += confirmations
        score = min(1.0, 0.3 + 0.3 * similarite + 0.2 * len(confirmations))
        resultats.append({"candidat": candidat, "score": round(score, 3), "methode": "SIMILARITE", "motifs": motifs})

    return resultats


def enregistrer_signalements(beneficiaire):
    """Crée les signalements nouveaux (un par paire) ; renvoie [(signalement, cree)]."""
    from ..models import SignalementDoublon

    sortie = []
    for item in rechercher_doublons(beneficiaire):
        b1, b2 = sorted([beneficiaire, item["candidat"]], key=lambda b: b.pk)
        signalement, cree = SignalementDoublon.objects.get_or_create(
            beneficiaire_1=b1,
            beneficiaire_2=b2,
            defaults={"score": item["score"], "methode": item["methode"], "motifs": item["motifs"]},
        )
        sortie.append((signalement, cree))
    return sortie


def reverifier_signalements():
    """
    Repasse les signalements encore « Signalé » avec les règles actuelles : ceux qui ne
    tiennent plus (faux positifs des anciennes règles) sont retirés, les autres mis à jour.
    Les signalements déjà traités (écarté, fusionné) ne bougent pas.
    """
    from ..models import SignalementDoublon

    retires = maintenus = 0
    for s in SignalementDoublon.objects.filter(statut=SignalementDoublon.Statut.SIGNALE).select_related(
        "beneficiaire_1", "beneficiaire_2"
    ):
        trouve = next((r for r in rechercher_doublons(s.beneficiaire_1) if r["candidat"].pk == s.beneficiaire_2_id), None)
        if trouve is None:
            s.delete()
            retires += 1
        else:
            s.score, s.methode, s.motifs = trouve["score"], trouve["methode"], trouve["motifs"]
            s.save(update_fields=["score", "methode", "motifs"])
            maintenus += 1
    return {"retires": retires, "maintenus": maintenus}
