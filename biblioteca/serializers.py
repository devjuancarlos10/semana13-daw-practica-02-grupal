"""Serializadores del Caso 1 - Biblioteca."""

import re

from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import F
from django.utils import timezone
from drf_spectacular.utils import OpenApiExample, extend_schema_serializer
from rest_framework import serializers

from .models import (
    MAX_PRESTAMOS_ACTIVOS,
    Autor,
    Libro,
    PerfilUsuario,
    Prestamo,
    Reserva,
    SolicitudAdquisicion,
)

User = get_user_model()


# ---------------------------------------------------------------------------
# Autores y libros
# ---------------------------------------------------------------------------
class AutorSerializer(serializers.HyperlinkedModelSerializer):
    url = serializers.HyperlinkedIdentityField(view_name="autor-detail")
    total_libros = serializers.IntegerField(read_only=True, required=False)

    class Meta:
        model = Autor
        fields = ["id", "url", "nombre", "nacionalidad", "biografia", "total_libros"]


@extend_schema_serializer(
    examples=[
        OpenApiExample(
            "Crear libro",
            request_only=True,
            value={
                "isbn": "978-0262046305",
                "titulo": "Introduction to Algorithms",
                "autor_id": 1,
                "editorial": "MIT Press",
                "año": 2022,
                "categoria": "ingenieria",
                "stock": 4,
                "estante": "A-12",
                "piso": 2,
            },
        ),
        OpenApiExample(
            "Libro (respuesta)",
            response_only=True,
            value={
                "id": 1,
                "url": "http://127.0.0.1:8000/api/libros/1/",
                "isbn": "978-0262046305",
                "titulo": "Introduction to Algorithms",
                "autor": {
                    "id": 1,
                    "url": "http://127.0.0.1:8000/api/autores/1/",
                    "nombre": "Thomas H. Cormen",
                    "nacionalidad": "Estadounidense",
                    "biografia": "Profesor de ciencias de la computación en Dartmouth.",
                },
                "editorial": "MIT Press",
                "año": 2022,
                "categoria": "ingenieria",
                "stock": 4,
                "disponible": True,
                "ubicacion": {"estante": "A-12", "piso": 2},
            },
        ),
    ]
)
class LibroSerializer(serializers.ModelSerializer):
    """Serialización avanzada: HATEOAS, autor anidado y campo calculado."""

    url = serializers.HyperlinkedIdentityField(view_name="libro-detail")
    # Nested serialization (lectura) + id para escritura
    autor = AutorSerializer(read_only=True)
    autor_id = serializers.PrimaryKeyRelatedField(queryset=Autor.objects.all(), source="autor", write_only=True)
    año = serializers.IntegerField(source="anio", min_value=1450)
    # Campo calculado: stock > 0
    disponible = serializers.SerializerMethodField()
    ubicacion = serializers.SerializerMethodField()

    class Meta:
        model = Libro
        fields = [
            "id",
            "url",
            "isbn",
            "titulo",
            "autor",
            "autor_id",
            "editorial",
            "año",
            "categoria",
            "stock",
            "disponible",
            "estante",
            "piso",
            "ubicacion",
        ]
        extra_kwargs = {"estante": {"write_only": True}, "piso": {"write_only": True}}

    def get_disponible(self, obj) -> bool:
        return obj.stock > 0

    def get_ubicacion(self, obj) -> dict:
        return {"estante": obj.estante, "piso": obj.piso}

    def validate_isbn(self, value: str) -> str:
        digitos = re.sub(r"[-\s]", "", value)
        if not re.fullmatch(r"\d{9}[\dXx]|\d{13}", digitos):
            raise serializers.ValidationError("El ISBN debe tener 10 o 13 dígitos (se permiten guiones).")
        return value

    def validate_año(self, value: int) -> int:
        if value > timezone.localdate().year:
            raise serializers.ValidationError("El año de publicación no puede ser futuro.")
        return value


class LibroResumenSerializer(serializers.ModelSerializer):
    url = serializers.HyperlinkedIdentityField(view_name="libro-detail")

    class Meta:
        model = Libro
        fields = ["id", "url", "isbn", "titulo"]


# ---------------------------------------------------------------------------
# Préstamos
# ---------------------------------------------------------------------------
@extend_schema_serializer(
    examples=[
        OpenApiExample(
            "Registrar préstamo",
            request_only=True,
            value={"usuario": 5, "libro": 12, "fecha_devolucion": "2026-12-10"},
        ),
        OpenApiExample(
            "Préstamo (respuesta)",
            response_only=True,
            value={
                "id": 31,
                "url": "http://127.0.0.1:8000/api/prestamos/31/",
                "usuario": 5,
                "usuario_nombre": "María Quispe",
                "libro": 12,
                "libro_detalle": {"id": 12, "url": "http://127.0.0.1:8000/api/libros/12/", "isbn": "978-6123040116", "titulo": "Cálculo Diferencial"},
                "fecha_prestamo": "2026-11-26",
                "fecha_devolucion": "2026-12-10",
                "fecha_entrega": None,
                "estado": "activo",
                "dias_restantes": 14,
                "multa": "0.00",
            },
        ),
    ]
)
class PrestamoSerializer(serializers.ModelSerializer):
    url = serializers.HyperlinkedIdentityField(view_name="prestamo-detail")
    usuario = serializers.PrimaryKeyRelatedField(queryset=User.objects.all())
    usuario_nombre = serializers.SerializerMethodField()
    libro_detalle = LibroResumenSerializer(source="libro", read_only=True)
    dias_restantes = serializers.SerializerMethodField()
    # Campo calculado: S/ 2.00 por cada día de retraso (propiedad del modelo)
    multa = serializers.DecimalField(max_digits=8, decimal_places=2, read_only=True)

    class Meta:
        model = Prestamo
        fields = [
            "id",
            "url",
            "usuario",
            "usuario_nombre",
            "libro",
            "libro_detalle",
            "fecha_prestamo",
            "fecha_devolucion",
            "fecha_entrega",
            "estado",
            "dias_restantes",
            "multa",
        ]
        read_only_fields = ["fecha_prestamo", "fecha_entrega", "estado"]

    def get_usuario_nombre(self, obj) -> str:
        return obj.usuario.get_full_name() or obj.usuario.username

    def get_dias_restantes(self, obj) -> int:
        """fecha_devolucion - hoy (negativo si está vencido, 0 si ya se devolvió)."""
        return obj.dias_restantes

    # --- Validaciones de negocio --------------------------------------------
    def validate_usuario(self, usuario):
        perfil = getattr(usuario, "perfil_biblioteca", None)
        if perfil is not None and not perfil.carnet_activo:
            raise serializers.ValidationError("El usuario no tiene el carnet activo.")
        if self.instance is None:
            activos = Prestamo.objects.activos().filter(usuario=usuario).count()
            if activos >= MAX_PRESTAMOS_ACTIVOS:
                raise serializers.ValidationError(
                    f"El usuario ya tiene {activos} préstamos activos (máximo {MAX_PRESTAMOS_ACTIVOS})."
                )
        return usuario

    def validate_libro(self, libro):
        if self.instance is None and libro.stock <= 0:
            raise serializers.ValidationError("El libro no tiene stock disponible.")
        return libro

    def validate(self, attrs):
        if self.instance is not None:
            for campo in ("usuario", "libro"):
                if campo in attrs and attrs[campo] != getattr(self.instance, campo):
                    raise serializers.ValidationError({campo: "No se puede cambiar en un préstamo existente."})
        fecha_dev = attrs.get("fecha_devolucion")
        inicio = self.instance.fecha_prestamo if self.instance else timezone.localdate()
        if fecha_dev and fecha_dev <= inicio:
            raise serializers.ValidationError({"fecha_devolucion": "Debe ser posterior a la fecha de préstamo."})
        return attrs

    @transaction.atomic
    def create(self, validated_data):
        libro = Libro.objects.select_for_update().get(pk=validated_data["libro"].pk)
        if libro.stock <= 0:
            raise serializers.ValidationError({"libro": "El libro no tiene stock disponible."})
        Libro.objects.filter(pk=libro.pk).update(stock=F("stock") - 1)
        return super().create(validated_data)


class PrestamoHistorialSerializer(serializers.ModelSerializer):
    """Versión compacta para el historial dentro del perfil privado."""

    libro = serializers.CharField(source="libro.titulo")
    multa = serializers.DecimalField(max_digits=8, decimal_places=2, read_only=True)

    class Meta:
        model = Prestamo
        fields = ["id", "libro", "fecha_prestamo", "fecha_devolucion", "fecha_entrega", "estado", "multa"]


# ---------------------------------------------------------------------------
# Usuarios (serialización diferenciada)
# ---------------------------------------------------------------------------
class UsuarioPublicoSerializer(serializers.ModelSerializer):
    """Vista pública: solo nombre, tipo y carrera."""

    nombre = serializers.SerializerMethodField()
    tipo = serializers.CharField(source="perfil_biblioteca.tipo", read_only=True, default=None)
    carrera = serializers.CharField(source="perfil_biblioteca.carrera", read_only=True, default="")

    class Meta:
        model = User
        fields = ["id", "nombre", "tipo", "carrera"]

    def get_nombre(self, obj) -> str:
        return obj.get_full_name() or obj.username


class UsuarioPrivadoSerializer(UsuarioPublicoSerializer):
    """Vista privada (propio usuario o admin): contacto e historial."""

    url = serializers.HyperlinkedIdentityField(view_name="usuario-detail")
    telefono = serializers.CharField(source="perfil_biblioteca.telefono", read_only=True, default="")
    codigo = serializers.CharField(source="perfil_biblioteca.codigo", read_only=True, default="")
    carnet_activo = serializers.BooleanField(source="perfil_biblioteca.carnet_activo", read_only=True, default=False)
    prestamos_activos = serializers.IntegerField(read_only=True)
    historial_prestamos = PrestamoHistorialSerializer(source="prestamos", many=True, read_only=True)

    class Meta(UsuarioPublicoSerializer.Meta):
        fields = [
            "id",
            "url",
            "username",
            "nombre",
            "email",
            "telefono",
            "tipo",
            "carrera",
            "codigo",
            "carnet_activo",
            "prestamos_activos",
            "historial_prestamos",
        ]
        read_only_fields = ["username"]


class UsuarioCrearSerializer(serializers.ModelSerializer):
    """Alta de usuarios de biblioteca (solo administrador)."""

    password = serializers.CharField(write_only=True, min_length=8)
    tipo = serializers.ChoiceField(choices=PerfilUsuario.Tipo.choices, write_only=True)
    codigo = serializers.CharField(write_only=True)
    carrera = serializers.CharField(write_only=True, required=False, allow_blank=True)
    telefono = serializers.CharField(write_only=True, required=False, allow_blank=True)

    class Meta:
        model = User
        fields = ["id", "username", "password", "first_name", "last_name", "email", "tipo", "codigo", "carrera", "telefono"]

    def validate_codigo(self, value):
        if PerfilUsuario.objects.filter(codigo=value).exists():
            raise serializers.ValidationError("Ya existe un usuario con ese código.")
        return value

    @transaction.atomic
    def create(self, validated_data):
        perfil = {k: validated_data.pop(k, "") for k in ("tipo", "codigo", "carrera", "telefono")}
        user = User.objects.create_user(**validated_data)
        PerfilUsuario.objects.create(user=user, **perfil)
        return user


class PerfilActualizarSerializer(serializers.Serializer):
    """Datos que el propio usuario puede actualizar (IsOwnerOrReadOnly)."""

    email = serializers.EmailField(required=False)
    telefono = serializers.CharField(required=False, allow_blank=True, max_length=15)
    carrera = serializers.CharField(required=False, allow_blank=True, max_length=120)

    def update(self, instance, validated_data):
        if "email" in validated_data:
            instance.email = validated_data["email"]
            instance.save(update_fields=["email"])
        perfil, _ = PerfilUsuario.objects.get_or_create(user=instance, defaults={"codigo": f"U{instance.pk:06d}"})
        for campo in ("telefono", "carrera"):
            if campo in validated_data:
                setattr(perfil, campo, validated_data[campo])
        perfil.save()
        return instance


# ---------------------------------------------------------------------------
# Reservas y adquisiciones (docentes/investigadores)
# ---------------------------------------------------------------------------
class ReservaSerializer(serializers.ModelSerializer):
    url = serializers.HyperlinkedIdentityField(view_name="reserva-detail")
    usuario = serializers.HiddenField(default=serializers.CurrentUserDefault())
    libro_detalle = LibroResumenSerializer(source="libro", read_only=True)

    class Meta:
        model = Reserva
        fields = ["id", "url", "usuario", "libro", "libro_detalle", "fecha_reserva", "estado"]
        read_only_fields = ["fecha_reserva", "estado"]

    def validate(self, attrs):
        if Reserva.objects.filter(
            usuario=attrs["usuario"], libro=attrs["libro"], estado=Reserva.Estado.PENDIENTE
        ).exists():
            raise serializers.ValidationError("Ya tiene una reserva pendiente para este libro.")
        return attrs


class SolicitudAdquisicionSerializer(serializers.ModelSerializer):
    url = serializers.HyperlinkedIdentityField(view_name="adquisicion-detail")
    usuario = serializers.HiddenField(default=serializers.CurrentUserDefault())
    solicitante = serializers.CharField(source="usuario.username", read_only=True)

    class Meta:
        model = SolicitudAdquisicion
        fields = ["id", "url", "usuario", "solicitante", "titulo", "autor", "isbn", "justificacion", "estado", "fecha_solicitud"]
        read_only_fields = ["estado", "fecha_solicitud"]
