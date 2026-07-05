from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    bot_token: str
    support_group_id: int
    superadmin_telegram_id: int
    notify_support_chat_ids: str = ""
    notify_admin_chat_ids: str = ""

    database_url: str
    redis_url: str

    postgres_user: str = "sipuser"
    postgres_password: str = "password"
    postgres_db: str = "sipcrm"

    # development | production — production включает validate_production_config()
    sipcrm_env: str = "development"
    redis_password: str = ""

    secret_key: str = "change-me-dev-only"
    api_host: str = "0.0.0.0"
    api_port: int = 8000

    web_admin_username: str = "roof"
    web_admin_password: str = "change-me-dev-only"

    admin_username: str = "@admin"

    cooldown_minutes: int = 3
    max_tickets_per_day: int = 10

    test_mode: bool = False

    bot_api_secret: str = "change-me-dev-bot-secret"
    bot_webhook_host: str = "0.0.0.0"
    bot_webhook_port: int = 8080
    bot_webhook_url: str = "http://bot:8080"
    crm_api_url: str = "http://api:8000"
    public_web_url: str = ""

    session_https_only: bool = False

    notion_api_token: str = ""
    notion_enabled: bool = False
    notion_database_id: str = ""
    notion_api_version: str = "2022-06-28"

    # SIP trunk / WebRTC softphone (Telegram Mini App)
    sip_trunk_enabled: bool = False
    sip_wss_url: str = ""
    sip_domain: str = ""
    sip_display_name: str = "SIP CRM"
    sip_stun_servers: str = "stun:stun.l.google.com:19302"
    sip_turn_url: str = ""
    sip_turn_username: str = ""
    sip_turn_credential: str = ""
    sip_dial_prefix: str = ""
    sip_outbound_proxy: str = ""
    sip_session_ttl_seconds: int = 300

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
    )

    @property
    def is_production(self) -> bool:
        return self.sipcrm_env.strip().lower() == "production"

    @property
    def cookie_https_only(self) -> bool:
        # QA/pytest and internal health checks use HTTP (127.0.0.1, TestClient).
        if self.test_mode or not self.is_production:
            return False
        if self.session_https_only:
            return True
        return self.public_web_url.lower().startswith("https://")


settings = Settings()
