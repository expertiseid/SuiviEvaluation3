"""
Données d'enquête : import d'un fichier (Excel ou CSV, export KoboToolbox…) et estimations pondérées avec leur
marge d'erreur.

Import : une ligne par répondant, la première ligne donne les noms de colonnes. Les colonnes d'identification
personnelle (noms, téléphones, pièces, positions GPS…) et les colonnes techniques des outils de collecte sont
écartées d'office ; chaque colonne est typée (NOMBRE si presque toutes ses valeurs sont des nombres, sinon TEXTE).

Estimations : proportion (part des répondants ayant certaines réponses), moyenne et total, sur l'ensemble ou par
sous-groupe. Le plan de sondage est pris en compte : poids, strates et grappes (unités primaires). La variance
est calculée par linéarisation de Taylor (estimateur par le ratio, tirage avec remise des grappes dans chaque
strate) ; l'intervalle de confiance à 95 % utilise la loi de Student avec (grappes − strates) degrés de liberté.
L'effet de plan compare cette variance à celle d'un sondage aléatoire simple de même taille.
"""
import csv
import io
import math
import re
import unicodedata

from apps.core.vocabulaire import v

MAX_LIGNES = 50_000
MAX_COLONNES = 400
EFFECTIF_MINIMUM = 30
PART_NOMBRES = 0.95

# Mots qui signalent une donnée personnelle ou technique (nom de colonne découpé en mots).
IDENTIFIANTS = {
    "nom", "noms", "prenom", "prenoms", "name", "names", "firstname", "lastname", "surname", "telephone", "tel", "phone",
    "phonenumber", "portable", "mobile", "contact", "email", "mail", "courriel", "cni", "cnib", "piece", "passeport",
    "passport", "adresse", "address", "gps", "geolocation", "geopoint", "latitude", "longitude", "altitude", "precision",
    "photo", "signature", "imei", "deviceid", "subscriberid", "simserial", "username", "uuid", "instanceid",
}
TECHNIQUES = {
    "_id", "_index", "_submission_time", "_submitted_by", "_validation_status", "_notes", "_status", "_tags",
    "__version__", "_xform_id", "_xform_id_string", "_attachments", "_parent_index", "start", "end", "today", "audit",
}

# Loi de Student : quantile à 97,5 % (intervalle à 95 %) selon les degrés de liberté.
STUDENT = {1: 12.706, 2: 4.303, 3: 3.182, 4: 2.776, 5: 2.571, 6: 2.447, 7: 2.365, 8: 2.306, 9: 2.262, 10: 2.228,
           11: 2.201, 12: 2.179, 13: 2.160, 14: 2.145, 15: 2.131, 16: 2.120, 17: 2.110, 18: 2.101, 19: 2.093, 20: 2.086,
           21: 2.080, 22: 2.074, 23: 2.069, 24: 2.064, 25: 2.060, 26: 2.056, 27: 2.052, 28: 2.048, 29: 2.045, 30: 2.042,
           40: 2.021, 60: 2.000, 120: 1.980}


class EnqueteInvalide(ValueError):
    pass


def quantile_student(degres):
    """Quantile à 97,5 % ; entre deux lignes de la table, la plus prudente (moins de degrés)."""
    if degres >= 1000:
        return 1.960
    return STUDENT[max(d for d in STUDENT if d <= max(degres, 1))]


# --- Import -------------------------------------------------------------------------------------------


def _mots(nom):
    texte = unicodedata.normalize("NFD", str(nom)).encode("ascii", "ignore").decode().lower()
    return texte, [m for m in re.split(r"[^a-z0-9]+", texte) if m]


def a_ecarter(nom) -> bool:
    texte, mots = _mots(nom)
    dernier = texte.rsplit("/", 1)[-1]  # colonnes de groupes Kobo : « groupe/question »
    return dernier in TECHNIQUES or texte in TECHNIQUES or any(m in IDENTIFIANTS for m in mots)


def _nombre(valeur):
    if isinstance(valeur, bool):
        return None
    if isinstance(valeur, (int, float)):
        return float(valeur) if math.isfinite(valeur) else None
    try:
        return float(str(valeur).strip().replace(" ", "").replace(" ", "").replace(",", "."))
    except ValueError:
        return None


def _lignes_du_fichier(fichier):
    nom = (getattr(fichier, "name", "") or "").lower()
    if nom.endswith((".xlsx", ".xlsm")):
        from openpyxl import load_workbook

        try:
            feuille = load_workbook(fichier, read_only=True, data_only=True).worksheets[0]
        except Exception:
            raise EnqueteInvalide(v("Le fichier Excel n'a pas pu être lu."))
        return [list(l) for l in feuille.iter_rows(values_only=True)]
    if nom.endswith((".csv", ".txt")):
        brut = fichier.read()
        try:
            texte = brut.decode("utf-8-sig")
        except UnicodeDecodeError:
            texte = brut.decode("latin-1")
        try:
            dialecte = csv.Sniffer().sniff(texte[:5000], delimiters=";,\t")
        except csv.Error:
            dialecte = csv.excel
        return list(csv.reader(io.StringIO(texte), dialecte))
    raise EnqueteInvalide(v("Choisissez un fichier Excel (.xlsx) ou CSV."))


def lire(fichier) -> dict:
    """Colonnes typées, colonnes écartées et données d'un fichier d'enquête."""
    lignes = [l for l in _lignes_du_fichier(fichier) if any(c not in (None, "") for c in l)]
    if len(lignes) < 2:
        raise EnqueteInvalide(v("Le fichier doit contenir une ligne d'en-têtes puis au moins une réponse."))
    if len(lignes) - 1 > MAX_LIGNES:
        raise EnqueteInvalide(v("{0} réponses au plus par fichier.").format(MAX_LIGNES))
    entetes = [str(e).strip() if e not in (None, "") else f"colonne_{i + 1}" for i, e in enumerate(lignes[0])]
    gardees = [i for i, e in enumerate(entetes) if not a_ecarter(e)]
    if len(gardees) > MAX_COLONNES:
        raise EnqueteInvalide(v("{0} colonnes au plus.").format(MAX_COLONNES))
    if not gardees:
        raise EnqueteInvalide(v("Aucune colonne utilisable dans ce fichier."))
    reponses = lignes[1:]
    colonnes, donnees = [], [[] for _ in reponses]
    for i in gardees:
        valeurs = [(r[i] if i < len(r) else None) for r in reponses]
        valeurs = [None if x is None or (isinstance(x, str) and not x.strip()) else x for x in valeurs]
        renseignees = [x for x in valeurs if x is not None]
        nombres = [_nombre(x) for x in renseignees]
        numerique = bool(renseignees) and sum(n is not None for n in nombres) >= PART_NOMBRES * len(renseignees)
        colonnes.append({"nom": entetes[i], "type": "NOMBRE" if numerique else "TEXTE"})
        for ligne, x in zip(donnees, valeurs):
            if x is None:
                ligne.append(None)
            elif numerique:
                ligne.append(_nombre(x))
            else:
                ligne.append(x.strip() if isinstance(x, str) else (str(int(x)) if isinstance(x, float) and x.is_integer() else str(x)))
    poids = next((c["nom"] for c in colonnes if c["type"] == "NOMBRE"
                  and any(m in ("poids", "weight", "ponderation", "wt") for m in _mots(c["nom"])[1])), "")
    return {"colonnes": colonnes, "colonnes_ecartees": [entetes[i] for i in range(len(entetes)) if i not in gardees],
            "donnees": donnees, "nombre_reponses": len(donnees), "colonne_poids": poids}


def modalites(enquete, colonne, maximum=50):
    """Réponses d'une colonne texte et leur nombre (les plus fréquentes d'abord)."""
    from collections import Counter

    i = _indice(enquete, colonne)
    compte = Counter(l[i] for l in enquete.donnees if l[i] is not None)
    return [{"valeur": str(x), "nombre": n} for x, n in compte.most_common(maximum)]


# --- Estimations ----------------------------------------------------------------------------------------


def _indice(enquete, colonne):
    noms = [c["nom"] for c in enquete.colonnes]
    if colonne not in noms:
        raise EnqueteInvalide(v("Colonne inconnue : « {0} ».").format(colonne))
    return noms.index(colonne)


def _estimer(observations, calcul):
    """
    observations : [(poids, strate, grappe, y, x)] du domaine (y, x à 0 hors domaine ou valeur manquante).
    Renvoie estimation, erreur type, degrés de liberté, effet de plan, effectifs.
    """
    n = sum(1 for o in observations if o[4])
    pondere = sum(o[0] * o[4] for o in observations)
    if calcul == "total":
        estimation = sum(o[0] * o[3] for o in observations)
        z = [o[0] * o[3] for o in observations]
    else:
        if not pondere:
            return None
        estimation = sum(o[0] * o[3] for o in observations) / pondere
        z = [o[0] * (o[3] - estimation * o[4]) / pondere for o in observations]
    # Variance : écarts entre les totaux de grappes, strate par strate.
    par_strate = {}
    for o, zi in zip(observations, z):
        grappes = par_strate.setdefault(o[1], {})
        grappes[o[2]] = grappes.get(o[2], 0.0) + zi
    variance, nb_grappes, strates_seules = 0.0, 0, 0
    for grappes in par_strate.values():
        k = len(grappes)
        nb_grappes += k
        if k < 2:
            strates_seules += 1
            continue
        moyenne = sum(grappes.values()) / k
        variance += k / (k - 1) * sum((g - moyenne) ** 2 for g in grappes.values())
    degres = max(nb_grappes - len(par_strate), 1)
    # Effet de plan : rapport à la variance d'un sondage aléatoire simple de n répondants.
    deff = None
    if calcul != "total" and n > 1 and pondere:
        dispersion = sum(o[0] * o[4] * (o[3] - estimation) ** 2 for o in observations) / pondere * n / (n - 1)
        if dispersion:
            deff = variance / (dispersion / n)
    return {"estimation": estimation, "erreur_type": math.sqrt(variance), "degres": degres, "deff": deff, "n": n,
            "pondere": pondere, "strates_a_une_grappe": strates_seules}


def estimer(enquete, calcul, colonne, valeurs=None, par=None, domaine=None) -> dict:
    """
    calcul : « proportion » (part des réponses parmi `valeurs`, en %), « moyenne » ou « total » (somme pondérée
    d'une colonne numérique, ou nombre estimé de répondants ayant ces réponses). `par` : colonne de ventilation.
    `domaine` : (colonne, valeur) qui restreint l'estimation à un sous-groupe. Résultat :
    {resultats: [{groupe, estimation, erreur_type, ic_bas, ic_haut, marge, n, effectif_pondere, deff,
    effectif_faible}], plan, avertissements}.
    """
    if calcul not in ("proportion", "moyenne", "total"):
        raise EnqueteInvalide(v("Calcul inconnu."))
    i = _indice(enquete, colonne)
    numerique = enquete.colonnes[i]["type"] == "NOMBRE"
    valeurs = {str(x) for x in (valeurs or [])}
    if calcul == "proportion" and not valeurs:
        raise EnqueteInvalide(v("Choisissez la ou les réponses dont on calcule la part."))
    if calcul == "moyenne" and not numerique:
        raise EnqueteInvalide(v("Une moyenne se calcule sur une colonne de nombres."))
    if calcul == "total" and not numerique and not valeurs:
        raise EnqueteInvalide(v("Choisissez les réponses à compter, ou une colonne de nombres."))
    ip = _indice(enquete, enquete.colonne_poids) if enquete.colonne_poids else None
    ist = _indice(enquete, enquete.colonne_strate) if enquete.colonne_strate else None
    ig = _indice(enquete, enquete.colonne_grappe) if enquete.colonne_grappe else None
    ipar = _indice(enquete, par) if par else None
    idom = (_indice(enquete, domaine[0]), str(domaine[1])) if domaine else None

    avertissements, base = [], []
    sans_poids = 0
    for numero, l in enumerate(enquete.donnees):
        poids = 1.0
        if ip is not None:
            poids = l[ip] if isinstance(l[ip], (int, float)) else None
            if poids is None or poids <= 0:
                sans_poids += 1
                continue
        valeur = l[i]
        if valeur is None:
            y, x = 0.0, 0
        elif calcul == "proportion":
            y, x = (1.0 if str(valeur) in valeurs else 0.0), 1
        elif numerique and not (calcul == "total" and valeurs):
            y, x = float(valeur), 1
        else:
            y, x = (1.0 if str(valeur) in valeurs else 0.0), 1
        if idom is not None and str(l[idom[0]]) != idom[1]:
            y, x = 0.0, 0
        strate = str(l[ist]) if ist is not None else "_"
        grappe = str(l[ig]) if ig is not None else f"_{numero}"
        groupe = None if ipar is None else (str(l[ipar]) if l[ipar] is not None else None)
        base.append((poids, strate, grappe, y, x, groupe))
    if sans_poids:
        avertissements.append(v("{0} réponse(s) sans poids valide écartée(s).").format(sans_poids))

    groupes = [None] if ipar is None else sorted({o[5] for o in base if o[5] is not None and o[4]}, key=str)
    resultats = []
    for groupe in groupes:
        obs = [(o[0], o[1], o[2], o[3] if groupe is None or o[5] == groupe else 0.0, o[4] if groupe is None or o[5] == groupe else 0)
               for o in base]
        r = _estimer(obs, calcul)
        if r is None:
            continue
        echelle = 100 if calcul == "proportion" else 1
        marge = quantile_student(r["degres"]) * r["erreur_type"] * echelle
        estimation = r["estimation"] * echelle
        if r["strates_a_une_grappe"]:
            avertissements.append(v("Strate(s) avec une seule grappe : leur variance n'est pas estimable (comptée nulle)."))
        resultats.append({
            "groupe": groupe, "estimation": round(estimation, 4), "erreur_type": round(r["erreur_type"] * echelle, 4),
            "ic_bas": round(max(estimation - marge, 0) if calcul == "proportion" else estimation - marge, 4),
            "ic_haut": round(min(estimation + marge, 100) if calcul == "proportion" else estimation + marge, 4),
            "marge": round(marge, 4), "n": r["n"], "effectif_pondere": round(r["pondere"], 2),
            "deff": round(r["deff"], 2) if r["deff"] is not None else None, "effectif_faible": r["n"] < EFFECTIF_MINIMUM,
        })
    plan = []
    if enquete.colonne_poids:
        plan.append(v("pondéré par « {0} »").format(enquete.colonne_poids))
    if enquete.colonne_strate:
        plan.append(v("stratifié par « {0} »").format(enquete.colonne_strate))
    if enquete.colonne_grappe:
        plan.append(v("grappes : « {0} »").format(enquete.colonne_grappe))
    return {"resultats": resultats, "plan": " ; ".join(plan) or v("sondage aléatoire simple, sans pondération"),
            "avertissements": list(dict.fromkeys(avertissements))}
