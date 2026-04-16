from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    sql_beijing_host: str = "sqlserver_beijing"
    sql_beijing_port: int = 1433
    sql_ukraine_host: str = "sqlserver_ukraine"
    sql_ukraine_port: int = 1433
    sql_database:     str = "rpa_db"
    sql_user:         str = "sa"
    sql_password:     str = "RPA_StrongPass123!"

    mongo_host:     str = "mongodb_lapaz"
    mongo_port:     int = 27017
    mongo_user:     str = "rpa_admin"
    mongo_password: str = "RPA_MongoPass123!"
    mongo_database: str = "rpa_db"

    sync_interval_seconds: int = 30
    context_path:          str = "/app/context"

    def mongo_uri(self) -> str:
        return (
            f"mongodb://{self.mongo_user}:{self.mongo_password}"
            f"@{self.mongo_host}:{self.mongo_port}/{self.mongo_database}"
            "?authSource=admin"
        )


settings = Settings()
