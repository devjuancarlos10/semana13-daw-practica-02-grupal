"""Rutas del Caso 1 - Biblioteca (routing automático con SimpleRouter)."""

from django.urls import include, path
from rest_framework.routers import SimpleRouter

from . import views

router = SimpleRouter()
router.register("libros", views.LibroViewSet, basename="libro")
router.register("autores", views.AutorViewSet, basename="autor")
router.register("prestamos", views.PrestamoViewSet, basename="prestamo")
router.register("usuarios", views.UsuarioViewSet, basename="usuario")
router.register("reservas", views.ReservaViewSet, basename="reserva")
router.register("adquisiciones", views.SolicitudAdquisicionViewSet, basename="adquisicion")

urlpatterns = [
    path("", include(router.urls)),
]
