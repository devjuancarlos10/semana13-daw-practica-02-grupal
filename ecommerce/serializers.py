"""Serializadores del Caso 2 - TecnoMarket Perú."""

from decimal import Decimal

from django.contrib.auth import get_user_model
from django.db import transaction
from drf_spectacular.utils import OpenApiExample, extend_schema_field, extend_schema_serializer
from rest_framework import serializers

from .models import (
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
    compro_producto,
)

User = get_user_model()


# ---------------------------------------------------------------------------
# Catálogo
# ---------------------------------------------------------------------------
class CategoriaSerializer(serializers.ModelSerializer):
    url = serializers.HyperlinkedIdentityField(view_name="categoria-detail")
    total_productos = serializers.IntegerField(read_only=True, required=False)

    class Meta:
        model = Categoria
        fields = ["id", "url", "nombre", "slug", "descripcion", "imagen", "total_productos"]


class VendedorSerializer(serializers.ModelSerializer):
    url = serializers.HyperlinkedIdentityField(view_name="vendedor-detail")
    total_productos = serializers.IntegerField(read_only=True, required=False)

    class Meta:
        model = Vendedor
        fields = ["id", "url", "nombre_tienda", "ruc", "aprobado", "fecha_registro", "total_productos"]
        read_only_fields = ["aprobado", "fecha_registro"]


class ImagenProductoSerializer(serializers.ModelSerializer):
    class Meta:
        model = ImagenProducto
        fields = ["url", "alt", "orden"]


class ProductoListSerializer(serializers.ModelSerializer):
    """Vista de listado: ligera para cumplir < 150 ms en catálogo."""

    url = serializers.HyperlinkedIdentityField(view_name="producto-detail")
    categoria = CategoriaSerializer(read_only=True)
    vendedor = serializers.HyperlinkedRelatedField(view_name="vendedor-detail", read_only=True)
    precio_con_descuento = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    rating_promedio = serializers.SerializerMethodField()
    disponible = serializers.SerializerMethodField()
    imagen_principal = serializers.SerializerMethodField()

    class Meta:
        model = Producto
        fields = [
            "id", "url", "sku", "nombre", "marca", "categoria", "vendedor", "precio", "descuento",
            "precio_con_descuento", "rating_promedio", "disponible", "imagen_principal",
        ]

    @extend_schema_field(serializers.FloatField(allow_null=True))
    def get_rating_promedio(self, obj):
        valor = getattr(obj, "rating_promedio", None)
        if valor is None and not hasattr(obj, "rating_promedio"):
            valores = [r.calificacion for r in obj.resenas.all()]
            valor = sum(valores) / len(valores) if valores else None
        return round(float(valor), 2) if valor is not None else None

    def get_disponible(self, obj) -> bool:
        return obj.stock > 0

    @extend_schema_field(serializers.URLField(allow_null=True))
    def get_imagen_principal(self, obj):
        imagenes = list(obj.imagenes.all())
        return imagenes[0].url if imagenes else None


@extend_schema_serializer(
    examples=[
        OpenApiExample(
            "Crear producto",
            request_only=True,
            value={
                "sku": "LAP-DELL-G15-5530",
                "nombre": "Laptop Dell G15 Gaming",
                "descripcion": "Laptop gamer con RTX 4060 y pantalla 165 Hz",
                "marca": "Dell",
                "categoria_id": 1,
                "precio": "4899.00",
                "descuento": "10.00",
                "stock": 15,
                "especificaciones": {"cpu": "Intel Core i7-13650HX", "ram": "16 GB DDR5", "gpu": "RTX 4060 8 GB"},
                "imagenes": [{"url": "https://cdn.tecnomarket.pe/img/dell-g15-1.jpg", "alt": "Vista frontal", "orden": 0}],
            },
        )
    ]
)
class ProductoDetailSerializer(ProductoListSerializer):
    """Detalle con especificaciones completas, imágenes y enlaces a reseñas."""

    categoria_id = serializers.PrimaryKeyRelatedField(queryset=Categoria.objects.all(), source="categoria", write_only=True)
    vendedor_id = serializers.PrimaryKeyRelatedField(
        queryset=Vendedor.objects.all(), source="vendedor", write_only=True, required=False, allow_null=True,
        help_text="Solo administradores; un vendedor siempre publica a su nombre.",
    )
    imagenes = ImagenProductoSerializer(many=True, required=False)
    resenas_url = serializers.HyperlinkedIdentityField(view_name="producto-resenas")
    resenas = serializers.HyperlinkedRelatedField(many=True, view_name="resena-detail", read_only=True)
    total_resenas = serializers.SerializerMethodField()

    class Meta(ProductoListSerializer.Meta):
        fields = ProductoListSerializer.Meta.fields + [
            "categoria_id", "vendedor_id", "descripcion", "stock", "especificaciones", "imagenes",
            "resenas_url", "resenas", "total_resenas", "activo", "fecha_creacion", "fecha_actualizacion",
        ]
        read_only_fields = ["fecha_creacion", "fecha_actualizacion"]

    def get_total_resenas(self, obj) -> int:
        return len(obj.resenas.all())

    def validate_especificaciones(self, value):
        if not isinstance(value, dict):
            raise serializers.ValidationError("Debe ser un objeto JSON (clave: valor).")
        return value

    def validate_sku(self, value: str) -> str:
        return value.strip().upper()

    @transaction.atomic
    def create(self, validated_data):
        imagenes = validated_data.pop("imagenes", [])
        producto = super().create(validated_data)
        ImagenProducto.objects.bulk_create([ImagenProducto(producto=producto, **img) for img in imagenes])
        return producto

    @transaction.atomic
    def update(self, instance, validated_data):
        imagenes = validated_data.pop("imagenes", None)
        producto = super().update(instance, validated_data)
        if imagenes is not None:  # reemplaza la galería completa
            producto.imagenes.all().delete()
            ImagenProducto.objects.bulk_create([ImagenProducto(producto=producto, **img) for img in imagenes])
        return producto


class ProductoResumenSerializer(serializers.ModelSerializer):
    url = serializers.HyperlinkedIdentityField(view_name="producto-detail")
    precio_con_descuento = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)

    class Meta:
        model = Producto
        fields = ["id", "url", "sku", "nombre", "precio_con_descuento", "stock"]


# ---------------------------------------------------------------------------
# Carrito
# ---------------------------------------------------------------------------
class ItemCarritoSerializer(serializers.ModelSerializer):
    producto = ProductoResumenSerializer(read_only=True)
    subtotal = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)

    class Meta:
        model = ItemCarrito
        fields = ["id", "producto", "cantidad", "subtotal"]


class CarritoSerializer(serializers.Serializer):
    """Serialización con lógica de negocio: totales, IGV y cupón."""

    id = serializers.IntegerField(read_only=True)
    usuario = serializers.CharField(source="usuario.username", read_only=True)
    items = ItemCarritoSerializer(many=True, read_only=True)
    cupon = serializers.CharField(source="cupon.codigo", read_only=True, default=None)
    cantidad_items = serializers.IntegerField(read_only=True)
    subtotal = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    impuestos = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True, help_text="IGV 18%")
    total = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    descuento_cupon = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    total_con_descuento = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)


class AgregarItemSerializer(serializers.Serializer):
    producto = serializers.PrimaryKeyRelatedField(queryset=Producto.objects.filter(activo=True))
    cantidad = serializers.IntegerField(min_value=1, default=1)

    def validate(self, attrs):
        carrito = self.context["carrito"]
        en_carrito = carrito.items.filter(producto=attrs["producto"]).values_list("cantidad", flat=True).first() or 0
        if self.context.get("reemplazar"):
            en_carrito = 0
        if en_carrito + attrs["cantidad"] > attrs["producto"].stock:
            raise serializers.ValidationError(
                {"cantidad": f"La cantidad excede el stock disponible ({attrs['producto'].stock})."}
            )
        return attrs


class EliminarItemSerializer(serializers.Serializer):
    producto = serializers.PrimaryKeyRelatedField(queryset=Producto.objects.all())


class AplicarCuponSerializer(serializers.Serializer):
    codigo = serializers.CharField()

    def validate_codigo(self, value):
        cupon = Cupon.objects.filter(codigo__iexact=value).first()
        if cupon is None or not cupon.vigente:
            raise serializers.ValidationError("Cupón inválido o vencido.")
        return cupon


class CheckoutSerializer(serializers.Serializer):
    direccion_envio = serializers.CharField(max_length=255)
    metodo_pago = serializers.ChoiceField(choices=Orden.MetodoPago.choices)


# ---------------------------------------------------------------------------
# Órdenes
# ---------------------------------------------------------------------------
class ItemOrdenSerializer(serializers.ModelSerializer):
    """Item con el precio al momento de la compra (no el precio actual)."""

    producto = serializers.HyperlinkedRelatedField(view_name="producto-detail", read_only=True)
    subtotal = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)

    class Meta:
        model = ItemOrden
        fields = ["id", "producto", "sku", "nombre_producto", "precio_unitario", "cantidad", "subtotal"]


class TiempoEntregaSerializer(serializers.Serializer):
    desde = serializers.DateField()
    hasta = serializers.DateField()


@extend_schema_serializer(
    examples=[
        OpenApiExample(
            "Orden (respuesta)",
            response_only=True,
            value={
                "id": 51,
                "url": "http://127.0.0.1:8000/api/ordenes/51/",
                "usuario": "cliente1",
                "items": [{
                    "id": 120, "producto": "http://127.0.0.1:8000/api/productos/7/", "sku": "LAP-DELL-G15-5530",
                    "nombre_producto": "Laptop Dell G15 Gaming", "precio_unitario": "4409.10", "cantidad": 1,
                    "subtotal": "4409.10",
                }],
                "direccion_envio": "Av. Huancavelica 1234, El Tambo, Huancayo",
                "metodo_pago": "culqi",
                "estado": "pendiente",
                "subtotal": "4409.10",
                "impuestos": "793.64",
                "descuento": "0.00",
                "total": "5202.74",
                "cupon": "",
                "numero_seguimiento": "",
                "tiempo_estimado_entrega": {"desde": "2026-11-29", "hasta": "2026-12-01"},
                "fecha_creacion": "2026-11-26T10:30:00-05:00",
            },
        )
    ]
)
class OrdenSerializer(serializers.ModelSerializer):
    url = serializers.HyperlinkedIdentityField(view_name="orden-detail")
    usuario = serializers.CharField(source="usuario.username", read_only=True)
    items = ItemOrdenSerializer(many=True, read_only=True)
    tiempo_estimado_entrega = TiempoEntregaSerializer(read_only=True)

    class Meta:
        model = Orden
        fields = [
            "id", "url", "usuario", "items", "direccion_envio", "metodo_pago", "estado", "subtotal", "impuestos",
            "descuento", "total", "cupon", "numero_seguimiento", "tiempo_estimado_entrega", "fecha_creacion",
        ]
        read_only_fields = fields


class OrdenEstadoSerializer(serializers.Serializer):
    estado = serializers.ChoiceField(choices=Orden.Estado.choices)


# ---------------------------------------------------------------------------
# Reseñas
# ---------------------------------------------------------------------------
@extend_schema_serializer(
    examples=[
        OpenApiExample(
            "Crear reseña",
            request_only=True,
            value={"producto": 7, "calificacion": 5, "titulo": "Excelente laptop", "comentario": "Corre todo en ultra."},
        )
    ]
)
class ResenaSerializer(serializers.ModelSerializer):
    url = serializers.HyperlinkedIdentityField(view_name="resena-detail")
    usuario = serializers.CharField(source="usuario.username", read_only=True)
    producto_url = serializers.HyperlinkedRelatedField(source="producto", view_name="producto-detail", read_only=True)
    es_compra_verificada = serializers.SerializerMethodField()

    class Meta:
        model = Resena
        fields = [
            "id", "url", "usuario", "producto", "producto_url", "calificacion", "titulo", "comentario",
            "es_compra_verificada", "fecha_creacion",
        ]
        read_only_fields = ["fecha_creacion"]

    def get_es_compra_verificada(self, obj) -> bool:
        return compro_producto(obj.usuario, obj.producto)

    def validate_calificacion(self, value):
        if not 1 <= value <= 5:
            raise serializers.ValidationError("La calificación debe estar entre 1 y 5.")
        return value

    def validate(self, attrs):
        request = self.context["request"]
        producto = attrs.get("producto") or getattr(self.instance, "producto", None)
        if self.instance is None:
            if not compro_producto(request.user, producto):
                raise serializers.ValidationError("Solo puede reseñar productos que ha comprado.")
            if Resena.objects.filter(usuario=request.user, producto=producto).exists():
                raise serializers.ValidationError("Ya reseñó este producto.")
        return attrs


# ---------------------------------------------------------------------------
# Cuenta de cliente
# ---------------------------------------------------------------------------
class RegistroClienteSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=8, style={"input_type": "password"})
    telefono = serializers.CharField(required=False, allow_blank=True, write_only=True)

    class Meta:
        model = User
        fields = ["id", "username", "password", "email", "first_name", "last_name", "telefono"]

    def validate_email(self, value):
        if User.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError("Ya existe una cuenta con ese correo.")
        return value

    @transaction.atomic
    def create(self, validated_data):
        telefono = validated_data.pop("telefono", "")
        user = User.objects.create_user(**validated_data)
        PerfilCliente.objects.create(user=user, telefono=telefono)
        return user


class CuentaSerializer(serializers.ModelSerializer):
    telefono = serializers.CharField(source="perfil_cliente.telefono", required=False, allow_blank=True)
    direccion = serializers.CharField(source="perfil_cliente.direccion", required=False, allow_blank=True)
    distrito = serializers.CharField(source="perfil_cliente.distrito", required=False, allow_blank=True)
    puntos = serializers.IntegerField(source="perfil_cliente.puntos", read_only=True)
    es_vendedor = serializers.SerializerMethodField()
    total_ordenes = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            "id", "username", "email", "first_name", "last_name", "telefono", "direccion", "distrito", "puntos",
            "es_vendedor", "total_ordenes",
        ]
        read_only_fields = ["username"]

    def get_es_vendedor(self, obj) -> bool:
        return hasattr(obj, "vendedor")

    def get_total_ordenes(self, obj) -> int:
        return obj.ordenes.count()

    def update(self, instance, validated_data):
        perfil_datos = validated_data.pop("perfil_cliente", {})
        instance = super().update(instance, validated_data)
        perfil, _ = PerfilCliente.objects.get_or_create(user=instance)
        for campo, valor in perfil_datos.items():
            setattr(perfil, campo, valor)
        perfil.save()
        return instance


class WebhookPagoSerializer(serializers.Serializer):
    orden = serializers.PrimaryKeyRelatedField(queryset=Orden.objects.all())
    estado = serializers.ChoiceField(choices=["aprobado", "rechazado"])
    referencia = serializers.CharField(max_length=60)
    monto = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=Decimal("0"))


class WebhookLogisticaSerializer(serializers.Serializer):
    numero_seguimiento = serializers.CharField(max_length=30)
    estado = serializers.ChoiceField(choices=["en_ruta", "entregado"])
    courier = serializers.ChoiceField(choices=["olva", "shalom"])
