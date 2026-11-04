import pytest


@pytest.fixture(autouse=True)
def _organisation_unique(settings):
    """Les tests tournent en installation unique, quel que soit le .env du poste ; les tests de la
    plateforme multi-organisations (apps/organisations/tests.py) l'activent eux-mêmes."""
    settings.MULTI_ORGANISATIONS = False
    settings.MODE_DEMO = False
