"""Middleware de auditoría.

Registra en ``logs/auditoria.log`` toda operación de escritura (POST, PUT,
PATCH, DELETE) realizada sobre ``/api/``: quién, qué, dónde y resultado.
"""

import logging
import time

logger = logging.getLogger("api.auditoria")
METODOS_AUDITADOS = {"POST", "PUT", "PATCH", "DELETE"}


class AuditoriaMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        inicio = time.perf_counter()
        response = self.get_response(request)
        if request.method in METODOS_AUDITADOS and request.path.startswith("/api/"):
            # DRF autentica dentro de la vista; lo propagamos al request de Django
            usuario = getattr(response, "renderer_context", {}).get("request", None)
            usuario = getattr(usuario, "user", None) or getattr(request, "user", None)
            nombre = usuario.username if usuario is not None and usuario.is_authenticated else "anonimo"
            logger.info(
                "usuario=%s metodo=%s ruta=%s status=%s ip=%s duracion_ms=%.1f",
                nombre,
                request.method,
                request.path,
                response.status_code,
                request.META.get("REMOTE_ADDR"),
                (time.perf_counter() - inicio) * 1000,
            )
        return response
