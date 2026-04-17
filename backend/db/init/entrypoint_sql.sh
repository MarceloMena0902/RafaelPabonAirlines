#!/bin/bash
# ─────────────────────────────────────────────────────────────────
# entrypoint_sql.sh
# Arranca SQL Server y ejecuta el script de inicialización
# de la base de datos rpa_db la primera vez.
# ─────────────────────────────────────────────────────────────────
set -e

echo "[rpa] Iniciando SQL Server..."
/opt/mssql/bin/sqlservr &
MSSQL_PID=$!

echo "[rpa] Esperando que SQL Server acepte conexiones..."
for i in $(seq 1 90); do
    if /opt/mssql-tools18/bin/sqlcmd \
        -S "localhost,1433" -U sa -P "${SA_PASSWORD}" -No \
        -Q "SELECT 1" > /dev/null 2>&1; then
        echo "[rpa] SQL Server listo (intento ${i})."
        break
    fi
    sleep 2
done

echo "[rpa] Ejecutando script de inicialización..."
/opt/mssql-tools18/bin/sqlcmd \
    -S "localhost,1433" -U sa -P "${SA_PASSWORD}" -No \
    -i /init/init_schema.sql \
    && echo "[rpa] Esquema creado / ya existía." \
    || echo "[rpa] WARN: error en init_schema.sql (puede ser que ya exista)."

echo "[rpa] SQL Server listo para recibir conexiones."
wait $MSSQL_PID
