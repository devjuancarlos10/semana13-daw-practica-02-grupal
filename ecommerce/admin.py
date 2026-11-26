from django.contrib import admin

from .models import (
    Carrito,
    Categoria,
    Cupon,
    ImagenProducto,
    ItemCarrito,
    ItemOrden,
    Orden,
    PerfilCliente,
    Producto,
    Resena,
    Vendedor,
)


class ImagenInline(admin.TabularInline):
    model = ImagenProducto
    extra = 0


@admin.register(Producto)
class ProductoAdmin(admin.ModelAdmin):
    list_display = ["sku", "nombre", "marca", "categoria", "precio", "descuento", "stock", "activo"]
    list_filter = ["categoria", "marca", "activo"]
    search_fields = ["sku", "nombre", "marca"]
    inlines = [ImagenInline]
    list_select_related = ["categoria"]


class ItemOrdenInline(admin.TabularInline):
    model = ItemOrden
    extra = 0
    readonly_fields = ["sku", "nombre_producto", "precio_unitario", "cantidad"]


@admin.register(Orden)
class OrdenAdmin(admin.ModelAdmin):
    list_display = ["id", "usuario", "estado", "metodo_pago", "total", "numero_seguimiento", "fecha_creacion"]
    list_filter = ["estado", "metodo_pago"]
    inlines = [ItemOrdenInline]


class ItemCarritoInline(admin.TabularInline):
    model = ItemCarrito
    extra = 0


@admin.register(Carrito)
class CarritoAdmin(admin.ModelAdmin):
    list_display = ["id", "usuario", "activo", "cupon"]
    inlines = [ItemCarritoInline]


@admin.register(Resena)
class ResenaAdmin(admin.ModelAdmin):
    list_display = ["producto", "usuario", "calificacion", "fecha_creacion"]
    list_filter = ["calificacion"]


admin.site.register([Categoria, Vendedor, PerfilCliente, Cupon])
