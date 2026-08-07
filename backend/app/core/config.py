from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    app_name: str = "Oracle Operational Intelligence"
    app_env: str = "development"
    api_v1_prefix: str = "/api/v1"
    secret_key: str = "change-this"
    access_token_expire_minutes: int = 60
    database_url: str = "postgresql+psycopg://ooi:ooi@localhost:5432/ooi"
    redis_url: str = "redis://localhost:6379/0"
    cors_origins: str = "http://localhost:5173"
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @property
    def cors_origin_list(self) -> list[str]:
        return [x.strip() for x in self.cors_origins.split(",") if x.strip()]

@lru_cache
def get_settings() -> Settings:
    return Settings()

settings = get_settings()
