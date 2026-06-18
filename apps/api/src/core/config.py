import os
from dataclasses import dataclass
from dotenv import load_dotenv

# Load local environment variables from .env file
load_dotenv()



@dataclass(frozen=True)
class Settings:
    env: str = os.getenv("APP_ENV", "local")
    api_title: str = os.getenv("API_TITLE", "Recruitment Platform API")
    api_version: str = os.getenv("API_VERSION", "0.1.0")
    log_level: str = os.getenv("LOG_LEVEL", "info")
    database_dsn: str = os.getenv("DATABASE_DSN", "")
    kafka_brokers: str = os.getenv("KAFKA_BROKERS", "")
    storage_root: str = os.getenv("STORAGE_ROOT", "/tmp/recruitment-platform")
    openai_api_key: str = os.getenv("OPENAI_API_KEY", "")
    openai_base_url: str = os.getenv("OPENAI_BASE_URL", "https://generativelanguage.googleapis.com/v1beta/openai/")
    gemini_api_key: str = os.getenv("GEMINI_API_KEY", "")
    llm_model: str = os.getenv("LLM_MODEL", "gemini-1.5-flash")
    embedding_model: str = os.getenv("EMBEDDING_MODEL", "gemini-embedding-001")
    embedding_dimensions: int = int(os.getenv("EMBEDDING_DIMENSIONS", "768"))

    def broker_list(self) -> list[str]:
        return [item.strip() for item in self.kafka_brokers.split(",") if item.strip()]

    @property
    def llm_api_key(self) -> str:
        return self.openai_api_key
    
    @property
    def llm_base_url(self) -> str:
        return self.openai_base_url


settings = Settings()
