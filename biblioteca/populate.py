"""Datos de prueba del Caso 1 - Biblioteca.

Genera como mínimo: 55 libros, 25 autores, 12 usuarios y 35 préstamos
(activos, devueltos y vencidos) más reservas y solicitudes. Es idempotente:
borra los datos previos de la app antes de volver a poblar.
"""

import random
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone

from .models import Autor, Libro, PerfilUsuario, Prestamo, Reserva, SolicitudAdquisicion

User = get_user_model()
PASSWORD = "Biblioteca2026!"

AUTORES = [
    ("Thomas H. Cormen", "Estadounidense", "Profesor de Dartmouth, coautor del clásico CLRS de algoritmos."),
    ("Andrew S. Tanenbaum", "Neerlandés-estadounidense", "Creador de MINIX, referente en sistemas operativos y redes."),
    ("Ian Sommerville", "Británico", "Profesor emérito de ingeniería de software en St Andrews."),
    ("Roger S. Pressman", "Estadounidense", "Consultor y autor de referencia en ingeniería de software."),
    ("Abraham Silberschatz", "Israelí-estadounidense", "Profesor de Yale, especialista en bases de datos y SO."),
    ("Robert C. Martin", "Estadounidense", "Conocido como 'Uncle Bob', autor de Clean Code."),
    ("Martin Fowler", "Británico", "Experto en refactorización, arquitectura y metodologías ágiles."),
    ("James Stewart", "Canadiense", "Matemático, autor de la serie de textos de Cálculo más usada."),
    ("Eduardo Espinoza Ramos", "Peruano", "Matemático peruano, autor de textos de análisis matemático."),
    ("Raymond A. Serway", "Estadounidense", "Físico y autor de Física para Ciencias e Ingeniería."),
    ("Mario Vargas Llosa", "Peruano", "Premio Nobel de Literatura 2010."),
    ("José María Arguedas", "Peruano", "Novelista y antropólogo, figura del indigenismo peruano."),
    ("César Vallejo", "Peruano", "Poeta vanguardista, autor de Trilce y Los heraldos negros."),
    ("Gabriel García Márquez", "Colombiano", "Premio Nobel de Literatura 1982."),
    ("Paul Samuelson", "Estadounidense", "Premio Nobel de Economía 1970."),
    ("N. Gregory Mankiw", "Estadounidense", "Profesor de Harvard, autor de Principios de Economía."),
    ("Paulo Freire", "Brasileño", "Pedagogo, autor de Pedagogía del oprimido."),
    ("Arthur C. Guyton", "Estadounidense", "Fisiólogo, autor del Tratado de Fisiología Médica."),
    ("Frank H. Netter", "Estadounidense", "Médico e ilustrador del Atlas de Anatomía Humana."),
    ("Marcial Rubio Correa", "Peruano", "Jurista, autor de El Sistema Jurídico."),
    ("Stuart Russell", "Británico", "Profesor de Berkeley, coautor de IA: Un enfoque moderno."),
    ("Aurélien Géron", "Francés", "Autor de Hands-On Machine Learning."),
    ("Douglas C. Montgomery", "Estadounidense", "Estadístico, autor de Diseño y análisis de experimentos."),
    ("Hamdy A. Taha", "Egipcio-estadounidense", "Autor de Investigación de Operaciones."),
    ("Kenneth C. Laudon", "Estadounidense", "Autor de Sistemas de Información Gerencial."),
]

LIBROS = [
    ("Introducción a los Algoritmos", 0, "MIT Press", 2022, "ingenieria"),
    ("Redes de Computadoras", 1, "Pearson", 2021, "ingenieria"),
    ("Sistemas Operativos Modernos", 1, "Pearson", 2015, "ingenieria"),
    ("Ingeniería de Software", 2, "Pearson", 2016, "ingenieria"),
    ("Ingeniería del Software: Un Enfoque Práctico", 3, "McGraw-Hill", 2020, "ingenieria"),
    ("Fundamentos de Bases de Datos", 4, "McGraw-Hill", 2019, "ingenieria"),
    ("Fundamentos de Sistemas Operativos", 4, "McGraw-Hill", 2018, "ingenieria"),
    ("Código Limpio", 5, "Anaya Multimedia", 2012, "ingenieria"),
    ("Arquitectura Limpia", 5, "Anaya Multimedia", 2018, "ingenieria"),
    ("Refactoring", 6, "Addison-Wesley", 2018, "ingenieria"),
    ("Patrones de Arquitectura de Aplicaciones Empresariales", 6, "Addison-Wesley", 2002, "ingenieria"),
    ("Inteligencia Artificial: Un Enfoque Moderno", 20, "Pearson", 2021, "ingenieria"),
    ("Aprendizaje Automático con Scikit-Learn y TensorFlow", 21, "O'Reilly", 2023, "ingenieria"),
    ("Sistemas de Información Gerencial", 24, "Pearson", 2020, "ingenieria"),
    ("Investigación de Operaciones", 23, "Pearson", 2017, "ingenieria"),
    ("Algoritmos en Python", 0, "MIT Press", 2024, "ingenieria"),
    ("Cálculo de una Variable", 7, "Cengage", 2021, "matematica"),
    ("Cálculo de Varias Variables", 7, "Cengage", 2021, "matematica"),
    ("Precálculo", 7, "Cengage", 2017, "matematica"),
    ("Análisis Matemático I", 8, "Editorial Servicios Gráficos", 2012, "matematica"),
    ("Análisis Matemático II", 8, "Editorial Servicios Gráficos", 2012, "matematica"),
    ("Ecuaciones Diferenciales y sus Aplicaciones", 8, "Editorial Servicios Gráficos", 2010, "matematica"),
    ("Probabilidad y Estadística Aplicadas a la Ingeniería", 22, "Limusa Wiley", 2015, "matematica"),
    ("Diseño y Análisis de Experimentos", 22, "Limusa Wiley", 2019, "matematica"),
    ("Física para Ciencias e Ingeniería Vol. 1", 9, "Cengage", 2019, "ciencias"),
    ("Física para Ciencias e Ingeniería Vol. 2", 9, "Cengage", 2019, "ciencias"),
    ("Física Moderna", 9, "Cengage", 2014, "ciencias"),
    ("La Ciudad y los Perros", 10, "Alfaguara", 2012, "humanidades"),
    ("Conversación en La Catedral", 10, "Alfaguara", 2010, "humanidades"),
    ("La Fiesta del Chivo", 10, "Alfaguara", 2000, "humanidades"),
    ("Los Ríos Profundos", 11, "Editorial Losada", 2011, "humanidades"),
    ("Todas las Sangres", 11, "Editorial Losada", 2001, "humanidades"),
    ("El Zorro de Arriba y el Zorro de Abajo", 11, "Editorial Losada", 1990, "humanidades"),
    ("Los Heraldos Negros", 12, "Ediciones Copé", 2018, "humanidades"),
    ("Trilce", 12, "Ediciones Copé", 2019, "humanidades"),
    ("Cien Años de Soledad", 13, "Penguin Random House", 2017, "humanidades"),
    ("El Amor en los Tiempos del Cólera", 13, "Penguin Random House", 2015, "humanidades"),
    ("Economía", 14, "McGraw-Hill", 2010, "economia"),
    ("Principios de Economía", 15, "Cengage", 2020, "economia"),
    ("Macroeconomía", 15, "Antoni Bosch", 2021, "economia"),
    ("Pedagogía del Oprimido", 16, "Siglo XXI", 2005, "educacion"),
    ("Pedagogía de la Autonomía", 16, "Siglo XXI", 2004, "educacion"),
    ("La Educación como Práctica de la Libertad", 16, "Siglo XXI", 2009, "educacion"),
    ("Tratado de Fisiología Médica", 17, "Elsevier", 2021, "medicina"),
    ("Atlas de Anatomía Humana", 18, "Elsevier", 2023, "medicina"),
    ("Fisiología Humana: Casos Clínicos", 17, "Elsevier", 2016, "medicina"),
    ("El Sistema Jurídico", 19, "Fondo Editorial PUCP", 2020, "derecho"),
    ("Estudio de la Constitución Política de 1993", 19, "Fondo Editorial PUCP", 2018, "derecho"),
    ("Para Leer el Código Civil", 19, "Fondo Editorial PUCP", 2015, "derecho"),
    ("Teoría General del Proceso", 19, "Fondo Editorial PUCP", 2017, "derecho"),
    ("Redes de Computadoras: Un Enfoque Descendente", 1, "Pearson", 2022, "ingenieria"),
    ("Sistemas Distribuidos", 1, "Pearson", 2017, "ingenieria"),
    ("UML Gota a Gota", 6, "Addison-Wesley", 2004, "ingenieria"),
    ("El Programador Ágil", 5, "Anaya Multimedia", 2011, "ingenieria"),
    ("Cálculo Vectorial", 7, "Cengage", 2016, "matematica"),
]

USUARIOS = [
    # username, nombres, apellidos, tipo, carrera, staff
    ("admin", "Rosa", "Huamán Ccori", "administrador", "Dirección de Biblioteca", True),
    ("bibliotecario1", "Luis", "Paucar Rojas", "bibliotecario", "Atención al Usuario", False),
    ("bibliotecario2", "Carmen", "Ticse Ore", "bibliotecario", "Atención al Usuario", False),
    ("docente1", "Jorge", "Ramos Inga", "docente", "Ingeniería de Sistemas", False),
    ("docente2", "Patricia", "Baquerizo Cárdenas", "docente", "Educación", False),
    ("estudiante1", "María", "Quispe Mamani", "estudiante", "Ingeniería de Sistemas", False),
    ("estudiante2", "Carlos", "Poma Huaranga", "estudiante", "Ingeniería de Sistemas", False),
    ("estudiante3", "Lucía", "Orihuela Vílchez", "estudiante", "Medicina Humana", False),
    ("estudiante4", "Diego", "Canchari Soto", "estudiante", "Economía", False),
    ("estudiante5", "Valeria", "Rojas Laureano", "estudiante", "Derecho", False),
    ("estudiante6", "Kevin", "Hinostroza Meza", "estudiante", "Ingeniería Civil", False),
    ("estudiante7", "Andrea", "Zevallos Cerrón", "estudiante", "Educación", False),
]


@transaction.atomic
def run(verbose: bool = True) -> dict:
    rnd = random.Random(13)
    hoy = timezone.localdate()

    Prestamo.objects.all().delete()
    Reserva.objects.all().delete()
    SolicitudAdquisicion.objects.all().delete()
    Libro.objects.all().delete()
    Autor.objects.all().delete()
    PerfilUsuario.objects.all().delete()
    User.objects.filter(username__in=[u[0] for u in USUARIOS]).delete()

    autores = [Autor.objects.create(nombre=n, nacionalidad=nac, biografia=bio) for n, nac, bio in AUTORES]

    libros = []
    for i, (titulo, autor_idx, editorial, anio, categoria) in enumerate(LIBROS):
        libros.append(
            Libro.objects.create(
                isbn=f"978-612-{4000 + i:04d}-{rnd.randint(10, 99)}-{i % 10}",
                titulo=titulo,
                autor=autores[autor_idx],
                editorial=editorial,
                anio=anio,
                categoria=categoria,
                stock=0 if i % 11 == 0 else rnd.randint(2, 8),
                estante=f"{'ABCDEFGH'[i % 8]}-{rnd.randint(1, 30):02d}",
                piso=(i % 4) + 1,
            )
        )

    usuarios = {}
    for i, (username, nombres, apellidos, tipo, carrera, staff) in enumerate(USUARIOS):
        user = User.objects.create_user(
            username=username,
            password=PASSWORD,
            first_name=nombres,
            last_name=apellidos,
            email=f"{username}@uncp.edu.pe",
            is_staff=staff,
            is_superuser=staff,
        )
        PerfilUsuario.objects.create(
            user=user,
            tipo=tipo,
            codigo=f"2026{i:04d}A",
            carrera=carrera,
            telefono=f"9{rnd.randint(10000000, 99999999)}",
        )
        usuarios[username] = user

    lectores = [u for n, u in usuarios.items() if n.startswith(("estudiante", "docente"))]
    staff = usuarios["bibliotecario1"]
    prestables = [lb for lb in libros if lb.stock > 0]
    conteo = {"activo": 0, "devuelto": 0, "vencido": 0}

    for i in range(36):
        usuario = lectores[i % len(lectores)]
        libro = prestables[(i * 7) % len(prestables)]
        if i % 3 == 0:  # devuelto (algunos con retraso -> multa histórica)
            inicio = hoy - timedelta(days=rnd.randint(30, 90))
            fin = inicio + timedelta(days=14)
            entrega = fin + timedelta(days=rnd.choice([0, 0, 2, 5]))
            estado = Prestamo.Estado.DEVUELTO
        elif i % 3 == 1:  # vencido
            inicio = hoy - timedelta(days=rnd.randint(20, 40))
            fin = inicio + timedelta(days=14)
            entrega = None
            estado = Prestamo.Estado.VENCIDO
        else:  # activo
            inicio = hoy - timedelta(days=rnd.randint(0, 10))
            fin = inicio + timedelta(days=14)
            entrega = None
            estado = Prestamo.Estado.ACTIVO
        if estado != Prestamo.Estado.DEVUELTO and Prestamo.objects.activos().filter(usuario=usuario).count() >= 5:
            estado, entrega = Prestamo.Estado.DEVUELTO, fin
        Prestamo.objects.create(
            usuario=usuario,
            libro=libro,
            fecha_prestamo=inicio,
            fecha_devolucion=fin,
            fecha_entrega=entrega,
            estado=estado,
            registrado_por=staff,
        )
        if estado != Prestamo.Estado.DEVUELTO:
            libro.stock -= 1
            libro.save(update_fields=["stock"])
            if libro.stock == 0:
                prestables.remove(libro)
        conteo[estado] += 1

    for docente in (usuarios["docente1"], usuarios["docente2"]):
        for libro in rnd.sample(libros, 3):
            Reserva.objects.create(usuario=docente, libro=libro)
    SolicitudAdquisicion.objects.create(
        usuario=usuarios["docente1"],
        titulo="Designing Data-Intensive Applications",
        autor="Martin Kleppmann",
        isbn="978-1449373320",
        justificacion="Bibliografía del curso de Arquitectura de Software (IS093A).",
    )
    SolicitudAdquisicion.objects.create(
        usuario=usuarios["docente2"],
        titulo="Evaluación del aprendizaje en educación superior",
        autor="Santos Guerra",
        justificacion="Material para la línea de investigación en evaluación educativa.",
    )

    resumen = {
        "autores": Autor.objects.count(),
        "libros": Libro.objects.count(),
        "usuarios": len(usuarios),
        "prestamos": Prestamo.objects.count(),
        "prestamos_por_estado": conteo,
        "reservas": Reserva.objects.count(),
        "solicitudes": SolicitudAdquisicion.objects.count(),
    }
    if verbose:
        print(f"[biblioteca] {resumen}")
        print(f"[biblioteca] Contraseña de todos los usuarios: {PASSWORD}")
    return resumen
