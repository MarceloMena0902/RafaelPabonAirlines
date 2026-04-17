-- ═══════════════════════════════════════════════════════════════
--  RafaelPabonAirlines — Esquema SQL Server
--  Se ejecuta automáticamente al levantar los contenedores
--  (Beijing y Ucrania). Usa IF NOT EXISTS para ser idempotente.
-- ═══════════════════════════════════════════════════════════════

-- ── Crear base de datos ───────────────────────────────────────
IF DB_ID('rpa_db') IS NULL
    CREATE DATABASE rpa_db;
GO

USE rpa_db;
GO

-- ── Tabla: aircrafts (lookup 4 filas) ────────────────────────
IF OBJECT_ID('dbo.aircrafts', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.aircrafts (
        id          INT          NOT NULL,
        type_code   VARCHAR(10)  NOT NULL,
        first_seats INT          NOT NULL DEFAULT 0,
        eco_seats   INT          NOT NULL DEFAULT 0,
        CONSTRAINT PK_aircrafts PRIMARY KEY (id)
    );
    INSERT INTO dbo.aircrafts VALUES
        (1, 'A380', 10, 439),
        (2, 'B777', 10, 300),
        (3, 'A350', 12, 250),
        (4, 'B787',  8, 220);
END
GO

-- ── Tabla: flights ───────────────────────────────────────────
IF OBJECT_ID('dbo.flights', 'U') IS NULL
    CREATE TABLE dbo.flights (
        id                INT            NOT NULL,
        origin            VARCHAR(10)    NOT NULL,
        destination       VARCHAR(10)    NOT NULL,
        flight_date       DATE           NOT NULL,
        departure_time    TIME           NOT NULL,
        duration_hours    FLOAT          NOT NULL DEFAULT 0,
        price_economy     DECIMAL(10,2)  NOT NULL DEFAULT 0,
        price_first       DECIMAL(10,2)  NOT NULL DEFAULT 0,
        available_economy INT            NOT NULL DEFAULT 0,
        available_first   INT            NOT NULL DEFAULT 0,
        aircraft_id       INT            NOT NULL DEFAULT 1,
        gate              VARCHAR(10)    NULL,
        status            VARCHAR(20)    NOT NULL DEFAULT 'SCHEDULED',
        node_owner        VARCHAR(20)    NOT NULL DEFAULT 'beijing',
        CONSTRAINT PK_flights PRIMARY KEY (id),
        CONSTRAINT FK_flights_aircraft
            FOREIGN KEY (aircraft_id) REFERENCES dbo.aircrafts(id)
    );
GO

-- ── Tabla: passengers ────────────────────────────────────────
IF OBJECT_ID('dbo.passengers', 'U') IS NULL
    CREATE TABLE dbo.passengers (
        passport    VARCHAR(20)   NOT NULL,
        full_name   VARCHAR(100)  NOT NULL,
        nationality VARCHAR(50)   NULL,
        home_region VARCHAR(50)   NULL,
        email       VARCHAR(100)  NULL,
        created_at  DATETIME2     NOT NULL DEFAULT GETUTCDATE(),
        CONSTRAINT PK_passengers PRIMARY KEY (passport)
    );
GO

-- ── Tabla: reservations ──────────────────────────────────────
IF OBJECT_ID('dbo.reservations', 'U') IS NULL
    CREATE TABLE dbo.reservations (
        id                 BIGINT         NOT NULL,
        transaction_id     VARCHAR(60)    NOT NULL,
        flight_id          INT            NOT NULL,
        passenger_passport VARCHAR(20)    NOT NULL,
        seat_number        VARCHAR(10)    NOT NULL,
        cabin_class        VARCHAR(10)    NOT NULL,
        status             VARCHAR(20)    NOT NULL DEFAULT 'CONFIRMED',
        price_paid         DECIMAL(10,2)  NOT NULL DEFAULT 0,
        node_origin        VARCHAR(20)    NOT NULL,
        vector_clock       NVARCHAR(300)  NULL,
        created_at         DATETIME2      NOT NULL DEFAULT GETUTCDATE(),
        updated_at         DATETIME2      NOT NULL DEFAULT GETUTCDATE(),
        CONSTRAINT PK_reservations PRIMARY KEY (id),
        CONSTRAINT UQ_reservations_tx UNIQUE (transaction_id)
    );
GO

-- ── Tabla: sync_queue (replicación entre nodos) ──────────────
IF OBJECT_ID('dbo.sync_queue', 'U') IS NULL
    CREATE TABLE dbo.sync_queue (
        id              INT            IDENTITY(1,1) NOT NULL,
        transaction_id  VARCHAR(60)    NOT NULL,
        operation_type  VARCHAR(20)    NOT NULL,
        target_node     VARCHAR(20)    NOT NULL,
        payload         NVARCHAR(MAX)  NULL,
        vector_clock    NVARCHAR(300)  NULL,
        queued_at       DATETIME2      NOT NULL DEFAULT GETUTCDATE(),
        replayed        BIT            NOT NULL DEFAULT 0,
        CONSTRAINT PK_sync_queue PRIMARY KEY (id)
    );
GO

-- ── Índices ───────────────────────────────────────────────────
IF NOT EXISTS (
    SELECT 1 FROM sys.indexes
    WHERE object_id = OBJECT_ID('dbo.flights')
      AND name = 'IX_flights_route_date'
)
    CREATE INDEX IX_flights_route_date
        ON dbo.flights(origin, destination, flight_date);
GO

IF NOT EXISTS (
    SELECT 1 FROM sys.indexes
    WHERE object_id = OBJECT_ID('dbo.reservations')
      AND name = 'IX_reservations_flight'
)
    CREATE INDEX IX_reservations_flight
        ON dbo.reservations(flight_id);
GO

IF NOT EXISTS (
    SELECT 1 FROM sys.indexes
    WHERE object_id = OBJECT_ID('dbo.sync_queue')
      AND name = 'IX_sync_pending'
)
    CREATE INDEX IX_sync_pending
        ON dbo.sync_queue(target_node, replayed);
GO

PRINT 'rpa_db schema OK';
GO
