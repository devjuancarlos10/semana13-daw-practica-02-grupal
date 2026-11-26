"""ViewSets del Caso 2 - TecnoMarket Perú."""

from django.db.models import Avg, Count, Q, Sum
from drf_spectacular.utils import (
    OpenApiExample,
    OpenApiParameter,
    OpenApiTypes,
    extend_schema,
    extend_schema_view,
    inline_serializer,
)
from rest_framework import mixins, permissions, serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.pagination import LimitOffsetPagination, PageNumberPagination
from rest_framework.response import Response

from core.permissions import IsOwnerOrReadOnly

from . import services
from .filters import OrdenFilter, ProductoFilter, ResenaFilter
from .models import Categoria, ItemCarrito, Orden, PerfilCliente, Producto, Resena, Vendedor
from .permissions import (
    EsCompradorVerificado,
    EsDuenoDelProductoOAdmin,
    EsPropietarioOAdmin,
    PuedeActualizarEstadoOrden,
    PuedeVender,
    WebhookSecretoValido,
    vendedor_de,
)
from .serializers import (
    AgregarItemSerializer,
    AplicarCuponSerializer,
    CarritoSerializer,
    CategoriaSerializer,
    CheckoutSerializer,
    CuentaSerializer,
    EliminarItemSerializer,
    OrdenEstadoSerializer,
    OrdenSerializer,
    ProductoDetailSerializer,
    ProductoListSerializer,
    RegistroClienteSerializer,
    ResenaSerializer,
    VendedorSerializer,
    WebhookLogisticaSerializer,
    WebhookPagoSerializer,
)
from .throttling import THROTTLES_TIENDA, CheckoutRateThrottle, SearchRateThrottle


# ---------------------------------------------------------------------------
# Paginación
# ---------------------------------------------------------------------------
class ProductoPagination(PageNumberPagination):
    page_size = 24
    page_size_query_param = "page_size"
    max_page_size = 96


class OrdenPagination(LimitOffsetPagination):
    default_limit = 50
    max_limit = 200


class TiendaViewSetMixin:
    throttle_classes = THROTTLES_TIENDA


# ---------------------------------------------------------------------------
# RF1 - Catálogo
# ---------------------------------------------------------------------------
@extend_schema_view(
    list=extend_schema(
        tags=["tienda"],
        summary="Catálogo público (24 por página)",
        parameters=[
            OpenApiParameter("categoria", OpenApiTypes.STR, description="slug: laptops, smartphones, ..."),
            OpenApiParameter("marca", OpenApiTypes.STR, description="dell, lenovo, samsung, ..."),
            OpenApiParameter("precio_min", OpenApiTypes.NUMBER),
            OpenApiParameter("precio_max", OpenApiTypes.NUMBER),
            OpenApiParameter("disponible", OpenApiTypes.BOOL),
            OpenApiParameter("search", OpenApiTypes.STR, description="Full-text: 'gaming laptop' (100 req/h)"),
            OpenApiParameter("ordering", OpenApiTypes.STR, description="-precio, rating_promedio, -fecha_creacion"),
        ],
    ),
    retrieve=extend_schema(tags=["tienda"], summary="Detalle con especificaciones completas"),
    create=extend_schema(tags=["tienda"], summary="Crear producto (admin o vendedor aprobado)"),
    update=extend_schema(tags=["tienda"], summary="Actualizar producto (dueño o admin)"),
    partial_update=extend_schema(tags=["tienda"], summary="Actualizar parcialmente (dueño o admin)"),
    destroy=extend_schema(tags=["tienda"], summary="Eliminar producto (solo admin)"),
)
class ProductoViewSet(TiendaViewSetMixin, viewsets.ModelViewSet):
    pagination_class = ProductoPagination
    filterset_class = ProductoFilter
    search_fields = ["nombre", "descripcion", "marca", "categoria__nombre", "sku"]
    ordering_fields = ["precio", "rating_promedio", "fecha_creacion", "nombre", "stock"]
    ordering = ["-fecha_creacion"]

    def get_throttles(self):
        throttles = super().get_throttles()
        if self.action == "list":
            throttles.append(SearchRateThrottle())
        return throttles

    def get_queryset(self):
        qs = (
            Producto.objects.select_related("categoria", "vendedor")
            .prefetch_related("imagenes")
            .annotate(rating_promedio=Avg("resenas__calificacion"))
        )
        if self.action == "retrieve":
            qs = qs.prefetch_related("resenas")
        user = self.request.user
        if user.is_authenticated and user.is_staff:
            return qs
        # Invitados y clientes ven solo productos activos; el vendedor ve también los suyos
        vendedor = vendedor_de(user)
        filtro = Q(activo=True) | Q(vendedor=vendedor) if vendedor else Q(activo=True)
        return qs.filter(filtro)

    def get_serializer_class(self):
        return ProductoListSerializer if self.action == "list" else ProductoDetailSerializer

    def get_permissions(self):
        if self.action in ("list", "retrieve", "resenas"):
            return [permissions.AllowAny()]
        if self.action == "create":
            return [permissions.IsAuthenticated(), PuedeVender()]
        if self.action == "destroy":
            return [permissions.IsAdminUser()]
        return [permissions.IsAuthenticated(), PuedeVender(), EsDuenoDelProductoOAdmin()]

    def perform_create(self, serializer):
        if self.request.user.is_staff:
            serializer.save()
        else:
            serializer.save(vendedor=self.request.user.vendedor)

    def perform_update(self, serializer):
        if not self.request.user.is_staff:
            serializer.validated_data.pop("vendedor", None)  # un vendedor no puede ceder su producto
        serializer.save()

    @extend_schema(tags=["tienda"], summary="Reseñas de un producto", responses=ResenaSerializer(many=True))
    @action(detail=True, methods=["get"], url_path="reseñas", url_name="resenas")
    def resenas(self, request, pk=None):
        producto = self.get_object()
        qs = producto.resenas.select_related("usuario", "producto").order_by("-fecha_creacion")
        pagina = self.paginate_queryset(qs)
        serializer = ResenaSerializer(pagina, many=True, context=self.get_serializer_context())
        return self.get_paginated_response(serializer.data)


@extend_schema_view(
    list=extend_schema(tags=["tienda"]),
    retrieve=extend_schema(tags=["tienda"]),
    create=extend_schema(tags=["tienda"]),
    update=extend_schema(tags=["tienda"]),
    partial_update=extend_schema(tags=["tienda"]),
    destroy=extend_schema(tags=["tienda"]),
)
class CategoriaViewSet(TiendaViewSetMixin, viewsets.ModelViewSet):
    queryset = Categoria.objects.annotate(total_productos=Count("productos"))
    serializer_class = CategoriaSerializer
    search_fields = ["nombre"]
    ordering_fields = ["nombre", "total_productos"]

    def get_permissions(self):
        if self.action in ("list", "retrieve"):
            return [permissions.AllowAny()]
        return [permissions.IsAdminUser()]


@extend_schema_view(
    list=extend_schema(tags=["tienda"], summary="Vendedores del marketplace"),
    retrieve=extend_schema(tags=["tienda"]),
    create=extend_schema(tags=["tienda"], summary="Registrarse como vendedor (queda pendiente de aprobación)"),
    aprobar=extend_schema(tags=["tienda"], summary="Aprobar vendedor (admin)"),
)
class VendedorViewSet(
    TiendaViewSetMixin, mixins.ListModelMixin, mixins.RetrieveModelMixin, mixins.CreateModelMixin, viewsets.GenericViewSet
):
    queryset = Vendedor.objects.annotate(total_productos=Count("productos"))
    serializer_class = VendedorSerializer
    filterset_fields = ["aprobado"]
    search_fields = ["nombre_tienda"]

    def get_permissions(self):
        if self.action in ("list", "retrieve"):
            return [permissions.AllowAny()]
        if self.action == "aprobar":
            return [permissions.IsAdminUser()]
        return [permissions.IsAuthenticated()]

    def perform_create(self, serializer):
        if hasattr(self.request.user, "vendedor"):
            raise ValidationError({"detail": "Ya tiene una tienda registrada."})
        serializer.save(user=self.request.user)

    @action(detail=True, methods=["post"])
    def aprobar(self, request, pk=None):
        vendedor = self.get_object()
        vendedor.aprobado = True
        vendedor.save(update_fields=["aprobado"])
        return Response(self.get_serializer(vendedor).data)


# ---------------------------------------------------------------------------
# RF2 - Carrito
# ---------------------------------------------------------------------------
CARRITO_EJEMPLO = OpenApiExample(
    "Carrito",
    response_only=True,
    value={
        "id": 3, "usuario": "cliente1",
        "items": [{"id": 9, "producto": {"id": 7, "url": "http://127.0.0.1:8000/api/productos/7/", "sku": "LAP-DELL-G15",
                                          "nombre": "Laptop Dell G15", "precio_con_descuento": "4409.10", "stock": 15},
                   "cantidad": 1, "subtotal": "4409.10"}],
        "cupon": "CYBERWOW", "cantidad_items": 1, "subtotal": "4409.10", "impuestos": "793.64",
        "total": "5202.74", "descuento_cupon": "780.41", "total_con_descuento": "4422.33",
    },
)


@extend_schema_view(list=extend_schema(tags=["tienda"], summary="Ver carrito actual", responses=CarritoSerializer, examples=[CARRITO_EJEMPLO]))
class CarritoViewSet(TiendaViewSetMixin, viewsets.GenericViewSet):
    """Carrito del usuario autenticado. Solo el propietario puede verlo/modificarlo."""

    permission_classes = [permissions.IsAuthenticated]
    serializer_class = CarritoSerializer
    pagination_class = None
    filter_backends = []

    def get_carrito(self):
        return services.carrito_activo(self.request.user)

    def respuesta(self, carrito, codigo=status.HTTP_200_OK):
        carrito.refresh_from_db()
        return Response(CarritoSerializer(carrito, context=self.get_serializer_context()).data, status=codigo)

    def list(self, request):
        return self.respuesta(self.get_carrito())

    @extend_schema(
        tags=["tienda"], request=AgregarItemSerializer, responses=CarritoSerializer,
        examples=[OpenApiExample("Agregar", value={"producto": 7, "cantidad": 2}, request_only=True)],
    )
    @action(detail=False, methods=["post"])
    def agregar(self, request):
        carrito = self.get_carrito()
        datos = AgregarItemSerializer(data=request.data, context={"carrito": carrito})
        datos.is_valid(raise_exception=True)
        item, creado = ItemCarrito.objects.get_or_create(
            carrito=carrito, producto=datos.validated_data["producto"], defaults={"cantidad": datos.validated_data["cantidad"]}
        )
        if not creado:
            item.cantidad += datos.validated_data["cantidad"]
            item.save(update_fields=["cantidad"])
        return self.respuesta(carrito, status.HTTP_201_CREATED if creado else status.HTTP_200_OK)

    @extend_schema(tags=["tienda"], request=EliminarItemSerializer, responses=CarritoSerializer)
    @action(detail=False, methods=["post"])
    def eliminar(self, request):
        carrito = self.get_carrito()
        datos = EliminarItemSerializer(data=request.data)
        datos.is_valid(raise_exception=True)
        borrados, _ = carrito.items.filter(producto=datos.validated_data["producto"]).delete()
        if not borrados:
            return Response({"detail": "El producto no está en el carrito."}, status=status.HTTP_404_NOT_FOUND)
        return self.respuesta(carrito)

    @extend_schema(tags=["tienda"], request=AgregarItemSerializer, responses=CarritoSerializer)
    @action(detail=False, methods=["post"])
    def actualizar(self, request):
        carrito = self.get_carrito()
        datos = AgregarItemSerializer(data=request.data, context={"carrito": carrito, "reemplazar": True})
        datos.is_valid(raise_exception=True)
        actualizados = carrito.items.filter(producto=datos.validated_data["producto"]).update(
            cantidad=datos.validated_data["cantidad"]
        )
        if not actualizados:
            return Response({"detail": "El producto no está en el carrito."}, status=status.HTTP_404_NOT_FOUND)
        return self.respuesta(carrito)

    @extend_schema(tags=["tienda"], request=None, responses=CarritoSerializer)
    @action(detail=False, methods=["post"])
    def vaciar(self, request):
        carrito = self.get_carrito()
        carrito.items.all().delete()
        carrito.cupon = None
        carrito.save(update_fields=["cupon"])
        return self.respuesta(carrito)

    @extend_schema(
        tags=["tienda"], request=AplicarCuponSerializer, responses=CarritoSerializer,
        examples=[OpenApiExample("Cupón", value={"codigo": "CYBERWOW"}, request_only=True)],
    )
    @action(detail=False, methods=["post"], url_path="aplicar-cupon")
    def aplicar_cupon(self, request):
        carrito = self.get_carrito()
        datos = AplicarCuponSerializer(data=request.data)
        datos.is_valid(raise_exception=True)
        carrito.cupon = datos.validated_data["codigo"]
        carrito.save(update_fields=["cupon"])
        return self.respuesta(carrito)

    @extend_schema(
        tags=["tienda"], request=CheckoutSerializer, responses={201: OrdenSerializer},
        summary="Convertir carrito en orden (10 req/hora)",
        examples=[OpenApiExample(
            "Checkout", request_only=True,
            value={"direccion_envio": "Av. Huancavelica 1234, El Tambo, Huancayo", "metodo_pago": "culqi"},
        )],
    )
    @action(detail=False, methods=["post"], throttle_classes=THROTTLES_TIENDA + [CheckoutRateThrottle])
    def checkout(self, request):
        datos = CheckoutSerializer(data=request.data)
        datos.is_valid(raise_exception=True)
        orden = services.checkout(request.user, **datos.validated_data)
        return Response(OrdenSerializer(orden, context=self.get_serializer_context()).data, status=status.HTTP_201_CREATED)


# ---------------------------------------------------------------------------
# RF3 - Órdenes
# ---------------------------------------------------------------------------
@extend_schema_view(
    list=extend_schema(tags=["tienda"], summary="Órdenes visibles (limit/offset, 50 por página)"),
    retrieve=extend_schema(tags=["tienda"], summary="Detalle (propietario, vendedor o admin)"),
    create=extend_schema(
        tags=["tienda"], summary="Crear orden desde el carrito (10 req/hora)", request=CheckoutSerializer,
        responses={201: OrdenSerializer},
    ),
    partial_update=extend_schema(
        tags=["tienda"], summary="Actualizar estado (admin o vendedor del producto)", request=OrdenEstadoSerializer,
        responses=OrdenSerializer,
        examples=[OpenApiExample("Enviar", value={"estado": "enviada"}, request_only=True)],
    ),
)
class OrdenViewSet(
    TiendaViewSetMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.CreateModelMixin,
    mixins.UpdateModelMixin,
    viewsets.GenericViewSet,
):
    serializer_class = OrdenSerializer
    pagination_class = OrdenPagination
    filterset_class = OrdenFilter
    search_fields = ["numero_seguimiento", "items__nombre_producto"]
    ordering_fields = ["fecha_creacion", "total", "estado"]
    ordering = ["-fecha_creacion"]
    http_method_names = ["get", "post", "patch", "head", "options"]

    def get_queryset(self):
        qs = Orden.objects.select_related("usuario").prefetch_related("items")
        if getattr(self, "swagger_fake_view", False):
            return qs.none()
        user = self.request.user
        if user.is_staff:
            return qs
        if self.action == "mis_ordenes":
            return qs.filter(usuario=user)
        vendedor = vendedor_de(user)
        if vendedor:
            return qs.filter(Q(usuario=user) | Q(items__vendedor=vendedor)).distinct()
        return qs.filter(usuario=user)

    def get_permissions(self):
        if self.action == "partial_update":
            return [permissions.IsAuthenticated(), PuedeActualizarEstadoOrden()]
        if self.action == "cancelar":
            return [permissions.IsAuthenticated(), EsPropietarioOAdmin()]
        if self.action == "resumen":
            return [permissions.IsAdminUser()]
        return [permissions.IsAuthenticated(), IsOwnerOrReadOnly()]

    def get_throttles(self):
        throttles = super().get_throttles()
        if self.action == "create":
            throttles.append(CheckoutRateThrottle())
        return throttles

    def create(self, request, *args, **kwargs):
        datos = CheckoutSerializer(data=request.data)
        datos.is_valid(raise_exception=True)
        orden = services.checkout(request.user, **datos.validated_data)
        return Response(self.get_serializer(orden).data, status=status.HTTP_201_CREATED)

    def partial_update(self, request, *args, **kwargs):
        orden = self.get_object()
        datos = OrdenEstadoSerializer(data=request.data)
        datos.is_valid(raise_exception=True)
        nuevo = datos.validated_data["estado"]
        if nuevo == Orden.Estado.CANCELADA and not request.user.is_staff and orden.usuario != request.user:
            # un vendedor no cancela órdenes ajenas pagadas: debe hacerlo el admin
            raise ValidationError({"estado": "Solo el cliente o un administrador puede cancelar."})
        services.cambiar_estado(orden, nuevo)
        return Response(self.get_serializer(orden).data)

    def update(self, request, *args, **kwargs):
        if not kwargs.get("partial"):
            return Response({"detail": "Use PATCH para actualizar el estado."}, status=status.HTTP_405_METHOD_NOT_ALLOWED)
        return super().update(request, *args, **kwargs)

    @extend_schema(tags=["tienda"], request=None, responses=OrdenSerializer, summary="Cancelar orden (solo si está pendiente)")
    @action(detail=True, methods=["post"])
    def cancelar(self, request, pk=None):
        orden = self.get_object()
        if orden.estado != Orden.Estado.PENDIENTE:
            return Response(
                {"detail": f"Solo se pueden cancelar órdenes pendientes (estado actual: {orden.estado})."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        services.cambiar_estado(orden, Orden.Estado.CANCELADA)
        return Response(self.get_serializer(orden).data)

    @extend_schema(tags=["tienda"], summary="Órdenes del usuario autenticado")
    @action(detail=False, methods=["get"], url_path="mis-ordenes")
    def mis_ordenes(self, request):
        qs = self.filter_queryset(self.get_queryset())
        pagina = self.paginate_queryset(qs)
        return self.get_paginated_response(self.get_serializer(pagina, many=True).data)

    @extend_schema(
        tags=["tienda"], summary="Reporte de ventas (admin)",
        responses=inline_serializer("ResumenVentas", {
            "por_estado": serializers.DictField(),
            "ingresos_confirmados": serializers.DecimalField(max_digits=14, decimal_places=2),
            "top_productos": serializers.ListField(),
        }),
    )
    @action(detail=False, methods=["get"])
    def resumen(self, request):
        por_estado = dict(Orden.objects.values_list("estado").annotate(n=Count("id")).order_by())
        ingresos = Orden.objects.filter(
            estado__in=[Orden.Estado.PAGADA, Orden.Estado.ENVIADA, Orden.Estado.ENTREGADA]
        ).aggregate(total=Sum("total"))["total"] or 0
        top = list(
            Producto.objects.annotate(vendidos=Sum("items_vendidos__cantidad"))
            .filter(vendidos__gt=0).order_by("-vendidos").values("id", "nombre", "vendidos")[:5]
        )
        return Response({"por_estado": por_estado, "ingresos_confirmados": ingresos, "top_productos": top})


# ---------------------------------------------------------------------------
# RF4 - Reseñas
# ---------------------------------------------------------------------------
@extend_schema_view(
    list=extend_schema(tags=["tienda"], summary="Listar reseñas (público)"),
    retrieve=extend_schema(tags=["tienda"]),
    create=extend_schema(tags=["tienda"], summary="Crear reseña (comprador verificado)"),
    partial_update=extend_schema(tags=["tienda"], summary="Editar reseña propia"),
    destroy=extend_schema(tags=["tienda"], summary="Eliminar reseña (propia o admin)"),
)
class ResenaViewSet(TiendaViewSetMixin, viewsets.ModelViewSet):
    queryset = Resena.objects.select_related("usuario", "producto")
    serializer_class = ResenaSerializer
    filterset_class = ResenaFilter
    ordering_fields = ["fecha_creacion", "calificacion"]
    ordering = ["-fecha_creacion"]
    http_method_names = ["get", "post", "patch", "delete", "head", "options"]

    def get_permissions(self):
        if self.action in ("list", "retrieve"):
            return [permissions.AllowAny()]
        if self.action == "create":
            return [permissions.IsAuthenticated(), EsCompradorVerificado()]
        return [permissions.IsAuthenticated(), IsOwnerOrReadOnly()]

    def perform_create(self, serializer):
        serializer.save(usuario=self.request.user)

    def perform_update(self, serializer):
        serializer.validated_data.pop("producto", None)  # la reseña no cambia de producto
        serializer.save()


# ---------------------------------------------------------------------------
# Cuenta del cliente (perfil + registro)
# ---------------------------------------------------------------------------
class CuentaViewSet(TiendaViewSetMixin, viewsets.GenericViewSet):
    serializer_class = CuentaSerializer
    pagination_class = None
    filter_backends = []

    def get_permissions(self):
        if self.action == "registro":
            return [permissions.AllowAny()]
        return [permissions.IsAuthenticated()]

    def perfil_usuario(self):
        PerfilCliente.objects.get_or_create(user=self.request.user)
        self.request.user.refresh_from_db()
        return self.request.user

    @extend_schema(tags=["tienda"], summary="Perfil del cliente autenticado", responses=CuentaSerializer)
    def list(self, request):
        return Response(CuentaSerializer(self.perfil_usuario()).data)

    @extend_schema(tags=["tienda"], summary="Actualizar perfil", request=CuentaSerializer, responses=CuentaSerializer)
    @action(detail=False, methods=["patch"])
    def actualizar(self, request):
        serializer = CuentaSerializer(self.perfil_usuario(), data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(CuentaSerializer(self.perfil_usuario()).data)

    @extend_schema(
        tags=["tienda"], summary="Registro de cliente", request=RegistroClienteSerializer,
        responses={201: RegistroClienteSerializer}, auth=[],
    )
    @action(detail=False, methods=["post"])
    def registro(self, request):
        serializer = RegistroClienteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_201_CREATED)


# ---------------------------------------------------------------------------
# Sistemas externos: webhooks de pagos y logística
# ---------------------------------------------------------------------------
class WebhookViewSet(viewsets.GenericViewSet):
    """Endpoints para Culqi/MercadoPago/Niubiz y Olva/Shalom.

    No usan sesión ni token de usuario (sin CSRF): se autentican con el
    header ``X-Webhook-Token`` (secreto compartido, comparación constante).
    """

    authentication_classes = []
    permission_classes = [WebhookSecretoValido]
    pagination_class = None
    filter_backends = []
    serializer_class = WebhookPagoSerializer

    @extend_schema(
        tags=["tienda"], summary="Webhook de pasarela de pago", request=WebhookPagoSerializer, responses=OrdenSerializer,
        parameters=[OpenApiParameter("X-Webhook-Token", OpenApiTypes.STR, OpenApiParameter.HEADER, required=True)],
        examples=[OpenApiExample("Pago aprobado", request_only=True,
                                 value={"orden": 51, "estado": "aprobado", "referencia": "chr_live_8f2a", "monto": "5202.74"})],
    )
    @action(detail=False, methods=["post"])
    def pagos(self, request):
        datos = WebhookPagoSerializer(data=request.data)
        datos.is_valid(raise_exception=True)
        orden = datos.validated_data["orden"]
        if datos.validated_data["monto"] != orden.total:
            raise ValidationError({"monto": "El monto no coincide con el total de la orden."})
        nuevo = Orden.Estado.PAGADA if datos.validated_data["estado"] == "aprobado" else Orden.Estado.CANCELADA
        services.cambiar_estado(orden, nuevo)
        return Response(OrdenSerializer(orden, context=self.get_serializer_context()).data)

    @extend_schema(
        tags=["tienda"], summary="Webhook de courier (Olva / Shalom)", request=WebhookLogisticaSerializer,
        responses=OrdenSerializer,
        parameters=[OpenApiParameter("X-Webhook-Token", OpenApiTypes.STR, OpenApiParameter.HEADER, required=True)],
    )
    @action(detail=False, methods=["post"])
    def logistica(self, request):
        datos = WebhookLogisticaSerializer(data=request.data)
        datos.is_valid(raise_exception=True)
        orden = Orden.objects.filter(numero_seguimiento=datos.validated_data["numero_seguimiento"]).first()
        if orden is None:
            return Response({"detail": "Número de seguimiento desconocido."}, status=status.HTTP_404_NOT_FOUND)
        if datos.validated_data["estado"] == "entregado":
            services.cambiar_estado(orden, Orden.Estado.ENTREGADA)
        return Response(OrdenSerializer(orden, context=self.get_serializer_context()).data)
