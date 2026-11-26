"""Permisos del Caso 1 - Biblioteca.

Roles (PerfilUsuario.tipo): administrador, bibliotecario, estudiante, docente.
Un usuario ``is_staff`` de Django siempre se considera administrador.
"""

from rest_framework import permissions

from .models import MAX_PRESTAMOS_ACTIVOS, PerfilUsuario, Prestamo


def tipo_de(user) -> str | None:
    if not user or not user.is_authenticated:
        return None
    perfil = getattr(user, "perfil_biblioteca", None)
    return perfil.tipo if perfil else None


def es_admin(user) -> bool:
    return bool(user and user.is_authenticated and (user.is_staff or tipo_de(user) == PerfilUsuario.Tipo.ADMINISTRADOR))


def es_bibliotecario(user) -> bool:
    return tipo_de(user) == PerfilUsuario.Tipo.BIBLIOTECARIO


def es_personal(user) -> bool:
    """Administrador o bibliotecario."""
    return es_admin(user) or es_bibliotecario(user)


class EsAdministrador(permissions.BasePermission):
    message = "Solo el administrador (bibliotecario jefe) puede realizar esta acción."

    def has_permission(self, request, view):
        return es_admin(request.user)


class EsPersonalBiblioteca(permissions.BasePermission):
    message = "Solo administradores o bibliotecarios pueden realizar esta acción."

    def has_permission(self, request, view):
        return es_personal(request.user)


class EsDocenteInvestigador(permissions.BasePermission):
    message = "Solo docentes/investigadores (o el administrador) pueden realizar esta acción."

    def has_permission(self, request, view):
        return es_admin(request.user) or tipo_de(request.user) == PerfilUsuario.Tipo.DOCENTE


class EsPropietarioOAdmin(permissions.BasePermission):
    """El préstamo/reserva solo es visible para su dueño o el personal."""

    message = "Solo puede consultar sus propios registros."

    def has_object_permission(self, request, view, obj):
        return es_personal(request.user) or getattr(obj, "usuario", obj) == request.user


class PuedeCrearPrestamo(permissions.BasePermission):
    """Permiso personalizado: el usuario destino no puede superar 5 préstamos activos.

    Se evalúa antes de llegar al serializer, devolviendo 403 con un mensaje
    claro. El serializer repite la validación como defensa en profundidad.
    """

    message = f"El usuario ya alcanzó el límite de {MAX_PRESTAMOS_ACTIVOS} préstamos activos."

    def has_permission(self, request, view):
        if request.method != "POST":
            return True
        usuario_id = request.data.get("usuario")
        if not usuario_id:
            return True  # el serializer reportará el campo faltante
        try:
            activos = Prestamo.objects.activos().filter(usuario_id=int(usuario_id)).count()
        except (TypeError, ValueError):
            return True
        return activos < MAX_PRESTAMOS_ACTIVOS
