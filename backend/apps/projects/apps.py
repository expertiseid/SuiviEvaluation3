from django.apps import AppConfig


class ProjectsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.projects"
    label = "projects"

    def ready(self):
        from . import approbation, verrou

        verrou.connecter()
        approbation.connecter()
