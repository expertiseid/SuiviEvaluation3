from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularRedocView,
    SpectacularSwaggerView,
)
from rest_framework_simplejwt.views import TokenRefreshView, TokenVerifyView

from apps.core.views import ConnexionAuditee

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/v1/auth/token/", ConnexionAuditee.as_view(), name="token_obtain_pair"),
    path("api/v1/auth/token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    path("api/v1/auth/token/verify/", TokenVerifyView.as_view(), name="token_verify"),
    path("api/v1/", include("apps.accounts.urls")),
    path("api/v1/", include("apps.geo.urls")),
    path("api/v1/", include("apps.strategy.urls")),
    path("api/v1/", include("apps.partners.urls")),
    path("api/v1/", include("apps.intervenants.urls")),
    path("api/v1/", include("apps.projects.urls")),
    path("api/v1/", include("apps.indicators.urls")),
    path("api/v1/", include("apps.beneficiaries.urls")),
    path("api/v1/", include("apps.documents.urls")),
    path("api/v1/", include("apps.dashboard.urls")),
    path("api/v1/", include("apps.suivi.urls")),
    path("api/v1/", include("apps.audit.urls")),
    path("api/v1/", include("apps.notifications.urls")),
    path("api/v1/", include("apps.planification.urls")),
    path("api/v1/", include("apps.plaintes.urls")),
    path("api/v1/", include("apps.reports.urls")),
    path("api/v1/", include("apps.core.urls")),
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger-ui"),
    path("api/redoc/", SpectacularRedocView.as_view(url_name="schema"), name="redoc"),
]
