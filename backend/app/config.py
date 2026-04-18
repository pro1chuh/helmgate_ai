from pydantic_settings import BaseSettings
from pydantic import field_validator
from functools import lru_cache
from typing import Literal


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

    # -------------------------------------------------------
    # Deployment mode
    # cloud → NVIDIA NIM + Groq (default)
    # local → Ollama only (air-gapped, 152-ФЗ compliance)
    # -------------------------------------------------------
    DEPLOYMENT_MODE: Literal["cloud", "local"] = "cloud"

    # -------------------------------------------------------
    # Cloud providers
    # -------------------------------------------------------

    # NVIDIA NIM — LLM, Vision, Image Gen, Embeddings
    NVIDIA_API_KEY: str = ""
    NVIDIA_BASE_URL: str = "https://integrate.api.nvidia.com/v1"

    # Groq — ASR (Whisper), fast LLM fallback
    GROQ_API_KEY: str = ""
    GROQ_BASE_URL: str = "https://api.groq.com/openai/v1"

    # -------------------------------------------------------
    # Local provider (Ollama)
    # -------------------------------------------------------
    OLLAMA_BASE_URL: str = "http://ollama:11434/v1"
    OLLAMA_API_KEY: str = "ollama"  # Ollama не требует ключ, но клиент ждёт поле

    # -------------------------------------------------------
    # Model mapping — cloud
    # -------------------------------------------------------
    CLOUD_MODEL_TEXT: str = "meta/llama-4-scout-17b-16e-instruct"
    CLOUD_MODEL_VISION: str = "meta/llama-4-scout-17b-16e-instruct"  # нативно мультимодальная
    CLOUD_MODEL_IMAGE_GEN: str = "black-forest-labs/flux.2-klein-4b"
    CLOUD_MODEL_ASR: str = "whisper-large-v3-turbo"      # через Groq
    CLOUD_MODEL_EMBEDDING: str = "nvidia/nv-embedqa-e5-v5"

    # -------------------------------------------------------
    # Model mapping — local (Ollama)
    # -------------------------------------------------------
    LOCAL_MODEL_TEXT: str = "llama3.2"
    LOCAL_MODEL_VISION: str = "llava"
    LOCAL_MODEL_IMAGE_GEN: str = ""          # image gen локально не поддерживается
    LOCAL_MODEL_ASR: str = "whisper"
    LOCAL_MODEL_EMBEDDING: str = "nomic-embed-text"

    # Files
    UPLOAD_DIR: str = "/app/uploads"
    MAX_FILE_SIZE_MB: int = 50

    # Chroma (RAG)
    CHROMA_PATH: str = "/app/chroma"

    @field_validator("NVIDIA_API_KEY", "GROQ_API_KEY", mode="before")
    @classmethod
    def empty_string_allowed(cls, v):
        return v or ""

    class Config:
        env_file = ".env"


@lru_cache
def get_settings() -> Settings:
    return Settings()
