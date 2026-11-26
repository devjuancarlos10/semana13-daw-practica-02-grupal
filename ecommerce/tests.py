"""Tests unitarios del Caso 2 - TecnoMarket Perú."""

from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import override_settings
from django.urls import reverse
from django.utils import timezone
from rest_framework.authtoken.models import Token
from rest_framework.test import APITestCase

from .models import Carrito, Categoria, Cupon, ItemOrden, Orden, PerfilCliente, Producto, Resena, Vendedor

User = get_user_model()


class BaseTiendaTest(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = User.objects.create_user("admin_t", password="ClaveSegura123", is_staff=True)
        cls.cliente = User.objects.create_user("cliente", password="ClaveSegura123")
        cls.otro_cliente = User.objects.create_user("otro", password="ClaveSegura123")
        cls.user_vendedor = User.objects.create_user("tienda", password="ClaveSegura123")
        cls.user_vendedor2 = User.objects.create_user("tienda2", password="ClaveSegura123")
        cls.vendedor = Vendedor.objects.create(user=cls.user_vendedor, nombre_tienda="Gamer HYO", ruc="20600000001", aprobado=True)
        cls.vendedor2 = Vendedor.objects.create(user=cls.user_vendedor2, nombre_tienda="Otra", ruc="20600000002", aprobado=True)
        cls.laptops = Categoria.objects.create(nombre="Laptops", slug="laptops")
        cls.celulares = Categoria.objects.create(nombre="Smartphones", slug="smartphones")
        cls.laptop = Producto.objects.create(
            sku="LAP-DELL-1", nombre="Dell G15 Gaming Laptop", descripcion="Laptop gaming RTX 4060", marca="Dell",
            categoria=cls.laptops, vendedor=cls.vendedor, precio=Decimal("4000.00"), descuento=Decimal("10"), stock=5,
            especificaciones={"ram": "16 GB"},
        )
        cls.celular = Producto.objects.create(
            sku="CEL-SAM-1", nombre="Samsung Galaxy A55", descripcion="Smartphone 5G", marca="Samsung",
            categoria=cls.celulares, precio=Decimal("1500.00"), stock=10,
        )
        cls.agotado = Producto.objects.create(
            sku="LAP-LEN-1", nombre="Lenovo Legion", descripcion="Laptop gaming", marca="Lenovo",
            categoria=cls.laptops, precio=Decimal("6000.00"), stock=0,
        )

    def setUp(self):
        cache.clear()

    def login(self, user):
        token, _ = Token.objects.get_or_create(user=user)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")

    def comprar(self, user, producto, estado=Orden.Estado.ENTREGADA):
        orden = Orden.objects.create(
            usuario=user, direccion_envio="Huancayo", metodo_pago="culqi", estado=estado,
            subtotal=producto.precio, impuestos=0, total=producto.precio,
        )
        ItemOrden.objects.create(
            orden=orden, producto=producto, vendedor=producto.vendedor, sku=producto.sku,
            nombre_producto=producto.nombre, precio_unitario=producto.precio_con_descuento, cantidad=1,
        )
        return orden


class ProductoTests(BaseTiendaTest):
    def test_catalogo_publico_con_campos_calculados(self):
        Resena.objects.create(usuario=self.cliente, producto=self.laptop, calificacion=5, titulo="A", comentario="B")
        Resena.objects.create(usuario=self.otro_cliente, producto=self.laptop, calificacion=4, titulo="A", comentario="B")
        r = self.client.get(reverse("producto-list"))
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data["count"], 3)
        laptop = next(p for p in r.data["results"] if p["sku"] == "LAP-DELL-1")
        self.assertEqual(laptop["precio_con_descuento"], "3600.00")
        self.assertEqual(laptop["rating_promedio"], 4.5)
        self.assertTrue(laptop["disponible"])
        self.assertEqual(laptop["categoria"]["slug"], "laptops")
        self.assertIn(f"/api/vendedores/{self.vendedor.pk}/", laptop["vendedor"])

    def test_detalle_con_especificaciones_y_enlaces(self):
        r = self.client.get(reverse("producto-detail", args=[self.laptop.pk]))
        self.assertEqual(r.data["especificaciones"], {"ram": "16 GB"})
        self.assertTrue(r.data["resenas_url"].endswith(f"/api/productos/{self.laptop.pk}/rese%C3%B1as/"))

    def test_filtros_avanzados(self):
        url = reverse("producto-list")
        self.assertEqual(self.client.get(url, {"categoria": "laptops"}).data["count"], 2)
        self.assertEqual(self.client.get(url, {"marca": "dell"}).data["count"], 1)
        self.assertEqual(self.client.get(url, {"precio_min": 1000, "precio_max": 4500}).data["count"], 2)
        self.assertEqual(self.client.get(url, {"disponible": "true"}).data["count"], 2)
        self.assertEqual(self.client.get(url, {"search": "gaming laptop"}).data["count"], 2)
        precios = [p["precio"] for p in self.client.get(url, {"ordering": "-precio"}).data["results"]]
        self.assertEqual(precios, ["6000.00", "4000.00", "1500.00"])

    def test_paginacion_24(self):
        Producto.objects.bulk_create([
            Producto(sku=f"ACC-{i}", nombre=f"Cable {i}", descripcion="x", marca="Baseus", categoria=self.celulares,
                     precio=Decimal("10"), stock=1)
            for i in range(30)
        ])
        r = self.client.get(reverse("producto-list"))
        self.assertEqual(len(r.data["results"]), 24)
        self.assertIsNotNone(r.data["next"])

    def test_permisos_crear_actualizar_eliminar(self):
        datos = {
            "sku": "NEW-1", "nombre": "Mouse", "descripcion": "Mouse gamer", "marca": "Logitech",
            "categoria_id": self.celulares.pk, "precio": "199.00", "stock": 3,
            "imagenes": [{"url": "https://cdn.tecnomarket.pe/img/m.jpg", "alt": "mouse", "orden": 0}],
        }
        self.login(self.cliente)
        self.assertEqual(self.client.post(reverse("producto-list"), datos, format="json").status_code, 403)
        self.login(self.user_vendedor)
        r = self.client.post(reverse("producto-list"), datos, format="json")
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(Producto.objects.get(sku="NEW-1").vendedor, self.vendedor)
        self.assertEqual(len(r.data["imagenes"]), 1)
        # Dueño puede actualizar; otro vendedor no
        url = reverse("producto-detail", args=[r.data["id"]])
        self.assertEqual(self.client.patch(url, {"stock": 9}, format="json").status_code, 200)
        self.login(self.user_vendedor2)
        self.assertEqual(self.client.patch(url, {"stock": 1}, format="json").status_code, 403)
        # Solo admin elimina
        self.login(self.user_vendedor)
        self.assertEqual(self.client.delete(url).status_code, 403)
        self.login(self.admin)
        self.assertEqual(self.client.delete(url).status_code, 204)

    def test_vendedor_no_aprobado_no_publica(self):
        user = User.objects.create_user("nuevo", password="ClaveSegura123")
        Vendedor.objects.create(user=user, nombre_tienda="Pendiente", ruc="20600000009")
        self.login(user)
        r = self.client.post(reverse("producto-list"), {"sku": "X"}, format="json")
        self.assertEqual(r.status_code, 403)


class CarritoTests(BaseTiendaTest):
    def test_flujo_completo_carrito(self):
        self.login(self.cliente)
        r = self.client.post(reverse("carrito-agregar"), {"producto": self.laptop.pk, "cantidad": 2})
        self.assertEqual(r.status_code, 201)
        r = self.client.post(reverse("carrito-agregar"), {"producto": self.celular.pk})
        self.assertEqual(r.data["cantidad_items"], 3)
        self.assertEqual(r.data["subtotal"], "8700.00")  # 2*3600 + 1500
        self.assertEqual(r.data["impuestos"], "1566.00")
        self.assertEqual(r.data["total"], "10266.00")
        r = self.client.post(reverse("carrito-actualizar"), {"producto": self.laptop.pk, "cantidad": 1})
        self.assertEqual(r.data["cantidad_items"], 2)
        r = self.client.post(reverse("carrito-eliminar"), {"producto": self.celular.pk})
        self.assertEqual(r.data["cantidad_items"], 1)
        r = self.client.post(reverse("carrito-vaciar"))
        self.assertEqual(r.data["items"], [])
        self.assertEqual(self.client.get(reverse("carrito-list")).data["total"], "0.00")

    def test_cantidad_no_excede_stock(self):
        self.login(self.cliente)
        r = self.client.post(reverse("carrito-agregar"), {"producto": self.laptop.pk, "cantidad": 6})
        self.assertEqual(r.status_code, 400)
        self.client.post(reverse("carrito-agregar"), {"producto": self.laptop.pk, "cantidad": 4})
        r = self.client.post(reverse("carrito-agregar"), {"producto": self.laptop.pk, "cantidad": 2})
        self.assertEqual(r.status_code, 400)

    def test_un_solo_carrito_activo(self):
        self.login(self.cliente)
        self.client.get(reverse("carrito-list"))
        self.client.get(reverse("carrito-list"))
        self.assertEqual(Carrito.objects.filter(usuario=self.cliente, activo=True).count(), 1)

    def test_cupon_total_con_descuento(self):
        Cupon.objects.create(codigo="CYBERWOW", porcentaje=10, valido_hasta=timezone.localdate() + timedelta(days=3))
        Cupon.objects.create(codigo="VIEJO", porcentaje=10, valido_hasta=timezone.localdate() - timedelta(days=1))
        self.login(self.cliente)
        self.client.post(reverse("carrito-agregar"), {"producto": self.celular.pk})
        self.assertEqual(self.client.post(reverse("carrito-aplicar-cupon"), {"codigo": "VIEJO"}).status_code, 400)
        r = self.client.post(reverse("carrito-aplicar-cupon"), {"codigo": "cyberwow"})
        self.assertEqual(r.data["total"], "1770.00")
        self.assertEqual(r.data["total_con_descuento"], "1593.00")

    def test_checkout_crea_orden_con_snapshot(self):
        self.login(self.cliente)
        self.client.post(reverse("carrito-agregar"), {"producto": self.laptop.pk, "cantidad": 2})
        r = self.client.post(reverse("carrito-checkout"), {"direccion_envio": "Huancayo", "metodo_pago": "culqi"})
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(r.data["estado"], "pendiente")
        self.assertEqual(r.data["items"][0]["precio_unitario"], "3600.00")
        self.laptop.refresh_from_db()
        self.assertEqual(self.laptop.stock, 3)
        # El precio histórico no cambia si cambia el precio actual
        Producto.objects.filter(pk=self.laptop.pk).update(precio=Decimal("9999"))
        r = self.client.get(reverse("orden-detail", args=[r.data["id"]]))
        self.assertEqual(r.data["items"][0]["precio_unitario"], "3600.00")
        self.assertFalse(Carrito.objects.filter(usuario=self.cliente, activo=True, items__isnull=False).exists())

    def test_checkout_carrito_vacio(self):
        self.login(self.cliente)
        r = self.client.post(reverse("carrito-checkout"), {"direccion_envio": "Huancayo", "metodo_pago": "culqi"})
        self.assertEqual(r.status_code, 400)

    def test_carrito_requiere_autenticacion(self):
        self.assertEqual(self.client.get(reverse("carrito-list")).status_code, 401)


class OrdenTests(BaseTiendaTest):
    def crear_orden_via_api(self, user=None):
        self.login(user or self.cliente)
        self.client.post(reverse("carrito-agregar"), {"producto": self.laptop.pk})
        return self.client.post(reverse("orden-list"), {"direccion_envio": "Huancayo", "metodo_pago": "yape"}).data

    def test_flujo_de_estados_y_seguimiento(self):
        orden = self.crear_orden_via_api()
        url = reverse("orden-detail", args=[orden["id"]])
        # El cliente no puede actualizar estado
        self.assertEqual(self.client.patch(url, {"estado": "pagada"}).status_code, 403)
        # El vendedor del producto sí
        self.login(self.user_vendedor)
        self.assertEqual(self.client.patch(url, {"estado": "pagada"}).data["estado"], "pagada")
        r = self.client.patch(url, {"estado": "enviada"})
        self.assertTrue(r.data["numero_seguimiento"].startswith("TM-"))
        self.assertEqual(self.client.patch(url, {"estado": "pendiente"}).status_code, 400)
        # Otro vendedor no ve la orden
        self.login(self.user_vendedor2)
        self.assertEqual(self.client.patch(url, {"estado": "entregada"}).status_code, 404)
        # Admin la entrega -> puntos de fidelidad
        self.login(self.admin)
        self.assertEqual(self.client.patch(url, {"estado": "entregada"}).data["estado"], "entregada")
        self.assertGreater(PerfilCliente.objects.get(user=self.cliente).puntos, 0)

    def test_cancelar_solo_pendiente_y_restaura_stock(self):
        orden = self.crear_orden_via_api()
        self.laptop.refresh_from_db()
        self.assertEqual(self.laptop.stock, 4)
        r = self.client.post(reverse("orden-cancelar", args=[orden["id"]]))
        self.assertEqual(r.data["estado"], "cancelada")
        self.laptop.refresh_from_db()
        self.assertEqual(self.laptop.stock, 5)
        self.assertEqual(self.client.post(reverse("orden-cancelar", args=[orden["id"]])).status_code, 400)

    def test_mis_ordenes_y_privacidad(self):
        self.crear_orden_via_api()
        otra = self.comprar(self.otro_cliente, self.celular)
        self.login(self.cliente)
        r = self.client.get(reverse("orden-mis-ordenes"))
        self.assertEqual(r.data["count"], 1)  # LimitOffsetPagination
        self.assertEqual(self.client.get(reverse("orden-detail", args=[otra.pk])).status_code, 404)
        self.assertIn("tiempo_estimado_entrega", r.data["results"][0])

    def test_resumen_solo_admin(self):
        self.comprar(self.cliente, self.laptop)
        self.login(self.cliente)
        self.assertEqual(self.client.get(reverse("orden-resumen")).status_code, 403)
        self.login(self.admin)
        r = self.client.get(reverse("orden-resumen"))
        self.assertEqual(r.data["por_estado"], {"entregada": 1})

    def test_put_no_permitido(self):
        orden = self.crear_orden_via_api()
        self.login(self.admin)
        r = self.client.put(reverse("orden-detail", args=[orden["id"]]), {"estado": "pagada"})
        self.assertEqual(r.status_code, 405)


class ResenaTests(BaseTiendaTest):
    def test_solo_compradores_verificados(self):
        datos = {"producto": self.laptop.pk, "calificacion": 5, "titulo": "Top", "comentario": "Muy buena"}
        self.login(self.cliente)
        self.assertEqual(self.client.post(reverse("resena-list"), datos).status_code, 403)
        self.comprar(self.cliente, self.laptop)
        r = self.client.post(reverse("resena-list"), datos)
        self.assertEqual(r.status_code, 201, r.data)
        self.assertTrue(r.data["es_compra_verificada"])
        self.assertEqual(self.client.post(reverse("resena-list"), datos).status_code, 400)  # duplicada

    def test_orden_pendiente_no_cuenta_como_compra(self):
        self.comprar(self.cliente, self.laptop, estado=Orden.Estado.PENDIENTE)
        self.login(self.cliente)
        r = self.client.post(reverse("resena-list"), {"producto": self.laptop.pk, "calificacion": 4, "titulo": "x", "comentario": "y"})
        self.assertEqual(r.status_code, 403)

    def test_calificacion_rango(self):
        self.comprar(self.cliente, self.laptop)
        self.login(self.cliente)
        r = self.client.post(reverse("resena-list"), {"producto": self.laptop.pk, "calificacion": 6, "titulo": "x", "comentario": "y"})
        self.assertEqual(r.status_code, 400)
        self.assertIn("calificacion", r.data)

    def test_listado_publico_y_eliminar_propia(self):
        resena = Resena.objects.create(usuario=self.cliente, producto=self.laptop, calificacion=4, titulo="a", comentario="b")
        self.assertEqual(self.client.get(reverse("resena-list")).data["count"], 1)
        r = self.client.get(reverse("producto-resenas", args=[self.laptop.pk]))
        self.assertEqual(r.data["count"], 1)
        self.login(self.otro_cliente)
        self.assertEqual(self.client.delete(reverse("resena-detail", args=[resena.pk])).status_code, 403)
        self.login(self.cliente)
        self.assertEqual(self.client.delete(reverse("resena-detail", args=[resena.pk])).status_code, 204)


class CuentaYWebhookTests(BaseTiendaTest):
    def test_registro_y_perfil(self):
        r = self.client.post(reverse("cuenta-registro"), {
            "username": "nuevo_cliente", "password": "ClaveSegura123", "email": "nuevo@correo.pe", "telefono": "999111222",
        })
        self.assertEqual(r.status_code, 201, r.data)
        self.login(User.objects.get(username="nuevo_cliente"))
        r = self.client.get(reverse("cuenta-list"))
        self.assertEqual(r.data["telefono"], "999111222")
        r = self.client.patch(reverse("cuenta-actualizar"), {"direccion": "Jr. Puno 456"})
        self.assertEqual(r.data["direccion"], "Jr. Puno 456")

    def test_jwt_para_moviles(self):
        r = self.client.post(reverse("jwt-obtain"), {"username": "cliente", "password": "ClaveSegura123"})
        self.assertEqual(r.status_code, 200)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {r.data['access']}")
        self.assertEqual(self.client.get(reverse("carrito-list")).status_code, 200)

    @override_settings(WEBHOOK_SECRET="secreto-test")
    def test_webhooks_pago_y_logistica(self):
        orden = self.comprar(self.cliente, self.laptop, estado=Orden.Estado.PENDIENTE)
        datos = {"orden": orden.pk, "estado": "aprobado", "referencia": "chr_1", "monto": str(orden.total)}
        self.assertEqual(self.client.post(reverse("webhook-pagos"), datos).status_code, 403)
        r = self.client.post(reverse("webhook-pagos"), datos, HTTP_X_WEBHOOK_TOKEN="secreto-test")
        self.assertEqual(r.data["estado"], "pagada")
        orden.refresh_from_db()
        from .services import cambiar_estado
        cambiar_estado(orden, Orden.Estado.ENVIADA)
        r = self.client.post(
            reverse("webhook-logistica"),
            {"numero_seguimiento": orden.numero_seguimiento, "estado": "entregado", "courier": "olva"},
            HTTP_X_WEBHOOK_TOKEN="secreto-test",
        )
        self.assertEqual(r.data["estado"], "entregada")

    def test_cors_origenes_tecnomarket(self):
        r = self.client.get(reverse("producto-list"), HTTP_ORIGIN="https://app.tecnomarket.pe")
        self.assertEqual(r["Access-Control-Allow-Origin"], "https://app.tecnomarket.pe")

    def test_throttling_checkout_429(self):
        from rest_framework.settings import api_settings
        from rest_framework.throttling import SimpleRateThrottle

        rates = {**api_settings.DEFAULT_THROTTLE_RATES, "tienda_checkout": "2/hour"}
        original = SimpleRateThrottle.THROTTLE_RATES
        SimpleRateThrottle.THROTTLE_RATES = rates
        try:
            self.login(self.cliente)
            datos = {"direccion_envio": "Huancayo", "metodo_pago": "culqi"}
            codigos = [self.client.post(reverse("carrito-checkout"), datos).status_code for _ in range(3)]
        finally:
            SimpleRateThrottle.THROTTLE_RATES = original
        self.assertEqual(codigos, [400, 400, 429])
