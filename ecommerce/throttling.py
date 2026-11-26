"""Throttling del Caso 2 - TecnoMarket.

* Anónimos (catálogo): 60 req/hora
* Usuarios autenticados: 2000 req/hora
* Checkout: 10 req/hora (previene abuso de checkout)
* Búsquedas (?search=): 100 req/hora (previene scraping de precios)
"""

from core.throttling import LoggingAnonRateThrottle, LoggingScopedRateThrottle, LoggingUserRateThrottle


class TiendaAnonRateThrottle(LoggingAnonRateThrottle):
    scope = "tienda_anon"


class TiendaUserRateThrottle(LoggingUserRateThrottle):
    scope = "tienda_user"

    def allow_request(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return True
        return super().allow_request(request, view)


class CheckoutRateThrottle(LoggingScopedRateThrottle):
    scope = "tienda_checkout"


class SearchRateThrottle(LoggingScopedRateThrottle):
    """Solo cuenta las peticiones que realmente usan ``?search=``."""

    scope = "tienda_search"

    def allow_request(self, request, view):
        if not request.query_params.get("search"):
            return True
        return super().allow_request(request, view)


THROTTLES_TIENDA = [TiendaAnonRateThrottle, TiendaUserRateThrottle]
