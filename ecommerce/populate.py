"""Datos de prueba del Caso 2 - TecnoMarket Perú.

Genera más de 200 productos (catálogo base + variantes), 25 usuarios (1 admin, 4 vendedores,
20 clientes), 70 órdenes en todos los estados y 100+ reseñas de compras
verificadas. Es idempotente: borra los datos previos de la app.
"""

import random
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone

from .models import (
    ESTADOS_COMPRA_VALIDA,
    Carrito,
    Categoria,
    Cupon,
    ImagenProducto,
    ItemOrden,
    Orden,
    PerfilCliente,
    Producto,
    Resena,
    Vendedor,
    redondear,
)

User = get_user_model()
PASSWORD = "TecnoMarket2026!"
CDN = "https://cdn.tecnomarket.pe/img"

CATEGORIAS = [
    ("Laptops", "laptops", "Laptops para trabajo, estudio y gaming"),
    ("Smartphones", "smartphones", "Teléfonos inteligentes Android e iOS"),
    ("Tablets", "tablets", "Tablets y lectores electrónicos"),
    ("Monitores", "monitores", "Monitores para oficina y gaming"),
    ("Componentes", "componentes", "Procesadores, tarjetas de video, memorias y SSD"),
    ("Periféricos", "perifericos", "Teclados, mouse y webcams"),
    ("Audio", "audio", "Audífonos, parlantes y micrófonos"),
    ("Accesorios", "accesorios", "Cargadores, cables, mochilas y fundas"),
    ("Redes", "redes", "Routers, switches y repetidores WiFi"),
    ("Smartwatches", "smartwatches", "Relojes y pulseras inteligentes"),
]

# categoria_slug: [(marca, modelo, precio_base, specs)]
CATALOGO = {
    "laptops": [
        ("Dell", "G15 Gaming RTX 4060", 4899, {"cpu": "Intel Core i7-13650HX", "ram": "16 GB", "gpu": "RTX 4060"}),
        ("Dell", "Inspiron 15 3530", 2499, {"cpu": "Intel Core i5-1335U", "ram": "8 GB", "ssd": "512 GB"}),
        ("Lenovo", "IdeaPad Slim 3", 2199, {"cpu": "AMD Ryzen 5 7520U", "ram": "8 GB", "ssd": "512 GB"}),
        ("Lenovo", "Legion 5 Pro", 6299, {"cpu": "AMD Ryzen 7 7745HX", "ram": "32 GB", "gpu": "RTX 4070"}),
        ("HP", "Victus 15 Gaming", 3799, {"cpu": "AMD Ryzen 5 7535HS", "ram": "16 GB", "gpu": "RTX 3050"}),
        ("HP", "Pavilion x360 14", 3199, {"cpu": "Intel Core i5-1335U", "ram": "8 GB", "pantalla": "Táctil 14\""}),
        ("ASUS", "TUF Gaming F15", 4299, {"cpu": "Intel Core i7-12700H", "ram": "16 GB", "gpu": "RTX 4050"}),
        ("ASUS", "Vivobook 16", 2399, {"cpu": "Intel Core i5-1235U", "ram": "16 GB", "ssd": "512 GB"}),
        ("Apple", "MacBook Air M3 13\"", 5699, {"chip": "Apple M3", "ram": "8 GB", "ssd": "256 GB"}),
        ("Acer", "Nitro V 15", 3599, {"cpu": "Intel Core i5-13420H", "ram": "16 GB", "gpu": "RTX 4050"}),
        ("MSI", "Katana 15", 4999, {"cpu": "Intel Core i7-13620H", "ram": "16 GB", "gpu": "RTX 4060"}),
        ("Lenovo", "ThinkPad E14 Gen 5", 3899, {"cpu": "Intel Core i7-1355U", "ram": "16 GB", "ssd": "1 TB"}),
    ],
    "smartphones": [
        ("Samsung", "Galaxy S24 256 GB", 3999, {"pantalla": "6.2\" AMOLED", "camara": "50 MP", "bateria": "4000 mAh"}),
        ("Samsung", "Galaxy A55 5G", 1699, {"pantalla": "6.6\" AMOLED", "camara": "50 MP", "ram": "8 GB"}),
        ("Samsung", "Galaxy A15", 749, {"pantalla": "6.5\"", "camara": "50 MP", "ram": "4 GB"}),
        ("Apple", "iPhone 15 128 GB", 3899, {"chip": "A16 Bionic", "camara": "48 MP", "pantalla": "6.1\""}),
        ("Apple", "iPhone 15 Pro 256 GB", 5799, {"chip": "A17 Pro", "camara": "48 MP", "material": "Titanio"}),
        ("Xiaomi", "Redmi Note 13 Pro", 1299, {"pantalla": "6.67\" AMOLED", "camara": "200 MP", "ram": "8 GB"}),
        ("Xiaomi", "Poco X6 Pro", 1499, {"cpu": "Dimensity 8300 Ultra", "ram": "12 GB", "carga": "67 W"}),
        ("Motorola", "Moto G84 5G", 999, {"pantalla": "6.5\" pOLED", "ram": "12 GB", "almacenamiento": "256 GB"}),
        ("Motorola", "Edge 50 Fusion", 1599, {"pantalla": "6.7\" curva", "camara": "50 MP", "ip": "IP68"}),
        ("Honor", "Magic6 Lite", 1399, {"pantalla": "6.78\" AMOLED", "bateria": "5300 mAh", "camara": "108 MP"}),
        ("Google", "Pixel 8a", 2299, {"chip": "Tensor G3", "camara": "64 MP", "ram": "8 GB"}),
        ("OPPO", "Reno 11 F", 1299, {"pantalla": "6.7\" AMOLED", "camara": "64 MP", "carga": "67 W"}),
    ],
    "tablets": [
        ("Apple", "iPad 10ma Gen 64 GB", 1899, {"pantalla": "10.9\"", "chip": "A14 Bionic"}),
        ("Apple", "iPad Air M2 11\"", 3499, {"pantalla": "11\" Liquid Retina", "chip": "M2"}),
        ("Samsung", "Galaxy Tab S9 FE", 1899, {"pantalla": "10.9\"", "spen": "Incluido"}),
        ("Samsung", "Galaxy Tab A9+", 999, {"pantalla": "11\"", "ram": "4 GB"}),
        ("Lenovo", "Tab M11", 849, {"pantalla": "11\"", "ram": "4 GB", "lapiz": "Incluido"}),
        ("Xiaomi", "Redmi Pad SE", 799, {"pantalla": "11\" 90 Hz", "ram": "6 GB"}),
        ("Amazon", "Kindle Paperwhite", 699, {"pantalla": "6.8\" E-ink", "almacenamiento": "16 GB"}),
        ("Huawei", "MatePad 11.5", 1299, {"pantalla": "11.5\" 120 Hz", "ram": "8 GB"}),
    ],
    "monitores": [
        ("LG", "UltraGear 27GN800 27\" QHD 144 Hz", 1299, {"panel": "IPS", "resolucion": "2560x1440"}),
        ("LG", "27MP400 27\" FHD", 549, {"panel": "IPS", "resolucion": "1920x1080"}),
        ("Samsung", "Odyssey G5 32\" Curvo", 1499, {"panel": "VA", "frecuencia": "165 Hz"}),
        ("Samsung", "ViewFinity S6 27\" 4K", 1699, {"panel": "IPS", "resolucion": "3840x2160"}),
        ("ASUS", "TUF VG249Q1A 24\"", 699, {"panel": "IPS", "frecuencia": "165 Hz"}),
        ("AOC", "24G2 24\" 144 Hz", 649, {"panel": "IPS", "tiempo_respuesta": "1 ms"}),
        ("Dell", "P2422H 24\"", 799, {"panel": "IPS", "ajuste": "Altura y pivote"}),
        ("Xiaomi", "Mi Curved Gaming 34\"", 1599, {"panel": "VA", "resolucion": "3440x1440"}),
        ("ViewSonic", "VX2479 24\"", 589, {"panel": "IPS", "frecuencia": "180 Hz"}),
        ("BenQ", "GW2490 24\"", 529, {"panel": "IPS", "eye_care": "Sí"}),
    ],
    "componentes": [
        ("AMD", "Ryzen 5 7600", 949, {"nucleos": 6, "socket": "AM5"}),
        ("AMD", "Ryzen 7 7800X3D", 1899, {"nucleos": 8, "socket": "AM5"}),
        ("Intel", "Core i5-14400F", 899, {"nucleos": 10, "socket": "LGA1700"}),
        ("Intel", "Core i7-14700K", 1799, {"nucleos": 20, "socket": "LGA1700"}),
        ("NVIDIA", "GeForce RTX 4060 8 GB", 1399, {"vram": "8 GB GDDR6", "tdp": "115 W"}),
        ("NVIDIA", "GeForce RTX 4070 Super 12 GB", 2999, {"vram": "12 GB GDDR6X", "tdp": "220 W"}),
        ("AMD", "Radeon RX 7600 8 GB", 1199, {"vram": "8 GB GDDR6"}),
        ("Kingston", "Fury Beast 16 GB DDR5 5600", 269, {"tipo": "DDR5", "capacidad": "16 GB"}),
        ("Corsair", "Vengeance 32 GB DDR5 6000", 529, {"tipo": "DDR5", "capacidad": "2x16 GB"}),
        ("Samsung", "990 Pro 1 TB NVMe", 499, {"interfaz": "PCIe 4.0", "lectura": "7450 MB/s"}),
        ("Kingston", "NV2 1 TB NVMe", 249, {"interfaz": "PCIe 4.0", "lectura": "3500 MB/s"}),
        ("WD", "Blue SN580 1 TB", 289, {"interfaz": "PCIe 4.0", "lectura": "4150 MB/s"}),
        ("ASUS", "TUF Gaming B650-Plus WiFi", 949, {"socket": "AM5", "formato": "ATX"}),
        ("MSI", "MAG B760 Tomahawk WiFi", 899, {"socket": "LGA1700", "formato": "ATX"}),
        ("Corsair", "RM750e 750 W 80+ Gold", 449, {"potencia": "750 W", "modular": "Sí"}),
    ],
    "perifericos": [
        ("Logitech", "G502 HERO", 199, {"dpi": 25600, "conexion": "USB"}),
        ("Logitech", "MX Master 3S", 459, {"dpi": 8000, "conexion": "Bluetooth"}),
        ("Logitech", "G Pro X Superlight 2", 649, {"peso": "60 g", "conexion": "Lightspeed"}),
        ("Razer", "DeathAdder V3", 349, {"dpi": 30000, "peso": "59 g"}),
        ("Redragon", "Kumara K552 RGB", 149, {"switch": "Outemu Red", "formato": "TKL"}),
        ("HyperX", "Alloy Origins Core", 399, {"switch": "HyperX Red", "formato": "TKL"}),
        ("Logitech", "K380 Multi-Device", 159, {"conexion": "Bluetooth", "dispositivos": 3}),
        ("Logitech", "C920 HD Pro Webcam", 299, {"resolucion": "1080p 30 fps"}),
        ("Razer", "BlackWidow V4", 699, {"switch": "Razer Green", "formato": "Full size"}),
        ("Microsoft", "Bluetooth Ergonomic Mouse", 149, {"conexion": "Bluetooth"}),
    ],
    "audio": [
        ("Sony", "WH-1000XM5", 1499, {"anc": "Sí", "autonomia": "30 h"}),
        ("Sony", "WF-C700N", 449, {"tipo": "In-ear", "anc": "Sí"}),
        ("JBL", "Flip 6", 499, {"ip": "IP67", "autonomia": "12 h"}),
        ("JBL", "Tune 520BT", 199, {"tipo": "On-ear", "autonomia": "57 h"}),
        ("Apple", "AirPods Pro 2", 1099, {"anc": "Sí", "carga": "USB-C"}),
        ("Samsung", "Galaxy Buds FE", 399, {"anc": "Sí", "autonomia": "21 h"}),
        ("HyperX", "Cloud II", 349, {"tipo": "Gaming", "sonido": "7.1 virtual"}),
        ("Logitech", "G435 Lightspeed", 299, {"tipo": "Gaming", "peso": "165 g"}),
        ("Marshall", "Emberton II", 799, {"ip": "IP67", "autonomia": "30 h"}),
        ("HyperX", "QuadCast S", 649, {"tipo": "Micrófono USB", "patrones": 4}),
    ],
    "accesorios": [
        ("Anker", "Cargador Nano 65 W USB-C", 179, {"potencia": "65 W", "puertos": 2}),
        ("Anker", "PowerCore 20000 mAh", 199, {"capacidad": "20000 mAh"}),
        ("Baseus", "Cable USB-C 100 W 2 m", 49, {"longitud": "2 m"}),
        ("Samsonite", "Mochila Guardit 15.6\"", 349, {"material": "Poliéster"}),
        ("Spigen", "Funda Ultra Hybrid iPhone 15", 129, {"compatibilidad": "iPhone 15"}),
        ("Ugreen", "Hub USB-C 7 en 1", 199, {"puertos": "HDMI 4K, USB 3.0, SD"}),
        ("Kingston", "DataTraveler Exodia 128 GB", 59, {"interfaz": "USB 3.2"}),
        ("SanDisk", "microSD Extreme 256 GB", 129, {"velocidad": "190 MB/s"}),
        ("Cooler Master", "Base NotePal X3", 159, {"ventilador": "200 mm"}),
        ("Logitech", "Soporte para laptop Casa Pop-Up", 299, {"material": "Aluminio"}),
    ],
    "redes": [
        ("TP-Link", "Archer AX55 WiFi 6", 349, {"estandar": "WiFi 6", "velocidad": "AX3000"}),
        ("TP-Link", "Deco X20 (pack x2)", 699, {"tipo": "Mesh", "estandar": "WiFi 6"}),
        ("TP-Link", "RE315 Repetidor", 119, {"velocidad": "AC1200"}),
        ("ASUS", "RT-AX58U", 649, {"estandar": "WiFi 6", "velocidad": "AX3000"}),
        ("Mercusys", "MR70X", 199, {"estandar": "WiFi 6", "velocidad": "AX1800"}),
        ("TP-Link", "TL-SG108 Switch 8 puertos", 99, {"puertos": "8 Gigabit"}),
        ("Ubiquiti", "UniFi U6 Lite", 599, {"tipo": "Access Point", "estandar": "WiFi 6"}),
        ("Huawei", "WiFi AX3", 249, {"estandar": "WiFi 6", "velocidad": "AX3000"}),
    ],
    "smartwatches": [
        ("Apple", "Watch Series 9 GPS 41 mm", 1799, {"pantalla": "Retina siempre activa", "gps": "Sí"}),
        ("Apple", "Watch SE 2da Gen", 1199, {"pantalla": "Retina", "resistencia": "50 m"}),
        ("Samsung", "Galaxy Watch6 44 mm", 1199, {"so": "Wear OS", "sensores": "BioActive"}),
        ("Xiaomi", "Smart Band 8", 179, {"autonomia": "16 días"}),
        ("Huawei", "Watch GT 4", 999, {"autonomia": "14 días", "gps": "Sí"}),
        ("Amazfit", "GTR 4", 849, {"autonomia": "14 días", "gps": "Dual band"}),
        ("Garmin", "Forerunner 265", 1999, {"pantalla": "AMOLED", "gps": "Multibanda"}),
        ("Xiaomi", "Redmi Watch 4", 399, {"pantalla": "1.97\" AMOLED", "autonomia": "20 días"}),
    ],
}

VENDEDORES = [
    ("vendedor1", "Tienda Gamer Huancayo", "20601234561", True),
    ("vendedor2", "Smart Store Lima", "20601234562", True),
    ("vendedor3", "Componentes PC Perú", "20601234563", True),
    ("vendedor4", "Accesorios Express", "20601234564", False),
]

NOMBRES = [
    ("Ana", "Torres Quispe"), ("Bruno", "Salazar Rojas"), ("Camila", "Huamán Paredes"), ("Daniel", "Cárdenas Ríos"),
    ("Elena", "Vargas Ccahuana"), ("Fernando", "Mendoza Ticse"), ("Gabriela", "Rojas Inga"), ("Héctor", "Palacios Soto"),
    ("Isabel", "Ramírez Poma"), ("Jorge", "Castillo Meza"), ("Karen", "Flores Orihuela"), ("Luis", "Chávez Aliaga"),
    ("Milagros", "Gutiérrez Laura"), ("Nicolás", "Espinoza Baldeón"), ("Olga", "Sánchez Huaringa"),
    ("Pedro", "Ccanto Rivera"), ("Rocío", "Medina Arias"), ("Sergio", "Navarro Villena"), ("Tatiana", "Ruiz Cerrón"),
    ("Víctor", "León Zárate"),
]
DIRECCIONES = [
    "Av. Huancavelica 1234, El Tambo, Huancayo", "Jr. Puno 456, Huancayo", "Av. Ferrocarril 890, Chilca",
    "Av. Javier Prado Este 2450, San Borja, Lima", "Calle Las Begonias 415, San Isidro, Lima",
    "Av. Ejército 101, Yanahuara, Arequipa", "Av. España 1555, Trujillo", "Av. La Cultura 733, Cusco",
]
RESENAS_POSITIVAS = [
    ("Excelente compra", "Llegó en el tiempo indicado y funciona perfecto."),
    ("Muy recomendado", "Gran relación calidad-precio, lo volvería a comprar."),
    ("Cumple lo prometido", "Las especificaciones coinciden con la descripción."),
    ("Superó mis expectativas", "Rendimiento muy bueno para el precio."),
]
RESENAS_NEUTRAS = [
    ("Está bien", "Cumple, aunque el empaque llegó algo maltratado."),
    ("Bueno pero mejorable", "Funciona bien, pero la batería dura menos de lo esperado."),
]
RESENAS_NEGATIVAS = [
    ("No lo recomiendo", "Presentó fallas a la semana, tuve que usar la garantía."),
    ("Demoró el envío", "El producto está bien pero el envío tardó más de una semana."),
]


def _texto_resena(calificacion: int, rnd: random.Random):
    if calificacion >= 4:
        return rnd.choice(RESENAS_POSITIVAS)
    if calificacion == 3:
        return rnd.choice(RESENAS_NEUTRAS)
    return rnd.choice(RESENAS_NEGATIVAS)


@transaction.atomic
def run(verbose: bool = True) -> dict:
    rnd = random.Random(26)
    ahora = timezone.now()

    Resena.objects.all().delete()
    Orden.objects.all().delete()
    Carrito.objects.all().delete()
    Producto.objects.all().delete()
    Categoria.objects.all().delete()
    Cupon.objects.all().delete()
    nombres_usuario = ["admin_tienda"] + [v[0] for v in VENDEDORES] + [f"cliente{i}" for i in range(1, 21)]
    User.objects.filter(username__in=nombres_usuario).delete()

    categorias = {
        slug: Categoria.objects.create(nombre=n, slug=slug, descripcion=d, imagen=f"{CDN}/categorias/{slug}.jpg")
        for n, slug, d in CATEGORIAS
    }

    User.objects.create_user(
        "admin_tienda", "admin@tecnomarket.pe", PASSWORD, first_name="Admin", last_name="TecnoMarket",
        is_staff=True, is_superuser=True,
    )
    vendedores = []
    for username, tienda, ruc, aprobado in VENDEDORES:
        user = User.objects.create_user(username, f"{username}@tecnomarket.pe", PASSWORD, first_name=tienda)
        vendedores.append(Vendedor.objects.create(user=user, nombre_tienda=tienda, ruc=ruc, aprobado=aprobado))
    clientes = []
    for i, (nombre, apellidos) in enumerate(NOMBRES, start=1):
        user = User.objects.create_user(
            f"cliente{i}", f"cliente{i}@correo.pe", PASSWORD, first_name=nombre, last_name=apellidos
        )
        PerfilCliente.objects.create(
            user=user, telefono=f"9{rnd.randint(10000000, 99999999)}",
            direccion=DIRECCIONES[i % len(DIRECCIONES)], distrito=DIRECCIONES[i % len(DIRECCIONES)].split(",")[-2].strip(),
        )
        clientes.append(user)

    # --- Productos (catálogo base + variantes de color/capacidad) -----------
    productos = []
    variantes = ["", " - Edición Negra", " - Edición Plata"]
    for slug, items in CATALOGO.items():
        for variante in variantes:
            for marca, modelo, precio, specs in items:
                if variante and rnd.random() < 0.45:
                    continue
                sku = f"{slug[:3].upper()}-{marca[:3].upper()}-{len(productos) + 1:04d}"
                factor = Decimal("1.00") if not variante else Decimal("1.03")
                producto = Producto.objects.create(
                    sku=sku,
                    nombre=f"{marca} {modelo}{variante}",
                    descripcion=f"{marca} {modelo}. Garantía oficial de 12 meses en Perú. Envío a todo el país.",
                    marca=marca,
                    categoria=categorias[slug],
                    vendedor=rnd.choice([None, None] + vendedores[:3]),
                    precio=redondear(Decimal(precio) * factor),
                    descuento=Decimal(rnd.choice([0, 0, 0, 5, 10, 15, 20])),
                    stock=rnd.choice([0, 3, 8, 15, 25, 40, 60]),
                    especificaciones={**specs, "garantia": "12 meses"},
                    fecha_creacion=ahora - timedelta(days=rnd.randint(1, 300)),
                )
                ImagenProducto.objects.bulk_create(
                    [
                        ImagenProducto(producto=producto, url=f"{CDN}/{sku.lower()}-{n}.jpg", alt=f"{producto.nombre} vista {n}", orden=n)
                        for n in range(1, rnd.randint(2, 4) + 1)
                    ]
                )
                productos.append(producto)
    # fecha_creacion usa auto_now_add: se ajusta para tener datos realistas
    for p in productos:
        Producto.objects.filter(pk=p.pk).update(fecha_creacion=ahora - timedelta(days=rnd.randint(1, 300)))

    Cupon.objects.create(codigo="CYBERWOW", porcentaje=15, valido_hasta=timezone.localdate() + timedelta(days=30))
    Cupon.objects.create(codigo="BLACKFRIDAY", porcentaje=20, valido_hasta=timezone.localdate() + timedelta(days=10))
    Cupon.objects.create(codigo="VENCIDO2025", porcentaje=10, valido_hasta=timezone.localdate() - timedelta(days=5))

    # --- Órdenes con snapshot de precios -----------------------------------
    distribucion = (
        [Orden.Estado.ENTREGADA] * 30 + [Orden.Estado.ENVIADA] * 12 + [Orden.Estado.PAGADA] * 12
        + [Orden.Estado.PENDIENTE] * 10 + [Orden.Estado.CANCELADA] * 6
    )
    rnd.shuffle(distribucion)
    con_stock = [p for p in productos if p.stock > 0]
    ordenes = []
    for n, estado in enumerate(distribucion):
        cliente = clientes[n % len(clientes)]
        elegidos = rnd.sample(con_stock, rnd.randint(2, 4))
        fecha = ahora - timedelta(days=rnd.randint(1, 120), hours=rnd.randint(0, 23))
        lineas = [(p, rnd.randint(1, 2)) for p in elegidos]
        subtotal = redondear(sum(p.precio_con_descuento * c for p, c in lineas))
        impuestos = redondear(subtotal * Decimal("0.18"))
        orden = Orden.objects.create(
            usuario=cliente,
            direccion_envio=cliente.perfil_cliente.direccion,
            metodo_pago=rnd.choice(Orden.MetodoPago.values),
            estado=estado,
            subtotal=subtotal,
            impuestos=impuestos,
            total=subtotal + impuestos,
            numero_seguimiento=(
                f"TM-{fecha:%Y%m%d}-{rnd.randint(0, 0xFFFFFFFF):08X}"
                if estado in (Orden.Estado.ENVIADA, Orden.Estado.ENTREGADA) else ""
            ),
            fecha_creacion=fecha,
        )
        ItemOrden.objects.bulk_create(
            [
                ItemOrden(
                    orden=orden, producto=p, vendedor=p.vendedor, sku=p.sku, nombre_producto=p.nombre,
                    precio_unitario=p.precio_con_descuento, cantidad=c,
                )
                for p, c in lineas
            ]
        )
        if estado == Orden.Estado.ENTREGADA:
            perfil = cliente.perfil_cliente
            perfil.puntos += int(orden.total // 10)
            perfil.save(update_fields=["puntos"])
        ordenes.append(orden)

    # --- Reseñas: solo de compras verificadas ------------------------------
    pares = set(
        ItemOrden.objects.filter(orden__estado__in=ESTADOS_COMPRA_VALIDA).values_list("orden__usuario_id", "producto_id")
    )
    resenas = []
    for usuario_id, producto_id in sorted(pares):
        calificacion = rnd.choices([5, 4, 3, 2, 1], weights=[45, 30, 13, 7, 5])[0]
        titulo, comentario = _texto_resena(calificacion, rnd)
        resenas.append(
            Resena(usuario_id=usuario_id, producto_id=producto_id, calificacion=calificacion, titulo=titulo, comentario=comentario)
        )
    Resena.objects.bulk_create(resenas)

    # Carrito de ejemplo para cliente1
    carrito = Carrito.objects.create(usuario=clientes[0])
    for p in con_stock[:2]:
        carrito.items.create(producto=p, cantidad=1)

    resumen = {
        "categorias": Categoria.objects.count(),
        "productos": Producto.objects.count(),
        "usuarios": 1 + len(vendedores) + len(clientes),
        "ordenes": Orden.objects.count(),
        "resenas": Resena.objects.count(),
        "cupones": Cupon.objects.count(),
    }
    if verbose:
        print(f"[tienda] {resumen}")
        print(f"[tienda] Contraseña de todos los usuarios: {PASSWORD}")
    return resumen
