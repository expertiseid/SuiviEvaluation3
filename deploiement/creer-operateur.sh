#!/bin/bash
# Crée un compte Expertise-ID pour la console (page /expertise-id), sur le serveur de la plateforme.
# Le mot de passe est demandé au clavier (jamais écrit dans une commande) :
#   ssh -t alex@128.140.123.104 bash /opt/suivi-evaluation-plateforme/deploiement/creer-operateur.sh alexido@expertise-id.com
set -euo pipefail
COURRIEL="${1:?Adresse courriel du compte manquante}"
docker exec -it -e COURRIEL="$COURRIEL" suivi-evaluation-plateforme-backend-1 python manage.py shell -c "
import getpass, os
from django.contrib.auth import get_user_model
courriel = os.environ['COURRIEL'].strip().lower()
User = get_user_model()
if User.objects.filter(email__iexact=courriel).exists():
    raise SystemExit('Ce compte existe déjà.')
mdp = getpass.getpass('Mot de passe du compte : ')
if mdp != getpass.getpass('Encore une fois : '):
    raise SystemExit('Les deux mots de passe sont différents : rien n a été créé.')
User.objects.create_superuser(username=courriel.split('@')[0], email=courriel, password=mdp, role='ADMIN')
print('Compte créé : ' + courriel)
"
