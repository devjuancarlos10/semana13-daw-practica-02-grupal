"""Autenticación por token con expiración.

DRF trae ``TokenAuthentication`` pero sus tokens no caducan. Para cumplir el
requisito no funcional de "tokens con expiración" se extiende la clase base
y se invalida el token cuando supera ``TOKEN_EXPIRATION_HOURS``.
"""

from datetime import timedelta

from django.conf import settings
from django.utils import timezone
from rest_framework.authentication import TokenAuthentication
from rest_framework.exceptions import AuthenticationFailed


def token_expirado(token) -> bool:
    vida = timedelta(hours=settings.TOKEN_EXPIRATION_HOURS)
    return token.created < timezone.now() - vida


class ExpiringTokenAuthentication(TokenAuthentication):
    """``Authorization: Token <key>`` con caducidad configurable."""

    def authenticate_credentials(self, key):
        user, token = super().authenticate_credentials(key)
        if token_expirado(token):
            token.delete()
            raise AuthenticationFailed("El token ha expirado. Solicite uno nuevo en /api/auth/token/.")
        return user, token
