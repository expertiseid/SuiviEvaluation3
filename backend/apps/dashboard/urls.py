from django.urls import path

from .views import dashboard_configuration, dashboard_consolide, dashboard_echeances, dashboard_projet

urlpatterns = [
    path("dashboard/consolide/", dashboard_consolide, name="dashboard-consolide"),
    path("dashboard/configuration/", dashboard_configuration, name="dashboard-configuration"),
    path("dashboard/echeances/", dashboard_echeances, name="dashboard-echeances"),
    path("dashboard/projet/<int:projet_id>/", dashboard_projet, name="dashboard-projet"),
]
