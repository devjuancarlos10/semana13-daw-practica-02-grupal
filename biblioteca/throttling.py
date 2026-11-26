"""Throttling del Caso 1 - Biblioteca.

* Anónimos (catálogo público / sistemas externos): 100 req/hora
* Usuarios autenticados: 1000 req/hora
* Ráfaga: 20 req/minuto (previene scraping del catálogo)
"""

from core.throttling import LoggingAnonRateThrottle, LoggingScopedRateThrottle, LoggingUserRateThrottle


class BibliotecaAnonRateThrottle(LoggingAnonRateThrottle):
    scope = "biblioteca_anon"


class BibliotecaUserRateThrottle(LoggingUserRateThrottle):
    scope = "biblioteca_user"

    def allow_request(self, request, view):
        # Los anónimos ya los controla BibliotecaAnonRateThrottle
        if not request.user or not request.user.is_authenticated:
            return True
        return super().allow_request(request, view)


class BurstRateThrottle(LoggingScopedRateThrottle):
    scope = "biblioteca_burst"


THROTTLES_BIBLIOTECA = [BibliotecaAnonRateThrottle, BibliotecaUserRateThrottle, BurstRateThrottle]
