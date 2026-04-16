"""
powerbi/generate_template.py
──────────────────────────────
Genera RafaelPabonAirlines.pbit (template Power BI)
con el modelo de datos y las páginas predefinidas.

Uso:
    python powerbi/generate_template.py

Requisito:
    pip install requests   (solo para verificar conexión)
"""
import json
import zipfile
import io
from pathlib import Path

OUTPUT = Path(__file__).parent / "RafaelPabonAirlines.pbit"

SERVER   = "localhost,1433"
DATABASE = "rpa_db"

# ── Cadena de conexión M (Power Query) ───────────────────────

def m_query(view: str) -> str:
    return (
        f'let\n'
        f'    Source = Sql.Database("{SERVER}", "{DATABASE}"),\n'
        f'    Data = Source{{[Schema="dbo",Item="{view}"]}}[Data]\n'
        f'in\n'
        f'    Data'
    )


TABLES = [
    ("KPIs",                    "vw_kpis"),
    ("Vuelos_por_Estado",       "vw_vuelos_por_estado"),
    ("Vuelos_por_Nodo",         "vw_vuelos_por_nodo"),
    ("Vuelos_por_Fecha",        "vw_vuelos_por_fecha"),
    ("Top_Rutas",               "vw_top_rutas"),
    ("Pasajeros_Nacionalidad",  "vw_pasajeros_por_nacionalidad"),
    ("Pasajeros_Region",        "vw_pasajeros_por_region"),
    ("Reservas_Detalle",        "vw_reservas_detalle"),
    ("Reservas_por_Nodo",       "vw_reservas_por_nodo"),
    ("Ingresos_por_Ruta",       "vw_ingresos_por_ruta"),
]

# ── Esquema del modelo de datos (Tabular) ────────────────────

def build_model_schema() -> dict:
    tables = []
    for table_name, view_name in TABLES:
        tables.append({
            "name": table_name,
            "columns": [],          # Power BI los infiere al conectar
            "partitions": [{
                "name":   "Partition",
                "mode":   "import",
                "source": {
                    "type":       "m",
                    "expression": m_query(view_name),
                }
            }]
        })

    return {
        "name":          "RafaelPabonAirlines",
        "compatibilityLevel": 1550,
        "model": {
            "culture":     "es-BO",
            "dataAccessOptions": {"legacyRedirects": True, "returnErrorValuesAsNull": True},
            "defaultPowerBIDataSourceVersion": "powerBI_V3",
            "tables": tables,
            "relationships": [],
            "annotations": [{
                "name":  "PBI_QueryOrder",
                "value": json.dumps([t[0] for t in TABLES])
            }]
        }
    }


# ── Layout del reporte (páginas y visuales) ──────────────────

WINE_COLOR  = "#8B1B3D"
GOLD_COLOR  = "#D4A017"
NAVY_COLOR  = "#0A1F44"
WHITE_COLOR = "#FFFFFF"

def build_layout() -> dict:
    """
    Genera 4 páginas:
      1. Resumen KPIs
      2. Análisis de Vuelos
      3. Análisis de Pasajeros
      4. Reservas e Ingresos
    """
    pages = [
        _page_kpis(),
        _page_vuelos(),
        _page_pasajeros(),
        _page_reservas(),
    ]
    return {
        "id":      "RafaelPabonAirlines",
        "theme":   _theme(),
        "pages":   pages,
        "config":  json.dumps({"version": "5.49"}),
    }


def _theme() -> dict:
    return {
        "name":       "RPA Theme",
        "dataColors": [WINE_COLOR, GOLD_COLOR, "#2196F3", "#4CAF50", "#FF5722", "#9C27B0"],
        "background": WHITE_COLOR,
        "foreground": NAVY_COLOR,
        "tableAccent": WINE_COLOR,
    }


def _visual_card(x, y, w, h, title, measure_table, measure_field) -> dict:
    return {
        "x": x, "y": y, "z": 1,
        "width": w, "height": h,
        "config": json.dumps({
            "name":        f"card_{x}_{y}",
            "layouts":     [{"id": 0, "position": {"x": x, "y": y, "z": 1, "width": w, "height": h}}],
            "singleVisual": {
                "visualType": "card",
                "projections": {
                    "Values": [{"queryRef": f"{measure_table}.{measure_field}"}]
                },
                "prototypeQuery": {
                    "Version": 2,
                    "From": [{"Name": "t", "Entity": measure_table}],
                    "Select": [{"Column": {"Expression": {"SourceRef": {"Source": "t"}},
                                           "Property": measure_field},
                                "Name": f"{measure_table}.{measure_field}"}]
                },
                "title": {"text": title, "visible": True}
            }
        })
    }


def _visual_bar(x, y, w, h, title, table, category, value) -> dict:
    return {
        "x": x, "y": y, "z": 1,
        "width": w, "height": h,
        "config": json.dumps({
            "name": f"bar_{x}_{y}",
            "layouts": [{"id": 0, "position": {"x": x, "y": y, "z": 1, "width": w, "height": h}}],
            "singleVisual": {
                "visualType": "barChart",
                "projections": {
                    "Category": [{"queryRef": f"{table}.{category}"}],
                    "Y":        [{"queryRef": f"{table}.{value}"}],
                },
                "prototypeQuery": {
                    "Version": 2,
                    "From":   [{"Name": "t", "Entity": table}],
                    "Select": [
                        {"Column":   {"Expression": {"SourceRef": {"Source": "t"}}, "Property": category},
                         "Name": f"{table}.{category}"},
                        {"Aggregation": {"Expression": {"Column": {"Expression": {"SourceRef": {"Source": "t"}}, "Property": value}}, "Function": 0},
                         "Name": f"{table}.{value}"},
                    ]
                },
                "title": {"text": title, "visible": True}
            }
        })
    }


def _visual_donut(x, y, w, h, title, table, category, value) -> dict:
    visual = _visual_bar(x, y, w, h, title, table, category, value)
    cfg = json.loads(visual["config"])
    cfg["singleVisual"]["visualType"] = "donutChart"
    cfg["singleVisual"]["projections"] = {
        "Category": [{"queryRef": f"{table}.{category}"}],
        "Y":        [{"queryRef": f"{table}.{value}"}],
    }
    visual["config"] = json.dumps(cfg)
    return visual


def _page_kpis() -> dict:
    W, H = 1280, 720
    return {
        "name":          "KPIs",
        "displayName":   "📊 Resumen",
        "width":  W, "height": H,
        "visuals": [
            _visual_card(20,  60, 230, 120, "Total Vuelos",       "KPIs", "Total_Vuelos"),
            _visual_card(270, 60, 230, 120, "Total Pasajeros",    "KPIs", "Total_Pasajeros"),
            _visual_card(520, 60, 230, 120, "Reservas Confirmadas","KPIs","Reservas_Confirmadas"),
            _visual_card(770, 60, 230, 120, "Ingresos Totales",   "KPIs", "Ingresos_Totales"),
            _visual_bar(20,  220, 580, 300, "Vuelos por Nodo",    "Vuelos_por_Nodo",  "Nodo",  "Total_Vuelos"),
            _visual_bar(620, 220, 580, 300, "Vuelos por Estado",  "Vuelos_por_Estado","Estado","Total_Vuelos"),
            _visual_bar(20,  550, 1180,140, "Top Rutas",          "Top_Rutas",        "Ruta",  "Total_Vuelos"),
        ]
    }


def _page_vuelos() -> dict:
    return {
        "name":        "Vuelos",
        "displayName": "✈️ Vuelos",
        "width": 1280, "height": 720,
        "visuals": [
            _visual_bar(20,  20, 600, 320, "Vuelos por Fecha",          "Vuelos_por_Fecha", "Fecha",  "Total_Vuelos"),
            _visual_bar(640, 20, 600, 320, "Asientos disponibles/Nodo", "Vuelos_por_Nodo",  "Nodo",   "Asientos_Disponibles"),
            _visual_bar(20,  380, 600, 300,"Precio Eco Promedio / Nodo","Vuelos_por_Nodo",  "Nodo",   "Precio_Eco_Promedio"),
            _visual_bar(640, 380, 600, 300,"Top Rutas por Volumen",     "Top_Rutas",        "Ruta",   "Total_Vuelos"),
        ]
    }


def _page_pasajeros() -> dict:
    return {
        "name":        "Pasajeros",
        "displayName": "👥 Pasajeros",
        "width": 1280, "height": 720,
        "visuals": [
            _visual_donut(20,  20, 580, 340, "Pasajeros por Región",       "Pasajeros_Region",       "Region",       "Total_Pasajeros"),
            _visual_bar(640,  20, 600, 340, "Pasajeros por Nacionalidad",  "Pasajeros_Nacionalidad", "Nacionalidad", "Total_Pasajeros"),
            _visual_bar(20,  390, 1180,290, "Distribución por Región",     "Pasajeros_Region",       "Region",       "Total_Pasajeros"),
        ]
    }


def _page_reservas() -> dict:
    return {
        "name":        "Reservas",
        "displayName": "🎫 Reservas e Ingresos",
        "width": 1280, "height": 720,
        "visuals": [
            _visual_bar(20,  20, 580, 300, "Reservas por Nodo/Clase",  "Reservas_por_Nodo",  "Nodo",  "Total"),
            _visual_bar(640, 20, 600, 300, "Ingresos por Ruta",        "Ingresos_por_Ruta",  "Ruta",  "Ingresos_Total"),
            _visual_donut(20, 360, 380, 300,"Reservas por Clase",      "Reservas_por_Nodo",  "Clase", "Total"),
            _visual_donut(440,360, 380, 300,"Ingresos por Clase",      "Reservas_por_Nodo",  "Clase", "Ingresos"),
            _visual_bar(840, 360, 400, 300, "Confirmadas vs Canceladas","Reservas_por_Nodo", "Estado","Total"),
        ]
    }


# ── Generar el archivo .pbit ─────────────────────────────────

def generate():
    model_schema = build_model_schema()
    layout       = build_layout()

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("[Content_Types].xml",
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
            '<Default Extension="json" ContentType="application/json"/>'
            '<Default Extension="xml"  ContentType="application/xml"/>'
            '</Types>')

        zf.writestr("Version",         "3.0")
        zf.writestr("Settings",        json.dumps({"version": "1.0"}))
        zf.writestr("Metadata",        json.dumps({
            "version":         "4.0",
            "contentType":     "PowerBITemplate",
            "createdFrom":     "RafaelPabonAirlines",
        }))
        zf.writestr("DataModelSchema", json.dumps(model_schema, ensure_ascii=False))
        zf.writestr("DiagramState",    json.dumps({
            "version":    "0",
            "diagramLayout": {
                "nodes": [
                    {"nodeIndex": i, "left": (i % 3) * 300, "top": (i // 3) * 200,
                     "width": 250, "height": 150}
                    for i in range(len(TABLES))
                ]
            }
        }))
        zf.writestr("Report/Layout",   json.dumps(layout, ensure_ascii=False))

    OUTPUT.parent.mkdir(exist_ok=True)
    OUTPUT.write_bytes(buf.getvalue())
    print(f"✓ Template generado: {OUTPUT}")
    print(f"  Abrelo con Power BI Desktop.")
    print(f"  Cuando pida credenciales: servidor={SERVER}, user=sa, pwd=RPA_StrongPass123!")


if __name__ == "__main__":
    generate()
