from django.urls import path

from .views import (
    configuration_menu, dashboard_configuration, dashboard_consolide, dashboard_consolide_export, dashboard_echeances,
    dashboard_projet, export_graphique,
)

urlpatterns = [
    path("dashboard/consolide/", dashboard_consolide, name="dashboard-consolide"),
    path("dashboard/consolide/export/", dashboard_consolide_export, name="dashboard-consolide-export"),
    path("dashboard/graphique/excel/", export_graphique, name="dashboard-graphique-excel"),
    path("dashboard/configuration/", dashboard_configuration, name="dashboard-configuration"),
    path("dashboard/echeances/", dashboard_echeances, name="dashboard-echeances"),
    path("dashboard/projet/<int:projet_id>/", dashboard_projet, name="dashboard-projet"),
    path("interface/menu/", configuration_menu, name="configuration-menu"),
]
