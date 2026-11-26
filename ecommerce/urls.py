"""Rutas del Caso 2 - TecnoMarket (routing automático con SimpleRouter)."""

from django.urls import include, path
from rest_framework.routers import SimpleRouter

from . import views

router = SimpleRouter()
router.register("productos", views.ProductoViewSet, basename="producto")
router.register("categorias", views.CategoriaViewSet, basename="categoria")
router.register("vendedores", views.VendedorViewSet, basename="vendedor")
router.register("carrito", views.CarritoViewSet, basename="carrito")
router.register("ordenes", views.OrdenViewSet, basename="orden")
router.register("reseñas", views.ResenaViewSet, basename="resena")
router.register("cuenta", views.CuentaViewSet, basename="cuenta")
router.register("webhooks", views.WebhookViewSet, basename="webhook")

urlpatterns = [
    path("", include(router.urls)),
]
