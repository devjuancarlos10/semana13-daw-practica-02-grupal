"""Throttling con registro en logs para monitoreo.

Cada vez que una petición es rechazada con HTTP 429 se escribe una línea en
``logs/throttling.log`` (logger ``api.throttling``) con el scope, el cliente
y la ruta, de modo que el equipo pueda detectar scraping o abuso.
"""

import logging

from rest_framework.throttling import AnonRateThrottle, SimpleRateThrottle, UserRateThrottle

logger = logging.getLogger("api.throttling")


class LoggingThrottleMixin:
    def allow_request(self, request, view):
        permitido = super().allow_request(request, view)
        if not permitido:
            usuario = request.user.username if request.user and request.user.is_authenticated else "anonimo"
            logger.warning(
                "THROTTLED scope=%s usuario=%s ip=%s metodo=%s ruta=%s",
                getattr(self, "scope", "?"),
                usuario,
                self.get_ident(request),
                request.method,
                request.path,
            )
        return permitido


class LoggingAnonRateThrottle(LoggingThrottleMixin, AnonRateThrottle):
    """Límite para clientes anónimos (por IP)."""


class LoggingUserRateThrottle(LoggingThrottleMixin, UserRateThrottle):
    """Límite para usuarios autenticados (por usuario; por IP si es anónimo)."""


class LoggingScopedRateThrottle(LoggingThrottleMixin, SimpleRateThrottle):
    """Throttle con scope fijo aplicado a usuarios y anónimos."""

    def get_cache_key(self, request, view):
        if request.user and request.user.is_authenticated:
            ident = request.user.pk
        else:
            ident = self.get_ident(request)
        return self.cache_format % {"scope": self.scope, "ident": ident}
