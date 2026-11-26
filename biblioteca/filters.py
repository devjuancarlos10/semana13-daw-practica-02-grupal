"""FilterSets del Caso 1 - Biblioteca (DjangoFilterBackend)."""

import django_filters

from .models import Libro, Prestamo


class LibroFilter(django_filters.FilterSet):
    """Soporta: ?categoria=ingenieria  ?año__gte=2020  ?año__lte=2024  ?disponible=true"""

    categoria = django_filters.ChoiceFilter(choices=Libro.Categoria.choices)
    año = django_filters.NumberFilter(field_name="anio")
    año__gte = django_filters.NumberFilter(field_name="anio", lookup_expr="gte")
    año__lte = django_filters.NumberFilter(field_name="anio", lookup_expr="lte")
    disponible = django_filters.BooleanFilter(method="filtrar_disponible")
    editorial = django_filters.CharFilter(lookup_expr="icontains")
    autor = django_filters.NumberFilter(field_name="autor_id")

    class Meta:
        model = Libro
        fields = ["categoria", "piso"]

    def filtrar_disponible(self, queryset, name, value):
        return queryset.filter(stock__gt=0) if value else queryset.filter(stock=0)


class PrestamoFilter(django_filters.FilterSet):
    fecha_prestamo__gte = django_filters.DateFilter(field_name="fecha_prestamo", lookup_expr="gte")
    fecha_prestamo__lte = django_filters.DateFilter(field_name="fecha_prestamo", lookup_expr="lte")

    class Meta:
        model = Prestamo
        fields = ["estado", "usuario", "libro"]
