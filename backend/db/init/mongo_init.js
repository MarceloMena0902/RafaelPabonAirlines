// ═══════════════════════════════════════════════════════════════
//  RafaelPabonAirlines — Inicialización MongoDB (La Paz)
//  Se ejecuta automáticamente al crear el contenedor por primera vez.
// ═══════════════════════════════════════════════════════════════

var rpaDb = db.getSiblingDB('rpa_db');

// ── Contador IKJ para nodo La Paz (IDs desde 3_000_000_001) ──
if (rpaDb.ikj_counter.countDocuments({ node: "lapaz" }) === 0) {
    rpaDb.ikj_counter.insertOne({
        node:    "lapaz",
        next_id: NumberLong("3000000000")
    });
    print("[rpa] IKJ counter creado para La Paz.");
}

// ── Índices ───────────────────────────────────────────────────
rpaDb.flights.createIndex({ id: 1 },               { unique: true,  name: "IX_flights_id" });
rpaDb.flights.createIndex({ origin: 1, destination: 1, flight_date: 1 }, { name: "IX_flights_route" });

rpaDb.passengers.createIndex({ passport: 1 },      { unique: true,  name: "IX_passengers_passport" });

rpaDb.reservations.createIndex({ transaction_id: 1 }, { unique: true, name: "IX_reservations_tx" });
rpaDb.reservations.createIndex({ flight_id: 1 },      { name: "IX_reservations_flight" });

rpaDb.sync_queue.createIndex({ target_node: 1, replayed: 1 }, { name: "IX_sync_pending" });

rpaDb.node_heartbeat.createIndex({ node: 1 },      { unique: true,  name: "IX_heartbeat_node" });

print("[rpa] MongoDB rpa_db inicializado correctamente.");
