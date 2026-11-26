"""Población automática de datos de prueba para ambos casos.

Uso:
    python manage.py migrate
    python populate_data.py              # ambos casos
    python populate_data.py biblioteca   # solo Caso 1
    python populate_data.py tienda       # solo Caso 2

El script es idempotente: puede ejecutarse varias veces.
"""

import os
import sys

import django


def main(argv: list[str]) -> None:
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    django.setup()

    from biblioteca import populate as biblioteca
    from ecommerce import populate as tienda

    casos = set(argv) or {"biblioteca", "tienda"}
    if "biblioteca" in casos:
        biblioteca.run()
    if "tienda" in casos:
        tienda.run()

    print("\nUsuarios de prueba:")
    print(f"  Caso 1 -> admin, bibliotecario1, docente1, estudiante1 ... (clave: {biblioteca.PASSWORD})")
    print(f"  Caso 2 -> admin_tienda, vendedor1, cliente1 ... (clave: {tienda.PASSWORD})")


if __name__ == "__main__":
    main(sys.argv[1:])
