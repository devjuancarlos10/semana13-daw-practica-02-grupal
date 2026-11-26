"""Rutas principales del proyecto."""

from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularRedocView, SpectacularSwaggerView
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from core.views import ApiRootView, LogoutView, ObtenerTokenView

urlpatterns = [
    path("admin/", admin.site.urls),
    # Raíz navegable de la API (HATEOAS)
    path("api/", ApiRootView.as_view(), name="api-root"),
    # Autenticación
    path("api/auth/token/", ObtenerTokenView.as_view(), name="auth-token"),
    path("api/auth/logout/", LogoutView.as_view(), name="auth-logout"),
    path("api/auth/jwt/", TokenObtainPairView.as_view(), name="jwt-obtain"),
    path("api/auth/jwt/refresh/", TokenRefreshView.as_view(), name="jwt-refresh"),
    path("api-auth/", include("rest_framework.urls")),
    # Documentación OpenAPI 3.0
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger-ui"),
    path("api/redoc/", SpectacularRedocView.as_view(url_name="schema"), name="redoc"),
    # Caso 1 (biblioteca) y Caso 2 (ecommerce)
    path("api/", include("biblioteca.urls")),
    path("api/", include("ecommerce.urls")),
]
