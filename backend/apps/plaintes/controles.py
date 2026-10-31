"""
Contrôles du paramétrage : ce qui protège les personnes ou la fiabilité du mécanisme n'est pas
paramétrable. Chaque contrôle renvoie des messages en français clair qui disent quoi corriger et
où (« Circuit confidentiel, étape Décision : désignez une personne responsable »).

- controler_circuit : au moins une étape, une étape de clôture (la dernière), un responsable à
  chaque étape ; dans un circuit sensible, ce responsable est une personne nommément désignée,
  jamais un rôle entier (un rôle peut regrouper des personnes non habilitées).
- controler_activation : tout ce qu'il faut pour ouvrir la réception — au moins un type, une
  catégorie, une priorité urgente, un circuit ordinaire et un circuit confidentiel valides par
  défaut, une langue, et les durées de conservation fixées par l'organisation.
"""


def controler_circuit(circuit) -> list[str]:
    erreurs = []
    etapes = list(circuit.etapes.order_by("ordre", "id"))
    if not etapes:
        return [f"{circuit.nom} : ajoutez au moins une étape."]
    if not any(e.est_cloture for e in etapes):
        erreurs.append(f"{circuit.nom} : ajoutez une étape de clôture.")
    elif not etapes[-1].est_cloture:
        erreurs.append(f"{circuit.nom} : l'étape de clôture doit être la dernière.")
    # Un message par circuit, qui nomme les étapes encore sans responsable.
    if circuit.sensible:
        sans = [e.nom for e in etapes if e.responsable_id is None]
        if sans:
            erreurs.append(f"{circuit.nom} : désignez une personne responsable pour chaque étape (encore sans : "
                           f"{', '.join(sans)}).")
    else:
        sans = [e.nom for e in etapes if e.responsable_id is None and e.role_id is None]
        if sans:
            erreurs.append(f"{circuit.nom} : choisissez un rôle ou une personne responsable pour chaque étape "
                           f"(encore sans : {', '.join(sans)}).")
    return erreurs


def controler_activation(mecanisme) -> list[str]:
    from .models import Categorie, Circuit, Priorite, TypeRetour

    erreurs = []
    if not mecanisme.nom.strip():
        erreurs.append("Général : donnez un nom au mécanisme.")
    if not mecanisme.langues:
        erreurs.append("Général : choisissez au moins une langue pour le formulaire public.")
    if mecanisme.conservation_ordinaire_mois is None or mecanisme.conservation_sensible_mois is None:
        erreurs.append("Général : fixez les durées de conservation des dossiers ordinaires et sensibles.")
    if not TypeRetour.objects.filter(actif=True).exists():
        erreurs.append("Types de retours : activez au moins un type.")
    if not Categorie.objects.filter(actif=True, sensible=False).exists():
        erreurs.append("Catégories : activez au moins une catégorie ordinaire.")
    if not Priorite.objects.filter(actif=True, urgente=True).exists():
        erreurs.append("Priorités : gardez au moins une priorité urgente active.")
    if not Circuit.objects.filter(actif=True, sensible=False, par_defaut=True).exists():
        erreurs.append("Circuits : choisissez un circuit ordinaire par défaut.")
    if not Circuit.objects.filter(actif=True, sensible=True, par_defaut=True).exists():
        erreurs.append("Circuits : choisissez un circuit confidentiel par défaut.")
    for circuit in Circuit.objects.filter(actif=True).prefetch_related("etapes"):
        erreurs.extend(f"Circuits : {e}" for e in controler_circuit(circuit))
    for categorie in Categorie.objects.filter(actif=True, circuit__isnull=False).select_related("circuit", "parent"):
        if categorie.sensible_effective and not categorie.circuit.sensible:
            erreurs.append(f"Catégories : « {categorie} » est sensible, elle doit utiliser un circuit confidentiel.")
        if not categorie.circuit.actif:
            erreurs.append(f"Catégories : « {categorie} » utilise un circuit désactivé.")
    return erreurs
