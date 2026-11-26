"""
Configuración del proyecto - Práctica Grupal Semana 13 (DAW - UNCP).

Un solo proyecto Django expone dos APIs RESTful:
  * Caso 1: Biblioteca Universitaria UNCP   -> app ``biblioteca``
  * Caso 2: E-commerce TecnoMarket Perú     -> app ``ecommerce``

La app ``core`` agrupa piezas transversales (autenticación con expiración,
throttling con logs, auditoría, filtros y raíz de la API).
"""

import os
from datetime import timedelta
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent


def env_bool(nombre: str, defecto: bool = False) -> bool:
    return os.environ.get(nombre, str(defecto)).lower() in {"1", "true", "yes", "si"}


# ---------------------------------------------------------------------------
# Seguridad básica
# ---------------------------------------------------------------------------
SECRET_KEY = os.environ.get(
    "DJANGO_SECRET_KEY",
    "django-insecure-solo-para-desarrollo-cambiar-en-produccion",
)
DEBUG = env_bool("DJANGO_DEBUG", True)
ALLOWED_HOSTS = os.environ.get("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1,testserver").split(",")

# ---------------------------------------------------------------------------
# Aplicaciones
# ---------------------------------------------------------------------------
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # Terceros
    "rest_framework",
    "rest_framework.authtoken",
    "rest_framework_simplejwt",
    "django_filters",
    "corsheaders",
    "drf_spectacular",
    # Proyecto
    "core",
    "biblioteca",
    "ecommerce",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    # CORS debe ir lo más arriba posible (antes de CommonMiddleware)
    "corsheaders.middleware.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    # CSRF se mantiene activo para el admin web; los endpoints /api/ usan
    # tokens (ver core.authentication) y por tanto no dependen de CSRF.
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    # Logs de auditoría de operaciones de escritura sobre la API
    "core.middleware.AuditoriaMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
}

# Caché usada por el throttling. En producción se recomienda Redis.
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "daw-semana13",
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "es-pe"
TIME_ZONE = "America/Lima"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# ---------------------------------------------------------------------------
# Django REST Framework
# ---------------------------------------------------------------------------
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        # Token con expiración (header: "Authorization: Token <key>")
        "core.authentication.ExpiringTokenAuthentication",
        # JWT opcional para apps móviles (header: "Authorization: Bearer <jwt>")
        "rest_framework_simplejwt.authentication.JWTAuthentication",
        # Sesión para el admin web y la API navegable (requiere CSRF)
        "rest_framework.authentication.SessionAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticatedOrReadOnly",
    ],
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 20,
    "DEFAULT_FILTER_BACKENDS": [
        "django_filters.rest_framework.DjangoFilterBackend",
        "rest_framework.filters.SearchFilter",
        "core.filters.AliasOrderingFilter",
    ],
    # Cada app declara sus propias clases de throttling (los límites de cada
    # caso son distintos); aquí solo se definen las tasas por "scope".
    "DEFAULT_THROTTLE_CLASSES": [],
    "DEFAULT_THROTTLE_RATES": {
        # Endpoints de autenticación (login anónimo)
        "anon": "30/minute",
        # Caso 1 - Biblioteca
        "biblioteca_anon": "100/hour",
        "biblioteca_user": "1000/hour",
        "biblioteca_burst": "20/minute",
        # Caso 2 - E-commerce
        "tienda_anon": "60/hour",
        "tienda_user": "2000/hour",
        "tienda_checkout": "10/hour",
        "tienda_search": "100/hour",
    },
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "TEST_REQUEST_DEFAULT_FORMAT": "json",
}

# Vida útil del token DRF (tokens con expiración - requisito de seguridad)
TOKEN_EXPIRATION_HOURS = int(os.environ.get("TOKEN_EXPIRATION_HOURS", 24))

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=30),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=1),
    "AUTH_HEADER_TYPES": ("Bearer",),
}

# Secreto compartido con pasarelas de pago / logística (webhooks Caso 2)
WEBHOOK_SECRET = os.environ.get("WEBHOOK_SECRET", "webhook-secreto-desarrollo")

# ---------------------------------------------------------------------------
# Documentación OpenAPI 3.0 (drf-spectacular)
# ---------------------------------------------------------------------------
SPECTACULAR_SETTINGS = {
    "TITLE": "API Grupal Semana 13 - Biblioteca UNCP & TecnoMarket Perú",
    "DESCRIPTION": (
        "Práctica grupal de Desarrollo de Aplicaciones Web (IS093A) - UNCP.\n\n"
        "**Caso 1 - Biblioteca:** libros, autores, préstamos, usuarios, reservas y "
        "solicitudes de adquisición.\n\n"
        "**Caso 2 - TecnoMarket:** productos, categorías, carrito, órdenes, reseñas, "
        "vendedores y webhooks.\n\n"
        "Autenticación: `Authorization: Token <key>` (POST /api/auth/token/) o "
        "`Authorization: Bearer <jwt>` (POST /api/auth/jwt/)."
    ),
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
    "COMPONENT_SPLIT_REQUEST": True,
    "SCHEMA_PATH_PREFIX": r"/api/",
    # Nombres claros para los enums "estado" de distintos modelos
    "ENUM_NAME_OVERRIDES": {
        "EstadoPrestamoEnum": "biblioteca.models.Prestamo.Estado",
        "EstadoReservaEnum": "biblioteca.models.Reserva.Estado",
        "EstadoSolicitudEnum": "biblioteca.models.SolicitudAdquisicion.Estado",
        "EstadoOrdenEnum": "ecommerce.models.Orden.Estado",
    },
    "TAGS": [
        {"name": "auth", "description": "Obtención y revocación de tokens"},
        {"name": "biblioteca", "description": "Caso 1 - Biblioteca Central UNCP"},
        {"name": "tienda", "description": "Caso 2 - TecnoMarket Perú"},
    ],
}

# ---------------------------------------------------------------------------
# CORS (orígenes específicos de ambos casos)
# ---------------------------------------------------------------------------
CORS_ALLOWED_ORIGINS = [
    # Caso 1
    "https://campus.uncp.edu.pe",
    "https://app-movil.uncp.edu.pe",
    # Caso 2
    "https://tecnomarket.pe",
    "https://app.tecnomarket.pe",
    "https://admin.tecnomarket.pe",
]
if DEBUG:
    # Front-ends locales durante el desarrollo
    CORS_ALLOWED_ORIGINS += ["http://localhost:3000", "http://localhost:5173"]
CORS_ALLOW_CREDENTIALS = True
CORS_URLS_REGEX = r"^/api/.*$"

# ---------------------------------------------------------------------------
# HTTPS obligatorio en producción
# ---------------------------------------------------------------------------
if not DEBUG:
    SECURE_SSL_REDIRECT = True
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = 31536000
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_CONTENT_TYPE_NOSNIFF = True

# ---------------------------------------------------------------------------
# Logging: throttling (monitoreo) y auditoría
# ---------------------------------------------------------------------------
LOGS_DIR = BASE_DIR / "logs"
LOGS_DIR.mkdir(exist_ok=True)

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "simple": {"format": "[{asctime}] {levelname} {name}: {message}", "style": "{"},
    },
    "handlers": {
        "console": {"class": "logging.StreamHandler", "formatter": "simple"},
        "throttling_file": {
            "class": "logging.FileHandler",
            "filename": LOGS_DIR / "throttling.log",
            "formatter": "simple",
            "encoding": "utf-8",
        },
        "auditoria_file": {
            "class": "logging.FileHandler",
            "filename": LOGS_DIR / "auditoria.log",
            "formatter": "simple",
            "encoding": "utf-8",
        },
    },
    "loggers": {
        "api.throttling": {"handlers": ["console", "throttling_file"], "level": "WARNING", "propagate": False},
        "api.auditoria": {"handlers": ["auditoria_file"], "level": "INFO", "propagate": False},
    },
}
