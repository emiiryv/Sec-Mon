from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import List

class Settings(BaseSettings):
    APP_ENV: str = "dev"
    HOST: str = "127.0.0.1"
    PORT: int = 8000

    DATABASE_URL: str

    IP_SALT: str = "change_me"

    ALERT_SINKS: str = "stdout"
    ALERT_FILE_PATH: str = "./alerts.log"
    ALERT_WEBHOOK_URLS: str = ""
    ALERT_DEDUP_WINDOW_SEC: int = 300
    ALERT_COOLDOWN_GLOBAL_SEC: float = 1.0
    ALERT_RETRY_MAX: int = 3
    ALERT_RETRY_BACKOFF_MS: int = 250

    QUARANTINE_ENABLED: bool = True
    QUARANTINE_WINDOW_SEC: int = 30
    QUARANTINE_THRESHOLD_COUNT: int = 5
    QUARANTINE_BAN_SECONDS: int = 300
    ALLOWLIST_IPS: str = ""  # comma-separated raw IPs

    TRUSTED_PROXY_CIDRS: str = "127.0.0.1/32"

    RETENTION_DAYS: int = 30

    ZSCORE_ENABLED: bool = True
    ZSCORE_MIN_SAMPLES: int = 10
    ZSCORE_WINDOW_MIN: int = 30
    ZSCORE_THRESHOLD: float = 3.0
    ZSCORE_BUCKET_SEC: int = 60

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    def sinks(self) -> List[str]:
        return [s.strip() for s in self.ALERT_SINKS.split(",") if s.strip()]

    def webhook_urls(self) -> List[str]:
        return [u.strip() for u in self.ALERT_WEBHOOK_URLS.split(",") if u.strip()]

def get_settings() -> Settings:
    return Settings()  # cached by pydantic internally