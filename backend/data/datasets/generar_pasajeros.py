import csv
import random
import uuid

# Configuración
TOTAL_PASAJEROS = 5000000
ARCHIVO_SALIDA = "pasajeros.csv"

# Pools Culturales para coherencia geográfica e idiomas
DATA_CULTURAL = {
    "LATAM": { # Bolivia (Nodo), Brasil, España
        "nombres": ["Marcelo", "Juan", "Diego", "Lucia", "Elena", "Carlos", "Isabel", "Mateo", "Valentina", "Ricardo", "Camila", "Javier"],
        "apellidos": ["Mena", "Garcia", "Rodriguez", "Silva", "Santos", "Lopez", "Perez", "Mamani", "Quispe", "Vargas", "Mendoza"],
        "nacionalidades": ["Boliviano", "Brasilero", "Español"]
    },
    "EURO_ESTE": { # Ucrania (Nodo), Turquía
        "nombres": ["Andriy", "Oleksandr", "Dmytro", "Yaroslav", "Iryna", "Olena", "Mehmet", "Mustafa", "Can", "Fatma"],
        "apellidos": ["Shevchenko", "Bondarenko", "Tkachenko", "Kovalenko", "Yilmaz", "Kaya", "Demir", "Sahin"],
        "nacionalidades": ["Ucraniano", "Turco"]
    },
    "EURO_OESTE": { # Alemania, Francia, Países Bajos, UK
        "nombres": ["Hans", "Lukas", "Emma", "Marie", "Jean", "Pierre", "Bram", "Anke", "Thomas", "Sophie", "Oliver", "Charlotte"],
        "apellidos": ["Müller", "Schneider", "Dubois", "De Jong", "Fischer", "Weber", "Brown", "Smith", "Wilson"],
        "nacionalidades": ["Alemán", "Francés", "Holandés", "Británico"]
    },
    "ORIENTE": { # Dubái (Nodo), China, Japón, Singapur
        "nombres": ["Mohammed", "Ahmed", "Wei", "Li", "Hiroshi", "Yuki", "Zaid", "Omar", "Chen", "Mei", "Akira", "Kenji"],
        "apellidos": ["Al-Fayed", "Mansour", "Wang", "Zhang", "Sato", "Tanaka", "Suzuki", "Chen", "Lin", "Saleh"],
        "nacionalidades": ["Emiratí", "Chino", "Japonés", "Singapurense"]
    },
    "NORTE_AMERICA": { # USA
        "nombres": ["James", "John", "Robert", "Mary", "Patricia", "Jennifer", "Michael", "Linda", "William", "Elizabeth"],
        "apellidos": ["Johnson", "Williams", "Jones", "Miller", "Davis", "Garcia", "Rodriguez", "Wilson"],
        "nacionalidades": ["Estadounidense"]
    }
}

def generar_lote_pasajeros(cantidad):
    lote = []
    regiones = list(DATA_CULTURAL.keys())

    for _ in range(cantidad):
        region = random.choice(regiones)
        cultura = DATA_CULTURAL[region]

        nombre = random.choice(cultura["nombres"])
        apellido = random.choice(cultura["apellidos"])
        nacionalidad = random.choice(cultura["nacionalidades"])

        # Pasaporte: Código de región + número único
        pasaporte = f"{region[:2].upper()}{random.randint(10000000, 99999999)}"
        email = f"{nombre.lower()}.{apellido.lower()}{random.randint(100, 9999)}@airline-rp.com"

        lote.append([pasaporte, f"{nombre} {apellido}", nacionalidad, email])
    return lote

# Escritura eficiente en disco
print(f"Iniciando generación de {TOTAL_PASAJEROS} pasajeros...")

with open(ARCHIVO_SALIDA, "w", newline="", encoding="utf-8") as f:
    writer = csv.writer(f)
    writer.writerow(["Pasaporte", "NombreCompleto", "Nacionalidad", "Email"])

    # Procesar en bloques de 100k para no saturar la RAM
    procesados = 0
    tamano_bloque = 100000

    while procesados < TOTAL_PASAJEROS:
        bloque = generar_lote_pasajeros(tamano_bloque)
        writer.writerows(bloque)
        procesados += tamano_bloque
        print(f"Progreso: {procesados}/{TOTAL_PASAJEROS} ({(procesados/TOTAL_PASAJEROS)*100:.0f}%)")

print(f"¡Éxito! Archivo '{ARCHIVO_SALIDA}' generado correctamente.")