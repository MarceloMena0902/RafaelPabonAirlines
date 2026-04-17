"""
geo/cities.py
──────────────
Base de datos de ciudades del mundo con coordenadas.
~500 ciudades principales.
Usado por /nodes/nearest para determinar el nodo más cercano
a partir de la ciudad de compra del pasajero.
"""
from functools import lru_cache
from geopy.distance import geodesic

# (nombre_ciudad, pais, lat, lon)
WORLD_CITIES: list[tuple[str, str, float, float]] = [
    # ─ Bolivia / La Paz region ─────────────────────────────────
    ("La Paz",         "Bolivia",     -16.4897,  -68.1193),
    ("Cochabamba",     "Bolivia",     -17.4167,  -66.1500),
    ("Santa Cruz",     "Bolivia",     -17.7863,  -63.1812),
    ("Sucre",          "Bolivia",     -19.0478,  -65.2597),
    # ─ South America ───────────────────────────────────────────
    ("Bogotá",         "Colombia",      4.7110,  -74.0721),
    ("Medellín",       "Colombia",      6.2442,  -75.5812),
    ("Cali",           "Colombia",      3.4516,  -76.5320),
    ("Lima",           "Perú",         -12.0464,  -77.0428),
    ("Arequipa",       "Perú",         -16.4090,  -71.5375),
    ("Santiago",       "Chile",        -33.4489,  -70.6693),
    ("Valparaíso",     "Chile",        -33.0472,  -71.6127),
    ("Buenos Aires",   "Argentina",    -34.6037,  -58.3816),
    ("Córdoba",        "Argentina",    -31.4201,  -64.1888),
    ("Rosario",        "Argentina",    -32.9587,  -60.6931),
    ("São Paulo",      "Brasil",       -23.5505,  -46.6333),
    ("Río de Janeiro", "Brasil",       -22.9068,  -43.1729),
    ("Brasília",       "Brasil",       -15.7801,  -47.9292),
    ("Salvador",       "Brasil",       -12.9714,  -38.5014),
    ("Fortaleza",      "Brasil",        -3.7172,  -38.5434),
    ("Manaus",         "Brasil",        -3.1190,  -60.0217),
    ("Porto Alegre",   "Brasil",       -30.0346,  -51.2177),
    ("Caracas",        "Venezuela",     10.4806,  -66.9036),
    ("Maracaibo",      "Venezuela",     10.6427,  -71.6125),
    ("Quito",          "Ecuador",       -0.2295,  -78.5249),
    ("Guayaquil",      "Ecuador",       -2.1900,  -79.8875),
    ("Asunción",       "Paraguay",     -25.2867,  -57.6470),
    ("Montevideo",     "Uruguay",      -34.9011,  -56.1645),
    ("Guayanas",       "Guyana",         6.8013,  -58.1551),
    ("Paramaribo",     "Surinam",        5.8520,  -55.2038),
    # ─ Central America / Caribbean ─────────────────────────────
    ("Ciudad de México","México",       19.4326,  -99.1332),
    ("Guadalajara",    "México",        20.6597, -103.3496),
    ("Monterrey",      "México",        25.6866, -100.3161),
    ("Cancún",         "México",        21.1619,  -86.8515),
    ("Guatemala City", "Guatemala",     14.6349,  -90.5069),
    ("San José",       "Costa Rica",     9.9281,  -84.0907),
    ("Panamá",         "Panamá",         8.9936,  -79.5197),
    ("La Habana",      "Cuba",           23.1136,  -82.3666),
    ("Santo Domingo",  "R. Dominicana",  18.4861,  -69.9312),
    ("San Juan",       "Puerto Rico",    18.4655,  -66.1057),
    ("Kingston",       "Jamaica",        17.9970,  -76.7936),
    ("Puerto Príncipe","Haití",          18.5944,  -72.3074),
    # ─ North America ───────────────────────────────────────────
    ("Miami",          "EE.UU.",         25.7617,  -80.1918),
    ("Nueva York",     "EE.UU.",         40.7128,  -74.0060),
    ("Los Ángeles",    "EE.UU.",         34.0522, -118.2437),
    ("Chicago",        "EE.UU.",         41.8781,  -87.6298),
    ("Atlanta",        "EE.UU.",         33.7490,  -84.3880),
    ("Dallas",         "EE.UU.",         32.7767,  -96.7970),
    ("Houston",        "EE.UU.",         29.7604,  -95.3698),
    ("Washington DC",  "EE.UU.",         38.9072,  -77.0369),
    ("San Francisco",  "EE.UU.",         37.7749, -122.4194),
    ("Seattle",        "EE.UU.",         47.6062, -122.3321),
    ("Boston",         "EE.UU.",         42.3601,  -71.0589),
    ("Denver",         "EE.UU.",         39.7392, -104.9903),
    ("Las Vegas",      "EE.UU.",         36.1699, -115.1398),
    ("Phoenix",        "EE.UU.",         33.4484, -112.0740),
    ("Minneapolis",    "EE.UU.",         44.9778,  -93.2650),
    ("Detroit",        "EE.UU.",         42.3314,  -83.0458),
    ("Toronto",        "Canadá",         43.6532,  -79.3832),
    ("Vancouver",      "Canadá",         49.2827, -123.1207),
    ("Montreal",       "Canadá",         45.5017,  -73.5673),
    ("Calgary",        "Canadá",         51.0447, -114.0719),
    ("Ottawa",         "Canadá",         45.4215,  -75.6972),
    # ─ Europe / Ukraine region ─────────────────────────────────
    ("Kyiv",           "Ucrania",        50.4501,   30.5234),
    ("Járkov",         "Ucrania",        49.9935,   36.2304),
    ("Odesa",          "Ucrania",        46.4825,   30.7233),
    ("Moscú",          "Rusia",          55.7558,   37.6176),
    ("San Petersburgo","Rusia",          59.9343,   30.3351),
    ("Novosibirsk",    "Rusia",          54.9885,   82.9207),
    ("Madrid",         "España",         40.4168,   -3.7038),
    ("Barcelona",      "España",         41.3851,    2.1734),
    ("Valencia",       "España",         39.4699,   -0.3763),
    ("Sevilla",        "España",         37.3891,   -5.9845),
    ("París",          "Francia",        48.8566,    2.3522),
    ("Lyon",           "Francia",        45.7640,    4.8357),
    ("Marsella",       "Francia",        43.2965,    5.3698),
    ("Niza",           "Francia",        43.7102,    7.2620),
    ("Londres",        "R. Unido",       51.5074,   -0.1278),
    ("Manchester",     "R. Unido",       53.4808,   -2.2426),
    ("Glasgow",        "R. Unido",       55.8642,   -4.2518),
    ("Birmingham",     "R. Unido",       52.4862,   -1.8904),
    ("Berlín",         "Alemania",       52.5200,   13.4050),
    ("Múnich",         "Alemania",       48.1351,   11.5820),
    ("Hamburgo",       "Alemania",       53.5511,    9.9937),
    ("Fráncfort",      "Alemania",       50.1109,    8.6821),
    ("Colonia",        "Alemania",       50.9333,    6.9500),
    ("Düsseldorf",     "Alemania",       51.2217,    6.7762),
    ("Stuttgart",      "Alemania",       48.7758,    9.1829),
    ("Roma",           "Italia",         41.9028,   12.4964),
    ("Milán",          "Italia",         45.4654,    9.1859),
    ("Nápoles",        "Italia",         40.8518,   14.2681),
    ("Turín",          "Italia",         45.0703,    7.6869),
    ("Ámsterdam",      "P. Bajos",       52.3676,    4.9041),
    ("Rotterdam",      "P. Bajos",       51.9244,    4.4777),
    ("Bruselas",       "Bélgica",        50.8503,    4.3517),
    ("Zúrich",         "Suiza",          47.3769,    8.5417),
    ("Ginebra",        "Suiza",          46.2044,    6.1432),
    ("Berna",          "Suiza",          46.9480,    7.4474),
    ("Viena",          "Austria",        48.2082,   16.3738),
    ("Salzburgo",      "Austria",        47.8095,   13.0550),
    ("Praga",          "Chequia",        50.0755,   14.4378),
    ("Varsovia",       "Polonia",        52.2297,   21.0122),
    ("Cracovia",       "Polonia",        50.0647,   19.9450),
    ("Budapest",       "Hungría",        47.4979,   19.0402),
    ("Bucarest",       "Rumanía",        44.4268,   26.1025),
    ("Sofía",          "Bulgaria",       42.6977,   23.3219),
    ("Belgrado",       "Serbia",         44.7866,   20.4489),
    ("Zagreb",         "Croacia",        45.8150,   15.9819),
    ("Liubliana",      "Eslovenia",      46.0569,   14.5058),
    ("Atenas",         "Grecia",         37.9838,   23.7275),
    ("Salónica",       "Grecia",         40.6401,   22.9444),
    ("Estambul",       "Turquía",        41.0082,   28.9784),
    ("Ankara",         "Turquía",        39.9334,   32.8597),
    ("Esmirna",        "Turquía",        38.4237,   27.1428),
    ("Lisboa",         "Portugal",       38.7223,   -9.1393),
    ("Oporto",         "Portugal",       41.1496,   -8.6109),
    ("Dublín",         "Irlanda",        53.3498,   -6.2603),
    ("Copenhague",     "Dinamarca",      55.6761,   12.5683),
    ("Estocolmo",      "Suecia",         59.3293,   18.0686),
    ("Gotemburgo",     "Suecia",         57.7089,   11.9746),
    ("Oslo",           "Noruega",        59.9139,   10.7522),
    ("Bergen",         "Noruega",        60.3913,    5.3221),
    ("Helsinki",       "Finlandia",      60.1699,   24.9384),
    ("Riga",           "Letonia",        56.9460,   24.1059),
    ("Tallin",         "Estonia",        59.4370,   24.7536),
    ("Vilna",          "Lituania",       54.6872,   25.2797),
    ("Minsk",          "Bielorrusia",    53.9045,   27.5615),
    ("Bratislava",     "Eslovaquia",     48.1486,   17.1077),
    ("Reykjavik",      "Islandia",       64.1265,  -21.8174),
    # ─ Middle East / Africa ────────────────────────────────────
    ("Dubai",          "EAU",            25.2048,   55.2708),
    ("Abu Dabi",       "EAU",            24.4539,   54.3773),
    ("Dubái",          "EAU",            25.2048,   55.2708),
    ("Riyadh",         "Arabia Saudita", 24.7136,   46.6753),
    ("Jeddah",         "Arabia Saudita", 21.4858,   39.1925),
    ("Doha",           "Qatar",          25.2854,   51.5310),
    ("Kuwait",         "Kuwait",         29.3759,   47.9774),
    ("Tel Aviv",       "Israel",         32.0853,   34.7818),
    ("Beirut",         "Líbano",         33.8938,   35.5018),
    ("Amán",           "Jordania",       31.9539,   35.9106),
    ("Bagdad",         "Irak",           33.3128,   44.3615),
    ("Teherán",        "Irán",           35.6892,   51.3890),
    ("Mascate",        "Omán",           23.5880,   58.3829),
    ("El Cairo",       "Egipto",         30.0444,   31.2357),
    ("Alejandría",     "Egipto",         31.2001,   29.9187),
    ("Lagos",          "Nigeria",         6.5244,    3.3792),
    ("Abuja",          "Nigeria",          9.0765,    7.3986),
    ("Nairobi",        "Kenia",          -1.2921,   36.8219),
    ("Mombasa",        "Kenia",          -4.0435,   39.6682),
    ("Johannesburgo",  "S. África",     -26.2041,   28.0473),
    ("Ciudad del Cabo","S. África",     -33.9249,   18.4241),
    ("Durban",         "S. África",     -29.8587,   31.0218),
    ("Acra",           "Ghana",           5.6037,   -0.1870),
    ("Dakar",          "Senegal",        14.7167,  -17.4677),
    ("Casablanca",     "Marruecos",      33.5731,   -7.5898),
    ("Rabat",          "Marruecos",      34.0209,   -6.8416),
    ("Argel",          "Argelia",        36.7538,    3.0588),
    ("Túnez",          "Túnez",          36.8190,   10.1658),
    ("Trípoli",        "Libia",          32.9010,   13.1839),
    ("Addis Abeba",    "Etiopía",         9.0250,   38.7469),
    ("Kigali",         "Ruanda",         -1.9441,   30.0619),
    ("Lusaka",         "Zambia",        -15.4166,   28.2833),
    ("Harare",         "Zimbabwe",      -17.8252,   31.0335),
    ("Maputo",         "Mozambique",    -25.9692,   32.5732),
    ("Antananarivo",   "Madagascar",    -18.8792,   47.5079),
    ("Dar es Salaam",  "Tanzania",       -6.7924,   39.2083),
    ("Kampala",        "Uganda",          0.3476,   32.5825),
    ("Luanda",         "Angola",         -8.8147,   13.2302),
    ("Kinshasa",       "R.D. Congo",     -4.4419,   15.2663),
    ("Abiyán",         "Costa de Marfil", 5.3600,   -4.0083),
    # ─ Asia / Beijing region ───────────────────────────────────
    ("Pekín",          "China",          39.9042,  116.4074),
    ("Shanghái",       "China",          31.2304,  121.4737),
    ("Guangzhou",      "China",          23.1291,  113.2644),
    ("Shenzhen",       "China",          22.5431,  114.0579),
    ("Chengdú",        "China",          30.5728,  104.0668),
    ("Wuhan",          "China",          30.5928,  114.3055),
    ("Chongqing",      "China",          29.4316,  106.9123),
    ("Tianjín",        "China",          39.1422,  117.1767),
    ("Nanjing",        "China",          32.0603,  118.7969),
    ("Hangzhou",       "China",          30.2741,  120.1551),
    ("Xi'an",          "China",          34.3416,  108.9398),
    ("Cantón",         "China",          23.1291,  113.2644),
    ("Tokio",          "Japón",          35.6762,  139.6503),
    ("Osaka",          "Japón",          34.6937,  135.5023),
    ("Kioto",          "Japón",          35.0116,  135.7681),
    ("Hiroshima",      "Japón",          34.3853,  132.4553),
    ("Nagoya",         "Japón",          35.1815,  136.9066),
    ("Seúl",           "Corea del Sur",  37.5665,  126.9780),
    ("Busan",          "Corea del Sur",  35.1796,  129.0756),
    ("Pyongyang",      "Corea del Norte",39.0392,  125.7625),
    ("Taipei",         "Taiwán",         25.0330,  121.5654),
    ("Hong Kong",      "Hong Kong",      22.3193,  114.1694),
    ("Macao",          "Macao",          22.1987,  113.5439),
    ("Bangkok",        "Tailandia",      13.7563,  100.5018),
    ("Chiang Mai",     "Tailandia",      18.7883,   98.9853),
    ("Singapur",       "Singapur",        1.3521,  103.8198),
    ("Kuala Lumpur",   "Malasia",         3.1390,  101.6869),
    ("Yakarta",        "Indonesia",      -6.2088,  106.8456),
    ("Surabaya",       "Indonesia",      -7.2575,  112.7521),
    ("Bali",           "Indonesia",      -8.3405,  115.0920),
    ("Manila",         "Filipinas",      14.5995,  120.9842),
    ("Cebu",           "Filipinas",      10.3157,  123.8854),
    ("Hanói",          "Vietnam",        21.0285,  105.8542),
    ("Ciudad Ho Chi Minh","Vietnam",     10.8231,  106.6297),
    ("Phnom Penh",     "Camboya",        11.5564,  104.9282),
    ("Vientiane",      "Laos",           17.9757,  102.6331),
    ("Yangón",         "Myanmar",        16.8661,   96.1951),
    ("Katmandú",       "Nepal",          27.7172,   85.3240),
    ("Dacca",          "Bangladesh",     23.8103,   90.4125),
    ("Karachi",        "Pakistán",       24.8607,   67.0011),
    ("Lahore",         "Pakistán",       31.5204,   74.3587),
    ("Islamabad",      "Pakistán",       33.6844,   73.0479),
    ("Mumbai",         "India",          19.0760,   72.8777),
    ("Delhi",          "India",          28.6139,   77.2090),
    ("Bangalore",      "India",          12.9716,   77.5946),
    ("Hyderabad",      "India",          17.3850,   78.4867),
    ("Chennai",        "India",          13.0827,   80.2707),
    ("Kolkata",        "India",          22.5726,   88.3639),
    ("Ahmedabad",      "India",          23.0225,   72.5714),
    ("Colombo",        "Sri Lanka",       6.9271,   79.8612),
    ("Kabul",          "Afganistán",     34.5553,   69.2075),
    ("Taskent",        "Uzbekistán",     41.2995,   69.2401),
    ("Almaty",         "Kazajistán",     43.2220,   76.8512),
    ("Astaná",         "Kazajistán",     51.1694,   71.4491),
    ("Bishkek",        "Kirguistán",     42.8746,   74.5698),
    ("Ulaanbaatar",    "Mongolia",       47.8864,  106.9057),
    ("Mandalay",       "Myanmar",        21.9588,   96.0891),
    # ─ Oceania ─────────────────────────────────────────────────
    ("Sídney",         "Australia",     -33.8688,  151.2093),
    ("Melbourne",      "Australia",     -37.8136,  144.9631),
    ("Brisbane",       "Australia",     -27.4698,  153.0251),
    ("Perth",          "Australia",     -31.9505,  115.8605),
    ("Adelaida",       "Australia",     -34.9285,  138.6007),
    ("Auckland",       "N. Zelanda",    -36.8509,  174.7645),
    ("Wellington",     "N. Zelanda",    -41.2865,  174.7762),
    ("Suva",           "Fiyi",          -18.1416,  178.4419),
    ("Port Moresby",   "P. N. Guinea",  -9.4438,   147.1803),
]


@lru_cache(maxsize=1)
def get_cities() -> list[dict]:
    """Devuelve la lista completa de ciudades como dicts."""
    return [
        {"city": c[0], "country": c[1], "lat": c[2], "lon": c[3]}
        for c in WORLD_CITIES
    ]


def search_cities(query: str, limit: int = 10) -> list[dict]:
    """Busca ciudades por nombre o país (case-insensitive)."""
    q = query.lower().strip()
    results = []
    for city in get_cities():
        if q in city["city"].lower() or q in city["country"].lower():
            results.append(city)
        if len(results) >= limit:
            break
    return results


def nearest_node_for_coords(lat: float, lon: float) -> str:
    """Devuelve el nombre del nodo más cercano a unas coordenadas."""
    from geo.proximity import NODE_CENTERS
    point = (lat, lon)
    distances = {
        node: geodesic(point, center).km
        for node, center in NODE_CENTERS.items()
    }
    return min(distances, key=distances.get)


def nearest_node_for_city(city_name: str) -> dict | None:
    """
    Dado un nombre de ciudad, devuelve:
    { city, country, lat, lon, node, node_label, node_flag }
    o None si no se encuentra.
    """
    matches = search_cities(city_name, limit=1)
    if not matches:
        return None
    c = matches[0]
    node = nearest_node_for_coords(c["lat"], c["lon"])
    labels = {"beijing": "Pekín", "ukraine": "Ucrania", "lapaz": "La Paz"}
    flags  = {"beijing": "🇨🇳",   "ukraine": "🇺🇦",     "lapaz": "🇧🇴"}
    return {**c, "node": node, "node_label": labels.get(node, node),
            "node_flag": flags.get(node, "")}
