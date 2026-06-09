from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Telegram
    bot_token: str
    support_group_id: int

    # Database
    database_url: str
    postgres_user: str
    postgres_password: str
    postgres_db: str

    # Redis
    redis_url: str

    # API
    secret_key: str
    api_host: str = "0.0.0.0"
    api_port: int = 8000

    # Антиспам
    cooldown_minutes: int = 3
    max_tickets_per_day: int = 10

    # Суперадмин
    superadmin_telegram_id: int

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
    )


settings = Settings()
