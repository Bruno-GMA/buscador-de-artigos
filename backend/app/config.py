import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    database_url: str = os.getenv("DATABASE_URL", "sqlite:///./data/academic_pulse.db")
    ollama_host: str = os.getenv("OLLAMA_HOST", "http://localhost:11434")
    ollama_model: str = os.getenv("OLLAMA_MODEL", "gemma3:4b")
    schedule_hour: int = int(os.getenv("SCHEDULE_HOUR", "8"))
    schedule_minute: int = int(os.getenv("SCHEDULE_MINUTE", "0"))
    timezone: str = os.getenv("TIMEZONE", "America/Maceio")
    max_papers_per_run: int = int(os.getenv("MAX_PAPERS_PER_RUN", "9"))
    dashboard_url: str = os.getenv("DASHBOARD_URL", "http://localhost:5173").rstrip("/")
    telegram_bot_token: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
    telegram_chat_id: str = os.getenv("TELEGRAM_CHAT_ID", "")
    trigger_api_key: str = os.getenv("TRIGGER_API_KEY", "")
    ieee_api_key: str = os.getenv("IEEE_API_KEY", "")
    ieee_ai_permission_granted: bool = os.getenv("IEEE_AI_PERMISSION_GRANTED", "false").lower() == "true"
    capes_import_dir: str = os.getenv("CAPES_IMPORT_DIR", "./imports/capes")
    capes_rss_urls: str = os.getenv("CAPES_RSS_URLS", "")


settings = Settings()

