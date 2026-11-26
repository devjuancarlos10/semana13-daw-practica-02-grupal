"""Extensiones de drf-spectacular."""

from drf_spectacular.authentication import TokenScheme


class ExpiringTokenScheme(TokenScheme):
    """Documenta ExpiringTokenAuthentication igual que el TokenAuthentication de DRF."""

    target_class = "core.authentication.ExpiringTokenAuthentication"
    name = "tokenAuth"
