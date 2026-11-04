#!/bin/sh
# Démarrage du serveur d'application en production (deploiement/docker-compose.prod.yml).
set -e
# Base centrale puis chaque espace d'organisation : toutes les bases à jour avant d'ouvrir.
python manage.py migrer_organisations
python manage.py collectstatic --noinput --verbosity 0
exec gunicorn config.wsgi:application --bind 0.0.0.0:8000 \
  --workers "${GUNICORN_WORKERS:-2}" --threads "${GUNICORN_THREADS:-4}" \
  --timeout 120 --access-logfile - --error-logfile -
