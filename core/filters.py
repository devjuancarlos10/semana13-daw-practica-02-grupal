"""Filtros reutilizables."""

from rest_framework.filters import OrderingFilter


class AliasOrderingFilter(OrderingFilter):
    """OrderingFilter que acepta alias en español con tildes.

    Permite que el cliente use ``?ordering=-año`` u ``?ordering=título``
    aunque los campos del modelo se llamen ``anio`` y ``titulo``. Cada vista
    define ``ordering_aliases = {"año": "anio", ...}``.
    """

    def traducir(self, termino: str, aliases: dict) -> str:
        termino = termino.strip()
        signo = "-" if termino.startswith("-") else ""
        nombre = termino.lstrip("-")
        return signo + aliases.get(nombre, nombre)

    def get_ordering(self, request, queryset, view):
        params = request.query_params.get(self.ordering_param)
        if params:
            aliases = getattr(view, "ordering_aliases", {})
            campos = [self.traducir(t, aliases) for t in params.split(",")]
            ordering = self.remove_invalid_fields(queryset, campos, view, request)
            if ordering:
                return ordering
        return self.get_default_ordering(view)
