"""Permisos genéricos compartidos por ambos casos."""

from rest_framework import permissions


class IsOwnerOrReadOnly(permissions.BasePermission):
    """Lectura para todos; escritura solo para el propietario o un admin.

    El propietario se busca en ``obj.usuario`` o ``obj.user``; si el propio
    objeto es un usuario se compara directamente.
    """

    message = "Solo el propietario del recurso puede modificarlo."

    def has_object_permission(self, request, view, obj):
        if request.method in permissions.SAFE_METHODS:
            return True
        if request.user and request.user.is_staff:
            return True
        propietario = getattr(obj, "usuario", None) or getattr(obj, "user", None) or obj
        return propietario == request.user
