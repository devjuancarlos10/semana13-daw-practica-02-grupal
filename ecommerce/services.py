"""Lógica de negocio del Caso 2 (independiente de las vistas).

Mantener aquí el checkout y los cambios de estado permite reutilizarlos desde
``/api/carrito/checkout/``, ``POST /api/ordenes/`` y los webhooks.
"""

from decimal import Decimal

from django.db import transaction
from django.db.models import F
from rest_framework.exceptions import ValidationError

from .models import Carrito, ItemOrden, Orden, PerfilCliente, Producto, redondear


def carrito_activo(usuario) -> Carrito:
    carrito, _ = Carrito.objects.get_or_create(usuario=usuario, activo=True)
    return carrito


@transaction.atomic
def checkout(usuario, direccion_envio: str, metodo_pago: str) -> Orden:
    """Convierte el carrito activo en una orden.

    * Bloquea las filas de producto (select_for_update) para evitar sobreventa.
    * Guarda un snapshot de nombre/SKU/precio de cada item.
    * Descuenta stock y desactiva el carrito.
    """
    carrito = Carrito.objects.select_for_update().filter(usuario=usuario, activo=True).select_related("cupon").first()
    if carrito is None or not carrito.items.exists():
        raise ValidationError({"carrito": "El carrito está vacío."})

    items = list(carrito.items.select_related("producto"))
    productos = Producto.objects.select_for_update().in_bulk([i.producto_id for i in items])
    errores = []
    for item in items:
        producto = productos[item.producto_id]
        if not producto.activo:
            errores.append(f"'{producto.nombre}' ya no está disponible.")
        elif item.cantidad > producto.stock:
            errores.append(f"Stock insuficiente para '{producto.nombre}' (disponible: {producto.stock}).")
    if errores:
        raise ValidationError({"items": errores})

    subtotal, impuestos, total = carrito.subtotal, carrito.impuestos, carrito.total
    descuento = carrito.descuento_cupon
    orden = Orden.objects.create(
        usuario=usuario,
        direccion_envio=direccion_envio,
        metodo_pago=metodo_pago,
        subtotal=subtotal,
        impuestos=impuestos,
        descuento=descuento,
        total=redondear(total - descuento),
        cupon=carrito.cupon.codigo if carrito.cupon and descuento > 0 else "",
    )
    ItemOrden.objects.bulk_create(
        [
            ItemOrden(
                orden=orden,
                producto=productos[i.producto_id],
                vendedor_id=productos[i.producto_id].vendedor_id,
                sku=productos[i.producto_id].sku,
                nombre_producto=productos[i.producto_id].nombre,
                precio_unitario=productos[i.producto_id].precio_con_descuento,
                cantidad=i.cantidad,
            )
            for i in items
        ]
    )
    for item in items:
        Producto.objects.filter(pk=item.producto_id).update(stock=F("stock") - item.cantidad)

    carrito.activo = False
    carrito.save(update_fields=["activo"])
    return orden


@transaction.atomic
def cambiar_estado(orden: Orden, nuevo_estado: str) -> Orden:
    """Aplica una transición validando el flujo de estados."""
    if not orden.puede_cambiar_a(nuevo_estado):
        raise ValidationError(
            {"estado": f"Transición no permitida: {orden.estado} -> {nuevo_estado}. "
                       f"Permitidas: {sorted(orden.TRANSICIONES[orden.estado]) or 'ninguna'}."}
        )
    campos = ["estado", "fecha_actualizacion"]
    if nuevo_estado == Orden.Estado.ENVIADA and not orden.numero_seguimiento:
        orden.numero_seguimiento = Orden.generar_numero_seguimiento()
        campos.append("numero_seguimiento")
    if nuevo_estado == Orden.Estado.CANCELADA:
        # Devuelve el stock reservado por la orden
        for item in orden.items.exclude(producto=None):
            Producto.objects.filter(pk=item.producto_id).update(stock=F("stock") + item.cantidad)
    if nuevo_estado == Orden.Estado.ENTREGADA:
        # Programa de fidelidad: 1 punto por cada S/ 10
        perfil, _ = PerfilCliente.objects.get_or_create(user=orden.usuario)
        perfil.puntos = F("puntos") + int(orden.total // Decimal("10"))
        perfil.save(update_fields=["puntos"])
    orden.estado = nuevo_estado
    orden.save(update_fields=campos)
    return orden
