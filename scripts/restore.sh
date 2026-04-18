#!/usr/bin/env bash
# =============================================================
#  restore.sh  —  RafaelPabonAirlines
#  Restaura los 3 nodos desde un backup generado por backup.sh
#
#  Uso:
#    bash scripts/restore.sh backups/20250417_123456
#
#  ADVERTENCIA: reemplaza los datos actuales en los 3 nodos.
# =============================================================
set -euo pipefail

if [[ $# -lt 1 ]]; then
  echo "Uso: bash scripts/restore.sh <directorio_backup>"
  echo "Ejemplo: bash scripts/restore.sh backups/20250417_123456"
  exit 1
fi

DIR="$1"

# Verificar que el directorio existe y tiene los archivos esperados
for f in "${DIR}/rpa_beijing.bak" "${DIR}/rpa_ukraine.bak" "${DIR}/mongo_lapaz"; do
  if [[ ! -e "$f" ]]; then
    echo "ERROR: No se encontró '$f'. ¿Es un directorio de backup válido?"
    exit 1
  fi
done

echo "=== Restaurando desde: ${DIR} ==="
read -rp "¿Confirmar? Esto reemplazará TODOS los datos actuales. (escribe 'SI'): " confirm
if [[ "$confirm" != "SI" ]]; then
  echo "Restauración cancelada."
  exit 0
fi

# ── SQL Server: Beijing ──────────────────────────────────────
echo "[1/3] Restaurando Beijing..."
docker cp "${DIR}/rpa_beijing.bak" rpa_sqlserver_beijing:/var/opt/mssql/backup/rpa_beijing.bak
docker exec rpa_sqlserver_beijing bash -c "
  /opt/mssql-tools18/bin/sqlcmd -S localhost,1433 -U sa -P 'RPA_StrongPass123!' -No \
    -Q \"
      ALTER DATABASE rpa_db SET SINGLE_USER WITH ROLLBACK IMMEDIATE;
      RESTORE DATABASE rpa_db FROM DISK='/var/opt/mssql/backup/rpa_beijing.bak'
        WITH REPLACE, RECOVERY;
      ALTER DATABASE rpa_db SET MULTI_USER;
    \"
"
echo "  Beijing restaurado."

# ── SQL Server: Ukraine ──────────────────────────────────────
echo "[2/3] Restaurando Ukraine..."
docker cp "${DIR}/rpa_ukraine.bak" rpa_sqlserver_ukraine:/var/opt/mssql/backup/rpa_ukraine.bak
docker exec rpa_sqlserver_ukraine bash -c "
  /opt/mssql-tools18/bin/sqlcmd -S localhost,1433 -U sa -P 'RPA_StrongPass123!' -No \
    -Q \"
      ALTER DATABASE rpa_db SET SINGLE_USER WITH ROLLBACK IMMEDIATE;
      RESTORE DATABASE rpa_db FROM DISK='/var/opt/mssql/backup/rpa_ukraine.bak'
        WITH REPLACE, RECOVERY;
      ALTER DATABASE rpa_db SET MULTI_USER;
    \"
"
echo "  Ukraine restaurado."

# ── MongoDB: La Paz ──────────────────────────────────────────
echo "[3/3] Restaurando La Paz (MongoDB)..."
docker cp "${DIR}/mongo_lapaz" rpa_mongodb_lapaz:/tmp/rpa_restore
docker exec rpa_mongodb_lapaz bash -c "
  mongorestore \
    --uri='mongodb://rpa_admin:RPA_MongoPass123!@localhost:27017/?authSource=admin' \
    --db=rpa_db \
    /tmp/rpa_restore/ \
    --drop
"
echo "  La Paz restaurado."

echo ""
echo "=== Restauración completada ==="
