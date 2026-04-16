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

PRINT 'Vistas Power BI creadas correctamente en rpa_db.';
GO
