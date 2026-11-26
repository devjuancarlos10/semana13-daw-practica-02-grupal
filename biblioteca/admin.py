from django.contrib import admin

from .models import Autor, Libro, PerfilUsuario, Prestamo, Reserva, SolicitudAdquisicion


@admin.register(Autor)
class AutorAdmin(admin.ModelAdmin):
    list_display = ["nombre", "nacionalidad"]
    search_fields = ["nombre"]


@admin.register(Libro)
class LibroAdmin(admin.ModelAdmin):
    list_display = ["titulo", "isbn", "autor", "categoria", "anio", "stock", "estante", "piso"]
    list_filter = ["categoria", "piso"]
    search_fields = ["titulo", "isbn", "autor__nombre"]
    list_select_related = ["autor"]


@admin.register(PerfilUsuario)
class PerfilUsuarioAdmin(admin.ModelAdmin):
    list_display = ["user", "tipo", "codigo", "carrera", "carnet_activo"]
    list_filter = ["tipo", "carnet_activo"]


@admin.register(Prestamo)
class PrestamoAdmin(admin.ModelAdmin):
    list_display = ["id", "libro", "usuario", "fecha_prestamo", "fecha_devolucion", "estado"]
    list_filter = ["estado"]
    list_select_related = ["libro", "usuario"]


admin.site.register(Reserva)
admin.site.register(SolicitudAdquisicion)
