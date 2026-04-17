-- =============================================================
--  RafaelPabonAirlines — Vistas para Power BI
--  Ejecutar contra: rpa_db (SQL Server Beijing o Ucrania)
--  Deploy automático: python powerbi/deploy.py
-- =============================================================

USE rpa_db;
GO

-- ── 1. Vuelos por estado ──────────────────────────────────────
IF OBJECT_ID('dbo.vw_vuelos_por_estado', 'V') IS NOT NULL
    DROP VIEW dbo.vw_vuelos_por_estado;
GO
CREATE VIEW dbo.vw_vuelos_por_estado AS
SELECT
    status          AS Estado,
    COUNT(*)        AS Total_Vuelos
FROM dbo.flights
GROUP BY status;
GO

-- ── 2. Vuelos por nodo regional ───────────────────────────────
IF OBJECT_ID('dbo.vw_vuelos_por_nodo', 'V') IS NOT NULL
    DROP VIEW dbo.vw_vuelos_por_nodo;
GO
CREATE VIEW dbo.vw_vuelos_por_nodo AS
SELECT
    node_owner                                          AS Nodo,
    COUNT(*)                                            AS Total_Vuelos,
    SUM(available_economy + available_first)            AS Asientos_Disponibles,
    AVG(CAST(price_economy AS FLOAT))                   AS Precio_Eco_Promedio,
    AVG(CAST(price_first   AS FLOAT))                   AS Precio_First_Promedio
FROM dbo.flights
GROUP BY node_owner;
GO

-- ── 3. Top rutas por volumen ──────────────────────────────────
IF OBJECT_ID('dbo.vw_top_rutas', 'V') IS NOT NULL
    DROP VIEW dbo.vw_top_rutas;
GO
CREATE VIEW dbo.vw_top_rutas AS
SELECT TOP 50
    origin                              AS Origen,
    destination                         AS Destino,
    origin + ' → ' + destination        AS Ruta,
    COUNT(*)                            AS Total_Vuelos,
    AVG(CAST(price_economy AS FLOAT))   AS Precio_Eco_Promedio,
    AVG(CAST(price_first   AS FLOAT))   AS Precio_First_Promedio,
    AVG(duration_hours)                 AS Duracion_Promedio_Horas
FROM dbo.flights
GROUP BY origin, destination
ORDER BY COUNT(*) DESC;
GO

-- ── 4. Vuelos por fecha ───────────────────────────────────────
IF OBJECT_ID('dbo.vw_vuelos_por_fecha', 'V') IS NOT NULL
    DROP VIEW dbo.vw_vuelos_por_fecha;
GO
CREATE VIEW dbo.vw_vuelos_por_fecha AS
SELECT
    flight_date                 AS Fecha,
    COUNT(*)                    AS Total_Vuelos,
    SUM(available_economy)      AS Asientos_Eco_Disponibles,
    SUM(available_first)        AS Asientos_First_Disponibles
FROM dbo.flights
GROUP BY flight_date;
GO

-- ── 5. Pasajeros por nacionalidad ─────────────────────────────
IF OBJECT_ID('dbo.vw_pasajeros_por_nacionalidad', 'V') IS NOT NULL
    DROP VIEW dbo.vw_pasajeros_por_nacionalidad;
GO
CREATE VIEW dbo.vw_pasajeros_por_nacionalidad AS
SELECT
    nationality     AS Nacionalidad,
    home_region     AS Region,
    COUNT(*)        AS Total_Pasajeros
FROM dbo.passengers
GROUP BY nationality, home_region;
GO

-- ── 6. Pasajeros por región ───────────────────────────────────
IF OBJECT_ID('dbo.vw_pasajeros_por_region', 'V') IS NOT NULL
    DROP VIEW dbo.vw_pasajeros_por_region;
GO
CREATE VIEW dbo.vw_pasajeros_por_region AS
SELECT
    home_region     AS Region,
    COUNT(*)        AS Total_Pasajeros
FROM dbo.passengers
GROUP BY home_region;
GO

-- ── 7. Reservas con detalle de vuelo ─────────────────────────
IF OBJECT_ID('dbo.vw_reservas_detalle', 'V') IS NOT NULL
    DROP VIEW dbo.vw_reservas_detalle;
GO
CREATE VIEW dbo.vw_reservas_detalle AS
SELECT
    r.transaction_id            AS Transaction_ID,
    r.cabin_class               AS Clase,
    r.status                    AS Estado_Reserva,
    r.price_paid                AS Precio_Pagado,
    r.node_origin               AS Nodo_Origen,
    r.created_at                AS Fecha_Reserva,
    f.origin                    AS Origen,
    f.destination               AS Destino,
    f.origin + ' → ' + f.destination AS Ruta,
    f.flight_date               AS Fecha_Vuelo,
    f.node_owner                AS Nodo_Vuelo
FROM dbo.reservations r
JOIN dbo.flights f ON r.flight_id = f.id;
GO

-- ── 8. Ingresos por ruta ──────────────────────────────────────
IF OBJECT_ID('dbo.vw_ingresos_por_ruta', 'V') IS NOT NULL
    DROP VIEW dbo.vw_ingresos_por_ruta;
GO
CREATE VIEW dbo.vw_ingresos_por_ruta AS
SELECT
    f.origin + ' → ' + f.destination   AS Ruta,
    r.cabin_class                       AS Clase,
    COUNT(*)                            AS Total_Reservas,
    SUM(r.price_paid)                   AS Ingresos_Total,
    AVG(r.price_paid)                   AS Precio_Promedio
FROM dbo.reservations r
JOIN dbo.flights f ON r.flight_id = f.id
WHERE r.status = 'CONFIRMED'
GROUP BY f.origin, f.destination, r.cabin_class;
GO

-- ── 9. KPIs generales del sistema ────────────────────────────
IF OBJECT_ID('dbo.vw_kpis', 'V') IS NOT NULL
    DROP VIEW dbo.vw_kpis;
GO
CREATE VIEW dbo.vw_kpis AS
SELECT
    (SELECT COUNT(*) FROM dbo.flights)                          AS Total_Vuelos,
    (SELECT COUNT(*) FROM dbo.passengers)                       AS Total_Pasajeros,
    (SELECT COUNT(*) FROM dbo.reservations WHERE status='CONFIRMED') AS Reservas_Confirmadas,
    (SELECT COUNT(*) FROM dbo.reservations WHERE status='CANCELLED') AS Reservas_Canceladas,
    (SELECT ISNULL(SUM(price_paid),0) FROM dbo.reservations WHERE status='CONFIRMED') AS Ingresos_Totales,
    (SELECT COUNT(DISTINCT origin) FROM dbo.flights)            AS Aeropuertos_Origen,
    (SELECT COUNT(DISTINCT destination) FROM dbo.flights)       AS Aeropuertos_Destino;
GO

-- ── 10. Reservas por nodo y clase ────────────────────────────
IF OBJECT_ID('dbo.vw_reservas_por_nodo', 'V') IS NOT NULL
    DROP VIEW dbo.vw_reservas_por_nodo;
GO
CREATE VIEW dbo.vw_reservas_por_nodo AS
SELECT
    node_origin         AS Nodo,
    cabin_class         AS Clase,
    status              AS Estado,
    COUNT(*)            AS Total,
    SUM(price_paid)     AS Ingresos
FROM dbo.reservations
GROUP BY node_origin, cabin_class, status;
GO

-- ── 11. Ubicación de compra (nodo origen → ciudad) ──────────
IF OBJECT_ID('dbo.vw_ubicacion_compra', 'V') IS NOT NULL
    DROP VIEW dbo.vw_ubicacion_compra;
GO
CREATE VIEW dbo.vw_ubicacion_compra AS
SELECT
    r.node_origin                                       AS Nodo,
    CASE r.node_origin
        WHEN 'beijing' THEN 'Pekín, China'
        WHEN 'ukraine' THEN 'Kyiv, Ucrania'
        WHEN 'lapaz'   THEN 'La Paz, Bolivia'
        ELSE r.node_origin
    END                                                 AS Ciudad_Compra,
    CASE r.node_origin
        WHEN 'beijing' THEN 'Asia-Pacífico'
        WHEN 'ukraine' THEN 'Europa-África'
        WHEN 'lapaz'   THEN 'Américas'
        ELSE 'Desconocido'
    END                                                 AS Region_Compra,
    r.cabin_class                                       AS Clase,
    COUNT(*)                                            AS Total_Compras,
    SUM(r.price_paid)                                   AS Ingresos_Totales,
    AVG(r.price_paid)                                   AS Precio_Promedio,
    f.origin + ' → ' + f.destination                   AS Ruta
FROM dbo.reservations r
JOIN dbo.flights f ON r.flight_id = f.id
WHERE r.status = 'CONFIRMED'
GROUP BY r.node_origin, r.cabin_class, f.origin, f.destination;
GO

-- ── 12. Disponibilidad de flota por modelo ───────────────────
IF OBJECT_ID('dbo.vw_flota_disponibilidad', 'V') IS NOT NULL
    DROP VIEW dbo.vw_flota_disponibilidad;
GO
CREATE VIEW dbo.vw_flota_disponibilidad AS
SELECT
    a.type_code                                         AS Modelo,
    a.first_seats                                       AS Cap_Primera,
    a.eco_seats                                         AS Cap_Economica,
    a.first_seats + a.eco_seats                         AS Cap_Total,
    COUNT(f.id)                                         AS Vuelos_Asignados,
    SUM(f.available_economy)                            AS Eco_Disponibles,
    SUM(f.available_first)                              AS Primera_Disponibles,
    SUM(f.available_economy + f.available_first)        AS Total_Disponibles,
    SUM(a.eco_seats   - f.available_economy)            AS Eco_Ocupados,
    SUM(a.first_seats - f.available_first)              AS Primera_Ocupados,
    CASE WHEN COUNT(f.id) = 0 THEN 0
         ELSE CAST(SUM(a.eco_seats - f.available_economy) * 100.0
              / NULLIF(SUM(a.eco_seats), 0) AS DECIMAL(5,1))
    END                                                 AS Ocupacion_Eco_Pct
FROM dbo.aircrafts a
LEFT JOIN dbo.flights f ON f.aircraft_id = a.id
GROUP BY a.id, a.type_code, a.first_seats, a.eco_seats;
GO

-- ── 13. Lista de pasajeros (para autocompletar) ──────────────
IF OBJECT_ID('dbo.vw_pasajeros_lista', 'V') IS NOT NULL
    DROP VIEW dbo.vw_pasajeros_lista;
GO
CREATE VIEW dbo.vw_pasajeros_lista AS
SELECT
    passport        AS Pasaporte,
    full_name       AS Nombre_Completo,
    nationality     AS Nacionalidad,
    home_region     AS Region,
    email           AS Email,
    created_at      AS Fecha_Registro
FROM dbo.passengers;
GO

-- ── 14. Rutas más solicitadas (basado en 20,000 vuelos) ──────
IF OBJECT_ID('dbo.vw_rutas_mas_solicitadas', 'V') IS NOT NULL
    DROP VIEW dbo.vw_rutas_mas_solicitadas;
GO
CREATE VIEW dbo.vw_rutas_mas_solicitadas AS
SELECT TOP 100
    f.origin                                            AS Origen,
    f.destination                                       AS Destino,
    f.origin + ' → ' + f.destination                   AS Ruta,
    COUNT(r.id)                                         AS Total_Reservas,
    SUM(r.price_paid)                                   AS Ingresos_Ruta,
    AVG(r.price_paid)                                   AS Precio_Prom,
    COUNT(DISTINCT f.id)                                AS Vuelos_Disponibles
FROM dbo.flights f
LEFT JOIN dbo.reservations r
    ON r.flight_id = f.id AND r.status = 'CONFIRMED'
GROUP BY f.origin, f.destination
ORDER BY COUNT(r.id) DESC;
GO

PRINT 'Vistas Power BI (todas 14) creadas correctamente en rpa_db.';
GO
