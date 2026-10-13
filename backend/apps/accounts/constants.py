"""
Rôles métier, isolés dans un module sans dépendance vers models.py
pour pouvoir être importés par apps/core/permissions.py sans risque
d'import circulaire.
"""

ROLE_ADMIN = "ADMIN"
ROLE_COORDO_GENERAL = "COORDO_GENERAL"
ROLE_CHARGE_SE = "CHARGE_SE"
ROLE_CHEF_PROJET = "CHEF_PROJET"
ROLE_CHEF_SERVICE = "CHEF_SERVICE"
ROLE_ANIMATEUR_TERRAIN = "ANIMATEUR_TERRAIN"

# Rôles « système » : créés par la migration accounts.0004 et utilisés tels
# quels par le code. Les autres rôles sont gérés en base (modèle Role, écran
# Utilisateurs > Rôles), comme la visibilité de chaque rôle.
ROLE_CHOICES = [
    (ROLE_ADMIN, "Administrateur"),
    (ROLE_COORDO_GENERAL, "Coordonnateur général"),
    (ROLE_CHARGE_SE, "Chargé de Suivi-Évaluation"),
    (ROLE_CHEF_PROJET, "Chef de projet"),
    (ROLE_CHEF_SERVICE, "Chef de service"),
    (ROLE_ANIMATEUR_TERRAIN, "Animateur de terrain"),
]

# Rôles notifiés lors de la modification d'une activité déjà planifiée
ROLES_NOTIFIEES_MODIFICATION_ACTIVITE = {ROLE_COORDO_GENERAL, ROLE_CHARGE_SE}

# Niveau d'accès en écriture — indépendant du rôle (qui détermine seulement
# la visibilité : tous les projets ou uniquement les projets affectés).
# Un Administrateur a toujours un accès complet, quel que soit ce champ.
NIVEAU_ACCES_LECTURE_SEULE = "LECTURE_SEULE"
NIVEAU_ACCES_LECTURE_ECRITURE = "LECTURE_ECRITURE"

NIVEAU_ACCES_CHOICES = [
    (NIVEAU_ACCES_LECTURE_SEULE, "Lecture seule"),
    (NIVEAU_ACCES_LECTURE_ECRITURE, "Lecture et écriture"),
]
