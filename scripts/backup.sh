#!/usr/bin/env bash
# =============================================================
#  backup.sh  —  RafaelPabonAirlines
#  Genera un backup de los 3 nodos (Beijing, Ukraine, La Paz)
#  dentro de la carpeta backups/<timestamp>/
#
#  Uso:
#    bash scripts/backup.sh
# =============================================================
set -euo pipefail

TS=$(date +"%Y%m%d_%H%M%S")
DIR="backups/${TS}"
mkdir -p "${DIR}"

echo "=== Backup RPA — ${TS} ==="

# ── SQL Server: Beijing ──────────────────────────────────────
echo "[1/3] Exportando Beijing (SQL Server)..."
docker exec rpa_sqlserver_beijing bash -c "
  mkdir -p /var/opt/mssql/backup
  /opt/mssql-tools18/bin/sqlcmd -S localhost,1433 -U sa -P 'RPA_StrongPass123!' -No \
    -Q \"BACKUP DATABASE rpa_db TO DISK='/var/opt/mssql/backup/rpa_beijing.bak' WITH FORMAT, INIT, COMPRESSION\"
"
docker cp rpa_sqlserver_beijing:/var/opt/mssql/backup/rpa_beijing.bak "${DIR}/rpa_beijing.bak"
echo "  → ${DIR}/rpa_beijing.bak ($(du -h "${DIR}/rpa_beijing.bak" | cut -f1))"

# ── SQL Server: Ukraine ──────────────────────────────────────
echo "[2/3] Exportando Ukraine (SQL Server)..."
docker exec rpa_sqlserver_ukraine bash -c "
  mkdir -p /var/opt/mssql/backup
  /opt/mssql-tools18/bin/sqlcmd -S localhost,1433 -U sa -P 'RPA_StrongPass123!' -No \
    -Q \"BACKUP DATABASE rpa_db TO DISK='/var/opt/mssql/backup/rpa_ukraine.bak' WITH FORMAT, INIT, COMPRESSION\"
"
docker cp rpa_sqlserver_ukraine:/var/opt/mssql/backup/rpa_ukraine.bak "${DIR}/rpa_ukraine.bak"
echo "  → ${DIR}/rpa_ukraine.bak ($(du -h "${DIR}/rpa_ukraine.bak" | cut -f1))"

# ── MongoDB: La Paz ──────────────────────────────────────────
echo "[3/3] Exportando La Paz (MongoDB)..."
docker exec rpa_mongodb_lapaz bash -c "
  mongodump \
    --uri='mongodb://rpa_admin:RPA_MongoPass123!@localhost:27017/rpa_db?authSource=admin' \
    --out=/tmp/rpa_backup
"
docker cp rpa_mongodb_lapaz:/tmp/rpa_backup/rpa_db "${DIR}/mongo_lapaz"
echo "  → ${DIR}/mongo_lapaz/ ($(du -sh "${DIR}/mongo_lapaz" | cut -f1))"

# ── Resumen ──────────────────────────────────────────────────
echo ""
echo "=== Backup completado ==="
du -sh "${DIR}"
echo "Directorio: ${DIR}"
