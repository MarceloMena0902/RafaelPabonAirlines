"""
config.py
─────────
Centraliza todas las variables de entorno del sistema.
Cada sección corresponde a un nodo o servicio distinto.
"""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # ── Nodo Beijing (SQL Server) ─────────────────────────────
    sql_beijing_host: str = "sqlserver_beijing"
    sql_beijing_port: int = 1433

    # ── Nodo Ucrania (SQL Server) ─────────────────────────────
    sql_ukraine_host: str = "sqlserver_ukraine"
    sql_ukraine_port: int = 1433

    # ── Credenciales SQL compartidas ─────────────────────────
    sql_database: str = "rpa_db"
    sql_user: str = "sa"
    sql_password: str = "RPA_StrongPass123!"

    # ── Nodo La Paz (MongoDB) ─────────────────────────────────
    mongo_host: str = "mongodb_lapaz"
    mongo_port: int = 27017
    mongo_user: str = "rpa_admin"
    mongo_password: str = "RPA_MongoPass123!"
    mongo_database: str = "rpa_db"

    # ── Sincronización entre nodos ────────────────────────────
    sync_interval_seconds: int = 30   # frecuencia del healthcheck y sync

    # ── Ruta al dataset ───────────────────────────────────────
    context_path: str = "/app/context"

    # ── Helpers para construir cadenas de conexión ────────────
    def sql_connection_string(self, host: str, port: int) -> str:
        return (
            f"mssql+pyodbc://{self.sql_user}:{self.sql_password}"
            f"@{host}:{port}/{self.sql_database}"
            "?driver=ODBC+Driver+18+for+SQL+Server"
            "&TrustServerCertificate=yes"
        )

    def mongo_uri(self) -> str:
        return (
            f"mongodb://{self.mongo_user}:{self.mongo_password}"
            f"@{self.mongo_host}:{self.mongo_port}/{self.mongo_database}"
            "?authSource=admin"
        )


# Instancia global — importar desde aquí en toda la app
settings = Settings()
