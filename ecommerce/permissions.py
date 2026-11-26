"""Permisos del Caso 2 - TecnoMarket.

Roles:
  * Administrador -> ``user.is_staff``
  * Vendedor      -> tiene ``Vendedor`` aprobado
  * Cliente       -> cualquier usuario autenticado
  * Invitado      -> anónimo (solo catálogo)
  * Sistema externo -> webhooks con secreto compartido
"""

import hmac

from django.conf import settings
from rest_framework import permissions

from .models import Producto, compro_producto


def vendedor_de(user):
    if not user or not user.is_authenticated:
        return None
    return getattr(user, "vendedor", None)


def es_vendedor_aprobado(user) -> bool:
    vendedor = vendedor_de(user)
    return bool(vendedor and vendedor.aprobado)


class PuedeVender(permissions.BasePermission):
    """Custom permission: admin o vendedor aprobado del marketplace."""

    message = "Necesita una cuenta de vendedor aprobada para publicar productos."

    def has_permission(self, request, view):
        return bool(request.user and (request.user.is_staff or es_vendedor_aprobado(request.user)))


class EsDuenoDelProductoOAdmin(permissions.BasePermission):
    """PUT/PATCH de productos: solo el vendedor dueño o un admin."""

    message = "Solo puede modificar sus propios productos."

    def has_object_permission(self, request, view, obj: Producto):
        if request.user.is_staff:
            return True
        vendedor = vendedor_de(request.user)
        return vendedor is not None and obj.vendedor_id == vendedor.pk


class EsCompradorVerificado(permissions.BasePermission):
    """Custom permission: solo quien compró el producto puede reseñarlo."""

    message = "Solo puede reseñar productos que ha comprado (orden pagada, enviada o entregada)."

    def has_permission(self, request, view):
        if request.method != "POST":
            return True
        producto_id = request.data.get("producto")
        if not producto_id:
            return True  # el serializer informará el campo faltante
        try:
            producto = Producto.objects.get(pk=int(producto_id))
        except (Producto.DoesNotExist, TypeError, ValueError):
            return True
        return compro_producto(request.user, producto)


class EsPropietarioOAdmin(permissions.BasePermission):
    def has_object_permission(self, request, view, obj):
        return request.user.is_staff or obj.usuario_id == request.user.pk


class PuedeActualizarEstadoOrden(permissions.BasePermission):
    """PATCH de órdenes: admin o vendedor de alguno de los productos de la orden."""

    message = "Solo un administrador o el vendedor de los productos puede actualizar el estado."

    def has_object_permission(self, request, view, obj):
        if request.user.is_staff:
            return True
        vendedor = vendedor_de(request.user)
        return vendedor is not None and obj.items.filter(vendedor=vendedor).exists()


class WebhookSecretoValido(permissions.BasePermission):
    """Sistemas externos (pasarelas/logística) envían ``X-Webhook-Token``."""

    message = "Firma de webhook inválida."

    def has_permission(self, request, view):
        recibido = request.headers.get("X-Webhook-Token", "")
        return hmac.compare_digest(recibido, settings.WEBHOOK_SECRET)
