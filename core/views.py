"""Vistas transversales: raíz de la API y autenticación."""

from django.conf import settings
from django.contrib.auth import authenticate
from django.urls import NoReverseMatch
from drf_spectacular.utils import OpenApiExample, extend_schema, inline_serializer
from rest_framework import permissions, serializers, status
from rest_framework.authtoken.models import Token
from rest_framework.response import Response
from rest_framework.reverse import reverse
from rest_framework.views import APIView

from .authentication import token_expirado
from .throttling import LoggingAnonRateThrottle


class ApiRootView(APIView):
    """Punto de entrada (HATEOAS): enlaces a todos los recursos de la API."""

    permission_classes = [permissions.AllowAny]

    @extend_schema(exclude=True)
    def get(self, request, format=None):
        from biblioteca.urls import router as router_biblioteca
        from ecommerce.urls import router as router_tienda

        def enlaces(router):
            resultado = {}
            for prefijo, _viewset, basename in router.registry:
                try:
                    resultado[prefijo] = reverse(f"{basename}-list", request=request, format=format)
                except NoReverseMatch:  # viewsets sin ruta "list" (p. ej. webhooks)
                    continue
            return resultado

        return Response(
            {
                "biblioteca": enlaces(router_biblioteca),
                "tienda": enlaces(router_tienda),
                "auth": {
                    "token": reverse("auth-token", request=request, format=format),
                    "logout": reverse("auth-logout", request=request, format=format),
                    "jwt": reverse("jwt-obtain", request=request, format=format),
                    "jwt_refresh": reverse("jwt-refresh", request=request, format=format),
                },
                "docs": {
                    "swagger": reverse("swagger-ui", request=request, format=format),
                    "redoc": reverse("redoc", request=request, format=format),
                    "schema": reverse("schema", request=request, format=format),
                },
            }
        )


class LoginSerializer(serializers.Serializer):
    username = serializers.CharField()
    password = serializers.CharField(write_only=True, style={"input_type": "password"})


class ObtenerTokenView(APIView):
    """Devuelve un token DRF. Si el anterior expiró, genera uno nuevo."""

    permission_classes = [permissions.AllowAny]
    authentication_classes = []
    throttle_classes = [LoggingAnonRateThrottle]
    serializer_class = LoginSerializer

    @extend_schema(
        tags=["auth"],
        request=LoginSerializer,
        responses={
            200: inline_serializer(
                "TokenRespuesta",
                {
                    "token": serializers.CharField(),
                    "usuario": serializers.CharField(),
                    "expira_en_horas": serializers.IntegerField(),
                },
            )
        },
        examples=[
            OpenApiExample("Login", value={"username": "admin", "password": "admin123"}, request_only=True),
            OpenApiExample(
                "Token emitido",
                value={"token": "9944b09199c62bcf9418ad846dd0e4bbdfc6ee4b", "usuario": "admin", "expira_en_horas": 24},
                response_only=True,
            ),
        ],
    )
    def post(self, request):
        datos = LoginSerializer(data=request.data)
        datos.is_valid(raise_exception=True)
        user = authenticate(
            request,
            username=datos.validated_data["username"],
            password=datos.validated_data["password"],
        )
        if user is None or not user.is_active:
            return Response({"detail": "Credenciales inválidas."}, status=status.HTTP_400_BAD_REQUEST)
        token, creado = Token.objects.get_or_create(user=user)
        if not creado and token_expirado(token):
            token.delete()
            token = Token.objects.create(user=user)
        return Response(
            {"token": token.key, "usuario": user.username, "expira_en_horas": settings.TOKEN_EXPIRATION_HOURS}
        )


class LogoutView(APIView):
    """Revoca el token DRF del usuario autenticado."""

    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(tags=["auth"], request=None, responses={204: None})
    def post(self, request):
        Token.objects.filter(user=request.user).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
