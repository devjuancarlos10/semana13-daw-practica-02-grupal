"""ViewSets del Caso 1 - Biblioteca Central UNCP."""

from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import Count, F, Prefetch, Q
from django.utils import timezone
from drf_spectacular.utils import OpenApiParameter, OpenApiTypes, extend_schema, extend_schema_view
from rest_framework import mixins, permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.pagination import LimitOffsetPagination
from rest_framework.response import Response

from core.permissions import IsOwnerOrReadOnly

from .filters import LibroFilter, PrestamoFilter
from .models import Autor, Libro, Prestamo, Reserva, SolicitudAdquisicion
from .permissions import (
    EsAdministrador,
    EsDocenteInvestigador,
    EsPersonalBiblioteca,
    EsPropietarioOAdmin,
    PuedeCrearPrestamo,
    es_admin,
    es_personal,
)
from .serializers import (
    AutorSerializer,
    LibroSerializer,
    PerfilActualizarSerializer,
    PrestamoSerializer,
    ReservaSerializer,
    SolicitudAdquisicionSerializer,
    UsuarioCrearSerializer,
    UsuarioPrivadoSerializer,
    UsuarioPublicoSerializer,
)
from .throttling import THROTTLES_BIBLIOTECA

User = get_user_model()


class BibliotecaLimitOffsetPagination(LimitOffsetPagination):
    """Paginación limit/offset para endpoints específicos (vencidos, usuarios)."""

    default_limit = 20
    max_limit = 100


class BibliotecaViewSetMixin:
    throttle_classes = THROTTLES_BIBLIOTECA


# ---------------------------------------------------------------------------
# RF1 - Libros y autores
# ---------------------------------------------------------------------------
@extend_schema_view(
    list=extend_schema(
        tags=["biblioteca"],
        summary="Listar catálogo (público, 20 por página)",
        parameters=[
            OpenApiParameter("categoria", OpenApiTypes.STR, description="ingenieria, ciencias, medicina, ..."),
            OpenApiParameter("año__gte", OpenApiTypes.INT, description="Año de publicación mínimo"),
            OpenApiParameter("disponible", OpenApiTypes.BOOL, description="true = stock > 0"),
            OpenApiParameter("search", OpenApiTypes.STR, description="Busca en título, autor, ISBN"),
            OpenApiParameter("ordering", OpenApiTypes.STR, description="-año, título, stock"),
        ],
    ),
    retrieve=extend_schema(tags=["biblioteca"], summary="Detalle de libro"),
    create=extend_schema(tags=["biblioteca"], summary="Crear libro (admin/bibliotecario)"),
    update=extend_schema(tags=["biblioteca"], summary="Actualizar libro (admin/bibliotecario)"),
    partial_update=extend_schema(tags=["biblioteca"], summary="Actualizar parcialmente (admin/bibliotecario)"),
    destroy=extend_schema(tags=["biblioteca"], summary="Eliminar libro (solo admin)"),
)
class LibroViewSet(BibliotecaViewSetMixin, viewsets.ModelViewSet):
    """CRUD de libros. Lectura pública (campus virtual, apps móviles)."""

    queryset = Libro.objects.select_related("autor")
    serializer_class = LibroSerializer
    filterset_class = LibroFilter
    search_fields = ["titulo", "autor__nombre", "isbn", "editorial"]
    ordering_fields = ["anio", "titulo", "stock", "fecha_registro"]
    ordering_aliases = {"año": "anio", "título": "titulo"}
    ordering = ["titulo"]

    def get_permissions(self):
        if self.action in ("list", "retrieve"):
            return [permissions.AllowAny()]
        if self.action == "destroy":
            return [EsAdministrador()]
        return [EsPersonalBiblioteca()]

    def perform_destroy(self, instance):
        if instance.prestamos.activos().exists():
            raise ValidationError({"detail": "No se puede eliminar un libro con préstamos activos."})
        instance.delete()


@extend_schema_view(
    list=extend_schema(tags=["biblioteca"]),
    retrieve=extend_schema(tags=["biblioteca"]),
    create=extend_schema(tags=["biblioteca"]),
    update=extend_schema(tags=["biblioteca"]),
    partial_update=extend_schema(tags=["biblioteca"]),
    destroy=extend_schema(tags=["biblioteca"]),
)
class AutorViewSet(BibliotecaViewSetMixin, viewsets.ModelViewSet):
    queryset = Autor.objects.annotate(total_libros=Count("libros"))
    serializer_class = AutorSerializer
    search_fields = ["nombre", "nacionalidad"]
    ordering_fields = ["nombre", "total_libros"]
    filterset_fields = ["nacionalidad"]

    def get_permissions(self):
        if self.action in ("list", "retrieve"):
            return [permissions.AllowAny()]
        if self.action == "destroy":
            return [EsAdministrador()]
        return [EsPersonalBiblioteca()]


# ---------------------------------------------------------------------------
# RF2 - Préstamos
# ---------------------------------------------------------------------------
@extend_schema_view(
    list=extend_schema(tags=["biblioteca"], summary="Listar préstamos (propios o todos si es personal)"),
    retrieve=extend_schema(tags=["biblioteca"], summary="Detalle de préstamo (propietario o personal)"),
    create=extend_schema(tags=["biblioteca"], summary="Registrar préstamo (bibliotecario/admin)"),
    update=extend_schema(tags=["biblioteca"], summary="Actualizar préstamo (bibliotecario/admin)"),
    partial_update=extend_schema(tags=["biblioteca"], summary="Ampliar fecha de devolución (bibliotecario/admin)"),
    destroy=extend_schema(tags=["biblioteca"], summary="Eliminar préstamo (solo admin)"),
)
class PrestamoViewSet(BibliotecaViewSetMixin, viewsets.ModelViewSet):
    serializer_class = PrestamoSerializer
    filterset_class = PrestamoFilter
    search_fields = ["libro__titulo", "usuario__username", "usuario__last_name"]
    ordering_fields = ["fecha_prestamo", "fecha_devolucion", "estado"]
    ordering = ["-fecha_prestamo", "-id"]

    def get_queryset(self):
        # Mantiene el estado "vencido" al día antes de cualquier consulta
        if getattr(self, "swagger_fake_view", False):  # generación del esquema OpenAPI
            return Prestamo.objects.none()
        Prestamo.actualizar_vencidos()
        qs = Prestamo.objects.select_related("usuario", "libro")
        user = self.request.user
        if es_personal(user):
            return qs
        return qs.filter(usuario=user)

    def get_permissions(self):
        if self.action in ("create", "update", "partial_update", "devolver", "vencidos"):
            clases = [EsPersonalBiblioteca]
            if self.action == "create":
                clases.append(PuedeCrearPrestamo)
        elif self.action == "destroy":
            clases = [EsAdministrador]
        else:
            clases = [permissions.IsAuthenticated, EsPropietarioOAdmin]
        return [c() for c in clases]

    def perform_create(self, serializer):
        serializer.save(registrado_por=self.request.user)

    def perform_destroy(self, instance):
        with transaction.atomic():
            if instance.estado != Prestamo.Estado.DEVUELTO:
                Libro.objects.filter(pk=instance.libro_id).update(stock=F("stock") + 1)
            instance.delete()

    @extend_schema(tags=["biblioteca"], request=None, responses=PrestamoSerializer, summary="Marcar préstamo como devuelto")
    @action(detail=True, methods=["post"])
    def devolver(self, request, pk=None):
        prestamo = self.get_object()
        if prestamo.estado == Prestamo.Estado.DEVUELTO:
            return Response({"detail": "El préstamo ya fue devuelto."}, status=status.HTTP_400_BAD_REQUEST)
        with transaction.atomic():
            prestamo.estado = Prestamo.Estado.DEVUELTO
            prestamo.fecha_entrega = timezone.localdate()
            prestamo.save(update_fields=["estado", "fecha_entrega"])
            Libro.objects.filter(pk=prestamo.libro_id).update(stock=F("stock") + 1)
        return Response(self.get_serializer(prestamo).data)

    @extend_schema(tags=["biblioteca"], summary="Listar préstamos vencidos (paginación limit/offset)")
    @action(detail=False, methods=["get"], pagination_class=BibliotecaLimitOffsetPagination)
    def vencidos(self, request):
        qs = self.filter_queryset(self.get_queryset().vencidos()).order_by("fecha_devolucion")
        pagina = self.paginate_queryset(qs)
        serializer = self.get_serializer(pagina, many=True)
        return self.get_paginated_response(serializer.data)


# ---------------------------------------------------------------------------
# RF3 - Usuarios
# ---------------------------------------------------------------------------
@extend_schema_view(
    list=extend_schema(tags=["biblioteca"], summary="Listar usuarios (solo admin)", responses=UsuarioPrivadoSerializer(many=True)),
    retrieve=extend_schema(
        tags=["biblioteca"],
        summary="Detalle de usuario: privado si es propio/admin, público en otro caso",
        responses=UsuarioPrivadoSerializer,
    ),
    create=extend_schema(tags=["biblioteca"], summary="Crear usuario (solo admin)"),
    partial_update=extend_schema(tags=["biblioteca"], summary="Actualizar datos de contacto (propietario o admin)"),
    destroy=extend_schema(tags=["biblioteca"], summary="Desactivar usuario (solo admin)"),
)
class UsuarioViewSet(
    BibliotecaViewSetMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.CreateModelMixin,
    mixins.UpdateModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    http_method_names = ["get", "post", "patch", "delete", "head", "options"]
    pagination_class = BibliotecaLimitOffsetPagination
    search_fields = ["username", "first_name", "last_name", "perfil_biblioteca__codigo"]
    ordering_fields = ["username", "last_name", "prestamos_activos"]
    filterset_fields = ["perfil_biblioteca__tipo", "perfil_biblioteca__carnet_activo"]

    def get_queryset(self):
        return (
            User.objects.select_related("perfil_biblioteca")
            .annotate(
                prestamos_activos=Count(
                    "prestamos", filter=Q(prestamos__estado__in=[Prestamo.Estado.ACTIVO, Prestamo.Estado.VENCIDO])
                )
            )
            .prefetch_related(Prefetch("prestamos", queryset=Prestamo.objects.select_related("libro")))
            .order_by("username")
        )

    def get_permissions(self):
        if self.action in ("list", "create", "destroy"):
            return [EsAdministrador()]
        if self.action == "perfil":
            return [permissions.IsAuthenticated()]
        if self.action == "partial_update":
            return [permissions.IsAuthenticated(), IsOwnerOrReadOnly()]
        return [permissions.AllowAny()]

    def get_serializer_class(self):
        if self.action == "create":
            return UsuarioCrearSerializer
        if self.action in ("partial_update",) or (self.action == "perfil" and self.request.method == "PATCH"):
            return PerfilActualizarSerializer
        if self.action == "retrieve":
            objeto = getattr(self, "_objeto", None)
            user = self.request.user
            if objeto is not None and (es_admin(user) or objeto == user):
                return UsuarioPrivadoSerializer
            return UsuarioPublicoSerializer
        return UsuarioPrivadoSerializer

    def retrieve(self, request, *args, **kwargs):
        self._objeto = self.get_object()
        return Response(self.get_serializer(self._objeto).data)

    def partial_update(self, request, *args, **kwargs):
        usuario = self.get_object()
        serializer = PerfilActualizarSerializer(usuario, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(UsuarioPrivadoSerializer(self.get_queryset().get(pk=usuario.pk), context=self.get_serializer_context()).data)

    def perform_destroy(self, instance):
        # No se borra el historial: se desactiva la cuenta y el carnet
        instance.is_active = False
        instance.save(update_fields=["is_active"])
        perfil = getattr(instance, "perfil_biblioteca", None)
        if perfil:
            perfil.carnet_activo = False
            perfil.save(update_fields=["carnet_activo"])

    @extend_schema(
        tags=["biblioteca"],
        summary="Perfil del usuario autenticado (GET) o actualización de contacto (PATCH)",
        methods=["GET"],
        responses=UsuarioPrivadoSerializer,
    )
    @extend_schema(tags=["biblioteca"], methods=["PATCH"], request=PerfilActualizarSerializer, responses=UsuarioPrivadoSerializer)
    @action(detail=False, methods=["get", "patch"])
    def perfil(self, request):
        if request.method == "PATCH":
            serializer = PerfilActualizarSerializer(request.user, data=request.data, partial=True)
            serializer.is_valid(raise_exception=True)
            serializer.save()
        usuario = self.get_queryset().get(pk=request.user.pk)
        return Response(UsuarioPrivadoSerializer(usuario, context=self.get_serializer_context()).data)


# ---------------------------------------------------------------------------
# Docentes/Investigadores: reservas y solicitudes de adquisición
# ---------------------------------------------------------------------------
class PropiosOTodosMixin:
    """El personal ve todos los registros; cada docente solo los suyos."""

    def get_queryset(self):
        qs = super().get_queryset()
        if getattr(self, "swagger_fake_view", False) or es_personal(self.request.user):
            return qs
        return qs.filter(usuario=self.request.user)


@extend_schema_view(
    list=extend_schema(tags=["biblioteca"]),
    retrieve=extend_schema(tags=["biblioteca"]),
    create=extend_schema(tags=["biblioteca"], summary="Reservar libro (docente/investigador)"),
    destroy=extend_schema(tags=["biblioteca"], summary="Cancelar reserva"),
)
class ReservaViewSet(
    BibliotecaViewSetMixin,
    PropiosOTodosMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.CreateModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    queryset = Reserva.objects.select_related("libro", "usuario")
    serializer_class = ReservaSerializer
    filterset_fields = ["estado", "libro"]

    def get_permissions(self):
        if self.action == "create":
            return [EsDocenteInvestigador()]
        return [permissions.IsAuthenticated(), EsPropietarioOAdmin()]

    def perform_destroy(self, instance):
        instance.estado = Reserva.Estado.CANCELADA
        instance.save(update_fields=["estado"])


@extend_schema_view(
    list=extend_schema(tags=["biblioteca"]),
    retrieve=extend_schema(tags=["biblioteca"]),
    create=extend_schema(tags=["biblioteca"], summary="Solicitar adquisición (docente/investigador)"),
    partial_update=extend_schema(tags=["biblioteca"], summary="Aprobar/rechazar (admin)"),
)
class SolicitudAdquisicionViewSet(
    BibliotecaViewSetMixin,
    PropiosOTodosMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.CreateModelMixin,
    mixins.UpdateModelMixin,
    viewsets.GenericViewSet,
):
    queryset = SolicitudAdquisicion.objects.select_related("usuario")
    serializer_class = SolicitudAdquisicionSerializer
    http_method_names = ["get", "post", "patch", "head", "options"]
    filterset_fields = ["estado"]
    search_fields = ["titulo", "autor"]

    def get_permissions(self):
        if self.action == "create":
            return [EsDocenteInvestigador()]
        if self.action == "partial_update":
            return [EsAdministrador()]
        return [permissions.IsAuthenticated(), EsPropietarioOAdmin()]

    def perform_update(self, serializer):
        estado = self.request.data.get("estado")
        if estado not in SolicitudAdquisicion.Estado.values:
            raise ValidationError({"estado": f"Valores permitidos: {SolicitudAdquisicion.Estado.values}"})
        serializer.save(estado=estado)
