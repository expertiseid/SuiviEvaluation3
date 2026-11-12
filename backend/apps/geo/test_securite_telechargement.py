"""Téléchargements sortants des limites administratives : HTTPS, adresses officielles, jamais le réseau interne, taille bornée."""
import io
import socket

import pytest

from .services import limites
from .services.limites import LimitesIndisponibles, _adresse_autorisee, _lire_json, _RedirectionControlee


@pytest.fixture
def dns(monkeypatch):
    """Résolution des noms simulée : adresses publiques, sauf « interne » qui pointe vers le réseau local."""
    def resoudre(hote, port, proto=0):
        ip = "10.0.0.5" if hote == "github.com" and port == "piege" else ("192.168.1.10" if hote == "interne" else "140.82.121.4")
        return [(socket.AF_INET, socket.SOCK_STREAM, proto, "", (ip, 443))]
    monkeypatch.setattr(socket, "getaddrinfo", resoudre)


def test_adresses_autorisees(dns):
    assert _adresse_autorisee("https://www.geoboundaries.org/api/current/gbOpen/GHA/ADM1/")
    assert _adresse_autorisee("https://media.githubusercontent.com/media/wmgeolab/x.geojson")
    assert not _adresse_autorisee("http://github.com/wmgeolab/x.geojson")  # pas de HTTPS
    assert not _adresse_autorisee("https://exemple-malveillant.com/x.geojson")  # autre site
    assert not _adresse_autorisee("https://github.com:8443/x")  # autre port
    assert not _adresse_autorisee("https://169.254.169.254/latest/meta-data/")


def test_jamais_vers_le_reseau_interne(monkeypatch):
    monkeypatch.setattr(socket, "getaddrinfo", lambda *a, **k: [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("10.0.0.5", 443))])
    assert not _adresse_autorisee("https://github.com/wmgeolab/x.geojson")


def test_redirection_controlee(dns):
    with pytest.raises(LimitesIndisponibles):
        _RedirectionControlee().redirect_request(None, None, 302, "", {}, "http://169.254.169.254/")


def test_taille_maximale(dns, monkeypatch):
    class Reponse(io.BytesIO):
        headers = {"Content-Length": ""}

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

    monkeypatch.setattr(limites, "TAILLE_MAX", 100)
    monkeypatch.setattr(limites._OUVREUR, "open", lambda *a, **k: Reponse(b"[" + b"1," * 200 + b"1]"))
    with pytest.raises(LimitesIndisponibles):
        _lire_json("https://github.com/wmgeolab/x.geojson")
    monkeypatch.setattr(limites._OUVREUR, "open", lambda *a, **k: Reponse(b'{"ok": true}'))
    assert _lire_json("https://github.com/wmgeolab/x.geojson") == {"ok": True}
