"""Modelos del Caso 1 - Biblioteca Central UNCP."""

from datetime import timedelta
from decimal import Decimal

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone

MULTA_POR_DIA = Decimal("2.00")  # S/ 2.00 por día de retraso
MAX_PRESTAMOS_ACTIVOS = 5
DIAS_PRESTAMO = 14


class Autor(models.Model):
    nombre = models.CharField(max_length=150)
    nacionalidad = models.CharField(max_length=80)
    biografia = models.TextField(blank=True)

    class Meta:
        ordering = ["nombre"]
        verbose_name_plural = "autores"

    def __str__(self):
        return self.nombre


class Libro(models.Model):
    class Categoria(models.TextChoices):
        INGENIERIA = "ingenieria", "Ingeniería"
        CIENCIAS = "ciencias", "Ciencias"
        MATEMATICA = "matematica", "Matemática"
        MEDICINA = "medicina", "Medicina"
        HUMANIDADES = "humanidades", "Humanidades"
        ECONOMIA = "economia", "Economía"
        EDUCACION = "educacion", "Educación"
        DERECHO = "derecho", "Derecho"

    isbn = models.CharField("ISBN", max_length=17, unique=True)
    titulo = models.CharField(max_length=200, db_index=True)
    autor = models.ForeignKey(Autor, on_delete=models.PROTECT, related_name="libros")
    editorial = models.CharField(max_length=120)
    anio = models.PositiveIntegerField("año", validators=[MinValueValidator(1450)])
    categoria = models.CharField(max_length=20, choices=Categoria.choices, db_index=True)
    stock = models.PositiveIntegerField(default=1)
    estante = models.CharField(max_length=10)
    piso = models.PositiveSmallIntegerField(validators=[MinValueValidator(1), MaxValueValidator(5)])
    fecha_registro = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["titulo"]

    def __str__(self):
        return f"{self.titulo} ({self.isbn})"

    @property
    def disponible(self) -> bool:
        return self.stock > 0


class PerfilUsuario(models.Model):
    """Datos del usuario de biblioteca asociados al ``User`` de Django."""

    class Tipo(models.TextChoices):
        ADMINISTRADOR = "administrador", "Administrador"
        BIBLIOTECARIO = "bibliotecario", "Bibliotecario"
        ESTUDIANTE = "estudiante", "Estudiante"
        DOCENTE = "docente", "Docente/Investigador"

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="perfil_biblioteca")
    tipo = models.CharField(max_length=15, choices=Tipo.choices, default=Tipo.ESTUDIANTE)
    codigo = models.CharField("código/carnet", max_length=20, unique=True)
    carrera = models.CharField(max_length=120, blank=True)
    telefono = models.CharField(max_length=15, blank=True)
    carnet_activo = models.BooleanField(default=True)

    class Meta:
        verbose_name = "perfil de usuario"
        verbose_name_plural = "perfiles de usuario"

    def __str__(self):
        return f"{self.user.get_full_name() or self.user.username} ({self.get_tipo_display()})"


class PrestamoQuerySet(models.QuerySet):
    def activos(self):
        return self.filter(estado__in=[Prestamo.Estado.ACTIVO, Prestamo.Estado.VENCIDO])

    def vencidos(self):
        return self.filter(estado=Prestamo.Estado.VENCIDO)


def fecha_devolucion_por_defecto():
    return timezone.localdate() + timedelta(days=DIAS_PRESTAMO)


class Prestamo(models.Model):
    class Estado(models.TextChoices):
        ACTIVO = "activo", "Activo"
        DEVUELTO = "devuelto", "Devuelto"
        VENCIDO = "vencido", "Vencido"

    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="prestamos")
    libro = models.ForeignKey(Libro, on_delete=models.PROTECT, related_name="prestamos")
    fecha_prestamo = models.DateField(default=timezone.localdate)
    fecha_devolucion = models.DateField(default=fecha_devolucion_por_defecto)
    fecha_entrega = models.DateField(null=True, blank=True, help_text="Fecha real de devolución")
    estado = models.CharField(max_length=10, choices=Estado.choices, default=Estado.ACTIVO, db_index=True)
    registrado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="prestamos_registrados"
    )

    objects = PrestamoQuerySet.as_manager()

    class Meta:
        ordering = ["-fecha_prestamo", "-id"]

    def __str__(self):
        return f"Préstamo #{self.pk} - {self.libro.titulo} a {self.usuario.username}"

    @classmethod
    def actualizar_vencidos(cls) -> int:
        """Marca como vencidos los préstamos activos cuya fecha ya pasó."""
        return cls.objects.filter(estado=cls.Estado.ACTIVO, fecha_devolucion__lt=timezone.localdate()).update(
            estado=cls.Estado.VENCIDO
        )

    @property
    def dias_retraso(self) -> int:
        referencia = self.fecha_entrega or timezone.localdate()
        return max((referencia - self.fecha_devolucion).days, 0)

    @property
    def dias_restantes(self) -> int:
        if self.estado == self.Estado.DEVUELTO:
            return 0
        return (self.fecha_devolucion - timezone.localdate()).days

    @property
    def multa(self) -> Decimal:
        return MULTA_POR_DIA * self.dias_retraso


class Reserva(models.Model):
    """Reserva de un libro (permiso extendido de docentes/investigadores)."""

    class Estado(models.TextChoices):
        PENDIENTE = "pendiente", "Pendiente"
        ATENDIDA = "atendida", "Atendida"
        CANCELADA = "cancelada", "Cancelada"

    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="reservas")
    libro = models.ForeignKey(Libro, on_delete=models.CASCADE, related_name="reservas")
    fecha_reserva = models.DateTimeField(auto_now_add=True)
    estado = models.CharField(max_length=10, choices=Estado.choices, default=Estado.PENDIENTE)

    class Meta:
        ordering = ["-fecha_reserva"]

    def __str__(self):
        return f"Reserva {self.libro} - {self.usuario}"


class SolicitudAdquisicion(models.Model):
    """Solicitud de compra de material bibliográfico (docentes/investigadores)."""

    class Estado(models.TextChoices):
        PENDIENTE = "pendiente", "Pendiente"
        APROBADA = "aprobada", "Aprobada"
        RECHAZADA = "rechazada", "Rechazada"

    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="solicitudes")
    titulo = models.CharField(max_length=200)
    autor = models.CharField(max_length=150)
    isbn = models.CharField(max_length=17, blank=True)
    justificacion = models.TextField()
    estado = models.CharField(max_length=10, choices=Estado.choices, default=Estado.PENDIENTE)
    fecha_solicitud = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-fecha_solicitud"]
        verbose_name = "solicitud de adquisición"
        verbose_name_plural = "solicitudes de adquisición"

    def __str__(self):
        return self.titulo
