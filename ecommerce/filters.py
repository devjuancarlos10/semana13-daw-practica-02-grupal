"""FilterSets del Caso 2 - TecnoMarket (filtros exactos y por rangos)."""

import django_filters

from .models import Orden, Producto, Resena


class ProductoFilter(django_filters.FilterSet):
    """?categoria=laptops ?marca=dell ?precio_min=500&precio_max=2000 ?disponible=true"""

    categoria = django_filters.CharFilter(field_name="categoria__slug", lookup_expr="iexact")
    marca = django_filters.CharFilter(lookup_expr="iexact")
    precio_min = django_filters.NumberFilter(field_name="precio", lookup_expr="gte")
    precio_max = django_filters.NumberFilter(field_name="precio", lookup_expr="lte")
    disponible = django_filters.BooleanFilter(method="filtrar_disponible")
    con_descuento = django_filters.BooleanFilter(method="filtrar_descuento")
    vendedor = django_filters.NumberFilter(field_name="vendedor_id")
    rating_min = django_filters.NumberFilter(field_name="rating_promedio", lookup_expr="gte")

    class Meta:
        model = Producto
        fields = ["categoria", "marca", "vendedor"]

    def filtrar_disponible(self, queryset, name, value):
        return queryset.filter(stock__gt=0) if value else queryset.filter(stock=0)

    def filtrar_descuento(self, queryset, name, value):
        return queryset.filter(descuento__gt=0) if value else queryset.filter(descuento=0)


class OrdenFilter(django_filters.FilterSet):
    fecha_desde = django_filters.DateFilter(field_name="fecha_creacion", lookup_expr="date__gte")
    fecha_hasta = django_filters.DateFilter(field_name="fecha_creacion", lookup_expr="date__lte")
    total_min = django_filters.NumberFilter(field_name="total", lookup_expr="gte")

    class Meta:
        model = Orden
        fields = ["estado", "metodo_pago"]


class ResenaFilter(django_filters.FilterSet):
    calificacion_min = django_filters.NumberFilter(field_name="calificacion", lookup_expr="gte")

    class Meta:
        model = Resena
        fields = ["producto", "calificacion"]
