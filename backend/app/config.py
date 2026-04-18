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
    # cloud → NVIDIA NIM + Groq
    # local → Ollama only (air-gapped, 152-ФЗ)
    # -------------------------------------------------------
    DEPLOYMENT_MODE: Literal["cloud", "local"] = "cloud"

    # -------------------------------------------------------
    # Cloud providers
    # -------------------------------------------------------

    # NVIDIA NIM — LLM, Vision, Embeddings
    NVIDIA_API_KEY: str = ""
    NVIDIA_BASE_URL: str = "https://integrate.api.nvidia.com/v1"

    # Groq — ASR (Whisper)
    GROQ_API_KEY: str = ""
    GROQ_BASE_URL: str = "https://api.groq.com/openai/v1"

    # OpenRouter — агрегатор всех моделей (fallback + ручной выбор)
    OPENROUTER_API_KEY: str = ""
    OPENROUTER_BASE_URL: str = "https://openrouter.ai/api/v1"

    # -------------------------------------------------------
    # Model mapping — cloud (NVIDIA NIM)
    # -------------------------------------------------------

    # Основная модель — Llama-3.3-70B (текст, документы)
    CLOUD_MODEL_TEXT: str = "meta/llama-3.3-70b-instruct"

    # Код — Qwen2.5-Coder-32B (лучшая code-модель на NIM)
    CLOUD_MODEL_CODE: str = "qwen/qwen2.5-coder-32b-instruct"

    # Тяжёлый reasoning — GLM-5.1 (thinking-модель)
    CLOUD_MODEL_REASONING: str = "z-ai/glm-5.1"

    # Vision — анализ изображений
    CLOUD_MODEL_VISION: str = "meta/llama-3.2-90b-vision-instruct"

    # ASR — через Groq (NVIDIA NIM не поддерживает)
    CLOUD_MODEL_ASR: str = "whisper-large-v3-turbo"

    # Embeddings для RAG — мультиязычная
    CLOUD_MODEL_EMBEDDING: str = "nvidia/nv-embedqa-e5-v5"

    # Safety — фильтрация контента
    CLOUD_MODEL_SAFETY: str = "meta/llama-guard-4-12b"

    # -------------------------------------------------------
    # Model mapping — local (Ollama)
    # -------------------------------------------------------
    LOCAL_MODEL_TEXT: str = "llama3.2"
    LOCAL_MODEL_VISION: str = "llava"
    LOCAL_MODEL_ASR: str = "whisper"
    LOCAL_MODEL_EMBEDDING: str = "nomic-embed-text"

    # Files
    UPLOAD_DIR: str = "/app/uploads"
    MAX_FILE_SIZE_MB: int = 50

    # Chroma (RAG)
    CHROMA_PATH: str = "/app/chroma"

    @field_validator("NVIDIA_API_KEY", "GROQ_API_KEY", "OPENROUTER_API_KEY", mode="before")
    @classmethod
    def empty_string_allowed(cls, v):
        return v or ""

    class Config:
        env_file = ".env"


@lru_cache
def get_settings() -> Settings:
    return Settings()
