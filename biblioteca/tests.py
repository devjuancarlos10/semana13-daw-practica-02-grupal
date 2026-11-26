"""Tests unitarios del Caso 1 - Biblioteca."""

from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.test import APITestCase

from .models import Autor, Libro, PerfilUsuario, Prestamo

User = get_user_model()


class BaseBibliotecaTest(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.autor = Autor.objects.create(nombre="Thomas H. Cormen", nacionalidad="Estadounidense", biografia="Prof.")
        cls.libro = Libro.objects.create(
            isbn="978-0262046305", titulo="Introducción a los Algoritmos", autor=cls.autor,
            editorial="MIT Press", anio=2022, categoria="ingenieria", stock=3, estante="A-01", piso=1,
        )
        cls.libro_agotado = Libro.objects.create(
            isbn="978-0133594140", titulo="Redes de Computadoras", autor=cls.autor,
            editorial="Pearson", anio=2015, categoria="ingenieria", stock=0, estante="A-02", piso=1,
        )
        cls.libro_mate = Libro.objects.create(
            isbn="978-6070481", titulo="Cálculo de una Variable", autor=cls.autor,
            editorial="Cengage", anio=2021, categoria="matematica", stock=2, estante="B-01", piso=2,
        )
        cls.admin = cls.crear_usuario("admin", "administrador", staff=True)
        cls.bibliotecario = cls.crear_usuario("biblio", "bibliotecario")
        cls.estudiante = cls.crear_usuario("alumno", "estudiante")
        cls.otro = cls.crear_usuario("otro", "estudiante")
        cls.docente = cls.crear_usuario("docente", "docente")

    @staticmethod
    def crear_usuario(username, tipo, staff=False):
        user = User.objects.create_user(username=username, password="ClaveSegura123", is_staff=staff, first_name=username.title())
        PerfilUsuario.objects.create(user=user, tipo=tipo, codigo=f"C-{username}", carrera="Sistemas", telefono="999888777")
        return user

    def setUp(self):
        cache.clear()  # reinicia los contadores de throttling entre tests

    def login(self, user):
        token, _ = Token.objects.get_or_create(user=user)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")


class LibroTests(BaseBibliotecaTest):
    def test_listado_publico_paginado_con_campos_calculados(self):
        r = self.client.get(reverse("libro-list"))
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data["count"], 3)
        libro = next(x for x in r.data["results"] if x["isbn"] == "978-0262046305")
        self.assertTrue(libro["disponible"])
        self.assertTrue(libro["url"].endswith(f"/api/libros/{self.libro.pk}/"))
        self.assertEqual(libro["autor"]["nacionalidad"], "Estadounidense")
        self.assertEqual(libro["ubicacion"], {"estante": "A-01", "piso": 1})

    def test_filtros_busqueda_y_ordenamiento(self):
        url = reverse("libro-list")
        self.assertEqual(self.client.get(url, {"categoria": "matematica"}).data["count"], 1)
        self.assertEqual(self.client.get(url, {"año__gte": 2020}).data["count"], 2)
        self.assertEqual(self.client.get(url, {"disponible": "false"}).data["count"], 1)
        self.assertEqual(self.client.get(url, {"search": "algoritmos"}).data["count"], 1)
        ordenados = self.client.get(url, {"ordering": "-año"}).data["results"]
        self.assertEqual([x["año"] for x in ordenados], [2022, 2021, 2015])
        por_titulo = self.client.get(url, {"ordering": "título"}).data["results"]
        self.assertEqual(por_titulo[0]["titulo"], "Cálculo de una Variable")

    def test_crear_libro_requiere_personal(self):
        datos = {
            "isbn": "978-0134685991", "titulo": "Effective Java", "autor_id": self.autor.pk, "editorial": "AW",
            "año": 2018, "categoria": "ingenieria", "stock": 2, "estante": "C-01", "piso": 3,
        }
        self.assertEqual(self.client.post(reverse("libro-list"), datos).status_code, status.HTTP_401_UNAUTHORIZED)
        self.login(self.estudiante)
        self.assertEqual(self.client.post(reverse("libro-list"), datos).status_code, status.HTTP_403_FORBIDDEN)
        self.login(self.bibliotecario)
        r = self.client.post(reverse("libro-list"), datos)
        self.assertEqual(r.status_code, status.HTTP_201_CREATED, r.data)
        self.assertEqual(r.data["autor"]["nombre"], "Thomas H. Cormen")

    def test_validaciones_isbn_y_año(self):
        self.login(self.admin)
        datos = {
            "isbn": "123", "titulo": "X", "autor_id": self.autor.pk, "editorial": "Y",
            "año": timezone.localdate().year + 1, "categoria": "ingenieria", "stock": 1, "estante": "A", "piso": 1,
        }
        r = self.client.post(reverse("libro-list"), datos)
        self.assertEqual(r.status_code, 400)
        self.assertIn("isbn", r.data)
        self.assertIn("año", r.data)

    def test_solo_admin_elimina(self):
        url = reverse("libro-detail", args=[self.libro_mate.pk])
        self.login(self.bibliotecario)
        self.assertEqual(self.client.delete(url).status_code, 403)
        self.login(self.admin)
        self.assertEqual(self.client.delete(url).status_code, 204)

    def test_bibliotecario_actualiza(self):
        self.login(self.bibliotecario)
        r = self.client.patch(reverse("libro-detail", args=[self.libro.pk]), {"stock": 10})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data["stock"], 10)


class PrestamoTests(BaseBibliotecaTest):
    def test_registrar_prestamo_descuenta_stock(self):
        self.login(self.bibliotecario)
        r = self.client.post(reverse("prestamo-list"), {"usuario": self.estudiante.pk, "libro": self.libro.pk})
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(r.data["estado"], "activo")
        self.assertEqual(r.data["dias_restantes"], 14)
        self.assertEqual(r.data["multa"], "0.00")
        self.libro.refresh_from_db()
        self.assertEqual(self.libro.stock, 2)

    def test_estudiante_no_puede_registrar(self):
        self.login(self.estudiante)
        r = self.client.post(reverse("prestamo-list"), {"usuario": self.estudiante.pk, "libro": self.libro.pk})
        self.assertEqual(r.status_code, 403)

    def test_libro_sin_stock(self):
        self.login(self.bibliotecario)
        r = self.client.post(reverse("prestamo-list"), {"usuario": self.estudiante.pk, "libro": self.libro_agotado.pk})
        self.assertEqual(r.status_code, 400)
        self.assertIn("libro", r.data)

    def test_limite_cinco_prestamos_activos(self):
        for _ in range(5):
            Prestamo.objects.create(usuario=self.estudiante, libro=self.libro_mate)
        self.login(self.bibliotecario)
        r = self.client.post(reverse("prestamo-list"), {"usuario": self.estudiante.pk, "libro": self.libro.pk})
        self.assertEqual(r.status_code, 403)
        self.assertIn("límite", str(r.data["detail"]))

    def test_devolver_restaura_stock(self):
        prestamo = Prestamo.objects.create(usuario=self.estudiante, libro=self.libro)
        self.login(self.bibliotecario)
        r = self.client.post(reverse("prestamo-devolver", args=[prestamo.pk]))
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data["estado"], "devuelto")
        self.libro.refresh_from_db()
        self.assertEqual(self.libro.stock, 4)
        self.assertEqual(self.client.post(reverse("prestamo-devolver", args=[prestamo.pk])).status_code, 400)

    def test_vencidos_y_multa(self):
        hoy = timezone.localdate()
        Prestamo.objects.create(
            usuario=self.estudiante, libro=self.libro,
            fecha_prestamo=hoy - timedelta(days=20), fecha_devolucion=hoy - timedelta(days=3),
        )
        self.login(self.bibliotecario)
        r = self.client.get(reverse("prestamo-vencidos"))
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data["count"], 1)  # LimitOffsetPagination
        item = r.data["results"][0]
        self.assertEqual(item["estado"], "vencido")
        self.assertEqual(item["multa"], "6.00")
        self.assertEqual(item["dias_restantes"], -3)

    def test_consulta_solo_propietario(self):
        propio = Prestamo.objects.create(usuario=self.estudiante, libro=self.libro)
        ajeno = Prestamo.objects.create(usuario=self.otro, libro=self.libro)
        self.login(self.estudiante)
        r = self.client.get(reverse("prestamo-list"))
        self.assertEqual([p["id"] for p in r.data["results"]], [propio.pk])
        self.assertEqual(self.client.get(reverse("prestamo-detail", args=[ajeno.pk])).status_code, 404)
        self.assertEqual(self.client.get(reverse("prestamo-vencidos")).status_code, 403)

    def test_eliminar_solo_admin_devuelve_stock(self):
        prestamo = Prestamo.objects.create(usuario=self.estudiante, libro=self.libro)
        self.login(self.bibliotecario)
        self.assertEqual(self.client.delete(reverse("prestamo-detail", args=[prestamo.pk])).status_code, 403)
        self.login(self.admin)
        self.assertEqual(self.client.delete(reverse("prestamo-detail", args=[prestamo.pk])).status_code, 204)
        self.libro.refresh_from_db()
        self.assertEqual(self.libro.stock, 4)


class UsuarioTests(BaseBibliotecaTest):
    def test_listado_solo_admin(self):
        self.login(self.estudiante)
        self.assertEqual(self.client.get(reverse("usuario-list")).status_code, 403)
        self.login(self.admin)
        r = self.client.get(reverse("usuario-list"))
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data["count"], 5)

    def test_serializacion_diferenciada(self):
        Prestamo.objects.create(usuario=self.estudiante, libro=self.libro)
        url = reverse("usuario-detail", args=[self.estudiante.pk])
        publico = self.client.get(url).data
        self.assertEqual(set(publico), {"id", "nombre", "tipo", "carrera"})
        self.login(self.estudiante)
        privado = self.client.get(url).data
        self.assertEqual(privado["prestamos_activos"], 1)
        self.assertEqual(privado["telefono"], "999888777")
        self.assertEqual(len(privado["historial_prestamos"]), 1)
        self.login(self.otro)
        self.assertNotIn("telefono", self.client.get(url).data)

    def test_perfil_y_actualizacion_propia(self):
        self.login(self.estudiante)
        r = self.client.patch(reverse("usuario-perfil"), {"telefono": "911222333"})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data["telefono"], "911222333")
        self.assertEqual(self.client.get(reverse("usuario-perfil")).data["username"], "alumno")
        # IsOwnerOrReadOnly: no puede editar a otro usuario
        r = self.client.patch(reverse("usuario-detail", args=[self.otro.pk]), {"telefono": "000"})
        self.assertEqual(r.status_code, 403)

    def test_admin_crea_usuario(self):
        self.login(self.admin)
        r = self.client.post(reverse("usuario-list"), {
            "username": "nuevo", "password": "ClaveSegura123", "tipo": "estudiante", "codigo": "2026X",
            "first_name": "Nuevo", "last_name": "Alumno", "email": "nuevo@uncp.edu.pe",
        })
        self.assertEqual(r.status_code, 201, r.data)
        self.assertTrue(PerfilUsuario.objects.filter(codigo="2026X").exists())


class DocenteTests(BaseBibliotecaTest):
    def test_reservas_solo_docentes(self):
        self.login(self.estudiante)
        self.assertEqual(self.client.post(reverse("reserva-list"), {"libro": self.libro.pk}).status_code, 403)
        self.login(self.docente)
        self.assertEqual(self.client.post(reverse("reserva-list"), {"libro": self.libro.pk}).status_code, 201)
        self.assertEqual(self.client.post(reverse("reserva-list"), {"libro": self.libro.pk}).status_code, 400)

    def test_solicitud_adquisicion(self):
        self.login(self.docente)
        r = self.client.post(reverse("adquisicion-list"), {
            "titulo": "Designing Data-Intensive Applications", "autor": "Martin Kleppmann",
            "justificacion": "Curso de arquitectura",
        })
        self.assertEqual(r.status_code, 201)
        self.login(self.admin)
        r = self.client.patch(reverse("adquisicion-detail", args=[r.data["id"]]), {"estado": "aprobada"})
        self.assertEqual(r.data["estado"], "aprobada")


class SeguridadTests(BaseBibliotecaTest):
    def test_obtener_token_y_logout(self):
        r = self.client.post(reverse("auth-token"), {"username": "alumno", "password": "ClaveSegura123"})
        self.assertEqual(r.status_code, 200)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {r.data['token']}")
        self.assertEqual(self.client.get(reverse("usuario-perfil")).status_code, 200)
        self.assertEqual(self.client.post(reverse("auth-logout")).status_code, 204)
        self.assertEqual(self.client.get(reverse("usuario-perfil")).status_code, 401)

    def test_token_expirado(self):
        token = Token.objects.create(user=self.estudiante)
        Token.objects.filter(pk=token.pk).update(created=timezone.now() - timedelta(hours=48))
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")
        r = self.client.get(reverse("usuario-perfil"))
        self.assertEqual(r.status_code, 401)
        self.assertIn("expirado", str(r.data["detail"]))

    def test_throttling_burst_devuelve_429(self):
        from rest_framework.settings import api_settings
        from rest_framework.throttling import SimpleRateThrottle

        original = SimpleRateThrottle.THROTTLE_RATES
        SimpleRateThrottle.THROTTLE_RATES = {**api_settings.DEFAULT_THROTTLE_RATES, "biblioteca_burst": "3/minute"}
        try:
            codigos = [self.client.get(reverse("libro-list")).status_code for _ in range(4)]
        finally:
            SimpleRateThrottle.THROTTLE_RATES = original
        self.assertEqual(codigos, [200, 200, 200, status.HTTP_429_TOO_MANY_REQUESTS])

    def test_cors_origen_permitido(self):
        r = self.client.get(reverse("libro-list"), HTTP_ORIGIN="https://campus.uncp.edu.pe")
        self.assertEqual(r["Access-Control-Allow-Origin"], "https://campus.uncp.edu.pe")
        self.assertEqual(r["Access-Control-Allow-Credentials"], "true")
        r = self.client.get(reverse("libro-list"), HTTP_ORIGIN="https://malicioso.com")
        self.assertNotIn("Access-Control-Allow-Origin", r)

    def test_documentacion_disponible(self):
        self.assertEqual(self.client.get(reverse("swagger-ui")).status_code, 200)
        self.assertEqual(self.client.get(reverse("schema")).status_code, 200)
