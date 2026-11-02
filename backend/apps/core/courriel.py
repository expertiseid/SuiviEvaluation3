"""
Envoi de courriels par SMTP, vers n'importe quelle adresse réelle.

Les adresses des domaines réservés aux exemples (example.org, example.com, example.net, .test,
.invalid, .localhost, .local), qui sont celles des comptes de démonstration, sont toujours retirées :
elles n'existent pas et des envois vers elles nuiraient à la réputation de la boîte d'envoi.

EMAIL_DESTINATAIRES_AUTORISES (facultatif, ex : « @expertise-id.com,quelqu.un@exemple.org ») : si
renseigné, seuls ces destinataires reçoivent réellement les courriels (poste de test isolé). Vide :
toutes les adresses réelles sont servies. Les retraits sont journalisés sans adresse ni contenu.
"""
import logging

from django.conf import settings
from django.core.mail.backends.smtp import EmailBackend

logger = logging.getLogger(__name__)

DOMAINES_FICTIFS = ("example.org", "example.com", "example.net")
EXTENSIONS_FICTIVES = (".test", ".invalid", ".localhost", ".local", ".example")


def _autorises():
    return [a.strip().lower() for a in getattr(settings, "EMAIL_DESTINATAIRES_AUTORISES", "").split(",") if a.strip()]


def adresse_fictive(adresse):
    _, arobase, domaine = (adresse or "").strip().lower().rpartition("@")
    domaine = domaine.rstrip(">")
    return not arobase or not domaine or any(domaine == d or domaine.endswith("." + d) for d in DOMAINES_FICTIFS) \
        or domaine.endswith(EXTENSIONS_FICTIVES)


def destinataire_autorise(adresse, autorises=None):
    autorises = _autorises() if autorises is None else autorises
    adresse = (adresse or "").strip().lower()
    if adresse_fictive(adresse):
        return False
    return not autorises or any(adresse == a or (a.startswith("@") and adresse.endswith(a)) for a in autorises)


class EmailBackendFiltre(EmailBackend):
    def send_messages(self, email_messages):
        autorises = _autorises()
        gardes = []
        for message in email_messages:
            avant = len(message.to) + len(message.cc) + len(message.bcc)
            message.to = [a for a in message.to if destinataire_autorise(a, autorises)]
            message.cc = [a for a in message.cc if destinataire_autorise(a, autorises)]
            message.bcc = [a for a in message.bcc if destinataire_autorise(a, autorises)]
            retires = avant - len(message.to) - len(message.cc) - len(message.bcc)
            if retires:
                logger.info("Courriel : %s destinataire(s) fictif(s) ou hors liste autorisée non servi(s).", retires)
            if message.to or message.cc or message.bcc:
                gardes.append(message)
        return super().send_messages(gardes) if gardes else 0
