from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # App
    APP_NAME: str = "Helm"
    DEBUG: bool = False

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://helm:helm@db:5432/helm"

    # JWT
    SECRET_KEY: str = "change-me-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30

    # MWS GPT (OpenAI-compatible)
    MWS_API_KEY: str
    MWS_BASE_URL: str = "https://api.gpt.mws.ru/v1"

    # Models
    MODEL_TEXT: str = "mws-gpt-alpha"
    MODEL_VISION: str = "qwen2.5-vl"
    MODEL_IMAGE_GEN: str = "qwen-image-lightning"
    MODEL_ASR: str = "whisper-medium"

    # Files
    UPLOAD_DIR: str = "/app/uploads"
    MAX_FILE_SIZE_MB: int = 50

    # Chroma (RAG)
    CHROMA_PATH: str = "/app/chroma"

    class Config:
        env_file = ".env"


@lru_cache
def get_settings() -> Settings:
    return Settings()
