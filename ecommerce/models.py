"""Modelos del Caso 2 - TecnoMarket Perú."""

import uuid
from datetime import timedelta
from decimal import ROUND_HALF_UP, Decimal

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import Q
from django.utils import timezone

IGV = Decimal("0.18")
DOS_DECIMALES = Decimal("0.01")


def redondear(valor: Decimal) -> Decimal:
    return Decimal(valor).quantize(DOS_DECIMALES, rounding=ROUND_HALF_UP)


class Categoria(models.Model):
    nombre = models.CharField(max_length=80, unique=True)
    slug = models.SlugField(max_length=80, unique=True)
    descripcion = models.TextField(blank=True)
    imagen = models.URLField(blank=True)

    class Meta:
        ordering = ["nombre"]

    def __str__(self):
        return self.nombre


class Vendedor(models.Model):
    """Tienda registrada en el marketplace."""

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="vendedor")
    nombre_tienda = models.CharField(max_length=120, unique=True)
    ruc = models.CharField(max_length=11, unique=True)
    aprobado = models.BooleanField(default=False, help_text="Solo los vendedores aprobados pueden publicar")
    fecha_registro = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["nombre_tienda"]
        verbose_name_plural = "vendedores"

    def __str__(self):
        return self.nombre_tienda


class PerfilCliente(models.Model):
    """Datos de cliente y programa de fidelidad (puntos)."""

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="perfil_cliente")
    telefono = models.CharField(max_length=15, blank=True)
    direccion = models.CharField(max_length=255, blank=True)
    distrito = models.CharField(max_length=80, blank=True)
    puntos = models.PositiveIntegerField(default=0)

    def __str__(self):
        return f"Cliente {self.user.username}"


class Producto(models.Model):
    sku = models.CharField("SKU", max_length=40, unique=True)
    nombre = models.CharField(max_length=200, db_index=True)
    descripcion = models.TextField()
    marca = models.CharField(max_length=60, db_index=True)
    categoria = models.ForeignKey(Categoria, on_delete=models.PROTECT, related_name="productos")
    vendedor = models.ForeignKey(
        Vendedor, on_delete=models.CASCADE, null=True, blank=True, related_name="productos",
        help_text="Nulo = producto vendido directamente por TecnoMarket",
    )
    precio = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(Decimal("0.01"))])
    descuento = models.DecimalField(
        "descuento (%)", max_digits=5, decimal_places=2, default=0,
        validators=[MinValueValidator(0), MaxValueValidator(90)],
    )
    stock = models.PositiveIntegerField(default=0)
    especificaciones = models.JSONField(default=dict, blank=True)
    activo = models.BooleanField(default=True)
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_actualizacion = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-fecha_creacion"]
        indexes = [models.Index(fields=["categoria", "precio"])]

    def __str__(self):
        return f"{self.nombre} ({self.sku})"

    @property
    def precio_con_descuento(self) -> Decimal:
        return redondear(Decimal(self.precio) * (1 - Decimal(str(self.descuento)) / 100))


class ImagenProducto(models.Model):
    producto = models.ForeignKey(Producto, on_delete=models.CASCADE, related_name="imagenes")
    url = models.URLField()
    alt = models.CharField(max_length=120, blank=True)
    orden = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["orden", "id"]


class Cupon(models.Model):
    codigo = models.CharField(max_length=30, unique=True)
    porcentaje = models.PositiveSmallIntegerField(validators=[MinValueValidator(1), MaxValueValidator(50)])
    activo = models.BooleanField(default=True)
    valido_hasta = models.DateField()

    def __str__(self):
        return f"{self.codigo} (-{self.porcentaje}%)"

    @property
    def vigente(self) -> bool:
        return self.activo and self.valido_hasta >= timezone.localdate()


class Carrito(models.Model):
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="carritos")
    activo = models.BooleanField(default=True)
    cupon = models.ForeignKey(Cupon, on_delete=models.SET_NULL, null=True, blank=True)
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_actualizacion = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            # Regla de negocio: un usuario no puede tener más de 1 carrito activo
            models.UniqueConstraint(fields=["usuario"], condition=Q(activo=True), name="un_carrito_activo_por_usuario"),
        ]

    def __str__(self):
        return f"Carrito #{self.pk} de {self.usuario}"

    # --- Totales -------------------------------------------------------------
    def items_con_producto(self):
        return self.items.select_related("producto")

    @property
    def subtotal(self) -> Decimal:
        return redondear(sum((i.subtotal for i in self.items_con_producto()), Decimal("0")))

    @property
    def impuestos(self) -> Decimal:
        return redondear(self.subtotal * IGV)

    @property
    def total(self) -> Decimal:
        return redondear(self.subtotal + self.impuestos)

    @property
    def descuento_cupon(self) -> Decimal:
        if self.cupon and self.cupon.vigente:
            return redondear(self.total * self.cupon.porcentaje / 100)
        return Decimal("0.00")

    @property
    def total_con_descuento(self) -> Decimal:
        return redondear(self.total - self.descuento_cupon)

    @property
    def cantidad_items(self) -> int:
        return sum(i.cantidad for i in self.items.all())


class ItemCarrito(models.Model):
    carrito = models.ForeignKey(Carrito, on_delete=models.CASCADE, related_name="items")
    producto = models.ForeignKey(Producto, on_delete=models.CASCADE)
    cantidad = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    agregado = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [("carrito", "producto")]
        ordering = ["agregado"]

    @property
    def subtotal(self) -> Decimal:
        return redondear(self.producto.precio_con_descuento * self.cantidad)


class Orden(models.Model):
    class Estado(models.TextChoices):
        PENDIENTE = "pendiente", "Pendiente"
        PAGADA = "pagada", "Pagada"
        ENVIADA = "enviada", "Enviada"
        ENTREGADA = "entregada", "Entregada"
        CANCELADA = "cancelada", "Cancelada"

    class MetodoPago(models.TextChoices):
        CULQI = "culqi", "Culqi"
        MERCADOPAGO = "mercadopago", "MercadoPago"
        NIUBIZ = "niubiz", "Niubiz"
        YAPE = "yape", "Yape"

    # Transiciones válidas del flujo de estados
    TRANSICIONES = {
        Estado.PENDIENTE: {Estado.PAGADA, Estado.CANCELADA},
        Estado.PAGADA: {Estado.ENVIADA, Estado.CANCELADA},
        Estado.ENVIADA: {Estado.ENTREGADA},
        Estado.ENTREGADA: set(),
        Estado.CANCELADA: set(),
    }

    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="ordenes")
    direccion_envio = models.CharField(max_length=255)
    metodo_pago = models.CharField(max_length=15, choices=MetodoPago.choices)
    estado = models.CharField(max_length=10, choices=Estado.choices, default=Estado.PENDIENTE, db_index=True)
    subtotal = models.DecimalField(max_digits=12, decimal_places=2)
    impuestos = models.DecimalField(max_digits=12, decimal_places=2)
    descuento = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total = models.DecimalField(max_digits=12, decimal_places=2)
    cupon = models.CharField(max_length=30, blank=True)
    numero_seguimiento = models.CharField(max_length=30, blank=True)
    fecha_creacion = models.DateTimeField(default=timezone.now, db_index=True)
    fecha_actualizacion = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-fecha_creacion"]
        verbose_name_plural = "órdenes"

    def __str__(self):
        return f"Orden #{self.pk} ({self.estado})"

    def puede_cambiar_a(self, nuevo_estado: str) -> bool:
        return nuevo_estado in self.TRANSICIONES.get(self.estado, set())

    @staticmethod
    def generar_numero_seguimiento() -> str:
        return f"TM-{timezone.now():%Y%m%d}-{uuid.uuid4().hex[:8].upper()}"

    @property
    def tiempo_estimado_entrega(self) -> dict:
        base = self.fecha_creacion.date()
        return {"desde": base + timedelta(days=3), "hasta": base + timedelta(days=5)}


class ItemOrden(models.Model):
    """Snapshot del producto al momento de la compra (precio histórico)."""

    orden = models.ForeignKey(Orden, on_delete=models.CASCADE, related_name="items")
    producto = models.ForeignKey(Producto, on_delete=models.SET_NULL, null=True, related_name="items_vendidos")
    vendedor = models.ForeignKey(Vendedor, on_delete=models.SET_NULL, null=True, blank=True)
    sku = models.CharField(max_length=40)
    nombre_producto = models.CharField(max_length=200)
    precio_unitario = models.DecimalField(max_digits=10, decimal_places=2)
    cantidad = models.PositiveIntegerField()

    @property
    def subtotal(self) -> Decimal:
        return redondear(self.precio_unitario * self.cantidad)


class Resena(models.Model):
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="resenas")
    producto = models.ForeignKey(Producto, on_delete=models.CASCADE, related_name="resenas")
    calificacion = models.PositiveSmallIntegerField(validators=[MinValueValidator(1), MaxValueValidator(5)])
    titulo = models.CharField(max_length=120)
    comentario = models.TextField()
    fecha_creacion = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-fecha_creacion"]
        unique_together = [("usuario", "producto")]
        verbose_name = "reseña"

    def __str__(self):
        return f"{self.calificacion}★ {self.producto} por {self.usuario}"


ESTADOS_COMPRA_VALIDA = [Orden.Estado.PAGADA, Orden.Estado.ENVIADA, Orden.Estado.ENTREGADA]


def compro_producto(usuario, producto) -> bool:
    """True si el usuario tiene una orden pagada/enviada/entregada con el producto."""
    return ItemOrden.objects.filter(
        orden__usuario=usuario, orden__estado__in=ESTADOS_COMPRA_VALIDA, producto=producto
    ).exists()
